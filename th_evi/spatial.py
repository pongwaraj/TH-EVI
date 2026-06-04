"""POI and competitor spatial demand fields for click-based screening."""

from __future__ import annotations

import csv
import json
import os
from functools import lru_cache
from math import cos, exp, radians, sqrt
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from typing import Any

from .location import LocationDemandModel
from .data import load_district_population_for_province


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PROVINCE_SLUGS = {
    "เชียงใหม่": "chiang_mai",
    "Chiang Mai": "chiang_mai",
    "\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48": "chiang_mai",
    "เชียงราย": "chiang_rai",
    "Chiang Rai": "chiang_rai",
    "\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e23\u0e32\u0e22": "chiang_rai",
    "ลำปาง": "lampang",
    "Lampang": "lampang",
    "\u0e25\u0e33\u0e1b\u0e32\u0e07": "lampang",
    "แพร่": "phrae",
    "Phrae": "phrae",
    "\u0e41\u0e1e\u0e23\u0e48": "phrae",
    "พะเยา": "phayao",
    "Phayao": "phayao",
    "\u0e1e\u0e30\u0e40\u0e22\u0e32": "phayao",
    "หนองคาย": "nong_khai",
    "Nong Khai": "nong_khai",
    "\u0e2b\u0e19\u0e2d\u0e07\u0e04\u0e32\u0e22": "nong_khai",
    "อุดรธานี": "udon_thani",
    "Udon Thani": "udon_thani",
    "\u0e2d\u0e38\u0e14\u0e23\u0e18\u0e32\u0e19\u0e35": "udon_thani",
    "ขอนแก่น": "khon_kaen",
    "Khon Kaen": "khon_kaen",
    "\u0e02\u0e2d\u0e19\u0e41\u0e01\u0e48\u0e19": "khon_kaen",
    "อุบลราชธานี": "ubon_ratchathani",
    "Ubon Ratchathani": "ubon_ratchathani",
    "\u0e2d\u0e38\u0e1a\u0e25\u0e23\u0e32\u0e0a\u0e18\u0e32\u0e19\u0e35": "ubon_ratchathani",
    "Lamphun": "lamphun",
    "\u0e25\u0e33\u0e1e\u0e39\u0e19": "lamphun",
    "Nan": "nan",
    "\u0e19\u0e48\u0e32\u0e19": "nan",
    "Mae Hong Son": "mae_hong_son",
    "\u0e41\u0e21\u0e48\u0e2e\u0e48\u0e2d\u0e07\u0e2a\u0e2d\u0e19": "mae_hong_son",
    "\u004d\u0061\u0065\u0020\u0048\u006f\u006e\u0067\u0020\u0053\u006f\u006e": "mae_hong_son",
}

SCENARIO_FACTORS = {
    "conservative": 0.75,
    "base": 1.0,
    "upside": 1.25,
}
HEATMAP_MODES = {"urban", "community", "district"}

# A clicked charger site never captures the full demand field of every POI in
# the radius. This factor converts surrounding POI demand pools into first-pass
# capturable sessions before competitor penalties are applied.
POI_CAPTURE_FACTOR = 0.22

# Hot-zone demand pools are broader than individual POIs. A candidate site can
# capture only a slice of the zone field, so this sits below the POI capture
# factor but still makes click sessions respond to visible heat/zone scores.
ZONE_CAPTURE_FACTOR = 0.10
SECONDARY_ZONE_SHARE = 0.25
SPATIAL_OVERLAP_SHARE = 0.35
MAX_COMPETITOR_PENALTY_SHARE = 0.62
LOW_RELEVANCE_DEMAND_SHARE = 0.35
LOW_RELEVANCE_MAX_SESSIONS = 6.0
SURFACE_REJECT_DISTANCE_KM = 2.8
SURFACE_LOW_RELEVANCE_DISTANCE_KM = 1.6
ZONE_ACCESS_DISTANCE_KM = 2.2
ZONE_URBAN_SCORE_THRESHOLD = 18.0
POI_URBAN_SCORE_THRESHOLD = 16.0
LOW_RELEVANCE_CONTEXT_DISTANCE_KM = 4.5
LOW_RELEVANCE_CONTEXT_SCORE = 4.0
WATER_QUERY_ROUNDING = 4
OVERPASS_URL = os.getenv("TH_EVI_OVERPASS_URL", "https://overpass-api.de/api/interpreter")

ACCESS_SUPPORT_CATEGORIES = {
    "airport",
    "border_crossing",
    "bus_station",
    "city_center",
    "district_center",
    "event_space",
    "gas_station",
    "hotel",
    "hotel_condo",
    "lifestyle",
    "market_tourism",
    "office",
    "shopping_mall",
    "supermarket",
    "target_site",
    "tourism",
    "transport",
    "transport_corridor",
}

URBAN_SIGNAL_CATEGORIES = {
    "airport",
    "bus_station",
    "city_center",
    "education",
    "hospital",
    "hotel",
    "hotel_condo",
    "lifestyle",
    "market_tourism",
    "office",
    "shopping_mall",
    "supermarket",
    "target_site",
    "tourism",
    "transport",
}

POI_CATEGORY_RULES = {
    "airport": (46.0, 5.0),
    "border_crossing": (44.0, 5.0),
    "shopping_mall": (38.0, 3.5),
    "lifestyle": (32.0, 3.0),
    "supermarket": (26.0, 2.6),
    "hotel": (24.0, 2.6),
    "hotel_condo": (24.0, 2.6),
    "transport": (28.0, 3.0),
    "bus_station": (28.0, 3.0),
    "transport_corridor": (32.0, 4.5),
    "city_center": (28.0, 3.0),
    "hospital": (22.0, 2.3),
    "education": (22.0, 2.8),
    "recreation": (18.0, 2.3),
    "tourism": (18.0, 2.6),
    "tourism_museum": (18.0, 2.6),
    "market_tourism": (18.0, 2.3),
    "district_center": (16.0, 2.5),
    "gas_station": (20.0, 3.2),
    "office": (18.0, 2.0),
    "target_site": (24.0, 2.2),
    "event_space": (14.0, 1.8),
}

DISTRICT_NODE_RULES = {
    "district_center": (18.0, 3.6, "destination"),
    "transport_junction": (18.0, 4.0, "highway"),
    "tourism_town": (17.0, 3.5, "destination"),
    "district_mall": (18.0, 3.2, "destination"),
    "industrial_town": (18.0, 3.4, "destination"),
    "border_town": (22.0, 4.4, "highway"),
    "coverage_anchor": (14.0, 3.2, "suburban"),
}
DISTRICT_NODE_CAPTURE_FACTOR = 0.28

CONFIDENCE_MULTIPLIERS = {
    "high": 1.0,
    "medium_high": 0.9,
    "medium": 0.78,
    "low_medium": 0.62,
    "low": 0.45,
}

COMPETITOR_STATUS_MULTIPLIERS = {
    "verified": 1.0,
    "public_listing_verified_ac_only": 0.30,
    "public_listing_needs_operator_verification": 0.72,
    "operator_app_verification_needed": 0.70,
    "seed_needs_verification": 0.55,
    "poi_charger_unverified": 0.45,
    "public_listing_conflicting": 0.38,
    "osm_only_needs_operator_verification": 0.45,
}


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat_km = (lat1 - lat2) * 111.0
    lon_km = (lon1 - lon2) * 111.0 * cos(radians((lat1 + lat2) / 2))
    return sqrt(lat_km * lat_km + lon_km * lon_km)


def _slug_for_province(province: str) -> str | None:
    return PROVINCE_SLUGS.get(province)


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _filter_and_dedupe_chiang_mai_competitors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per real Chiang Mai station and drop context-only duplicates.

    The Chiang Mai loader combines seed, detailed, Google-verified, and OSM-like
    rows. Some represent the same station from different sources, while a few are
    context anchors rather than actual charging competitors.
    """
    alias_groups = [
        {
            "pea_volta_hub_chiang_mai",
            "pea_volta_nong_hoi_cmh",
            "pea_volta_hub_chiangmai_gmaps",
        },
        {
            "charging_station_cmu",
            "egat_cmu_area_osm",
        },
        {
            "pea_volta_doi_saket_side_osm",
            "pea_volta_doi_saket",
        },
        {
            "ev_station_pluz_green_park",
            "greenbus_fair_super_charge",
        },
    ]
    alias_lookup = {
        station_id: min(group)
        for group in alias_groups
        for station_id in group
    }

    def priority(row: dict[str, Any]) -> tuple[int, int, int]:
        status = str(row.get("verification_status") or "").strip().lower()
        source_type = str(row.get("source_type") or "").strip().lower()
        source = str(row.get("source") or "").strip().lower()
        status_rank = {
            "verified": 5,
            "partial": 4,
            "public_listing_verified_ac_only": 3,
            "public_listing_needs_operator_verification": 2,
            "operator_app_verification_needed": 2,
            "seed_needs_verification": 1,
        }.get(status, 0)
        source_rank = 1 if source_type in {"official", "directory", "news", "website"} or source == "cmhy.city" else 0
        power_rank = int(_parse_power_kw(row))
        return (status_rank, source_rank, power_rank)

    best_by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("verification_status") or "").strip().lower() == "context":
            continue
        if str(row.get("connector_summary") or "").strip().lower() == "not_charger":
            continue

        station_id = str(row.get("station_id") or "").strip()
        if not station_id:
            continue
        key = alias_lookup.get(station_id, station_id)
        current = best_by_key.get(key)
        if current is None or priority(row) > priority(current):
            best_by_key[key] = row

    return list(best_by_key.values())


@lru_cache(maxsize=32)
def load_pois_for_province(province: str) -> list[dict[str, Any]]:
    slug = _slug_for_province(province)
    if not slug:
        return []
    rows = _read_csv(DATA_DIR / f"poi_{slug}_seed.csv")
    if slug == "lampang" and not rows:
        rows.extend(_read_csv(DATA_DIR / "poi_lampang_city_seed.csv"))
    if slug == "chiang_mai":
        for extra in (
            "poi_central_airport_seed.csv",
            "poi_mahachok_park_seed.csv",
            "poi_punn_suk_sankamphaeng_seed.csv",
        ):
            rows.extend(_read_csv(DATA_DIR / extra))
    return rows


@lru_cache(maxsize=32)
def load_competitors_for_province(province: str) -> list[dict[str, Any]]:
    slug = _slug_for_province(province)
    if not slug:
        return []

    rows = _read_csv(DATA_DIR / f"competitors_{slug}_seed.csv")
    detailed = DATA_DIR / f"competitors_{slug}_detailed.csv"
    if detailed.exists():
        rows.extend(_read_csv(detailed))
    if slug == "chiang_mai":
        rows.extend(_read_csv(DATA_DIR / "competitors_chiang_mai_google_verified.csv"))
        rows = _filter_and_dedupe_chiang_mai_competitors(rows)
    return rows


@lru_cache(maxsize=32)
def load_hot_zones_for_province(province: str) -> list[dict[str, Any]]:
    slug = _slug_for_province(province)
    if not slug:
        return []
    return _read_csv(DATA_DIR / f"hot_zones_{slug}.csv")


@lru_cache(maxsize=32)
def load_district_nodes_for_province(province: str) -> list[dict[str, Any]]:
    slug = _slug_for_province(province)
    if not slug:
        return []
    return _read_csv(DATA_DIR / f"district_nodes_{slug}.csv")


POPULATION_WEIGHT_MIN = 0.75
POPULATION_WEIGHT_MAX = 1.35


def _compute_population_weight(population: int | None, all_populations: list[int]) -> float:
    """Map a district's population to a bounded multiplier using percentile.

    Returns a weight in [POPULATION_WEIGHT_MIN, POPULATION_WEIGHT_MAX].
    Returns 1.0 if population is missing or no district populations available.
    """
    if population is None or not all_populations:
        return 1.0
    sorted_pops = sorted(all_populations)
    rank = sum(1 for p in sorted_pops if p <= population) - 1
    max_rank = max(len(sorted_pops) - 1, 1)
    percentile = rank / max_rank
    return round(POPULATION_WEIGHT_MIN + percentile * (POPULATION_WEIGHT_MAX - POPULATION_WEIGHT_MIN), 4)


def enrich_district_nodes_with_population(province: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add population and population_weight to district node rows.

    Matches district_name to ADM2 district population data.
    Population weight is a bounded multiplier [0.75, 1.35] based on
    district population percentile within the province.

    Never deletes rows. Unmatched districts get population_weight=1.0.
    """
    pop_df = load_district_population_for_province(province)
    if pop_df.empty:
        for row in rows:
            row["population"] = None
            row["population_weight"] = 1.0
        return rows

    pop_lookup = dict(zip(pop_df["district"], pop_df["population"]))
    all_populations = list(pop_df["population"])

    for row in rows:
        district = str(row.get("district_name") or "").strip()
        population = pop_lookup.get(district)
        if population is None:
            row["population"] = None
            row["population_weight"] = 1.0
        else:
            row["population"] = population
            row["population_weight"] = _compute_population_weight(population, all_populations)
    return rows


@lru_cache(maxsize=32)
def load_enriched_district_nodes(province: str) -> list[dict[str, Any]]:
    """Load district nodes with population enrichment applied."""
    rows = load_district_nodes_for_province(province)
    return enrich_district_nodes_with_population(province, rows)


def _confidence_multiplier(value: str | None) -> float:
    return CONFIDENCE_MULTIPLIERS.get(str(value or "").strip(), 0.65)


def _poi_rule(category: str | None) -> tuple[float, float]:
    return POI_CATEGORY_RULES.get(str(category or "").strip(), (14.0, 2.0))


def _nearest_distance_km(
    lat: float,
    lon: float,
    rows: list[dict[str, Any]],
    *,
    lat_key: str = "lat",
    lon_key: str = "lon",
    category_filter: set[str] | None = None,
) -> float | None:
    nearest = None
    for row in rows:
        if category_filter and str(row.get("category") or "").strip() not in category_filter:
            continue
        row_lat = _float_or_none(row.get(lat_key))
        row_lon = _float_or_none(row.get(lon_key))
        if row_lat is None or row_lon is None:
            continue
        distance = km_between(lat, lon, row_lat, row_lon)
        if nearest is None or distance < nearest:
            nearest = distance
    return nearest


def _post_json(url: str, data: str, timeout: float = 4.0) -> dict[str, Any]:
    request = Request(
        url,
        data=data.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "TH-EVI/0.2 water-check",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _water_query(lat: float, lon: float) -> str:
    return f"""
[out:json][timeout:4];
is_in({lat},{lon})->.a;
(
  way(pivot.a)["natural"="water"];
  relation(pivot.a)["natural"="water"];
  way(pivot.a)["water"];
  relation(pivot.a)["water"];
  way(pivot.a)["waterway"="riverbank"];
  relation(pivot.a)["waterway"="riverbank"];
  way(pivot.a)["landuse"="reservoir"];
  relation(pivot.a)["landuse"="reservoir"];
);
out tags 1;
""".strip()


def _building_query(lat: float, lon: float) -> str:
    return f"""
[out:json][timeout:4];
is_in({lat},{lon})->.a;
(
  way(pivot.a)["building"];
  relation(pivot.a)["building"];
  way(pivot.a)["building:part"];
  relation(pivot.a)["building:part"];
);
out tags 1;
""".strip()


@lru_cache(maxsize=2048)
def lookup_water_surface(lat_key: float, lon_key: float) -> dict[str, Any]:
    lat = round(lat_key, WATER_QUERY_ROUNDING)
    lon = round(lon_key, WATER_QUERY_ROUNDING)
    try:
        payload = _post_json(OVERPASS_URL, f"data={_water_query(lat, lon)}")
    except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
        return {
            "is_water": False,
            "surface_type": "unknown",
            "reason": None,
            "warning": f"Water-layer lookup unavailable: {type(exc).__name__}.",
            "feature_name": None,
        }

    elements = payload.get("elements") or []
    if not elements:
        return {
            "is_water": False,
            "surface_type": "land_or_unclassified",
            "reason": None,
            "warning": None,
            "feature_name": None,
        }

    tags = elements[0].get("tags") or {}
    feature_name = tags.get("name") or tags.get("water") or tags.get("natural")
    return {
        "is_water": True,
        "surface_type": "water",
        "reason": "Point falls inside an OSM water polygon.",
        "warning": None,
        "feature_name": feature_name,
    }


@lru_cache(maxsize=2048)
def lookup_building_surface(lat_key: float, lon_key: float) -> dict[str, Any]:
    lat = round(lat_key, WATER_QUERY_ROUNDING)
    lon = round(lon_key, WATER_QUERY_ROUNDING)
    try:
        payload = _post_json(OVERPASS_URL, f"data={_building_query(lat, lon)}")
    except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
        return {
            "is_building": False,
            "surface_type": "unknown",
            "reason": None,
            "warning": f"Building-layer lookup unavailable: {type(exc).__name__}.",
            "feature_name": None,
        }

    elements = payload.get("elements") or []
    if not elements:
        return {
            "is_building": False,
            "surface_type": "land_or_unclassified",
            "reason": None,
            "warning": None,
            "feature_name": None,
        }

    tags = elements[0].get("tags") or {}
    feature_name = tags.get("name") or tags.get("building") or tags.get("building:part")
    return {
        "is_building": True,
        "surface_type": "building",
        "reason": "Point falls inside an OSM building footprint.",
        "warning": None,
        "feature_name": feature_name,
    }


def poi_attraction_field(
    lat: float,
    lon: float,
    pois: list[dict[str, Any]],
    max_distance_km: float = 10.0,
) -> tuple[float, list[dict[str, Any]]]:
    total = 0.0
    contributions = []
    for poi in pois:
        poi_lat = _float_or_none(poi.get("lat"))
        poi_lon = _float_or_none(poi.get("lon"))
        if poi_lat is None or poi_lon is None:
            continue

        distance = km_between(lat, lon, poi_lat, poi_lon)
        if distance > max_distance_km:
            continue

        base_sessions, radius = _poi_rule(poi.get("category"))
        confidence = _confidence_multiplier(poi.get("confidence"))
        weight = exp(-((distance / max(radius, 0.1)) ** 2))
        sessions = base_sessions * confidence * weight
        if sessions <= 0.2:
            continue

        total += sessions
        contributions.append({
            "name": poi.get("name") or poi.get("poi_id") or "POI",
            "category": poi.get("category") or "unknown",
            "distance_km": round(distance, 2),
            "radius_km": radius,
            "sessions": round(sessions, 1),
            "confidence": poi.get("confidence") or "medium",
        })

    contributions.sort(key=lambda item: item["sessions"], reverse=True)
    return round(total, 1), contributions


def zone_influence_field(
    lat: float,
    lon: float,
    zones: list[dict[str, Any]],
    scenario: str = "base",
) -> tuple[float, list[dict[str, Any]]]:
    """Return hot-zone field score using the same decay shape as the heat map."""
    total = 0.0
    contributions = []
    scenario_key = f"demand_pool_{scenario}"
    for zone in zones:
        zone_lat = _float_or_none(zone.get("center_lat"))
        zone_lon = _float_or_none(zone.get("center_lon"))
        radius = _float_or_none(zone.get("radius_km"))
        demand_pool = _float_or_none(zone.get(scenario_key))
        if zone_lat is None or zone_lon is None or radius is None or demand_pool is None:
            continue

        radius = max(radius, 0.1)
        distance = km_between(lat, lon, zone_lat, zone_lon)
        if distance > radius * 1.8:
            continue

        weight = max(0.0, 1.0 - distance / (radius * 1.8)) ** 2
        score = demand_pool * weight
        if score <= 0.2:
            continue

        total += score
        contributions.append({
            "name": zone.get("name") or zone.get("zone_id") or "Hot zone",
            "distance_km": round(distance, 2),
            "radius_km": round(radius, 1),
            "zone_score": round(score, 1),
            "competition_pressure": zone.get("competition_pressure") or "unknown",
            "confidence": zone.get("confidence") or "medium",
        })

    contributions.sort(key=lambda item: item["zone_score"], reverse=True)
    if contributions:
        primary = contributions[0]["zone_score"]
        secondary = max(0.0, total - primary) * SECONDARY_ZONE_SHARE
        total = primary + secondary
    return round(total, 1), contributions


def district_node_field(
    lat: float,
    lon: float,
    district_nodes: list[dict[str, Any]],
) -> tuple[float, list[dict[str, Any]]]:
    total = 0.0
    contributions = []
    for node in district_nodes:
        node_lat = _float_or_none(node.get("lat"))
        node_lon = _float_or_none(node.get("lon"))
        if node_lat is None or node_lon is None:
            continue

        node_type = str(node.get("node_type") or "coverage_anchor").strip()
        base_sessions, default_radius, suggested_location_type = DISTRICT_NODE_RULES.get(
            node_type,
            DISTRICT_NODE_RULES["coverage_anchor"],
        )
        radius = _float_or_none(node.get("radius_km")) or default_radius
        confidence = _float_or_none(node.get("confidence_multiplier")) or 1.0
        population_weight = _float_or_none(node.get("population_weight")) or 1.0
        distance = km_between(lat, lon, node_lat, node_lon)
        if distance > radius * 1.5:
            continue

        weight = exp(-((distance / max(radius, 0.1)) ** 2))
        sessions = base_sessions * confidence * population_weight * weight
        if sessions <= 0.15:
            continue

        total += sessions
        contributions.append({
            "name": node.get("name") or node.get("district_name") or node.get("node_id") or "District node",
            "district_name": node.get("district_name") or "",
            "node_type": node_type,
            "distance_km": round(distance, 2),
            "radius_km": round(radius, 1),
            "sessions": round(sessions, 1),
            "population": node.get("population"),
            "population_weight": round(population_weight, 3),
            "suggested_location_type": suggested_location_type,
        })

    contributions.sort(key=lambda item: item["sessions"], reverse=True)
    return round(total, 1), contributions


def _parse_power_kw(row: dict[str, Any]) -> float:
    for key in ("max_kw", "power_kw", "kw"):
        value = _float_or_none(row.get(key))
        if value:
            return value
    text = " ".join(str(row.get(key, "")) for key in ("power_summary", "connector_summary"))
    for token in text.replace(";", " ").replace(",", " ").split():
        try:
            value = float(token)
        except ValueError:
            continue
        if 20 <= value <= 1000:
            return value
    return 120.0


def _parse_guns(row: dict[str, Any]) -> int:
    for key in ("guns", "connector_count", "capacity"):
        value = _float_or_none(row.get(key))
        if value:
            return max(1, int(value))
    text = " ".join(str(row.get(key, "")) for key in ("connector_summary", "power_summary"))
    lowered = text.lower()
    if "x6" in lowered or "6 guns" in lowered:
        return 6
    if "x4" in lowered or "4 guns" in lowered:
        return 4
    if "x2" in lowered or "2 guns" in lowered:
        return 2
    return 2


def _competitor_status_multiplier(status: str | None) -> float:
    return COMPETITOR_STATUS_MULTIPLIERS.get(str(status or "").strip(), 0.60)


def competitor_penalty_field(
    lat: float,
    lon: float,
    competitors: list[dict[str, Any]],
    max_distance_km: float = 12.0,
) -> tuple[float, list[dict[str, Any]], int]:
    total = 0.0
    contributions = []
    skipped_without_coordinates = 0
    for competitor in competitors:
        comp_lat = _float_or_none(competitor.get("lat"))
        comp_lon = _float_or_none(competitor.get("lon"))
        if comp_lat is None or comp_lon is None:
            skipped_without_coordinates += 1
            continue

        distance = km_between(lat, lon, comp_lat, comp_lon)
        if distance > max_distance_km:
            continue

        guns = _parse_guns(competitor)
        max_kw = _parse_power_kw(competitor)
        status_mult = _competitor_status_multiplier(competitor.get("verification_status"))
        guns_factor = max(guns, 1) ** 0.55
        power_factor = max(0.45, min(max_kw / 120.0, 2.2)) ** 0.45
        radius = max(2.5, min(7.0, 2.0 + guns * 0.35 + max_kw / 140.0))
        weight = exp(-((distance / radius) ** 2))
        sessions = 9.0 * guns_factor * power_factor * status_mult * weight
        if sessions <= 0.2:
            continue

        total += sessions
        contributions.append({
            "name": competitor.get("name") or competitor.get("station_id") or "Competitor",
            "network": competitor.get("network") or competitor.get("operator") or "unknown",
            "distance_km": round(distance, 2),
            "radius_km": round(radius, 1),
            "guns": guns,
            "max_kw": round(max_kw, 0),
            "sessions": round(sessions, 1),
            "verification_status": competitor.get("verification_status") or "unknown",
        })

    contributions.sort(key=lambda item: item["sessions"], reverse=True)
    return round(total, 1), contributions, skipped_without_coordinates


def _spatial_location_type(
    top_pois: list[dict[str, Any]],
    top_districts: list[dict[str, Any]] | None = None,
) -> str:
    categories = {item["category"] for item in top_pois[:3]}
    if {"transport_corridor", "border_crossing"} & categories:
        return "highway"
    if "city_center" in categories:
        return "city_center"
    for item in (top_districts or [])[:2]:
        suggested = item.get("suggested_location_type")
        if suggested in {"highway", "city_center", "destination", "suburban"}:
            return str(suggested)
    if categories:
        return "destination"
    return "suburban"


def assess_surface_access(
    lat: float,
    lon: float,
    *,
    pois: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    zone_score: float,
    poi_field_score: float,
) -> dict[str, Any]:
    water = lookup_water_surface(lat, lon)
    if water["is_water"]:
        return {
            "status": "rejected",
            "surface_type": "water",
            "access_ok": False,
            "urban_eligible": False,
            "reason": water["reason"],
            "feature_name": water["feature_name"],
            "surface_warning": water["warning"],
            "nearest_access_anchor_km": None,
            "nearest_urban_anchor_km": None,
            "nearest_competitor_km": None,
            "nearest_zone_center_km": None,
        }

    building = lookup_building_surface(lat, lon)
    if building["is_building"]:
        return {
            "status": "rejected",
            "surface_type": "building",
            "access_ok": False,
            "urban_eligible": False,
            "reason": building["reason"],
            "feature_name": building["feature_name"],
            "surface_warning": building["warning"] or water["warning"],
            "nearest_access_anchor_km": None,
            "nearest_urban_anchor_km": None,
            "nearest_competitor_km": None,
            "nearest_zone_center_km": None,
        }

    access_anchor_km = _nearest_distance_km(
        lat,
        lon,
        pois,
        category_filter=ACCESS_SUPPORT_CATEGORIES,
    )
    urban_anchor_km = _nearest_distance_km(
        lat,
        lon,
        pois,
        category_filter=URBAN_SIGNAL_CATEGORIES,
    )
    competitor_km = _nearest_distance_km(lat, lon, competitors)
    zone_km = _nearest_distance_km(
        lat,
        lon,
        zones,
        lat_key="center_lat",
        lon_key="center_lon",
    )

    access_ok = any(
        value is not None and value <= threshold
        for value, threshold in (
            (access_anchor_km, SURFACE_REJECT_DISTANCE_KM),
            (competitor_km, SURFACE_LOW_RELEVANCE_DISTANCE_KM),
            (zone_km, ZONE_ACCESS_DISTANCE_KM),
        )
    )
    weak_context_present = any(
        value is not None and value <= LOW_RELEVANCE_CONTEXT_DISTANCE_KM
        for value in (urban_anchor_km, competitor_km, zone_km)
    ) or zone_score >= LOW_RELEVANCE_CONTEXT_SCORE or poi_field_score >= LOW_RELEVANCE_CONTEXT_SCORE
    urban_eligible = (
        zone_score >= ZONE_URBAN_SCORE_THRESHOLD
        or poi_field_score >= POI_URBAN_SCORE_THRESHOLD
        or (urban_anchor_km is not None and urban_anchor_km <= SURFACE_LOW_RELEVANCE_DISTANCE_KM)
    )

    if not access_ok:
        if weak_context_present:
            return {
                "status": "low_relevance",
                "surface_type": "road_access_candidate",
                "access_ok": False,
                "urban_eligible": False,
                "reason": "Nearby city activity exists, but direct access signal is still weak at this point.",
                "feature_name": water["feature_name"] or building["feature_name"],
                "surface_warning": water["warning"] or building["warning"],
                "nearest_access_anchor_km": round(access_anchor_km, 2) if access_anchor_km is not None else None,
                "nearest_urban_anchor_km": round(urban_anchor_km, 2) if urban_anchor_km is not None else None,
                "nearest_competitor_km": round(competitor_km, 2) if competitor_km is not None else None,
                "nearest_zone_center_km": round(zone_km, 2) if zone_km is not None else None,
            }
        return {
            "status": "rejected",
            "surface_type": "isolated_land",
            "access_ok": False,
            "urban_eligible": False,
            "reason": "No nearby urban access anchor, corridor, or verified competitor.",
            "feature_name": water["feature_name"] or building["feature_name"],
            "surface_warning": water["warning"] or building["warning"],
            "nearest_access_anchor_km": round(access_anchor_km, 2) if access_anchor_km is not None else None,
            "nearest_urban_anchor_km": round(urban_anchor_km, 2) if urban_anchor_km is not None else None,
            "nearest_competitor_km": round(competitor_km, 2) if competitor_km is not None else None,
            "nearest_zone_center_km": round(zone_km, 2) if zone_km is not None else None,
        }

    if not urban_eligible:
        return {
            "status": "low_relevance",
            "surface_type": "road_access_candidate",
            "access_ok": True,
            "urban_eligible": False,
            "reason": "Road access looks plausible, but the point is still outside a strong urban demand cluster.",
            "feature_name": water["feature_name"] or building["feature_name"],
            "surface_warning": water["warning"] or building["warning"],
            "nearest_access_anchor_km": round(access_anchor_km, 2) if access_anchor_km is not None else None,
            "nearest_urban_anchor_km": round(urban_anchor_km, 2) if urban_anchor_km is not None else None,
            "nearest_competitor_km": round(competitor_km, 2) if competitor_km is not None else None,
            "nearest_zone_center_km": round(zone_km, 2) if zone_km is not None else None,
        }

    return {
        "status": "eligible",
        "surface_type": "urban_access_candidate",
        "access_ok": True,
        "urban_eligible": True,
        "reason": "Point is close enough to urban access anchors to run a demand estimate.",
        "feature_name": water["feature_name"] or building["feature_name"],
        "surface_warning": water["warning"] or building["warning"],
        "nearest_access_anchor_km": round(access_anchor_km, 2) if access_anchor_km is not None else None,
        "nearest_urban_anchor_km": round(urban_anchor_km, 2) if urban_anchor_km is not None else None,
        "nearest_competitor_km": round(competitor_km, 2) if competitor_km is not None else None,
        "nearest_zone_center_km": round(zone_km, 2) if zone_km is not None else None,
    }


def analyze_click_location(
    lat: float,
    lon: float,
    province: str,
    year: int = 2030,
    scenario: str = "base",
    mode: str = "urban",
    avg_kwh_per_session: float = 32.0,
    price_per_kwh: float = 6.8,
) -> dict[str, Any]:
    """Estimate click-point demand from base area demand plus POI and competitor fields."""
    factor = SCENARIO_FACTORS.get(scenario, 1.0)
    mode = mode if mode in HEATMAP_MODES else "urban"
    pois = load_pois_for_province(province)
    competitors = load_competitors_for_province(province)
    zones = load_hot_zones_for_province(province)
    district_nodes = load_enriched_district_nodes(province)

    zone_score, zone_contributions = zone_influence_field(lat, lon, zones, scenario=scenario)
    poi_boost, poi_contributions = poi_attraction_field(lat, lon, pois)
    district_boost, district_contributions = district_node_field(lat, lon, district_nodes)
    competitor_penalty, competitor_contributions, skipped_competitors = competitor_penalty_field(
        lat,
        lon,
        competitors,
    )
    surface = assess_surface_access(
        lat,
        lon,
        pois=pois,
        competitors=competitors,
        zones=zones,
        zone_score=zone_score,
        poi_field_score=poi_boost,
    )
    location_type = _spatial_location_type(poi_contributions, district_contributions)
    location_result = LocationDemandModel(province=province).estimate(
        lat,
        lon,
        year,
        location_type=location_type,
    )

    raw_base_sessions = location_result["charging_sessions_per_day"] * factor
    capturable_zone_sessions = zone_score * ZONE_CAPTURE_FACTOR
    capturable_poi_sessions = poi_boost * POI_CAPTURE_FACTOR * factor
    capturable_district_sessions = district_boost * DISTRICT_NODE_CAPTURE_FACTOR * factor
    spatial_boost = (
        max(capturable_zone_sessions, capturable_poi_sessions)
        + min(capturable_zone_sessions, capturable_poi_sessions) * SPATIAL_OVERLAP_SHARE
    )
    if mode in {"community", "district"}:
        spatial_boost += capturable_district_sessions
    gross_area_demand = raw_base_sessions + (zone_score * factor) + (poi_boost * factor)
    if mode in {"community", "district"}:
        gross_area_demand += district_boost * factor
    demand_share = 1.0
    if surface["status"] == "low_relevance":
        demand_share = LOW_RELEVANCE_DEMAND_SHARE

    base_sessions = raw_base_sessions * demand_share
    if surface["status"] == "low_relevance":
        base_sessions = min(base_sessions, LOW_RELEVANCE_MAX_SESSIONS)
    effective_spatial_boost = spatial_boost * demand_share
    positive_demand = base_sessions + effective_spatial_boost
    effective_competitor_penalty = min(
        competitor_penalty,
        positive_demand * MAX_COMPETITOR_PENALTY_SHARE,
    )
    net_sessions = max(
        0.0,
        positive_demand - effective_competitor_penalty,
    )
    if surface["status"] == "low_relevance":
        net_sessions = min(net_sessions, LOW_RELEVANCE_MAX_SESSIONS)
    if surface["status"] == "rejected":
        net_sessions = 0.0

    confidence = "medium"
    warnings = []
    if not pois:
        confidence = "low"
        warnings.append("No POI seed file found for this province.")
    if not zones:
        warnings.append("No hot-zone seed file found for this province.")
    if mode in {"community", "district"} and not district_nodes:
        warnings.append("No district-node seed file found for this province.")
    if skipped_competitors:
        warnings.append(f"{skipped_competitors} competitor rows skipped because coordinates are missing.")
    if len(competitor_contributions) == 0:
        warnings.append("No coordinate-verified competitor within radius; penalty may be understated.")
    if len(poi_contributions) == 0:
        warnings.append("No strong POI within radius; demand relies mostly on base area model.")
    if surface.get("surface_warning"):
        warnings.append(surface["surface_warning"])
    if surface["status"] != "eligible":
        warnings.append(surface["reason"])
    if (poi_contributions or zone_contributions) and competitor_contributions:
        confidence = "medium_high"
    if surface["status"] == "rejected":
        confidence = "low"

    net_sessions_rounded = round(net_sessions, 1)

    return {
        "lat": lat,
        "lon": lon,
        "province": province,
        "year": year,
        "scenario": scenario,
        "mode": mode,
        "location_type": location_type,
        "aadt_used": location_result["aadt_used"],
        "fleet_ev_share_pct": location_result["fleet_ev_share_pct"],
        "charge_probability_pct": location_result["charge_probability_pct"],
        "raw_base_sessions": round(raw_base_sessions, 1),
        "base_sessions": round(base_sessions, 1),
        "gross_area_demand_sessions": round(gross_area_demand, 1),
        "raw_zone_score": round(zone_score, 1),
        "zone_boost_sessions": round(capturable_zone_sessions, 1),
        "raw_poi_field_sessions": round(poi_boost * factor, 1),
        "poi_boost_sessions": round(capturable_poi_sessions, 1),
        "raw_district_field_sessions": round(district_boost * factor, 1),
        "district_boost_sessions": round(capturable_district_sessions, 1),
        "raw_spatial_boost_sessions": round(spatial_boost, 1),
        "spatial_boost_sessions": round(effective_spatial_boost, 1),
        "raw_competitor_penalty_sessions": round(competitor_penalty, 1),
        "competitor_penalty_sessions": round(effective_competitor_penalty, 1),
        "net_sessions_per_day": net_sessions_rounded,
        "daily_kwh": round(net_sessions_rounded * avg_kwh_per_session, 1),
        "daily_revenue": round(net_sessions_rounded * avg_kwh_per_session * price_per_kwh, 0),
        "avg_kwh_per_session": avg_kwh_per_session,
        "price_per_kwh": price_per_kwh,
        "top_pois": poi_contributions[:5],
        "top_zones": zone_contributions[:5],
        "top_districts": district_contributions[:5],
        "top_competitors": competitor_contributions[:5],
        "zone_count": len(zone_contributions),
        "poi_count": len(poi_contributions),
        "district_count": len(district_contributions),
        "competitor_count": len(competitor_contributions),
        "skipped_competitors_without_coordinates": skipped_competitors,
        "surface_type": surface["surface_type"],
        "access_ok": surface["access_ok"],
        "urban_eligible": surface["urban_eligible"],
        "eligibility_status": surface["status"],
        "eligibility_reason": surface["reason"],
        "surface_feature_name": surface.get("feature_name"),
        "nearest_access_anchor_km": surface["nearest_access_anchor_km"],
        "nearest_urban_anchor_km": surface["nearest_urban_anchor_km"],
        "nearest_competitor_km": surface["nearest_competitor_km"],
        "nearest_zone_center_km": surface["nearest_zone_center_km"],
        "confidence": confidence,
        "warnings": warnings,
    }
