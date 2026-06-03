"""Ingest reference CSV data into reference DB tables with upsert.

Usage:
    python -m th_evi.ingest
    python -m th_evi.ingest --province khon_kaen
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .db import (
    AADTSegment,
    ChargerCompetitor,
    DistrictPopulation,
    POIReference,
    ProvinceIngestionRun,
    ReferenceSource,
    get_session_factory,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PROVINCE_SLUGS = [
    "chiang_mai",
    "chiang_rai",
    "lampang",
    "lamphun",
    "nan",
    "phayao",
    "phrae",
    "khon_kaen",
    "udon_thani",
    "ubon_ratchathani",
    "nong_khai",
    "mae_hong_son",
]

SLUG_TO_NAME = {
    "chiang_mai": "Chiang Mai",
    "chiang_rai": "Chiang Rai",
    "lampang": "Lampang",
    "lamphun": "Lamphun",
    "nan": "Nan",
    "phayao": "Phayao",
    "phrae": "Phrae",
    "khon_kaen": "Khon Kaen",
    "udon_thani": "Udon Thani",
    "ubon_ratchathani": "Ubon Ratchathani",
    "nong_khai": "Nong Khai",
    "mae_hong_son": "Mae Hong Son",
}


def _normalized_text(*parts: str | None) -> str:
    return " ".join(str(part or "").strip().lower() for part in parts if str(part or "").strip())


def _confidence_rank(value: str | None) -> int:
    ranks = {
        "unknown": 0,
        "low": 1,
        "low_medium": 2,
        "medium": 3,
        "medium_high": 4,
        "high": 5,
    }
    return ranks.get(str(value or "").strip().lower(), 3)


def _downgrade_confidence(current: str | None, floor: str = "low") -> str:
    current_value = str(current or "").strip().lower() or "medium"
    return floor if _confidence_rank(current_value) > _confidence_rank(floor) else current_value


def _int_or_none(val: str | None) -> int | None:
    if val is None:
        return None
    cleaned = str(val).strip()
    if not cleaned:
        return None
    try:
        return int(cleaned.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _float_or_none(val: str | None) -> float | None:
    if val is None:
        return None
    cleaned = str(val).strip()
    if not cleaned:
        return None
    try:
        return float(cleaned.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _thai_province_name(english_name: str) -> str:
    mapping = {
        "Chiang Mai": "เชียงใหม่",
        "Chiang Rai": "เชียงราย",
        "Lampang": "ลำปาง",
        "Lamphun": "ลำพูน",
        "Nan": "น่าน",
        "Phayao": "พะเยา",
        "Phrae": "แพร่",
        "Khon Kaen": "ขอนแก่น",
        "Udon Thani": "อุดรธานี",
        "Ubon Ratchathani": "อุบลราชธานี",
        "Nong Khai": "หนองคาย",
        "Mae Hong Son": "แม่ฮ่องสอน",
    }
    return mapping.get(english_name, english_name)


def _resolve_source_id(
    source_map: dict[str, int],
    *,
    source_text: str | None = None,
    source_type: str | None = None,
    source_url: str | None = None,
) -> int | None:
    text = _normalized_text(source_text, source_type, source_url)
    if not text:
        return source_map.get("seed_estimate")
    if "openstreetmap" in text or "data/osm" in text or text == "osm":
        return source_map.get("OpenStreetMap")
    if "doh" in text or "aadt_2566" in text:
        return source_map.get("DOH aadt_2566")
    if "dopa" in text or "adm2" in text or "stat.bora" in text:
        return source_map.get("DOPA tha_pop_adm2_2023")
    if any(token in text for token in ("official", "directory", "website", "public", "news", "web")):
        return source_map.get("Public facts / verified web")
    if "seed_estimate" in text or "seed_needs_verification" in text or "operator_app_verification_needed" in text:
        return source_map.get("seed_estimate")
    return source_map.get("seed_estimate")


@lru_cache(maxsize=1)
def _official_aadt_keys() -> set[tuple[str, str, str, int]]:
    path = DATA_DIR / "aadt_2566.csv"
    if not path.exists():
        return set()
    df = pd.read_csv(path)
    route_col, km_col, total_col, prov_col = df.columns[0], df.columns[3], df.columns[14], df.columns[-1]
    keys = set()
    for _, row in df.iterrows():
        route = str(row[route_col]).strip()
        km = str(row[km_col]).strip()
        province = str(row[prov_col]).strip()
        try:
            aadt = int(row[total_col])
        except (TypeError, ValueError):
            continue
        keys.add((province, route, km, aadt))
    return keys


def seed_reference_sources(session) -> dict[str, int]:
    """Insert known reference sources and return {source_name: id}."""
    sources = [
        {
            "source_name": "DOH aadt_2566",
            "source_type": "official",
            "source_url": "https://bmm.doh.go.th",
            "confidence": "high",
            "notes": "Department of Highways annual AADT report BE 2566.",
        },
        {
            "source_name": "DOPA tha_pop_adm2_2023",
            "source_type": "official",
            "source_url": "https://stat.bora.dopa.go.th",
            "confidence": "high",
            "notes": "DOPA official ADM2 population statistics BE 2566.",
        },
        {
            "source_name": "OpenStreetMap",
            "source_type": "map",
            "confidence": "medium_high",
            "notes": "OSM POI and amenity data for demand anchors.",
        },
        {
            "source_name": "Public facts / verified web",
            "source_type": "official",
            "confidence": "medium_high",
            "notes": "Publicly available information from official or verified websites.",
        },
        {
            "source_name": "seed_estimate",
            "source_type": "map",
            "confidence": "low",
            "notes": "Seed estimate; needs field or operator-app verification.",
        },
    ]
    name_to_id: dict[str, int] = {}
    for src in sources:
        existing = session.query(ReferenceSource).filter_by(source_name=src["source_name"]).first()
        if existing:
            name_to_id[src["source_name"]] = existing.id
            continue
        obj = ReferenceSource(**src)
        session.add(obj)
        session.flush()
        name_to_id[src["source_name"]] = obj.id
    return name_to_id


def ingest_district_population(session, source_map: dict[str, int]) -> int:
    """Upsert district population from tha_pop_adm2_2023.csv."""
    csv_path = DATA_DIR / "tha_pop_adm2_2023.csv"
    if not csv_path.exists():
        print(f"  SKIP district_population - {csv_path.name} not found")
        return 0
    df = pd.read_csv(csv_path)
    source_id = source_map.get("DOPA tha_pop_adm2_2023")
    count = 0
    for _, row in df.iterrows():
        province = str(row.get("ADM1_EN", "")).strip()
        district_en = str(row.get("ADM2_EN", "")).strip()
        population = _int_or_none(str(row.get("T_TL", "0")))
        male_pop = _int_or_none(str(row.get("M_TL")))
        female_pop = _int_or_none(str(row.get("F_TL")))
        year_be = _int_or_none(str(row.get("year", "2566"))) or 2566
        if not province or not district_en:
            continue
        existing = session.query(DistrictPopulation).filter_by(
            province=province,
            district_name_en=district_en,
            year_be=year_be,
        ).first()
        if existing:
            existing.population = population or 0
            existing.male_population = male_pop
            existing.female_population = female_pop
            existing.source_id = source_id
            existing.confidence = "high"
        else:
            session.add(
                DistrictPopulation(
                    province=province,
                    district_name_en=district_en,
                    year_be=year_be,
                    population=population or 0,
                    male_population=male_pop,
                    female_population=female_pop,
                    source_id=source_id,
                    confidence="high",
                )
            )
            count += 1
    session.flush()
    total = session.query(DistrictPopulation).count()
    print(f"  district_population: {count} new, {total} total")
    return count


def ingest_aadt_segments(session, source_map: dict[str, int], slug: str) -> dict[str, int]:
    """Upsert AADT segments from aadt_<slug>_seed.csv."""
    csv_path = DATA_DIR / f"aadt_{slug}_seed.csv"
    if not csv_path.exists():
        print(f"  SKIP aadt_segments - {csv_path.name} not found")
        return {"new_rows": 0, "processed_rows": 0, "crosscheck_failures": 0, "file_found": 0}

    official_source_id = source_map.get("DOH aadt_2566")
    fallback_source_id = source_map.get("seed_estimate")
    official_keys = _official_aadt_keys()
    count = 0
    processed = 0
    crosscheck_failures = 0

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            province = str(row.get("province", "")).strip()
            route = str(row.get("route", "")).strip()
            name = str(row.get("name", "")).strip()
            year_be = _int_or_none(row.get("year_be")) or 2566
            aadt = _int_or_none(row.get("aadt")) or 0
            hv_pct = _float_or_none(row.get("heavy_vehicle_pct"))
            km = str(row.get("km", "")).strip()
            confidence = str(row.get("source_confidence") or row.get("confidence") or "medium").strip()
            source_id = _resolve_source_id(source_map, source_text=str(row.get("source", "")).strip()) or fallback_source_id
            notes = str(row.get("notes", "")).strip() or None
            processed += 1

            if source_id == official_source_id:
                official_key = (_thai_province_name(province), route, km, aadt)
                if official_key not in official_keys:
                    source_id = fallback_source_id
                    confidence = _downgrade_confidence(confidence, "low")
                    prefix = "Official DOH cross-check failed; downgraded during ingest."
                    notes = f"{prefix} {notes}".strip() if notes else prefix
                    crosscheck_failures += 1

            existing = session.query(AADTSegment).filter_by(
                province=province,
                route_number=route,
                segment_name=name,
                km_start=km,
                year_be=year_be,
            ).first()
            if existing:
                existing.aadt = aadt
                existing.heavy_vehicle_share_pct = hv_pct
                existing.source_id = source_id
                existing.confidence = confidence
                existing.notes = notes
            else:
                session.add(
                    AADTSegment(
                        province=province,
                        route_number=route,
                        segment_name=name,
                        km_start=km,
                        aadt=aadt,
                        heavy_vehicle_share_pct=hv_pct,
                        year_be=year_be,
                        source_id=source_id,
                        confidence=confidence,
                        notes=notes,
                    )
                )
                count += 1

    session.flush()
    total = session.query(AADTSegment).filter_by(province=SLUG_TO_NAME.get(slug, slug)).count()
    print(f"  aadt_segments: {count} new, {total} total for {slug}")
    return {
        "new_rows": count,
        "processed_rows": processed,
        "crosscheck_failures": crosscheck_failures,
        "file_found": 1,
    }


def ingest_poi_reference(session, source_map: dict[str, int], slug: str) -> dict[str, int]:
    """Upsert POI from poi_<slug>_seed.csv."""
    csv_path = DATA_DIR / f"poi_{slug}_seed.csv"
    if not csv_path.exists():
        print(f"  SKIP poi_reference - {csv_path.name} not found")
        return {"new_rows": 0, "processed_rows": 0, "file_found": 0}

    fallback_source = source_map.get("seed_estimate")
    count = 0
    processed = 0

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poi_id = str(row.get("poi_id", "")).strip()
            province = str(row.get("province", "")).strip() or SLUG_TO_NAME.get(slug, slug)
            name = str(row.get("name", "")).strip()
            category = str(row.get("category", "")).strip()
            lat = _float_or_none(row.get("lat"))
            lon = _float_or_none(row.get("lon"))
            confidence = str(row.get("confidence", "medium")).strip()
            if not poi_id or not name or lat is None or lon is None:
                continue
            processed += 1
            source_id = _resolve_source_id(
                source_map,
                source_text=str(row.get("source", "")).strip(),
                source_type=str(row.get("source_type", "")).strip(),
                source_url=str(row.get("source_url", "")).strip(),
            ) or fallback_source
            existing = session.query(POIReference).filter_by(province=province, poi_id=poi_id).first()
            if existing:
                existing.name = name
                existing.category = category
                existing.lat = lat
                existing.lon = lon
                existing.confidence = confidence
                existing.source_id = source_id
            else:
                session.add(
                    POIReference(
                        poi_id=poi_id,
                        province=province,
                        name=name,
                        category=category,
                        lat=lat,
                        lon=lon,
                        confidence=confidence,
                        source_id=source_id,
                    )
                )
                count += 1

    session.flush()
    total = session.query(POIReference).filter_by(province=SLUG_TO_NAME.get(slug, slug)).count()
    print(f"  poi_reference: {count} new, {total} total for {slug}")
    return {"new_rows": count, "processed_rows": processed, "file_found": 1}


def ingest_competitors(session, source_map: dict[str, int], slug: str) -> dict[str, int]:
    """Upsert competitors from competitors_<slug>_seed.csv."""
    csv_path = DATA_DIR / f"competitors_{slug}_seed.csv"
    if not csv_path.exists():
        print(f"  SKIP charger_competitors - {csv_path.name} not found")
        return {"new_rows": 0, "processed_rows": 0, "file_found": 0}

    fallback_source = source_map.get("seed_estimate")
    count = 0
    processed = 0

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            station_id = str(row.get("station_id", "")).strip()
            province = str(row.get("province", "")).strip() or SLUG_TO_NAME.get(slug, slug)
            name = str(row.get("name", "")).strip()
            lat = _float_or_none(row.get("lat"))
            lon = _float_or_none(row.get("lon"))
            verification = str(row.get("verification_status", "seed_needs_verification")).strip()
            confidence = str(row.get("confidence", "low")).strip()
            if not station_id or not name or lat is None or lon is None:
                continue
            processed += 1
            source_id = _resolve_source_id(
                source_map,
                source_text=str(row.get("source", "")).strip(),
                source_type=str(row.get("source_type", "")).strip(),
                source_url=str(row.get("source_url", "")).strip(),
            ) or fallback_source
            district = str(row.get("district", "")).strip() or None
            existing = session.query(ChargerCompetitor).filter_by(province=province, station_id=station_id).first()
            if existing:
                existing.name = name
                existing.lat = lat
                existing.lon = lon
                existing.district = district
                existing.verification_status = verification
                existing.confidence = confidence
                existing.source_id = source_id
            else:
                session.add(
                    ChargerCompetitor(
                        station_id=station_id,
                        province=province,
                        district=district,
                        name=name,
                        lat=lat,
                        lon=lon,
                        verification_status=verification,
                        confidence=confidence,
                        source_id=source_id,
                    )
                )
                count += 1

    session.flush()
    total = session.query(ChargerCompetitor).filter_by(province=SLUG_TO_NAME.get(slug, slug)).count()
    print(f"  charger_competitors: {count} new, {total} total for {slug}")
    return {"new_rows": count, "processed_rows": processed, "file_found": 1}


def record_ingestion_run(session, slug: str, status: str, notes: str = "") -> int:
    """Record a province ingestion run."""
    now = datetime.utcnow()
    run = ProvinceIngestionRun(
        province=SLUG_TO_NAME.get(slug, slug),
        province_slug=slug,
        agent_name="opencode",
        model_name="big-pickle",
        started_at=now,
        finished_at=now,
        status=status,
        notes=notes.strip(),
    )
    session.add(run)
    session.flush()
    return run.id


def ingest_province(session, source_map: dict[str, int], slug: str) -> None:
    """Run full ingestion for a single province."""
    province_name = SLUG_TO_NAME.get(slug, slug)
    print(f"\n=== {province_name} ({slug}) ===")
    aadt_stats = ingest_aadt_segments(session, source_map, slug)
    poi_stats = ingest_poi_reference(session, source_map, slug)
    comp_stats = ingest_competitors(session, source_map, slug)

    total_new = aadt_stats["new_rows"] + poi_stats["new_rows"] + comp_stats["new_rows"]
    files_found = aadt_stats["file_found"] + poi_stats["file_found"] + comp_stats["file_found"]
    status = "imported_db" if files_found > 0 else "skipped"
    if files_found > 0:
        notes = (
            f"files:{files_found} "
            f"AADT:new={aadt_stats['new_rows']}/processed={aadt_stats['processed_rows']}/crosscheck_failures={aadt_stats['crosscheck_failures']} "
            f"POI:new={poi_stats['new_rows']}/processed={poi_stats['processed_rows']} "
            f"Competitors:new={comp_stats['new_rows']}/processed={comp_stats['processed_rows']}"
        )
    else:
        notes = "No seed files found"
    record_ingestion_run(session, slug, status, notes)
    print(f"  Done - {total_new} new rows ingested")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest reference CSV data into DB.")
    parser.add_argument("--province", "-p", type=str, default=None, help="Province slug (e.g. khon_kaen). Ingest all if omitted.")
    args = parser.parse_args()

    factory = get_session_factory()
    with factory() as session:
        print("Seeding reference sources...")
        source_map = seed_reference_sources(session)

        slugs_to_run = [args.province] if args.province else PROVINCE_SLUGS

        print("\nIngesting district population from tha_pop_adm2_2023.csv...")
        ingest_district_population(session, source_map)

        for slug in slugs_to_run:
            ingest_province(session, source_map, slug)

        session.commit()
        print("\nIngestion complete.")


if __name__ == "__main__":
    main()
