"""Province-level heat-map generation for EV charging demand."""

from __future__ import annotations

from math import cos, exp, radians
from typing import Any, Literal

from .location import LocationDemandModel
from .spatial import (
    POI_CAPTURE_FACTOR,
    SCENARIO_FACTORS,
    ZONE_CAPTURE_FACTOR,
    competitor_penalty_field,
    km_between,
    load_competitors_for_province,
    load_enriched_district_nodes,
    load_hot_zones_for_province,
    load_pois_for_province,
    poi_attraction_field,
    zone_influence_field,
)


VALID_HEATMAP_SCENARIOS = {"conservative", "base", "upside"}
VALID_HEATMAP_MODES = {"urban", "community"}
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

DISTRICT_NODE_RULES: dict[str, tuple[float, float, str]] = {
    "district_center": (18.0, 3.6, "destination"),
    "transport_junction": (18.0, 4.0, "highway"),
    "tourism_town": (17.0, 3.5, "destination"),
    "district_mall": (18.0, 3.2, "destination"),
    "industrial_town": (18.0, 3.4, "destination"),
    "border_town": (22.0, 4.4, "highway"),
    "coverage_anchor": (14.0, 3.2, "suburban"),
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
    top_districts: list[dict[str, Any]],
) -> str:
    categories = {item.get("category") for item in top_pois[:3]}
    if {"transport_corridor", "border_crossing"} & categories:
        return "highway"
    if "city_center" in categories:
        return "city_center"
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
    competitors: list[dict[str, Any]],
    district_nodes: list[dict[str, Any]],
    resolution_km: float,
) -> dict[str, float]:
    anchors = _iter_anchor_points(pois, zones, competitors, district_nodes)
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
        distance = km_between(lat, lon, node_lat, node_lon)
        if distance > radius * COMMUNITY_DISTANCE_FACTOR:
            continue

        weight = exp(-((distance / max(radius, 0.1)) ** 2))
        sessions = base_sessions * confidence * weight
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
            "suggested_location_type": suggested_location_type,
        })

    contributions.sort(key=lambda item: item["sessions"], reverse=True)
    return round(total, 1), contributions


def _heatmap_thresholds(mode: str) -> tuple[float, float]:
    if mode == "community":
        return COMMUNITY_MIN_CONTEXT_SESSIONS, COMMUNITY_MIN_HEAT_SCORE
    return URBAN_MIN_CONTEXT_SESSIONS, URBAN_MIN_HEAT_SCORE


def _heatmap_mask_passes(
    *,
    lat: float,
    lon: float,
    context_sessions: float,
    heat_score: float,
    pois: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    district_nodes: list[dict[str, Any]],
    mode: str,
) -> bool:
    min_context, min_heat = _heatmap_thresholds(mode)
    if context_sessions < min_context or heat_score < min_heat:
        return False

    nearest_poi = _nearest_row_distance_km(lat, lon, pois)
    nearest_zone_ratio = _nearest_zone_ratio(lat, lon, zones)
    nearest_competitor = _nearest_row_distance_km(lat, lon, competitors)
    nearest_district = _nearest_row_distance_km(lat, lon, district_nodes)

    near_poi = nearest_poi is not None and nearest_poi <= HEATMAP_MAX_POI_DISTANCE_KM
    near_zone = nearest_zone_ratio is not None and nearest_zone_ratio <= HEATMAP_MAX_ZONE_DISTANCE_FACTOR
    near_competitor = (
        nearest_competitor is not None and nearest_competitor <= HEATMAP_MAX_COMPETITOR_DISTANCE_KM
    )
    near_district = nearest_district is not None and nearest_district <= HEATMAP_MAX_ANCHOR_DISTANCE_KM
    near_any_anchor = near_poi or near_zone or near_competitor or near_district

    if mode == "community":
        return near_any_anchor and (near_district or near_poi or near_zone)
    return near_any_anchor and (near_poi or near_zone or near_competitor)


def generate_province_heatmap(
    province: str,
    year: int = 2030,
    scenario: Literal["conservative", "base", "upside"] = "base",
    resolution_km: float = 1.0,
    mode: Literal["urban", "community"] = "urban",
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
    competitors = load_competitors_for_province(province)
    district_nodes = load_enriched_district_nodes(province)
    bounds = _province_bounds(pois, zones, competitors, district_nodes, resolution_km)
    scenario_factor = SCENARIO_FACTORS.get(scenario, 1.0)

    lat_step = resolution_km / 111.0
    mid_lat = (bounds["lat_min"] + bounds["lat_max"]) / 2
    lon_step = resolution_km / (111.0 * max(0.2, cos(radians(mid_lat))))

    demand = LocationDemandModel(province=province)
    points = []
    lat = bounds["lat_min"]
    while lat <= bounds["lat_max"] + 1e-9:
        lon = bounds["lon_min"]
        while lon <= bounds["lon_max"] + 1e-9:
            zone_score, zone_contributions = zone_influence_field(lat, lon, zones, scenario=scenario)
            poi_score, poi_contributions = poi_attraction_field(lat, lon, pois)
            district_score, district_contributions = district_node_field(lat, lon, district_nodes)
            competitor_signal_raw, competitor_contributions, _ = competitor_penalty_field(
                lat,
                lon,
                competitors,
            )

            zone_sessions = zone_score * ZONE_CAPTURE_FACTOR
            poi_sessions = poi_score * POI_CAPTURE_FACTOR * scenario_factor
            district_sessions = district_score * DISTRICT_NODE_CAPTURE_FACTOR * scenario_factor
            competitor_signal_sessions = min(
                competitor_signal_raw * HEATMAP_MAX_COMPETITOR_SIGNAL_SHARE,
                max(zone_sessions + poi_sessions + district_sessions, competitor_signal_raw * 0.35),
            )
            if mode == "urban":
                context_sessions = zone_sessions + poi_sessions + competitor_signal_sessions
            else:
                context_sessions = zone_sessions + poi_sessions + district_sessions + competitor_signal_sessions

            location_type = _location_type_for_heat(poi_contributions, district_contributions)
            estimate = demand.estimate(lat, lon, year, location_type=location_type)
            model_sessions = estimate["charging_sessions_per_day"] * scenario_factor
            heat_score = model_sessions + context_sessions

            if _heatmap_mask_passes(
                lat=lat,
                lon=lon,
                context_sessions=context_sessions,
                heat_score=heat_score,
                pois=pois,
                zones=zones,
                competitors=competitors,
                district_nodes=district_nodes,
                mode=mode,
            ):
                points.append({
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "location_type": location_type,
                    "aadt_used": estimate["aadt_used"],
                    "model_sessions": round(model_sessions, 1),
                    "poi_score": round(poi_sessions, 1),
                    "zone_score": round(zone_sessions, 1),
                    "district_score": round(district_sessions, 1),
                    "competitor_signal_score": round(competitor_signal_sessions, 1),
                    "context_score": round(context_sessions, 1),
                    "heat_score": round(heat_score, 1),
                    "daily_kwh": round(heat_score * 24.0, 1),
                    "zones": [item["name"] for item in zone_contributions[:3]],
                    "pois": [item["name"] for item in poi_contributions[:3]],
                    "districts": [item["name"] for item in district_contributions[:3]],
                    "competitors": [item["name"] for item in competitor_contributions[:3]],
                })
            lon += lon_step
        lat += lat_step

    max_heat = max((p["heat_score"] for p in points), default=1.0)
    for point in points:
        point["intensity"] = round(point["heat_score"] / max_heat, 4)

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
        "points": points,
        "zones": zones,
        "metadata": {
            "poi_count": len(pois),
            "zone_count": len(zones),
            "competitor_count": len(competitors),
            "district_node_count": len(district_nodes),
            "heatmap_mode": mode,
            "urban_mask": "district_poi_zone_competitor" if mode == "community" else "poi_zone_competitor",
        },
    }


def generate_chiang_mai_heatmap(
    year: int = 2030,
    scenario: Literal["conservative", "base", "upside"] = "base",
    resolution_km: float = 1.0,
    mode: Literal["urban", "community"] = "urban",
) -> dict[str, Any]:
    """Backward-compatible wrapper for the Chiang Mai heat map."""
    return generate_province_heatmap(
        province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48",
        year=year,
        scenario=scenario,
        resolution_km=resolution_km,
        mode=mode,
    )
