"""POI and competitor spatial demand fields for click-based screening."""

from __future__ import annotations

import csv
from functools import lru_cache
from math import cos, exp, radians, sqrt
from pathlib import Path
from typing import Any

from .location import LocationDemandModel


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PROVINCE_SLUGS = {
    "เชียงใหม่": "chiang_mai",
    "Chiang Mai": "chiang_mai",
    "เชียงราย": "chiang_rai",
    "Chiang Rai": "chiang_rai",
    "ลำปาง": "lampang",
    "Lampang": "lampang",
    "แพร่": "phrae",
    "Phrae": "phrae",
    "พะเยา": "phayao",
    "Phayao": "phayao",
    "หนองคาย": "nong_khai",
    "Nong Khai": "nong_khai",
    "อุดรธานี": "udon_thani",
    "Udon Thani": "udon_thani",
    "ขอนแก่น": "khon_kaen",
    "Khon Kaen": "khon_kaen",
    "อุบลราชธานี": "ubon_ratchathani",
    "Ubon Ratchathani": "ubon_ratchathani",
}

SCENARIO_FACTORS = {
    "conservative": 0.75,
    "base": 1.0,
    "upside": 1.25,
}

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


@lru_cache(maxsize=32)
def load_pois_for_province(province: str) -> list[dict[str, Any]]:
    slug = _slug_for_province(province)
    if not slug:
        return []
    rows = _read_csv(DATA_DIR / f"poi_{slug}_seed.csv")
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
    return rows


@lru_cache(maxsize=32)
def load_hot_zones_for_province(province: str) -> list[dict[str, Any]]:
    slug = _slug_for_province(province)
    if not slug:
        return []
    return _read_csv(DATA_DIR / f"hot_zones_{slug}.csv")


def _confidence_multiplier(value: str | None) -> float:
    return CONFIDENCE_MULTIPLIERS.get(str(value or "").strip(), 0.65)


def _poi_rule(category: str | None) -> tuple[float, float]:
    return POI_CATEGORY_RULES.get(str(category or "").strip(), (14.0, 2.0))


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


def _spatial_location_type(top_pois: list[dict[str, Any]]) -> str:
    categories = {item["category"] for item in top_pois[:3]}
    if {"transport_corridor", "border_crossing"} & categories:
        return "highway"
    if "city_center" in categories:
        return "city_center"
    if categories:
        return "destination"
    return "suburban"


def analyze_click_location(
    lat: float,
    lon: float,
    province: str,
    year: int = 2030,
    scenario: str = "base",
    avg_kwh_per_session: float = 32.0,
    price_per_kwh: float = 6.8,
) -> dict[str, Any]:
    """Estimate click-point demand from base area demand plus POI and competitor fields."""
    factor = SCENARIO_FACTORS.get(scenario, 1.0)
    pois = load_pois_for_province(province)
    competitors = load_competitors_for_province(province)
    zones = load_hot_zones_for_province(province)

    zone_score, zone_contributions = zone_influence_field(lat, lon, zones, scenario=scenario)
    poi_boost, poi_contributions = poi_attraction_field(lat, lon, pois)
    competitor_penalty, competitor_contributions, skipped_competitors = competitor_penalty_field(
        lat,
        lon,
        competitors,
    )
    location_type = _spatial_location_type(poi_contributions)
    location_result = LocationDemandModel(province=province).estimate(
        lat,
        lon,
        year,
        location_type=location_type,
    )

    base_sessions = location_result["charging_sessions_per_day"] * factor
    capturable_zone_sessions = zone_score * ZONE_CAPTURE_FACTOR
    capturable_poi_sessions = poi_boost * POI_CAPTURE_FACTOR * factor
    spatial_boost = (
        max(capturable_zone_sessions, capturable_poi_sessions)
        + min(capturable_zone_sessions, capturable_poi_sessions) * SPATIAL_OVERLAP_SHARE
    )
    positive_demand = base_sessions + spatial_boost
    effective_competitor_penalty = min(
        competitor_penalty,
        positive_demand * MAX_COMPETITOR_PENALTY_SHARE,
    )
    net_sessions = max(
        0.0,
        positive_demand - effective_competitor_penalty,
    )

    confidence = "medium"
    warnings = []
    if not pois:
        confidence = "low"
        warnings.append("No POI seed file found for this province.")
    if not zones:
        warnings.append("No hot-zone seed file found for this province.")
    if skipped_competitors:
        warnings.append(f"{skipped_competitors} competitor rows skipped because coordinates are missing.")
    if len(competitor_contributions) == 0:
        warnings.append("No coordinate-verified competitor within radius; penalty may be understated.")
    if len(poi_contributions) == 0:
        warnings.append("No strong POI within radius; demand relies mostly on base area model.")
    if (poi_contributions or zone_contributions) and competitor_contributions:
        confidence = "medium_high"

    net_sessions_rounded = round(net_sessions, 1)

    return {
        "lat": lat,
        "lon": lon,
        "province": province,
        "year": year,
        "scenario": scenario,
        "location_type": location_type,
        "base_sessions": round(base_sessions, 1),
        "raw_zone_score": round(zone_score, 1),
        "zone_boost_sessions": round(capturable_zone_sessions, 1),
        "raw_poi_field_sessions": round(poi_boost * factor, 1),
        "poi_boost_sessions": round(capturable_poi_sessions, 1),
        "spatial_boost_sessions": round(spatial_boost, 1),
        "raw_competitor_penalty_sessions": round(competitor_penalty, 1),
        "competitor_penalty_sessions": round(effective_competitor_penalty, 1),
        "net_sessions_per_day": net_sessions_rounded,
        "daily_kwh": round(net_sessions_rounded * avg_kwh_per_session, 1),
        "daily_revenue": round(net_sessions_rounded * avg_kwh_per_session * price_per_kwh, 0),
        "avg_kwh_per_session": avg_kwh_per_session,
        "price_per_kwh": price_per_kwh,
        "top_pois": poi_contributions[:5],
        "top_zones": zone_contributions[:5],
        "top_competitors": competitor_contributions[:5],
        "zone_count": len(zone_contributions),
        "poi_count": len(poi_contributions),
        "competitor_count": len(competitor_contributions),
        "skipped_competitors_without_coordinates": skipped_competitors,
        "confidence": confidence,
        "warnings": warnings,
    }
