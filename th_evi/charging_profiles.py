"""Behaviour input readiness for the shared charging-energy model."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from math import fsum, isclose, isfinite

from .charging_energy import ChargingWindow, TravelCohort, calculate_daily_energy_budget
from .constants import canonical_province_name
from .data import get_evhub_dlt_fleet


PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "charging_behavior_profiles.json"
ROOT = PROFILE_PATH.parent.parent
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
        "travel_soc_preview": {"available": True, "endpoint": "/api/charging-demand/travel-preview",
                               "calibrated": False, "heatmap_integration_enabled": False},
        "pilot_evidence": pilot_evidence_status(profile),
        "dc_session_energy": dc_session_energy_status(canonical),
        "next_required_layers": ["representative_travel_soc_evidence_and_calibration", "incoming_travel_without_double_counting",
                                 "fixed_spatial_allocation_and_outside_option", "station_choice_and_capacity",
                                 "station_time_holdout_validation"],
    }


def pilot_evidence_status(profile: dict | None) -> dict:
    """Expose provenance without treating partial pilot evidence as calibrated inputs."""
    if not profile:
        return {"available": False, "forecast_enabled": False, "sources": {}}
    sources = {}
    for name, relative in profile.get("pilot_evidence", {}).items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            sources[name] = {"available": False, "status": "missing_evidence_file"}
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sources[name] = {"available": False, "status": "invalid_evidence_file"}
            continue
        if canonical_province_name(payload.get("province", "")) != profile["province"]:
            sources[name] = {"available": False, "status": "province_mismatch"}
            continue
        sources[name] = {"available": True, "status": "pilot_evidence_not_calibrated",
                         "file": relative, "forecast_enabled": False}
    return {"available": bool(sources) and all(s["available"] for s in sources.values()),
            "forecast_enabled": False, "sources": sources}


def load_pilot_evidence(province: str, name: str) -> dict | None:
    """Load versioned evidence without borrowing it across provinces."""
    profile = profile_for_province(province)
    if not profile:
        return None
    relative = profile.get("pilot_evidence", {}).get(name)
    if not relative:
        return None
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if canonical_province_name(payload.get("province", "")) != profile["province"]:
        return None
    return payload


def _resolve_dc_session_energy(province: str, requested_kwh: float | None = None) -> dict:
    """Resolve an explicit override or an audited province-local order-size reference.

    This divisor changes event equivalents, not the energy budget or visit capture.
    Other behavioural inputs remain required independently.
    """
    if requested_kwh is not None:
        if (isinstance(requested_kwh, bool) or not isinstance(requested_kwh, (int, float))
                or not isfinite(requested_kwh) or requested_kwh <= 0):
            raise ValueError("Session energy override must be finite and positive")
        return {"average_session_kwh": requested_kwh, "source": "caller_override",
                "scope": "caller_specified", "forecast_validated": False}
    profile = profile_for_province(province) or {}
    if profile.get("average_dc_session_kwh") is None:
        raise ValueError("No province-local session energy reference; supply an explicit session energy")
    evidence = load_pilot_evidence(province, "dc_session_energy")
    if not evidence:
        raise ValueError("Configured session energy evidence is missing or invalid")
    if (evidence.get("definition") != "Normal; duration >= 300 seconds AND connector energy >= 1 kWh"
            or evidence.get("aggregation") != "sum_connector_kwh_divided_by_sum_meaningful_orders"):
        raise ValueError("Session energy evidence requires comparable meaningful orders")
    stations = evidence.get("stations", [])
    ids = [row["station_id"] for row in stations]
    if not ids or not all(ids) or len(set(ids)) != len(ids):
        raise ValueError("Session energy evidence requires unique station samples")
    for row in stations:
        count, kwh = row["meaningful_orders"], row["connector_kwh"]
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("Session energy order counts must be positive integers")
        if isinstance(kwh, bool) or not isinstance(kwh, (int, float)) or not isfinite(kwh) or kwh <= 0:
            raise ValueError("Session energy totals must be finite and positive")
    count = sum(row["meaningful_orders"] for row in stations)
    kwh = fsum(row["connector_kwh"] for row in stations)
    mean = kwh / count
    for actual, stored in ((count, evidence["pooled_meaningful_orders"]),
                           (kwh, evidence["pooled_connector_kwh"]),
                           (mean, evidence["pooled_mean_connector_kwh"])):
        if not isclose(actual, stored, rel_tol=1e-10, abs_tol=1e-8):
            raise ValueError("Session energy pooled totals do not reconcile")
    default = evidence["default_session_kwh"]
    if (evidence.get("rounding") != "nearest_whole_kwh" or default != round(mean)
            or default != profile["average_dc_session_kwh"] or default <= 0):
        raise ValueError("Session energy profile and rounded evidence do not reconcile")
    relative = profile["pilot_evidence"]["dc_session_energy"]
    if profile.get("evidence", {}).get("energy_per_session") != relative:
        raise ValueError("Session energy provenance does not match the profile")
    return {"average_session_kwh": default, "source": "province_observed_dc_orders",
            "scope": evidence["scope"], "evidence_file": relative,
            "evidence_sha256": profile_fingerprint(evidence), "stations": stations,
            "pooled_orders": count, "pooled_connector_kwh": kwh, "pooled_mean_kwh": mean,
            "forecast_validated": False, "limitations": evidence["limitations"]}


def resolve_dc_session_energy(province: str, requested_kwh: float | None = None) -> dict:
    """Fail closed with a validation error if bundled evidence is malformed."""
    try:
        return _resolve_dc_session_energy(province, requested_kwh)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Configured session energy evidence has an invalid schema") from exc


def dc_session_energy_status(province: str) -> dict:
    try:
        return {"available": True, **resolve_dc_session_energy(province)}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {"available": False, "reason": str(exc), "forecast_validated": False}
