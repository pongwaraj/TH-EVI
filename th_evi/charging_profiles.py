"""Behaviour input readiness for the shared charging-energy model."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from .charging_energy import ChargingWindow, TravelCohort, calculate_daily_energy_budget
from .constants import canonical_province_name
from .data import get_evhub_dlt_fleet


PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "charging_behavior_profiles.json"
BEHAVIOUR_FIELDS = ("cohorts", "average_dc_session_kwh", "dc_vehicle_efficiency", "dc_station_efficiency")
EVIDENCE_FIELDS = ("travel_distance", "charging_access_and_dwell", "energy_per_session", "charging_efficiencies")


def profile_for_province(province: str) -> dict | None:
    registry = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    canonical = canonical_province_name(province)
    return next((p for p in registry["profiles"] if p["province"] == canonical), None)


def profile_fingerprint(profile: dict) -> str:
    payload = json.dumps(profile, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def observed_bev_fleet(province: str) -> dict | None:
    row = get_evhub_dlt_fleet(canonical_province_name(province))
    if row is None:
        return None
    return {
        "province": str(row["province"]),
        "source_month": str(row["source_month"]),
        "vehicle_segment": str(row["vehicle_segment"]),
        "bev": int(row["bev"]),
        "total_vehicles": int(row["total_vehicles"]),
        "source_file": str(row["source_file"]),
        "source_type": "DLT_observed_registration_stock",
    }


def energy_budget_from_profile(profile: dict, fleet: dict) -> dict:
    cohorts = []
    for row in profile["cohorts"]:
        values = dict(row)
        for window in ("home", "work", "public_ac"):
            values[window] = ChargingWindow(**values[window])
        cohorts.append(TravelCohort(**values))
    return calculate_daily_energy_budget(
        bev_fleet=fleet["bev"], cohorts=cohorts,
        **{key: profile[key] for key in BEHAVIOUR_FIELDS if key != "cohorts"},
    )


def configured_spatial_budget(province: str, year: int) -> dict | None:
    """Only explicitly enabled, evidenced, same-year inputs may supply kWh.

    No extrapolation from a registration snapshot into a future forecast.
    Coverage must reconcile the fleet's travel with this spatial support.
    """
    profile = profile_for_province(province) or {}
    if not profile.get("spatial_energy_enabled"):
        return None
    if any(not profile.get("evidence", {}).get(key) for key in EVIDENCE_FIELDS):
        raise ValueError("Enabled spatial energy requires complete behavioural evidence")
    coverage = profile.get("spatial_coverage_fraction")
    if coverage is None:
        raise ValueError("Enabled spatial energy requires an explicit coverage fraction")
    fleet = observed_bev_fleet(province)
    if fleet is None:
        raise ValueError("Enabled spatial energy requires observed DLT fleet")
    stock_year = int(fleet["source_month"].split("-")[0])
    stock_year = stock_year - 543 if stock_year > 2400 else stock_year
    if year != stock_year:
        return None
    try:
        result = energy_budget_from_profile(profile, fleet)
    except (KeyError, TypeError) as exc:
        raise ValueError("Enabled spatial energy has incomplete behavioural inputs") from exc
    return {"connector_kwh": result["public_dc_connector_kwh"], "coverage_fraction": coverage,
            "observed_fleet": fleet, "energy_balance": result,
            "validation_status": "not_validated_for_station_forecasting"}


def charging_basis_status(province: str) -> dict:
    canonical = canonical_province_name(province)
    profile = profile_for_province(canonical)
    fleet = observed_bev_fleet(canonical)
    missing = []
    if fleet is None:
        missing.append("observed_bev_fleet")
    missing.extend(key for key in BEHAVIOUR_FIELDS if not (profile or {}).get(key))
    evidence = (profile or {}).get("evidence", {})
    missing.extend(f"evidence.{key}" for key in EVIDENCE_FIELDS if not evidence.get(key))
    errors = []
    if fleet is not None and not any(key in missing for key in BEHAVIOUR_FIELDS):
        try:
            energy_budget_from_profile(profile, fleet)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            errors.append(str(exc))
    return {
        "province": canonical,
        "pilot_configured": profile is not None,
        "profile_sha256": profile_fingerprint(profile) if profile else None,
        "profile_runtime_source": "bundled_versioned_profile",
        "status": ("not_configured" if profile is None else "invalid_inputs" if errors
                   else "inputs_required" if missing else "inputs_supplied"),
        "observed_fleet": fleet,
        "missing_energy_inputs": missing,
        "input_errors": errors,
        "production_method": "fixed_support_area_v1" if (profile or {}).get("spatial_pilot_enabled") else "legacy_spatial_screening",
        "energy_budget_enforced_in_heatmap": False,
        "validation_status": "not_validated_for_station_forecasting",
        "next_required_layers": ["trip_and_soc_feasibility", "incoming_travel_without_double_counting",
                                 "fixed_spatial_allocation_and_outside_option", "station_choice_and_capacity",
                                 "station_time_holdout_validation"],
    }
