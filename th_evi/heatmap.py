"""Heat-map generation for Chiang Mai charging demand."""

from __future__ import annotations

import csv
from functools import lru_cache
from math import cos, radians, sqrt
from pathlib import Path
from typing import Literal

from .location import LocationDemandModel


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HOT_ZONES_PATH = DATA_DIR / "hot_zones_chiang_mai.csv"

CHIANG_MAI_BOUNDS = {
    "lat_min": 18.62,
    "lat_max": 18.94,
    "lon_min": 98.86,
    "lon_max": 99.13,
}

VALID_HEATMAP_SCENARIOS = {"conservative", "base", "upside"}


def _km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat_km = (lat1 - lat2) * 111.0
    lon_km = (lon1 - lon2) * 111.0 * cos(radians((lat1 + lat2) / 2))
    return sqrt(lat_km * lat_km + lon_km * lon_km)


@lru_cache(maxsize=1)
def load_hot_zones() -> list[dict]:
    """Load curated Chiang Mai hot zones from CSV."""
    if not HOT_ZONES_PATH.exists():
        return []
    with HOT_ZONES_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in [
            "center_lat",
            "center_lon",
            "radius_km",
            "heat_rank",
            "demand_pool_conservative",
            "demand_pool_base",
            "demand_pool_upside",
        ]:
            row[key] = float(row[key])
        row["heat_rank"] = int(row["heat_rank"])
    return rows


def _zone_influence(lat: float, lon: float, scenario: str) -> tuple[float, list[str]]:
    """Return additive hot-zone influence and the influencing zone names."""
    score = 0.0
    zones = []
    scenario_key = f"demand_pool_{scenario}"
    for zone in load_hot_zones():
        distance = _km_between(lat, lon, zone["center_lat"], zone["center_lon"])
        radius = max(zone["radius_km"], 0.1)
        if distance > radius * 1.8:
            continue
        weight = max(0.0, 1.0 - distance / (radius * 1.8)) ** 2
        score += zone[scenario_key] * weight
        if distance <= radius:
            zones.append(zone["name"])
    return score, zones[:3]


def _classify_grid_location(lat: float, lon: float) -> str:
    if 18.770 <= lat <= 18.810 and 98.960 <= lon <= 99.010:
        return "city_center"
    if any(_km_between(lat, lon, z["center_lat"], z["center_lon"]) <= z["radius_km"] for z in load_hot_zones()):
        return "destination"
    return "suburban"


def generate_chiang_mai_heatmap(
    year: int = 2030,
    scenario: Literal["conservative", "base", "upside"] = "base",
    resolution_km: float = 1.0,
) -> dict:
    """Generate an area-demand heat map for Chiang Mai.

    The heat score combines model-estimated charging sessions at grid points
    with curated hot-zone demand pools. It is intended for screening and map
    visualization, not final site-level capture.
    """
    if scenario not in VALID_HEATMAP_SCENARIOS:
        raise ValueError(f"scenario must be one of {sorted(VALID_HEATMAP_SCENARIOS)}")
    if resolution_km <= 0 or resolution_km > 5:
        raise ValueError("resolution_km must be in (0, 5]")

    lat_step = resolution_km / 111.0
    mid_lat = (CHIANG_MAI_BOUNDS["lat_min"] + CHIANG_MAI_BOUNDS["lat_max"]) / 2
    lon_step = resolution_km / (111.0 * cos(radians(mid_lat)))
    scenario_factor = {"conservative": 0.75, "base": 1.0, "upside": 1.25}[scenario]

    demand = LocationDemandModel(province="เชียงใหม่")
    points = []
    lat = CHIANG_MAI_BOUNDS["lat_min"]
    while lat <= CHIANG_MAI_BOUNDS["lat_max"] + 1e-9:
        lon = CHIANG_MAI_BOUNDS["lon_min"]
        while lon <= CHIANG_MAI_BOUNDS["lon_max"] + 1e-9:
            loc_type = _classify_grid_location(lat, lon)
            estimate = demand.estimate(lat, lon, year, location_type=loc_type)
            model_sessions = estimate["charging_sessions_per_day"] * scenario_factor
            zone_score, zones = _zone_influence(lat, lon, scenario)
            heat_score = model_sessions + zone_score
            if heat_score > 0.5:
                points.append({
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "location_type": loc_type,
                    "aadt_used": estimate["aadt_used"],
                    "model_sessions": round(model_sessions, 1),
                    "zone_score": round(zone_score, 1),
                    "heat_score": round(heat_score, 1),
                    "daily_kwh": round(heat_score * 24.0, 1),
                    "zones": zones,
                })
            lon += lon_step
        lat += lat_step

    max_heat = max((p["heat_score"] for p in points), default=1.0)
    for point in points:
        point["intensity"] = round(point["heat_score"] / max_heat, 4)

    return {
        "year": year,
        "scenario": scenario,
        "resolution_km": resolution_km,
        "bounds": CHIANG_MAI_BOUNDS,
        "point_count": len(points),
        "max_heat_score": round(max_heat, 1),
        "points": points,
        "zones": load_hot_zones(),
    }
