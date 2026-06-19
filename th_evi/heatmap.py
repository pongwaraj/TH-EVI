"""Province-level heat-map generation for EV charging demand."""

from __future__ import annotations

from functools import lru_cache
from math import cos, exp, radians
from typing import Any, Literal

from .location import LocationDemandModel
from .validation import station_calibration_summary
from .spatial import (
    BUSINESS_AREA_CAPTURE_FACTOR,
    POI_CAPTURE_FACTOR,
    SCENARIO_FACTORS,
    ZONE_CAPTURE_FACTOR,
    business_area_field,
    competitor_penalty_field,
    km_between,
    load_business_areas_for_province,
    load_competitors_for_province,
    load_enriched_district_nodes,
    load_heatmap_exclusions_for_province,
    load_hot_zones_for_province,
    load_pois_for_province,
    poi_attraction_field,
    zone_influence_field,
)


VALID_HEATMAP_SCENARIOS = {"conservative", "base", "upside"}
VALID_HEATMAP_MODES = {"urban", "community", "district"}
VALID_HEATMAP_LAYERS = {"demand", "competition", "net"}
HEATMAP_MAX_RESOLUTION_KM = 5.0
HEATMAP_PADDING_KM = 2.0
HEATMAP_MAX_COMPETITOR_SIGNAL_SHARE = 0.55
HEATMAP_MAX_ANCHOR_DISTANCE_KM = 6.5
HEATMAP_MAX_POI_DISTANCE_KM = 5.5
HEATMAP_MAX_ZONE_DISTANCE_FACTOR = 1.35
HEATMAP_MAX_COMPETITOR_DISTANCE_KM = 4.0
URBAN_MIN_CONTEXT_SESSIONS = 5.0
URBAN_MIN_HEAT_SCORE = 8.0
COMMUNITY_MIN_CONTEXT_SESSIONS = 2.4
COMMUNITY_MIN_HEAT_SCORE = 4.0
COMMUNITY_DISTANCE_FACTOR = 1.5
DISTRICT_NODE_CAPTURE_FACTOR = 0.28
ISOLATED_CELL_NEIGHBOR_FACTOR = 1.35
ISOLATED_CELL_STRONG_HEAT_SCORE = 28.0
ISOLATED_CELL_STRONG_CONTEXT_SCORE = 18.0
SEASONAL_TOURISM_CATEGORIES = {
    "tourism",
    "tourism_museum",
    "recreation",
}
COMMUNITY_SUPPORT_POI_CATEGORIES = {
    "airport",
    "bus_station",
    "city_center",
    "district_center",
    "education",
    "gas_station",
    "hospital",
    "hotel",
    "hotel_condo",
    "lifestyle",
    "market_tourism",
    "office",
    "shopping_mall",
    "supermarket",
    "target_site",
    "transport",
    "transport_corridor",
}
HIGHWAY_SUPPORT_POI_CATEGORIES = {
    "airport",
    "bus_station",
    "district_center",
    "education",
    "gas_station",
    "hospital",
    "office",
    "shopping_mall",
    "supermarket",
    "target_site",
    "transport",
    "transport_corridor",
}
SUPPORTIVE_POI_MAX_DISTANCE_KM = 4.5
HIGHWAY_SUPPORTIVE_POI_MAX_DISTANCE_KM = 3.5
URBAN_DESTINATION_POI_CATEGORIES = {
    "airport",
    "bus_station",
    "district_center",
    "education",
    "event_space",
    "hospital",
    "hotel",
    "hotel_condo",
    "lifestyle",
    "market_tourism",
    "office",
    "shopping_mall",
    "supermarket",
    "target_site",
    "transport",
}

DISTRICT_NODE_RULES: dict[str, tuple[float, float, str]] = {
    "district_center": (18.0, 3.6, "destination"),
    "transport_junction": (18.0, 4.0, "highway"),
    "tourism_town": (17.0, 3.5, "destination"),
    "district_mall": (18.0, 3.2, "destination"),
    "industrial_town": (18.0, 3.4, "destination"),
    "border_town": (22.0, 4.4, "highway"),
    "coverage_anchor": (14.0, 3.2, "suburban"),
}

HEATMAP_LAYER_SCORE_FIELDS = {
    "demand": "demand_score",
    "competition": "competition_score",
    "net": "net_opportunity_score",
}


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _location_type_for_heat(
    top_pois: list[dict[str, Any]],
    top_business_areas: list[dict[str, Any]],
    top_districts: list[dict[str, Any]],
) -> str:
    categories = {item.get("category") for item in top_pois[:3]}
    if {"transport_corridor", "border_crossing"} & categories:
        return "highway"
    if any(
        item.get("category") == "city_center"
        and (_float_or_none(item.get("distance_km")) or 999.0) <= 3.5
        for item in top_pois[:3]
    ):
        return "city_center"
    urban_destination_hits = sum(1 for category in categories if category in URBAN_DESTINATION_POI_CATEGORIES)
    if urban_destination_hits >= 2:
        return "destination"
    for item in top_business_areas[:2]:
        suggested = item.get("suggested_location_type")
        if suggested in {"highway", "city_center", "destination", "suburban"}:
            return str(suggested)
    for item in top_districts[:2]:
        suggested = item.get("suggested_location_type")
        if suggested in {"highway", "city_center", "destination", "suburban"}:
            return str(suggested)
    if categories:
        return "destination"
    return "suburban"


def _iter_anchor_points(
    pois: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    business_areas: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    district_nodes: list[dict[str, Any]],
) -> list[tuple[float, float]]:
    anchors: list[tuple[float, float]] = []
    for poi in pois:
        lat = _float_or_none(poi.get("lat"))
        lon = _float_or_none(poi.get("lon"))
        if lat is not None and lon is not None:
            anchors.append((lat, lon))
    for zone in zones:
        lat = _float_or_none(zone.get("center_lat"))
        lon = _float_or_none(zone.get("center_lon"))
        if lat is not None and lon is not None:
            anchors.append((lat, lon))
    for area in business_areas:
        lat = _float_or_none(area.get("center_lat"))
        lon = _float_or_none(area.get("center_lon"))
        if lat is not None and lon is not None:
            anchors.append((lat, lon))
    for competitor in competitors:
        lat = _float_or_none(competitor.get("lat"))
        lon = _float_or_none(competitor.get("lon"))
        if lat is not None and lon is not None:
            anchors.append((lat, lon))
    for node in district_nodes:
        lat = _float_or_none(node.get("lat"))
        lon = _float_or_none(node.get("lon"))
        if lat is not None and lon is not None:
            anchors.append((lat, lon))
    return anchors


def _province_bounds(
    pois: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    business_areas: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    district_nodes: list[dict[str, Any]],
    resolution_km: float,
) -> dict[str, float]:
    anchors = _iter_anchor_points(pois, zones, business_areas, competitors, district_nodes)
    if not anchors:
        raise ValueError("No POI, hot-zone, competitor, or district node coordinates found for this province.")

    lats = [lat for lat, _ in anchors]
    lons = [lon for _, lon in anchors]
    center_lat = (min(lats) + max(lats)) / 2
    lat_pad = (HEATMAP_PADDING_KM + resolution_km) / 111.0
    lon_pad = (HEATMAP_PADDING_KM + resolution_km) / (111.0 * max(0.2, cos(radians(center_lat))))
    return {
        "lat_min": min(lats) - lat_pad,
        "lat_max": max(lats) + lat_pad,
        "lon_min": min(lons) - lon_pad,
        "lon_max": max(lons) + lon_pad,
    }


def _nearest_row_distance_km(
    lat: float,
    lon: float,
    rows: list[dict[str, Any]],
    *,
    lat_key: str = "lat",
    lon_key: str = "lon",
) -> float | None:
    nearest = None
    for row in rows:
        row_lat = _float_or_none(row.get(lat_key))
        row_lon = _float_or_none(row.get(lon_key))
        if row_lat is None or row_lon is None:
            continue
        distance = km_between(lat, lon, row_lat, row_lon)
        if nearest is None or distance < nearest:
            nearest = distance
    return nearest


def _nearest_zone_ratio(
    lat: float,
    lon: float,
    zones: list[dict[str, Any]],
) -> float | None:
    best_ratio = None
    for zone in zones:
        zone_lat = _float_or_none(zone.get("center_lat"))
        zone_lon = _float_or_none(zone.get("center_lon"))
        radius = _float_or_none(zone.get("radius_km"))
        if zone_lat is None or zone_lon is None or radius is None or radius <= 0:
            continue
        ratio = km_between(lat, lon, zone_lat, zone_lon) / radius
        if best_ratio is None or ratio < best_ratio:
            best_ratio = ratio
    return best_ratio


def _nearest_business_area_ratio(
    lat: float,
    lon: float,
    business_areas: list[dict[str, Any]],
) -> float | None:
    best_ratio = None
    for area in business_areas:
        area_lat = _float_or_none(area.get("center_lat"))
        area_lon = _float_or_none(area.get("center_lon"))
        radius = _float_or_none(area.get("radius_km"))
        if area_lat is None or area_lon is None or radius is None or radius <= 0:
            continue
        ratio = km_between(lat, lon, area_lat, area_lon) / radius
        if best_ratio is None or ratio < best_ratio:
            best_ratio = ratio
    return best_ratio


def _point_hits_heatmap_exclusion(
    lat: float,
    lon: float,
    exclusions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for exclusion in exclusions:
        lat_min = _float_or_none(exclusion.get("lat_min"))
        lat_max = _float_or_none(exclusion.get("lat_max"))
        lon_min = _float_or_none(exclusion.get("lon_min"))
        lon_max = _float_or_none(exclusion.get("lon_max"))
        if (
            lat_min is not None
            and lat_max is not None
            and lon_min is not None
            and lon_max is not None
            and lat_min <= lat <= lat_max
            and lon_min <= lon <= lon_max
        ):
            return exclusion
        center_lat = _float_or_none(exclusion.get("center_lat"))
        center_lon = _float_or_none(exclusion.get("center_lon"))
        radius = _float_or_none(exclusion.get("radius_km"))
        if center_lat is None or center_lon is None or radius is None or radius <= 0:
            continue
        if km_between(lat, lon, center_lat, center_lon) <= radius:
            return exclusion
    return None


def _suppress_isolated_heat_points(
    points: list[dict[str, Any]],
    *,
    lat_step: float,
    lon_step: float,
    mode: str,
) -> list[dict[str, Any]]:
    if mode == "district" or len(points) <= 2:
        return points

    lat_limit = lat_step * ISOLATED_CELL_NEIGHBOR_FACTOR
    lon_limit = lon_step * ISOLATED_CELL_NEIGHBOR_FACTOR
    filtered: list[dict[str, Any]] = []

    for idx, point in enumerate(points):
        has_neighbor = False
        for other_idx, other in enumerate(points):
            if idx == other_idx:
                continue
            lat_gap = abs(point["lat"] - other["lat"])
            lon_gap = abs(point["lon"] - other["lon"])
            if lat_gap <= lat_limit and lon_gap <= lon_limit:
                has_neighbor = True
                break

        if has_neighbor:
            filtered.append(point)
            continue

        heat_score = _float_or_none(point.get("heat_score")) or 0.0
        context_score = _float_or_none(point.get("supportive_context_score")) or 0.0
        competitor_score = _float_or_none(point.get("competitor_signal_score")) or 0.0
        if (
            heat_score >= ISOLATED_CELL_STRONG_HEAT_SCORE
            or context_score >= ISOLATED_CELL_STRONG_CONTEXT_SCORE
            or competitor_score >= ISOLATED_CELL_STRONG_CONTEXT_SCORE
        ):
            filtered.append(point)

    return filtered


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
        if distance > radius * COMMUNITY_DISTANCE_FACTOR:
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


def _heatmap_thresholds(mode: str) -> tuple[float, float]:
    if mode in {"community", "district"}:
        return COMMUNITY_MIN_CONTEXT_SESSIONS, COMMUNITY_MIN_HEAT_SCORE
    return URBAN_MIN_CONTEXT_SESSIONS, URBAN_MIN_HEAT_SCORE


def _average_kwh_per_session_for_heat(location_type: str) -> float:
    return LocationDemandModel._avg_energy_per_session(location_type)


def _highway_support_multiplier(
    *,
    top_pois: list[dict[str, Any]],
    top_business_areas: list[dict[str, Any]],
    top_districts: list[dict[str, Any]],
    top_competitors: list[dict[str, Any]],
    poi_score: float,
    business_area_score: float,
    district_score: float,
    competitor_signal_score: float,
) -> float:
    nearby_supportive_poi = False
    for item in top_pois[:3]:
        category = str(item.get("category") or "").strip()
        distance = _float_or_none(item.get("distance_km"))
        if (
            category in HIGHWAY_SUPPORT_POI_CATEGORIES
            and distance is not None
            and distance <= HIGHWAY_SUPPORTIVE_POI_MAX_DISTANCE_KM
        ):
            nearby_supportive_poi = True
            break

    near_district = district_score >= 1.5 or _distance_within_limit(top_districts, max_distance_km=4.0)
    near_competitor = _distance_within_limit(top_competitors, max_distance_km=HEATMAP_MAX_COMPETITOR_DISTANCE_KM)
    area_types = {str(item.get("area_type") or "").strip() for item in top_business_areas[:2]}
    only_corridor_business = bool(area_types) and area_types <= {"periurban_connector"}

    # If the point is still mostly a corridor hypothesis with only weak support
    # from POI, district, and competitor evidence, do not let coarse AADT drive
    # a full highway demand base.
    if (
        only_corridor_business
        and poi_score < 4.0
        and district_score < 3.0
        and competitor_signal_score < 4.0
    ):
        return 0.05

    # A nearby competitor alone should not fully validate a high-AADT roadside
    # point if the surrounding evidence is still just corridor geometry.
    if only_corridor_business and near_competitor and not (nearby_supportive_poi or near_district):
        return 0.05

    if (
        poi_score < 3.0
        and business_area_score < 4.0
        and district_score < 2.5
        and competitor_signal_score < 8.5
    ):
        return 0.08

    # Do not let an outer-ring / corridor hypothesis get a near-full highway
    # multiplier from a weak district-junction signal alone. If there is no
    # truly supportive roadside POI nearby and the remaining evidence is still
    # thin, keep the point visible but not hot.
    if (
        not nearby_supportive_poi
        and only_corridor_business
        and poi_score < 5.0
        and business_area_score < 6.0
        and district_score < 2.0
    ):
        return 0.08

    if nearby_supportive_poi and near_district:
        return 1.0

    if nearby_supportive_poi or near_district:
        return 0.85

    if near_competitor:
        return 0.55

    if top_business_areas:
        if only_corridor_business:
            return 0.08
        return 0.55

    return 0.2


def _ratio_within_limit(
    contributions: list[dict[str, Any]],
    *,
    max_ratio: float,
) -> bool:
    if not contributions:
        return False
    distance = _float_or_none(contributions[0].get("distance_km"))
    radius = _float_or_none(contributions[0].get("radius_km"))
    if distance is None or radius is None or radius <= 0:
        return False
    return (distance / radius) <= max_ratio


def _distance_within_limit(
    contributions: list[dict[str, Any]],
    *,
    max_distance_km: float,
) -> bool:
    if not contributions:
        return False
    distance = _float_or_none(contributions[0].get("distance_km"))
    return distance is not None and distance <= max_distance_km


def _heatmap_supports_candidate(
    *,
    top_pois: list[dict[str, Any]],
    top_zones: list[dict[str, Any]],
    top_business_areas: list[dict[str, Any]],
    top_districts: list[dict[str, Any]],
    top_competitors: list[dict[str, Any]],
    mode: str,
) -> bool:
    near_poi = _distance_within_limit(top_pois, max_distance_km=HEATMAP_MAX_POI_DISTANCE_KM)
    near_zone = _ratio_within_limit(top_zones, max_ratio=HEATMAP_MAX_ZONE_DISTANCE_FACTOR)
    near_business_area = _ratio_within_limit(
        top_business_areas,
        max_ratio=HEATMAP_MAX_ZONE_DISTANCE_FACTOR,
    )
    near_competitor = _distance_within_limit(
        top_competitors,
        max_distance_km=HEATMAP_MAX_COMPETITOR_DISTANCE_KM,
    )
    near_district = _distance_within_limit(
        top_districts,
        max_distance_km=HEATMAP_MAX_ANCHOR_DISTANCE_KM,
    )

    near_any_anchor = near_poi or near_zone or near_business_area or near_competitor or near_district
    if not near_any_anchor:
        return False

    has_built_support = bool(top_business_areas or top_districts or top_competitors)
    nearby_poi_categories: set[str] = set()
    nearby_supportive_poi = False
    nearby_seasonal_tourism_poi = False
    for item in top_pois[:3]:
        category = str(item.get("category") or "").strip()
        distance = _float_or_none(item.get("distance_km"))
        if not category or distance is None:
            continue
        if distance <= HEATMAP_MAX_POI_DISTANCE_KM:
            nearby_poi_categories.add(category)
            if category in SEASONAL_TOURISM_CATEGORIES:
                nearby_seasonal_tourism_poi = True
        if distance <= SUPPORTIVE_POI_MAX_DISTANCE_KM and category in COMMUNITY_SUPPORT_POI_CATEGORIES:
            nearby_supportive_poi = True

    has_only_seasonal_tourism_poi = (
        bool(nearby_poi_categories)
        and nearby_poi_categories <= SEASONAL_TOURISM_CATEGORIES
        and nearby_seasonal_tourism_poi
    )

    if near_zone and not (near_poi or near_business_area or near_competitor or near_district):
        return False
    if has_only_seasonal_tourism_poi and not (has_built_support or nearby_supportive_poi):
        return False

    if mode in {"community", "district"}:
        return near_any_anchor and (near_district or near_poi or near_zone or near_business_area)
    return near_any_anchor and (near_poi or near_zone or near_business_area or near_competitor)


def _heatmap_mask_passes(
    *,
    lat: float,
    lon: float,
    context_sessions: float,
    heat_score: float,
    pois: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    business_areas: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    district_nodes: list[dict[str, Any]],
    top_pois: list[dict[str, Any]],
    top_business_areas: list[dict[str, Any]],
    top_districts: list[dict[str, Any]],
    top_competitors: list[dict[str, Any]],
    mode: str,
) -> bool:
    min_context, min_heat = _heatmap_thresholds(mode)
    if context_sessions < min_context or heat_score < min_heat:
        return False

    nearest_poi = _nearest_row_distance_km(lat, lon, pois)
    nearest_zone_ratio = _nearest_zone_ratio(lat, lon, zones)
    nearest_business_area_ratio = _nearest_business_area_ratio(lat, lon, business_areas)
    nearest_competitor = _nearest_row_distance_km(lat, lon, competitors)
    nearest_district = _nearest_row_distance_km(lat, lon, district_nodes)

    near_poi = nearest_poi is not None and nearest_poi <= HEATMAP_MAX_POI_DISTANCE_KM
    near_zone = nearest_zone_ratio is not None and nearest_zone_ratio <= HEATMAP_MAX_ZONE_DISTANCE_FACTOR
    near_business_area = (
        nearest_business_area_ratio is not None and nearest_business_area_ratio <= HEATMAP_MAX_ZONE_DISTANCE_FACTOR
    )
    near_competitor = (
        nearest_competitor is not None and nearest_competitor <= HEATMAP_MAX_COMPETITOR_DISTANCE_KM
    )
    near_district = nearest_district is not None and nearest_district <= HEATMAP_MAX_ANCHOR_DISTANCE_KM
    near_any_anchor = near_poi or near_zone or near_business_area or near_competitor or near_district
    has_built_support = bool(top_business_areas or top_districts or top_competitors)
    nearby_poi_categories: set[str] = set()
    nearby_supportive_poi = False
    nearby_seasonal_tourism_poi = False
    for item in top_pois[:3]:
        category = str(item.get("category") or "").strip()
        distance = _float_or_none(item.get("distance_km"))
        if not category or distance is None:
            continue
        if distance <= HEATMAP_MAX_POI_DISTANCE_KM:
            nearby_poi_categories.add(category)
            if category in SEASONAL_TOURISM_CATEGORIES:
                nearby_seasonal_tourism_poi = True
        if distance <= SUPPORTIVE_POI_MAX_DISTANCE_KM and category in COMMUNITY_SUPPORT_POI_CATEGORIES:
            nearby_supportive_poi = True
    has_only_seasonal_tourism_poi = (
        bool(nearby_poi_categories)
        and nearby_poi_categories <= SEASONAL_TOURISM_CATEGORIES
        and nearby_seasonal_tourism_poi
    )

    # Do not allow hot-zone spillover to create heat over implausible surfaces
    # or remote mountain tourism points when there is no nearby town, district,
    # business-area, or charger context to support a year-round station.
    if near_zone and not (near_poi or near_business_area or near_competitor or near_district):
        return False
    if has_only_seasonal_tourism_poi and not (has_built_support or nearby_supportive_poi):
        return False

    if mode in {"community", "district"}:
        return near_any_anchor and (near_district or near_poi or near_zone or near_business_area)
    return near_any_anchor and (near_poi or near_zone or near_business_area or near_competitor)


@lru_cache(maxsize=96)
def generate_province_heatmap(
    province: str,
    year: int = 2030,
    scenario: Literal["conservative", "base", "upside"] = "base",
    resolution_km: float = 1.0,
    mode: Literal["urban", "community", "district"] = "urban",
) -> dict[str, Any]:
    """Generate a province heat map for urban hotspots or community coverage."""
    if scenario not in VALID_HEATMAP_SCENARIOS:
        raise ValueError(f"scenario must be one of {sorted(VALID_HEATMAP_SCENARIOS)}")
    if mode not in VALID_HEATMAP_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_HEATMAP_MODES)}")
    if resolution_km <= 0 or resolution_km > HEATMAP_MAX_RESOLUTION_KM:
        raise ValueError(f"resolution_km must be in (0, {HEATMAP_MAX_RESOLUTION_KM}]")

    pois = load_pois_for_province(province)
    zones = load_hot_zones_for_province(province)
    business_areas = load_business_areas_for_province(province)
    competitors = load_competitors_for_province(province)
    district_nodes = load_enriched_district_nodes(province)
    exclusions = load_heatmap_exclusions_for_province(province)
    bounds = _province_bounds(pois, zones, business_areas, competitors, district_nodes, resolution_km)
    scenario_factor = SCENARIO_FACTORS.get(scenario, 1.0)
    min_context, min_heat = _heatmap_thresholds(mode)

    lat_step = resolution_km / 111.0
    mid_lat = (bounds["lat_min"] + bounds["lat_max"]) / 2
    lon_step = resolution_km / (111.0 * max(0.2, cos(radians(mid_lat))))

    demand = LocationDemandModel(province=province)
    points = []
    lat = bounds["lat_min"]
    while lat <= bounds["lat_max"] + 1e-9:
        lon = bounds["lon_min"]
        while lon <= bounds["lon_max"] + 1e-9:
            if _point_hits_heatmap_exclusion(lat, lon, exclusions):
                lon += lon_step
                continue
            zone_score, zone_contributions = zone_influence_field(lat, lon, zones, scenario=scenario)
            business_area_score, business_area_contributions = business_area_field(
                lat,
                lon,
                business_areas,
                scenario=scenario,
            )
            poi_score, poi_contributions = poi_attraction_field(lat, lon, pois)
            district_score, district_contributions = district_node_field(lat, lon, district_nodes)
            competitor_signal_raw, competitor_contributions, _ = competitor_penalty_field(
                lat,
                lon,
                competitors,
            )

            zone_sessions = zone_score * ZONE_CAPTURE_FACTOR
            business_area_sessions = business_area_score * BUSINESS_AREA_CAPTURE_FACTOR
            poi_sessions = poi_score * POI_CAPTURE_FACTOR * scenario_factor
            district_sessions = district_score * DISTRICT_NODE_CAPTURE_FACTOR * scenario_factor
            competitor_signal_sessions = min(
                competitor_signal_raw * HEATMAP_MAX_COMPETITOR_SIGNAL_SHARE,
                max(zone_sessions + business_area_sessions + poi_sessions + district_sessions, competitor_signal_raw * 0.35),
            )
            supportive_context_sessions = zone_sessions + business_area_sessions + poi_sessions
            if mode != "urban":
                supportive_context_sessions += district_sessions
            evidence_context_sessions = supportive_context_sessions + competitor_signal_sessions

            if evidence_context_sessions < min_context:
                lon += lon_step
                continue

            if not _heatmap_supports_candidate(
                top_pois=poi_contributions,
                top_zones=zone_contributions,
                top_business_areas=business_area_contributions,
                top_districts=district_contributions,
                top_competitors=competitor_contributions,
                mode=mode,
            ):
                lon += lon_step
                continue

            location_type = _location_type_for_heat(
                poi_contributions,
                business_area_contributions,
                district_contributions,
            )
            estimate = demand.estimate(lat, lon, year, location_type=location_type)
            model_sessions = estimate["charging_sessions_per_day"] * scenario_factor
            if location_type == "highway":
                model_sessions *= _highway_support_multiplier(
                    top_pois=poi_contributions,
                    top_business_areas=business_area_contributions,
                    top_districts=district_contributions,
                    top_competitors=competitor_contributions,
                    poi_score=poi_sessions,
                    business_area_score=business_area_sessions,
                    district_score=district_sessions,
                    competitor_signal_score=competitor_signal_sessions,
                )
            demand_score = model_sessions + supportive_context_sessions
            competition_score = competitor_signal_sessions
            net_opportunity_score = max(demand_score - competition_score, 0.0)
            heat_score = net_opportunity_score

            if heat_score < min_heat:
                lon += lon_step
                continue

            avg_kwh_per_session = _average_kwh_per_session_for_heat(location_type)

            points.append({
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "location_type": location_type,
                "aadt_used": estimate["aadt_used"],
                "model_sessions": round(model_sessions, 1),
                "poi_score": round(poi_sessions, 1),
                "zone_score": round(zone_sessions, 1),
                "business_area_score": round(business_area_sessions, 1),
                "district_score": round(district_sessions, 1),
                "competitor_signal_score": round(competitor_signal_sessions, 1),
                "competition_score": round(competition_score, 1),
                "supportive_context_score": round(supportive_context_sessions, 1),
                "context_score": round(evidence_context_sessions, 1),
                "evidence_context_score": round(evidence_context_sessions, 1),
                "demand_score": round(demand_score, 1),
                "net_opportunity_score": round(net_opportunity_score, 1),
                "heat_score": round(heat_score, 1),
                "avg_kwh_per_session": round(avg_kwh_per_session, 1),
                "daily_kwh_equivalent": round(net_opportunity_score * avg_kwh_per_session, 1),
                "daily_kwh": round(net_opportunity_score * avg_kwh_per_session, 1),
                "zones": [item["name"] for item in zone_contributions[:3]],
                "business_areas": [item["name"] for item in business_area_contributions[:3]],
                "pois": [item["name"] for item in poi_contributions[:3]],
                "districts": [item["name"] for item in district_contributions[:3]],
                "district_name": (
                    district_contributions[0]["district_name"] if district_contributions else None
                ),
                "competitors": [item["name"] for item in competitor_contributions[:3]],
            })
            lon += lon_step
        lat += lat_step

    layer_max_scores = {
        layer: max((p[field] for p in points), default=1.0)
        for layer, field in HEATMAP_LAYER_SCORE_FIELDS.items()
    }
    max_heat = layer_max_scores["net"]
    for point in points:
        point["intensity_layers"] = {
            layer: round(point[field] / max(layer_max_scores[layer], 0.1), 4)
            for layer, field in HEATMAP_LAYER_SCORE_FIELDS.items()
        }
        point["intensity"] = point["intensity_layers"]["net"]

    points = _suppress_isolated_heat_points(
        points,
        lat_step=lat_step,
        lon_step=lon_step,
        mode=mode,
    )
    layer_max_scores = {
        layer: max((p[field] for p in points), default=1.0)
        for layer, field in HEATMAP_LAYER_SCORE_FIELDS.items()
    }
    max_heat = layer_max_scores["net"]
    for point in points:
        point["intensity_layers"] = {
            layer: round(point[field] / max(layer_max_scores[layer], 0.1), 4)
            for layer, field in HEATMAP_LAYER_SCORE_FIELDS.items()
        }
        point["intensity"] = point["intensity_layers"]["net"]

    district_summaries: list[dict[str, Any]] = []
    if mode == "district":
        district_node_lookup = {
            str(node.get("district_name") or ""): node
            for node in district_nodes
            if node.get("district_name")
        }
        district_max_heat: dict[str, float] = {}
        for point in points:
            district_name = point.get("district_name")
            if district_name:
                district_max_heat[district_name] = max(
                    district_max_heat.get(district_name, 0.0),
                    point["heat_score"],
                )

        province_district_max = max(district_max_heat.values(), default=1.0)
        for point in points:
            district_name = point.get("district_name")
            local_max = district_max_heat.get(district_name, point["heat_score"])
            district_potential = local_max / province_district_max
            local_intensity = point["heat_score"] / max(local_max, 0.1)
            point["district_potential"] = round(district_potential, 4)
            point["local_intensity"] = round(local_intensity, 4)
            point["display_intensity"] = round(
                local_intensity * (0.55 + 0.45 * district_potential),
                4,
            )

        for district_name, district_heat in sorted(
            district_max_heat.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            node = district_node_lookup.get(district_name, {})
            district_summaries.append({
                "district_name": district_name,
                "name": node.get("name") or district_name,
                "lat": _float_or_none(node.get("lat")),
                "lon": _float_or_none(node.get("lon")),
                "node_type": node.get("node_type"),
                "population": node.get("population"),
                "max_heat_score": round(district_heat, 1),
                "potential_score": round(district_heat / province_district_max, 4),
            })
    else:
        for point in points:
            point["display_intensity"] = point["intensity"]

    return {
        "province": province,
        "year": year,
        "scenario": scenario,
        "mode": mode,
        "resolution_km": resolution_km,
        "lat_step_deg": round(lat_step, 6),
        "lon_step_deg": round(lon_step, 6),
        "bounds": {key: round(value, 6) for key, value in bounds.items()},
        "point_count": len(points),
        "max_heat_score": round(max_heat, 1),
        "max_scores": {layer: round(value, 1) for layer, value in layer_max_scores.items()},
        "default_layer": "demand",
        "points": points,
        "zones": zones,
        "metadata": {
            "poi_count": len(pois),
            "zone_count": len(zones),
            "business_area_count": len(business_areas),
            "heatmap_exclusion_count": len(exclusions),
            "competitor_count": len(competitors),
            "district_node_count": len(district_nodes),
            "heatmap_mode": mode,
            "score_semantics": "screening_score_not_direct_forecast",
            "station_calibration": station_calibration_summary(),
            "urban_mask": "district_poi_zone_competitor" if mode in {"community", "district"} else "poi_zone_competitor",
            "normalization": "within_district_weighted_by_province_potential" if mode == "district" else "province_max",
        },
        "district_summaries": district_summaries,
    }


def generate_chiang_mai_heatmap(
    year: int = 2030,
    scenario: Literal["conservative", "base", "upside"] = "base",
    resolution_km: float = 1.0,
    mode: Literal["urban", "community", "district"] = "urban",
) -> dict[str, Any]:
    """Backward-compatible wrapper for the Chiang Mai heat map."""
    return generate_province_heatmap(
        province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48",
        year=year,
        scenario=scenario,
        resolution_km=resolution_km,
        mode=mode,
    )
