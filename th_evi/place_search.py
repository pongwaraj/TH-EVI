"""Read-only place lookup. Search aliases never become model demand inputs."""
from __future__ import annotations

import csv
from functools import lru_cache
import json
import logging
import math
from threading import Lock
from time import monotonic
import unicodedata

from . import spatial
from .db import CandidateSite, ChargerCompetitor, POIReference, ReferenceDatasetRelease, get_session_factory


logger = logging.getLogger(__name__)
_lock = Lock()
_cache: tuple[float, list[dict], bool] | None = None


def normalize(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC', str(value)).casefold()
                   if c.isalnum() or unicodedata.category(c).startswith('M'))


def canonical_province(value: str) -> str:
    slug = spatial._slug_for_province(value)
    return spatial.SLUG_TO_CANONICAL_PROVINCE.get(slug, value)


def _valid(row: dict) -> bool:
    try:
        lat, lon = float(row['lat']), float(row['lon'])
        return math.isfinite(lat) and math.isfinite(lon) and 5 <= lat <= 21 and 97 <= lon <= 106
    except (KeyError, TypeError, ValueError):
        return False


@lru_cache(maxsize=1)
def aliases() -> dict:
    path = spatial.DATA_DIR / 'place_search_aliases.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


@lru_cache(maxsize=1)
def csv_catalog() -> list[dict]:
    rows = []
    for slug, province in spatial.SLUG_TO_CANONICAL_PROVINCE.items():
        paths = [(f'poi_{slug}_seed.csv', 'poi', 'poi_id')]
        if not (spatial.DATA_DIR / paths[0][0]).exists():
            paths = [(f'poi_{slug}_city_seed.csv', 'poi', 'poi_id')]
        paths.extend((f'competitors_{slug}_{suffix}.csv', 'competitor', 'station_id')
                     for suffix in ('seed', 'detailed', 'google_verified'))
        for name, kind, key in paths:
            path = spatial.DATA_DIR / name
            if path.exists():
                with path.open(encoding='utf-8-sig', newline='') as source:
                    rows.extend(dict(row, kind=kind, record_id=row.get(key), province=province)
                                for row in csv.DictReader(source))
    if spatial.NATIONWIDE_KML_COMPETITOR_PATH.exists():
        with spatial.NATIONWIDE_KML_COMPETITOR_PATH.open(encoding='utf-8-sig', newline='') as source:
            rows.extend(dict(row, kind='competitor', record_id=row.get('station_id'),
                             province=canonical_province(row.get('province', '')))
                        for row in csv.DictReader(source))
    return rows


def merge_catalog(csv_rows: list[dict], db_rows: list[dict], published: set[str]) -> list[dict]:
    """Match the map's DB-led published / CSV-led fallback precedence."""
    merged = {}
    for row in csv_rows:
        key = (canonical_province(row.get('province', '')), row['kind'], row.get('record_id'))
        if key[2]:
            merged.setdefault(key, row)
    for row in db_rows:
        province = canonical_province(row.get('province', ''))
        key = (province, row['kind'], row.get('record_id'))
        if province in published:
            if row.get('active') is False:
                merged.pop(key, None)
            else:
                merged[key] = row
        elif row.get('active') is not False:
            merged.setdefault(key, row)
    return [row for row in merged.values()
            if str(row.get('active', 'true')).lower() not in {'false', '0', 'no'} and _valid(row)]


def clear_cache() -> None:
    global _cache
    with _lock:
        _cache = None
    csv_catalog.cache_clear()
    aliases.cache_clear()


def reference_catalog() -> tuple[list[dict], bool]:
    global _cache
    with _lock:
        if _cache and monotonic() - _cache[0] < (5 if _cache[2] else 30):
            return _cache[1], _cache[2]
        db_rows, published, partial = [], set(), False
        try:
            with get_session_factory()() as session:
                published = {canonical_province(row[0]) for row in session.query(ReferenceDatasetRelease.province)
                             .filter_by(status='published', parity_passed=True).all()}
                for model, kind, key in ((POIReference, 'poi', 'poi_id'),
                                         (ChargerCompetitor, 'competitor', 'station_id')):
                    fields = [getattr(model, field) for field in
                              (key, 'province', 'district', 'name', 'lat', 'lon', 'active')]
                    db_rows.extend(dict(zip(('record_id', 'province', 'district', 'name', 'lat', 'lon', 'active'), row),
                                        kind=kind) for row in session.query(*fields).all())
        except Exception:
            logger.warning('Place search reference database unavailable; using CSV fallback')
            db_rows, published, partial = [], set(), True
        catalog = merge_catalog(csv_catalog(), db_rows, published)
        _cache = monotonic(), catalog, partial
        return catalog, partial


def saved_sites() -> tuple[list[dict], bool]:
    try:
        with get_session_factory()() as session:
            rows = session.query(CandidateSite.id, CandidateSite.name, CandidateSite.province,
                                 CandidateSite.district, CandidateSite.lat, CandidateSite.lon).filter(
                                     CandidateSite.active.is_(True)).all()
            return [dict(record_id=str(r.id), name=r.name, province=canonical_province(r.province),
                         district=r.district, lat=r.lat, lon=r.lon, kind='saved')
                    for r in rows if _valid({'lat': r.lat, 'lon': r.lon})], False
    except Exception:
        logger.warning('Saved sites unavailable for place search')
        return [], True


def search_places(query: str, province: str = '', limit: int = 8) -> dict:
    compact = normalize(query)
    if len(compact) < 2:
        return {'results': [], 'partial': False}
    tokens = [normalize(token) for token in query.split() if normalize(token)]
    catalog, partial = reference_catalog()
    saved, saved_partial = saved_sites()
    thai = any('\u0e00' <= char <= '\u0e7f' for char in query)
    preferred = canonical_province(province)
    thai_provinces = {en: th for th, en in spatial.THAILAND_PROVINCE_PAIRS}
    ranked = []
    for row in catalog + saved:
        canonical = canonical_province(row.get('province', ''))
        province_th = thai_provinces.get(canonical, canonical)
        # Aliases are scoped to an existing place, never used to create a place.
        alias = aliases().get(f"{canonical}/{row['kind']}/{row['record_id']}", {})
        names = [row.get('name') or str(row['record_id']), alias.get('name_th', ''),
                 alias.get('name_en', ''), *alias.get('aliases', [])]
        name_keys = [normalize(name) for name in names if name]
        haystack = normalize(' '.join(names + [canonical, province_th, row.get('district') or '']))
        if compact not in haystack and not all(token in haystack for token in tokens):
            continue
        score = (0 if compact in name_keys else 1 if any(compact in name for name in name_keys) else 2,
                 0 if canonical == preferred else 1, 0 if row['kind'] == 'poi' else 1)
        name = alias.get('name_th' if thai else 'name_en') or row.get('name') or str(row['record_id'])
        result = {'id': f"{canonical}/{row['kind']}/{row['record_id']}", 'name': name,
                  'province': canonical, 'province_th': province_th, 'district': row.get('district') or '',
                  'lat': float(row['lat']), 'lon': float(row['lon']), 'kind': row['kind'], 'source': 'th_evi'}
        ranked.append((score, name, result))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]['id']))
    results, seen = [], set()
    for _, _, row in ranked:
        key = (normalize(row['name']), row['kind'], round(row['lat'], 4), round(row['lon'], 4))
        if key not in seen:
            seen.add(key)
            results.append(row)
        if len(results) >= limit:
            break
    return {'results': results, 'partial': partial or saved_partial}
