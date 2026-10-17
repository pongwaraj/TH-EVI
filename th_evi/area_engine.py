"""Shared fixed-support area screening and optional explicit energy allocation.

Display cells aggregate the same one-kilometre support; a click reads a cell,
not another forecast. Missing behaviour leaves physical outputs unavailable.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from math import ceil, floor, fsum, isfinite

from .charging_energy import allocate_energy_budget
from .competition import dc_competition_pressure
from .charging_profiles import configured_spatial_budget, profile_for_province
from .constants import canonical_province_name


METHOD = "fixed_support_area_v1"
SUPPORT_KM = 1.0


def use_pilot(province: str, method: str = "auto") -> bool:
    if method not in {"auto", "pilot", "legacy"}:
        raise ValueError("method must be auto, pilot or legacy")
    return method == "pilot" or (method == "auto" and bool((profile_for_province(province) or {}).get("spatial_pilot_enabled")))


def allocate_support(points: list[dict], competitors: list[dict], *, energy_kwh=None, coverage_fraction=None) -> dict:
    """POI evidence changes allocation weights, never the total input budget."""
    physical = energy_kwh is not None
    if physical and coverage_fraction is None:
        raise ValueError("Physical allocation requires an explicit spatial coverage fraction")
    weights = {}
    for index, point in enumerate(points):
        # These are legacy spatial proxies ONLY; never generate a physical budget.
        context = [max(0, point.get(k, 0)) for k in ("zone_score", "business_area_score", "poi_score")]
        primary = max(context, default=0)
        weights[str(index)] = max(0, point.get("model_sessions", 0)) + primary + 0.35 * (fsum(context) - primary) + max(0, point.get("district_score", 0))
    has_weights = fsum(weights.values()) > 0
    budget = float(energy_kwh) if physical else 100.0
    coverage = float(coverage_fraction) if physical else (1.0 if has_weights else 0.0)
    allocated = allocate_energy_budget(energy_kwh=budget, destination_weights=weights, coverage_fraction=coverage)
    output = []
    for point, assignment in zip(points, allocated["allocations"]):
        pressure = dc_competition_pressure(point["lat"], point["lon"], competitors)
        gross = assignment["assigned_kwh"]
        competition = gross * pressure["competition_share"]
        available = gross - competition
        row = deepcopy(point)
        row["support_id"] = str(len(output))
        row.update({
            "demand_score": gross, "competition_score": competition,
            "net_opportunity_score": available, "heat_score": available,
            "competition_evidence": pressure,
            "competition_score_bounds": [gross * share for share in pressure["competition_share_missing_data_bounds"]],
            "net_opportunity_score_bounds": [gross * (1 - share) for share in reversed(pressure["competition_share_missing_data_bounds"])],
        })
        # Never manufacture kWh/day or charging events from normalized scores.
        row.update(daily_kwh=None, daily_kwh_equivalent=None, avg_kwh_per_session=None,
                   model_sessions=None, forecast_available=False, score_semantics=(
                       "allocated_connector_kwh_not_site_forecast" if physical else "normalized_screening_share_percent"))
        row.update(area_gross_connector_kwh=gross if physical else None,
                   area_available_connector_kwh=available if physical else None)
        output.append(row)
    return {
        "points": output,
        "accounting": {
            "unit": "connector_kwh_per_day" if physical else "screening_share_percent",
            "input_budget": budget, "gross_allocated": allocated["allocated_kwh"],
            "competition_pressure_allocation": fsum(p["competition_score"] for p in output),
            "available_allocation": fsum(p["net_opportunity_score"] for p in output),
            "outside_coverage": allocated["outside_coverage_kwh"], "unserved": allocated["unserved_kwh"],
            "balance_error": allocated["balance_error_kwh"],
            "competition_balance_error": allocated["allocated_kwh"] - fsum(
                p["competition_score"] + p["net_opportunity_score"] for p in output),
            "energy_budget_enforced": physical,
            "competitor_sales_observed": False,
        },
    }


def aggregate_support(points: list[dict], lat_step: float, lon_step: float, resolution_km: float) -> list[dict]:
    """Area-overlap aggregation preserves mass even for non-integer resolutions.

    Fragments retain the original support mask when a large display cell spans
    a hole. Clients must draw fragments, not its enclosing display rectangle.
    """
    if not isfinite(resolution_km) or not 0.25 <= resolution_km <= 5:
        raise ValueError("Pilot resolution_km must be between 0.25 and 5")
    dy, dx = lat_step * resolution_km, lon_step * resolution_km
    cells = {}
    for source in points:
        south, north = source["lat"] - lat_step / 2, source["lat"] + lat_step / 2
        west, east = source["lon"] - lon_step / 2, source["lon"] + lon_step / 2
        for i in range(floor(south / dy), ceil(north / dy)):
            for j in range(floor(west / dx), ceil(east / dx)):
                s, n = max(south, i * dy), min(north, (i + 1) * dy)
                w, e = max(west, j * dx), min(east, (j + 1) * dx)
                fraction = max(0, n - s) * max(0, e - w) / (lat_step * lon_step)
                if fraction < 1e-12:
                    continue
                key = (i, j)
                if key not in cells:
                    row = {k: deepcopy(v) for k, v in source.items() if k != "competition_evidence"}
                    row.update(cell_id=f"{i}:{j}", lat=(i + 0.5) * dy, lon=(j + 0.5) * dx,
                               demand_score=0.0, competition_score=0.0, net_opportunity_score=0.0,
                               competition_score_bounds=[0.0, 0.0], net_opportunity_score_bounds=[0.0, 0.0],
                               coverage_fragments=[], support_area_km2=0.0, evidence_by_station={}, support_ids=set())
                    cells[key] = row
                row = cells[key]
                for field in ("demand_score", "competition_score", "net_opportunity_score"):
                    row[field] += source[field] * fraction
                for field in ("competition_score_bounds", "net_opportunity_score_bounds"):
                    for index in (0, 1):
                        row[field][index] += source[field][index] * fraction
                row["support_area_km2"] += fraction
                row["coverage_fragments"].append([[s, w], [n, e]])
                row["support_ids"].add(source["support_id"])
                for item in source["competition_evidence"]["contributions"]:
                    previous = row["evidence_by_station"].get(item["station_id"])
                    if previous is None or item["distance_km"] < previous["distance_km"]:
                        row["evidence_by_station"][item["station_id"]] = item
    output = []
    for row in cells.values():
        row["support_ids"] = sorted(row["support_ids"])
        if not any(s <= row["lat"] < n and w <= row["lon"] < e
                   for ((s, w), (n, e)) in row["coverage_fragments"]):
            ((s, w), (n, e)) = row["coverage_fragments"][0]
            row["lat"], row["lon"] = (s + n) / 2, (w + e) / 2
        row["lat"], row["lon"] = round(row["lat"], 7), round(row["lon"], 7)
        for field in ("demand_score", "competition_score", "net_opportunity_score"):
            row[field] = round(row[field], 12)
        row["heat_score"] = row["net_opportunity_score"]
        if row["score_semantics"] == "allocated_connector_kwh_not_site_forecast":
            row["area_gross_connector_kwh"] = row["demand_score"]
            row["area_available_connector_kwh"] = row["net_opportunity_score"]
        row["top_competitors"] = sorted(row.pop("evidence_by_station").values(), key=lambda p: p["pressure"], reverse=True)
        row["competition_unknown_count"] = sum(
            item["public_active"] and item["charging_type"] != "ac" and (
                not item["direct_dc_eligible"] or item["guns"] is None
            ) for item in row["top_competitors"]
        )
        row["top_competitors"] = row["top_competitors"][:5]
        output.append(row)
    return sorted(output, key=lambda p: (p["lat"], p["lon"]))


@lru_cache(maxsize=12)
def fixed_surface(province: str, year: int, scenario: str, mode: str) -> dict:
    from .heatmap import generate_province_heatmap
    from .spatial import load_competitors_for_province

    # Preserve the audited activity/water exclusion mask. Legacy values supply
    # relative evidence only; their session units are not carried into forecasts.
    support = generate_province_heatmap(province, year, scenario, SUPPORT_KM, mode, method="legacy")
    # Reconstruct coherent cell centers from the fixed origin; legacy JSON
    # rounds each coordinate separately, leaving sub-metre gaps/overlaps.
    dy, dx = support["lat_step_deg"], support["lon_step_deg"]
    a, b = support["bounds"]["lat_min"], support["bounds"]["lon_min"]
    source_points = []
    for row in support["points"]:
        row = dict(row)
        row["lat"] = a + round((row["lat"] - a) / dy) * dy
        row["lon"] = b + round((row["lon"] - b) / dx) * dx
        source_points.append(row)
    competitors = load_competitors_for_province(province, include_nationwide_kml=False)
    budget = configured_spatial_budget(province, year)
    surface = allocate_support(source_points, competitors,
                               energy_kwh=budget["connector_kwh"] if budget else None,
                               coverage_fraction=budget["coverage_fraction"] if budget else None)
    surface["physical_basis"] = budget
    surface.update(lat_step_deg=support["lat_step_deg"], lon_step_deg=support["lon_step_deg"],
                   bounds=support["bounds"], zones=support["zones"], source_metadata=support["metadata"])
    return surface


@lru_cache(maxsize=12)
def generate_area_surface(province: str, year: int, scenario: str, resolution_km: float, mode: str) -> dict:
    canonical = canonical_province_name(province)
    fixed = fixed_surface(canonical, year, scenario, mode)
    points = aggregate_support(fixed["points"], fixed["lat_step_deg"], fixed["lon_step_deg"], resolution_km)
    fields = {"demand": "demand_score", "competition": "competition_score", "net": "net_opportunity_score"}
    maxima = {layer: max((p[field] for p in points), default=0) for layer, field in fields.items()}
    density_max = {layer: max((p[field] for p in fixed["points"]), default=1) for layer, field in fields.items()}
    for point in points:
        point["intensity_layers"] = {
            layer: min(1.0, point[field] / max(point["support_area_km2"], 1e-12) / max(density_max[layer], 1e-12))
            for layer, field in fields.items()
        }
        point["intensity"] = point["display_intensity"] = point["intensity_layers"]["net"]
    physical = fixed["accounting"]["energy_budget_enforced"]
    metadata = {**fixed["source_metadata"], "production_method": METHOD,
                "score_semantics": "allocated_connector_kwh_not_site_forecast" if physical else "normalized_screening_share_percent", "forecast_available": False,
                "energy_budget_enforced": physical, "fixed_support_km": SUPPORT_KM,
                "accounting": fixed["accounting"], "competition_method": "dc_relative_pressure_v1_not_sales",
                "physical_basis": fixed.get("physical_basis"),
                "uncertainty_semantics": "missing_data_envelope_not_prediction_interval",
                "density_max_scores": density_max,
                "normalization": "fixed_support_density", "spatial_weights": "legacy_proxies_not_travel_model"}
    districts = {}
    if mode == "district":
        for point in fixed["points"]:
            name = point.get("district_name")
            if not name:
                continue
            group = districts.setdefault(name, [])
            group.append(point)
    summaries = [{"district_name": name, "name": name,
                  "lat": fsum(p["lat"] for p in rows) / len(rows),
                  "lon": fsum(p["lon"] for p in rows) / len(rows),
                  "heat_score": max(p["net_opportunity_score"] for p in rows),
                  "point_count": len(rows),
                  "demand_score": fsum(p["demand_score"] for p in rows),
                  "net_opportunity_score": fsum(p["net_opportunity_score"] for p in rows)}
                 for name, rows in districts.items()]
    summaries.sort(key=lambda p: p["demand_score"], reverse=True)
    return {"province": province, "year": year, "scenario": scenario, "mode": mode,
            "resolution_km": resolution_km, "lat_step_deg": fixed["lat_step_deg"] * resolution_km,
            "lon_step_deg": fixed["lon_step_deg"] * resolution_km,
            "bounds": fixed["bounds"], "point_count": len(points), "points": points,
            "max_scores": maxima, "max_heat_score": maxima["net"], "default_layer": "demand",
            "zones": fixed["zones"], "district_summaries": summaries, "metadata": metadata}


def heatmap_transport(surface: dict) -> dict:
    """Compact the wire format; keep the cached calculation and click unchanged."""
    if surface.get("metadata", {}).get("production_method") != METHOD:
        return surface
    evidence = {}
    for point in fixed_surface(canonical_province_name(surface["province"]), surface["year"], surface["scenario"], surface["mode"])["points"]:
        evidence[point["support_id"]] = {key: point.get(key, []) for key in ("pois", "zones", "business_areas", "districts")}
    fields = ("lat", "lon", "cell_id", "demand_score", "competition_score", "net_opportunity_score", "support_ids")
    points = []
    for row in surface["points"]:
        point = {field: row[field] for field in fields}
        if row["competition_unknown_count"]:
            point["competition_unknown_count"] = row["competition_unknown_count"]
        if abs(row["support_area_km2"] - surface["resolution_km"] ** 2) > 1e-8:
            point["coverage_fragments"] = row["coverage_fragments"]
            point["support_area_km2"] = row["support_area_km2"]
        points.append(point)
    return {**surface, "points": points, "support_evidence": evidence}


def analyze_area_cell(lat: float, lon: float, province: str, year: int, scenario: str, mode: str, resolution_km: float) -> dict:
    if not (isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid click coordinates")
    surface = generate_area_surface(province, year, scenario, resolution_km, mode)
    dy, dx = surface["lat_step_deg"], surface["lon_step_deg"]
    cell_id = f"{floor(lat / dy)}:{floor(lon / dx)}"
    cell = next((p for p in surface["points"] if p["cell_id"] == cell_id and any(
        s <= lat < n and w <= lon < e for ((s, w), (n, e)) in p["coverage_fragments"]
    )), None)
    result = deepcopy(cell) if cell else {
        "cell_id": cell_id, "demand_score": 0.0, "competition_score": 0.0,
        "net_opportunity_score": 0.0, "top_competitors": [], "daily_kwh": None,
    }
    result.update(lat=lat, lon=lon, province=province, year=year, scenario=scenario, mode=mode,
                  resolution_km=resolution_km, method=METHOD, forecast_available=False,
                  score_semantics=surface["metadata"]["score_semantics"],
                  gross_area_demand_sessions=None, competitor_penalty_sessions=None,
                  net_sessions_per_day=None, daily_revenue=None,
                  eligibility_status="screening_only" if cell else "outside_support",
                  confidence="not_validated", warnings=[
                      "Area screening share is not customers/day, competitor sales or a site forecast.",
                      "Travel behaviour, incoming travel and station choice are not calibrated.",
                  ], metadata=surface["metadata"])
    if cell and cell["competition_unknown_count"]:
        result["warnings"].append("Some nearby stations have unconfirmed DC type, power or connector counts; competition can be understated.")
    return result


def clear_caches():
    fixed_surface.cache_clear()
    generate_area_surface.cache_clear()
