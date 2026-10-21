"""Observed-station transfer for explicit new-site planning scenarios.

One station anchors the scale, not the accuracy of the spatial choice model.
No fleet energy, AADT conversion, unique vehicles or unseen-site validation is
inferred. Heat-map screening scores keep their existing meaning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import fsum, isclose

from .charging_energy import _number
from .charging_profiles import (load_pilot_evidence, profile_for_province,
                                resolve_dc_session_energy, dc_session_energy_status)
from .competition import dc_competition_pressure
from .constants import canonical_province_name
from .poi_policy import POI_POLICY_VERSION, screening_weight


def _positive(name, value, maximum=None):
    _number(name, value, 0, maximum)
    if value == 0:
        raise ValueError(f"{name} must be greater than zero")


def _period(period):
    """Count inclusive Bangkok calendar days, including a millisecond end-of-day."""
    local = timezone(timedelta(hours=7))
    values = []
    for key in ("from", "to"):
        raw = str(period[key])
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if len(raw) > 10 and dt.tzinfo is None:
            raise ValueError("Timestamp periods must include a time zone")
        values.append(dt.astimezone(local).date() if dt.tzinfo else dt.date())
    start, end = values
    if end < start:
        raise ValueError("Observation period must be ordered")
    return start, end, (end - start).days + 1


def daily_observations(evidence):
    start, end, days = _period(evidence["range"])
    orders = evidence["meaningful_orders"]
    count, kwh = orders["count"], orders["connector_kwh"]
    _positive("meaningful_order_count", count)
    if not isinstance(count, int) or isinstance(count, bool):
        raise ValueError("meaningful_order_count must be an integer")
    _positive("observed_connector_kwh", kwh)
    mean = kwh / count
    if not isclose(mean, orders["mean_connector_kwh"], rel_tol=1e-6):
        raise ValueError("Observed order energy does not reconcile with totals")
    return {"start_date": start.isoformat(), "end_date": end.isoformat(),
            "calendar_days": days, "meaningful_orders": count,
            "connector_kwh": kwh, "meaningful_orders_per_calendar_day": count / days,
            "connector_kwh_per_calendar_day": kwh / days,
            "mean_connector_kwh_per_order": mean,
            "unique_vehicles_available": False,
            "uptime_and_import_completeness_verified": False}


def demand_time_holdout(evidence, holdout):
    """Predict held-out *daily demand* with the preceding period's mean only."""
    train, test = holdout["train"], holdout["holdout"]
    a, b, train_days = _period(train["range"])
    c, d, test_days = _period(test["range"])
    first, last, _ = _period(evidence["range"])
    if a != first or d != last or c != b + timedelta(days=1):
        raise ValueError("Train and holdout must be consecutive and partition the observation period")
    for field, total in (("meaningful_orders", evidence["meaningful_orders"]["count"]),
                         ("connector_kwh", evidence["meaningful_orders"]["connector_kwh"])):
        _positive(f"train.{field}", train[field])
        _positive(f"holdout.{field}", test[field])
        if not isclose(train[field] + test[field], total, rel_tol=1e-8):
            raise ValueError("Train and holdout totals must reconcile with observations")

    def metric(field):
        predicted = train[field] / train_days * test_days
        actual = test[field]
        return {"predicted_holdout_total": predicted, "observed_holdout_total": actual,
                "predicted_per_day": predicted / test_days, "observed_per_day": actual / test_days,
                "signed_error": predicted - actual,
                "absolute_percentage_error": abs(predicted - actual) / actual}

    return {"method": "preceding_period_daily_mean_baseline", "train_days": train_days,
            "holdout_days": test_days, "connector_kwh": metric("connector_kwh"),
            "meaningful_orders": metric("meaningful_orders"),
            "scope": "one_station_one_period_not_new_site_validation",
            "daily_mae_available": False, "new_site_validation_available": False}


def reference_evidence(province):
    profile = profile_for_province(province) or {}
    config = profile.get("site_demand_reference")
    if not config:
        raise ValueError("No observed site-demand reference configured for this province")
    evidence = load_pilot_evidence(province, config["observations_key"])
    holdout = load_pilot_evidence(province, config["holdout_key"])
    if not evidence or not holdout:
        raise ValueError("Observed site-demand reference files are missing")
    if any(row.get("station_scope") != config["station_scope"] for row in (evidence, holdout)):
        raise ValueError("Observed station identity does not match the configured reference")
    summary = daily_observations(evidence)
    validation = demand_time_holdout(evidence, holdout)
    return config, evidence, summary, validation


def site_reference_status(province):
    canonical = canonical_province_name(province)
    try:
        config, evidence, summary, validation = reference_evidence(canonical)
    except (KeyError, TypeError, ValueError) as exc:
        return {"available": False, "province": canonical, "reason": str(exc),
                "forecast_available": False}
    return {"available": True, "province": canonical, "reference_station_id": config["station_id"],
            "reference_station_scope": evidence["station_scope"], "observations": summary,
            "daily_demand_holdout": validation, "forecast_available": False,
            "dc_session_energy": dc_session_energy_status(canonical),
            "status": "conditional_reference_transfer_available",
            "required_inputs": ["station_spec", "operating_hours", "availability", "mean_active_kw",
                                "plug_overhead_minutes", "demand_in_open_hours_share", "kernel_radius_km",
                                "outside_option_weight", "scenarios", "public_access_assumed"]}


@dataclass(frozen=True)
class ProposedStation:
    guns: int
    total_site_kw: float
    max_kw_per_gun: float
    operating_hours: float
    availability: float
    mean_active_kw: float
    plug_overhead_minutes: float
    demand_in_open_hours_share: float

    def __post_init__(self):
        if isinstance(self.guns, bool) or not isinstance(self.guns, int) or not 1 <= self.guns <= 100:
            raise ValueError("guns must be an integer from 1 to 100")
        for key in ("total_site_kw", "max_kw_per_gun", "mean_active_kw"):
            _positive(key, getattr(self, key))
        _positive("operating_hours", self.operating_hours, 24)
        _positive("availability", self.availability, 1)
        _number("plug_overhead_minutes", self.plug_overhead_minutes, 0, 120)
        _number("demand_in_open_hours_share", self.demand_in_open_hours_share, 0, 1)
        if self.operating_hours == 24 and self.demand_in_open_hours_share != 1:
            raise ValueError("A 24-hour station must cover the full demand time profile")
        if self.mean_active_kw > min(self.max_kw_per_gun, self.total_site_kw):
            raise ValueError("mean_active_kw must not exceed gun or site power")

    def connector_capacity(self, session_kwh):
        hours = self.operating_hours * self.availability
        minutes = session_kwh / self.mean_active_kw * 60 + self.plug_overhead_minutes
        return min(self.total_site_kw * hours, self.guns * hours * 60 / minutes * session_kwh)


def transfer_site_demand(*, lat, lon, year, points, competitors, reference_station_id,
                         observation, station, average_session_kwh, kernel_radius_km,
                         outside_option_weight, scenarios):
    """Normalize entry choice over a fixed pool anchored by one observed station.

    POI/support values affect relative distribution only. The inferred pool is
    conditional on that distribution and choice parameters, not provincial kWh.
    Capacity overflow stays unserved rather than creating competitor sales.
    """
    _number("lat", lat, -90, 90)
    _number("lon", lon, -180, 180)
    _positive("average_session_kwh", average_session_kwh)
    _positive("kernel_radius_km", kernel_radius_km, 10)
    _positive("outside_option_weight", outside_option_weight, 100)
    if not isinstance(station, ProposedStation):
        raise ValueError("An explicit ProposedStation is required")
    if isinstance(year, bool) or not isinstance(year, int) or any(
        int(observation[key][:4]) != year for key in ("start_date", "end_date")
    ):
        raise ValueError("Reference transfer is only available for the observed calendar year")
    _positive("observed_connector_kwh_per_day", observation["connector_kwh_per_calendar_day"])
    if not 1 <= len(scenarios) <= 10:
        raise ValueError("Provide one to ten explicit scenarios")
    labels = set()
    for case in scenarios:
        name = case.get("name", "")
        if not isinstance(name, str) or not name.strip() or name in labels:
            raise ValueError("Scenario names must be nonempty and unique")
        labels.add(name)
        _number("relative_access_attractiveness", case["relative_access_attractiveness"], 0, 2)
        _number("market_multiplier", case["market_multiplier"], 0, 3)
    ids = [row.get("station_id") or row.get("name") for row in competitors]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Competitor station IDs must be present and unique")
    if reference_station_id not in ids:
        raise ValueError("Observed reference station is missing from the province inventory")
    weights = []
    for point in points:
        _number("demand_score", point["demand_score"])
        weights.append(point["demand_score"])
    total_weight = fsum(weights)
    _positive("support_weight_sum", total_weight)
    candidate = {"station_id": "proposed_site", "lat": lat, "lon": lon,
                 "max_kw": station.max_kw_per_gun, "guns": station.guns,
                 "connector_summary": "DC CCS2"}
    choice_rows, unknowns = [], {}
    reference_share = 0.0
    for point, weight in zip(points, weights):
        pressure = dc_competition_pressure(point["lat"], point["lon"], competitors, kernel_radius_km)
        candidate_pressure = dc_competition_pressure(point["lat"], point["lon"], [candidate], kernel_radius_km)["pressure"]
        reference = next((row for row in pressure["contributions"] if row["station_id"] == reference_station_id), None)
        ref_utility = reference["pressure"] if reference else 0
        normalized = weight / total_weight
        denom = outside_option_weight + pressure["pressure"]
        reference_share += normalized * ref_utility / denom
        # Missing data in either station catchment may change the transfer ratio.
        if candidate_pressure > 0 or ref_utility > 0:
            for row in pressure["contributions"]:
                if row["station_id"] in pressure["unknown_station_ids"]:
                    unknowns[row["station_id"]] = {k: row.get(k) for k in
                                                  ("station_id", "name", "charging_type", "max_kw", "guns", "power_evidence")}
        choice_rows.append((normalized, pressure["pressure"], candidate_pressure))
    _positive("reference_model_share", reference_share)
    inferred_pool = observation["connector_kwh_per_calendar_day"] / reference_share
    capacity = station.connector_capacity(average_session_kwh)
    results = []
    for case in scenarios:
        pool = inferred_pool * case["market_multiplier"]
        online_share = station.demand_in_open_hours_share * station.availability
        before_existing, before_outside, after_existing, after_outside, captured = [], [], [], [], []
        for weight, existing, new in choice_rows:
            before = outside_option_weight + existing
            new *= case["relative_access_attractiveness"]
            after = before + new
            amount = pool * weight
            before_existing.append(amount * existing / before)
            before_outside.append(amount * outside_option_weight / before)
            after_existing.append(amount * ((1 - online_share) * existing / before + online_share * existing / after))
            after_outside.append(amount * ((1 - online_share) * outside_option_weight / before + online_share * outside_option_weight / after))
            captured.append(amount * online_share * new / after)
        demand = fsum(captured)
        served = min(demand, capacity)
        unserved = demand - served
        existing_before, outside_before = fsum(before_existing), fsum(before_outside)
        existing_after, outside_after = fsum(after_existing), fsum(after_outside)
        balance = pool - fsum((existing_after, outside_after, served, unserved))
        if not isclose(balance, 0, abs_tol=1e-6):
            raise ValueError("Site entry energy accounting does not close")
        results.append({"name": case["name"], "assumptions": dict(case),
                        "site_choice_connector_kwh_per_day": demand,
                        "site_served_connector_kwh_per_day": served,
                        "charging_event_equivalents_per_day": served / average_session_kwh,
                        "estimated_charging_visits_per_day": served / average_session_kwh,
                        "potential_charging_visits_per_day": demand / average_session_kwh,
                        "unserved_charging_visits_per_day": unserved / average_session_kwh,
                        "capacity_limited": demand > capacity,
                        "accounting": {"inferred_choice_pool_connector_kwh_per_day": pool,
                                       "existing_stations_before": existing_before,
                                       "outside_before": outside_before,
                                       "existing_stations_after": existing_after,
                                       "outside_after": outside_after,
                                       "proposed_station_served": served,
                                       "capacity_unserved": unserved,
                                       "shifted_from_existing_stations": existing_before - existing_after,
                                       "shifted_from_outside": outside_before - outside_after,
                                       "balance_error": balance}})
    return {"method": "observed_station_transfer_v1", "status": "conditional_estimate_not_validated",
            "estimate_available": True, "forecast_available": False,
            "new_site_validation_available": False, "unique_vehicles_per_day": None,
            "unit": "charging_event_equivalents_not_unique_vehicles",
            "visit_counting_basis": "one_charging_event_per_vehicle_visit_not_unique_daily_vehicles",
            "uncertainty_semantics": "input_sensitivity_not_prediction_interval",
            "reference_station_id": reference_station_id, "observations": observation,
            "reference_model_share_before_entry": reference_share,
            "calibration_reconstruction_connector_kwh_per_day": inferred_pool * reference_share,
            "pool_semantics": "reference_scaled_choice_pool_not_observed_provincial_energy",
            "capacity_connector_kwh_per_day": capacity,
            "capacity_semantics": "throughput_cap_under_explicit_inputs_not_queue_simulation",
            "assumptions": {"kernel_radius_km": kernel_radius_km, "outside_option_weight": outside_option_weight,
                            "average_session_kwh": average_session_kwh, "station": dict(vars(station))},
            "missing_competitor_evidence": list(unknowns.values()),
            "skipped_competitors_without_coordinates": dc_competition_pressure(
                lat, lon, competitors, kernel_radius_km)["skipped_without_coordinates"],
            "scenarios": results,
            "limitations": ["One reference station; no validation of new-site visit counts or station choice.",
                            "Observation rates use calendar days, without verified uptime/import completeness.",
                            "Spatial weights and distance decay are proxies, not measured travel or frontage traffic.",
                            "Unknown competitor power/type/heads are disclosed; resulting market shares remain conditional.",
                            "Charging-event equivalents are not unique vehicles; session energy is explicit.",
                            "Demand timing within opening hours is explicit; availability uses an independent outage scenario.",
                            "Public access, relative site attractiveness and market multipliers are scenario assumptions."]}


def preview_site_demand(*, province, lat, lon, year, station, average_session_kwh=None,
                        kernel_radius_km, outside_option_weight, scenarios, public_access_assumed):
    from .area_engine import fixed_surface
    from .spatial import load_competitors_for_province

    if public_access_assumed is not True:
        raise ValueError("Site transfer requires an explicitly publicly accessible candidate scenario")
    canonical = canonical_province_name(province)
    session_energy = resolve_dc_session_energy(canonical, average_session_kwh)
    average_session_kwh = session_energy["average_session_kwh"]
    config, evidence, observation, validation = reference_evidence(canonical)
    if any(int(observation[key][:4]) != year for key in ("start_date", "end_date")):
        raise ValueError("Reference transfer is only available for the observed calendar year")
    surface = fixed_surface(canonical, year, "base", "urban")
    dy, dx = surface["lat_step_deg"], surface["lon_step_deg"]
    if not any(p["lat"] - dy / 2 <= lat < p["lat"] + dy / 2 and
               p["lon"] - dx / 2 <= lon < p["lon"] + dx / 2 for p in surface["points"]):
        raise ValueError("Candidate is outside the audited activity support")
    # Keep the fixed mask, but exclude legacy traffic/session defaults from
    # transfer weights. Activity proxies describe relative location only.
    points = []
    for point in surface["points"]:
        activity = screening_weight(
            model_prior=0, poi_score=point.get("poi_score", 0),
            zone_score=point.get("zone_score", 0),
            business_area_score=point.get("business_area_score", 0),
            district_score=point.get("district_score", 0),
        )
        points.append({"lat": point["lat"], "lon": point["lon"],
                       "demand_score": activity["weight"]})
    result = transfer_site_demand(
        lat=lat, lon=lon, year=year, points=points,
        competitors=load_competitors_for_province(canonical, include_nationwide_kml=False),
        reference_station_id=config["station_id"], observation=observation,
        station=station, average_session_kwh=average_session_kwh,
        kernel_radius_km=kernel_radius_km, outside_option_weight=outside_option_weight,
        scenarios=scenarios,
    )
    result.update(province=canonical, lat=lat, lon=lon, year=year, heatmap_changed=False,
                  session_energy_basis=session_energy,
                  public_access_assumed=True, daily_demand_holdout=validation,
                  spatial_weight_method=POI_POLICY_VERSION + "_activity_only",
                  evidence_sha256=sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest())
    return result
