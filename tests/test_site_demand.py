from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from th_evi.api import app
from th_evi.site_demand import (
    ProposedStation, daily_observations, demand_time_holdout,
    preview_site_demand, site_reference_status, transfer_site_demand,
)


ROOT = Path(__file__).resolve().parents[1]


def observations():
    return {"start_date": "2026-07-01", "end_date": "2026-09-30",
            "connector_kwh_per_calendar_day": 1000}


def station(**changes):
    values = dict(guns=1, total_site_kw=120, max_kw_per_gun=120,
                  operating_hours=24, availability=1, mean_active_kw=60,
                  plug_overhead_minutes=0, demand_in_open_hours_share=1)
    return ProposedStation(**{**values, **changes})


def run(**changes):
    values = dict(lat=18.8, lon=99, year=2026,
                  points=[{"lat": 18.8, "lon": 99, "demand_score": 100}],
                  competitors=[{"station_id": "reference", "name": "Reference",
                                "lat": 18.8, "lon": 99, "guns": 1, "max_kw": 120,
                                "connector_summary": "DC CCS2"}],
                  reference_station_id="reference", observation=observations(), station=station(),
                  average_session_kwh=20, kernel_radius_km=3, outside_option_weight=1,
                  scenarios=[{"name": "base", "relative_access_attractiveness": 1, "market_multiplier": 1}])
    return transfer_site_demand(**{**values, **changes})


def test_calendar_days_and_order_energy_use_the_same_observed_period():
    evidence = json.loads((ROOT / "data/chiang_mai_operations_behavior_2026q3.json").read_text())
    result = daily_observations(evidence)
    assert result["calendar_days"] == 92
    assert result["meaningful_orders_per_calendar_day"] == pytest.approx(3147 / 92)
    assert result["connector_kwh_per_calendar_day"] == pytest.approx(86285.97 / 92)
    assert result["unique_vehicles_available"] is False
    evidence["meaningful_orders"]["mean_connector_kwh"] = 35
    with pytest.raises(ValueError, match="reconcile"):
        daily_observations(evidence)


def test_time_holdout_predicts_demand_not_just_energy_given_known_order_count():
    evidence = json.loads((ROOT / "data/chiang_mai_operations_behavior_2026q3.json").read_text())
    holdout = json.loads((ROOT / "data/chiang_mai_operations_holdout_2026q3.json").read_text())
    result = demand_time_holdout(evidence, holdout)
    assert result["train_days"] == 62
    assert result["holdout_days"] == 30
    assert result["connector_kwh"]["predicted_holdout_total"] == pytest.approx(54553.11 / 62 * 30)
    assert result["meaningful_orders"]["predicted_holdout_total"] == pytest.approx(1941 / 62 * 30)
    assert result["meaningful_orders"]["observed_holdout_total"] == 1206
    assert result["connector_kwh"]["absolute_percentage_error"] > 0.16
    assert result["meaningful_orders"]["absolute_percentage_error"] > 0.22
    assert result["new_site_validation_available"] is False
    holdout["holdout"]["range"]["from"] = "2026-08-31T16:59:59Z"
    with pytest.raises(ValueError, match="partition"):
        demand_time_holdout(evidence, holdout)


def test_reference_station_reconstruction_and_after_entry_accounting():
    result = run()
    row = result["scenarios"][0]
    account = row["accounting"]
    assert result["reference_model_share_before_entry"] == 0.5
    assert result["calibration_reconstruction_connector_kwh_per_day"] == 1000
    assert account["inferred_choice_pool_connector_kwh_per_day"] == 2000
    assert row["site_served_connector_kwh_per_day"] == pytest.approx(2000 / 3)
    assert account["existing_stations_after"] == pytest.approx(2000 / 3)
    assert account["outside_after"] == pytest.approx(2000 / 3)
    assert account["shifted_from_existing_stations"] + account["shifted_from_outside"] == pytest.approx(
        row["site_choice_connector_kwh_per_day"])
    assert account["balance_error"] == pytest.approx(0)
    assert result["unique_vehicles_per_day"] is None
    assert result["estimate_available"] is True
    assert result["forecast_available"] is False
    assert row["estimated_charging_visits_per_day"] == pytest.approx(
        row["site_served_connector_kwh_per_day"] / 20)
    assert row["potential_charging_visits_per_day"] == pytest.approx(
        row["estimated_charging_visits_per_day"] + row["unserved_charging_visits_per_day"])
    assert result["visit_counting_basis"] == "one_charging_event_per_vehicle_visit_not_unique_daily_vehicles"


def test_support_weight_units_and_display_splitting_cannot_create_demand():
    original = run()["scenarios"]
    split = run(points=[{"lat": 18.8, "lon": 99, "demand_score": n} for n in (1, 1, 2)])
    assert split["scenarios"][0]["site_served_connector_kwh_per_day"] == pytest.approx(
        original[0]["site_served_connector_kwh_per_day"])


def test_larger_charger_changes_capture_but_not_the_reference_scaled_pool():
    small, large = run(), run(station=station(guns=4, total_site_kw=720, max_kw_per_gun=180))
    a, b = small["scenarios"][0], large["scenarios"][0]
    assert a["accounting"]["inferred_choice_pool_connector_kwh_per_day"] == b["accounting"]["inferred_choice_pool_connector_kwh_per_day"]
    assert b["site_choice_connector_kwh_per_day"] > a["site_choice_connector_kwh_per_day"]
    assert b["accounting"]["balance_error"] == pytest.approx(0)


def test_selected_session_energy_changes_equivalents_not_unconstrained_energy():
    a, b = run(), run(average_session_kwh=35)
    x, y = a["scenarios"][0], b["scenarios"][0]
    assert x["site_choice_connector_kwh_per_day"] == y["site_choice_connector_kwh_per_day"]
    assert x["charging_event_equivalents_per_day"] * 20 == pytest.approx(y["charging_event_equivalents_per_day"] * 35)


def test_closed_access_gives_zero_and_capacity_overflow_stays_unserved():
    zero = run(scenarios=[{"name": "closed", "relative_access_attractiveness": 0, "market_multiplier": 1}])
    assert zero["scenarios"][0]["site_served_connector_kwh_per_day"] == 0
    limited = run(station=station(total_site_kw=30, max_kw_per_gun=30, mean_active_kw=20,
                                 operating_hours=1, plug_overhead_minutes=10))
    row = limited["scenarios"][0]
    assert row["capacity_limited"]
    assert row["site_served_connector_kwh_per_day"] <= 30
    assert row["accounting"]["capacity_unserved"] > 0
    assert row["unserved_charging_visits_per_day"] > 0
    assert row["estimated_charging_visits_per_day"] < row["potential_charging_visits_per_day"]
    assert row["accounting"]["balance_error"] == pytest.approx(0)


def test_opening_demand_and_outages_affect_capture_even_when_capacity_does_not_bind():
    full = run()["scenarios"][0]
    partial = run(station=station(operating_hours=12, availability=0.8,
                                 demand_in_open_hours_share=0.5))["scenarios"][0]
    assert partial["site_choice_connector_kwh_per_day"] == pytest.approx(
        full["site_choice_connector_kwh_per_day"] * 0.5 * 0.8)
    assert partial["accounting"]["balance_error"] == pytest.approx(0)
    with pytest.raises(ValueError, match="24-hour"):
        station(demand_in_open_hours_share=0.5)


def test_unknown_competitor_is_disclosed_without_imputed_power():
    base = {"station_id": "reference", "lat": 18.8, "lon": 99,
            "guns": 1, "max_kw": 120, "connector_summary": "DC CCS2"}
    unknown = {"station_id": "unknown", "lat": 18.8, "lon": 99, "connector_summary": "DC CCS2"}
    result = run(competitors=[base, unknown])
    assert result["missing_competitor_evidence"][0]["max_kw"] is None
    assert result["missing_competitor_evidence"][0]["station_id"] == "unknown"
    assert result["scenarios"][0]["site_choice_connector_kwh_per_day"] == run()["scenarios"][0]["site_choice_connector_kwh_per_day"]
    with pytest.raises(ValueError, match="unique"):
        run(competitors=[base, deepcopy(base)])


@pytest.mark.parametrize("change", [
    {"year": 2030}, {"lat": float("nan")}, {"average_session_kwh": 0},
    {"outside_option_weight": 0}, {"kernel_radius_km": float("inf")},
    {"reference_station_id": "missing"}, {"points": []},
])
def test_unsupported_or_non_finite_inputs_cannot_produce_numeric_estimates(change):
    with pytest.raises(ValueError):
        run(**change)


def test_other_provinces_do_not_borrow_chiang_mai_reference():
    assert site_reference_status("Chiang Mai")["available"] is True
    assert site_reference_status("Chiang Rai")["available"] is False


def test_api_requires_survey_and_choice_assumptions_instead_of_defaults(monkeypatch):
    client = TestClient(app)
    payload = {"province": "Chiang Mai", "lat": 18.829376, "lon": 99.005497, "year": 2026,
               "station": vars(station()), "average_session_kwh": 35, "kernel_radius_km": 3,
               "outside_option_weight": 1, "scenarios": [
                   {"name": "base", "relative_access_attractiveness": 0.75, "market_multiplier": 1}],
               "public_access_assumed": True}
    import th_evi.api as api
    monkeypatch.setattr(api, "preview_site_demand", lambda **values: run(station=values["station"]))
    response = client.post("/api/charging-demand/site-preview", json=payload)
    assert response.status_code == 200
    assert response.json()["forecast_available"] is False
    del payload["outside_option_weight"]
    assert client.post("/api/charging-demand/site-preview", json=payload).status_code == 422


def test_api_surfaces_new_site_validation_separately_from_order_energy_holdout():
    result = TestClient(app).get("/api/charging-demand/site-reference", params={"province": "Chiang Mai"})
    assert result.status_code == 200
    assert result.json()["daily_demand_holdout"]["new_site_validation_available"] is False
    basis = TestClient(app).get("/api/charging-demand/basis", params={"province": "Chiang Mai"}).json()
    assert basis["site_demand_preview"]["available"] is True
    assert basis["site_demand_preview"]["forecast_available"] is False


def test_shared_preview_excludes_legacy_traffic_session_scale_and_checks_support(monkeypatch):
    from th_evi import area_engine, spatial
    point = {"lat": 18.8, "lon": 99, "demand_score": 100,
             "zone_score": 0, "business_area_score": 0, "poi_score": 5, "model_sessions": 1000000}
    monkeypatch.setattr(area_engine, "fixed_surface", lambda *args: {
        "points": [point], "lat_step_deg": 0.01, "lon_step_deg": 0.01})
    monkeypatch.setattr(spatial, "load_competitors_for_province", lambda *args, **kwargs: [
        {"station_id": "tce_ev_meta_mall", "lat": 18.8, "lon": 99,
         "connector_summary": "DC CCS2", "max_kw": 120, "guns": 1}])
    args = dict(province="Chiang Mai", lat=18.8, lon=99, year=2026, station=station(),
                average_session_kwh=35, kernel_radius_km=3, outside_option_weight=1,
                scenarios=[{"name": "base", "relative_access_attractiveness": 1, "market_multiplier": 1}],
                public_access_assumed=True)
    before = preview_site_demand(**args)
    defaulted = preview_site_demand(**{**args, "average_session_kwh": None})
    assert defaulted["assumptions"]["average_session_kwh"] == 27
    assert defaulted["session_energy_basis"]["source"] == "province_observed_dc_orders"
    assert before["session_energy_basis"]["source"] == "caller_override"
    for old, new in zip(before["scenarios"], defaulted["scenarios"]):
        assert old["site_choice_connector_kwh_per_day"] == new["site_choice_connector_kwh_per_day"]
        assert old["site_served_connector_kwh_per_day"] == new["site_served_connector_kwh_per_day"]
        assert old["charging_event_equivalents_per_day"] * 35 == pytest.approx(
            new["charging_event_equivalents_per_day"] * 27)
    payload = {**args, "station": vars(args["station"])}
    del payload["average_session_kwh"]
    response = TestClient(app).post("/api/charging-demand/site-preview", json=payload)
    assert response.status_code == 200
    assert response.json()["assumptions"]["average_session_kwh"] == 27
    assert response.json()["session_energy_basis"]["pooled_orders"] == 3218
    point.update(model_sessions=999999999, demand_score=0.00001)
    after = preview_site_demand(**args)
    assert before["scenarios"] == after["scenarios"]
    assert after["heatmap_changed"] is False
    assert after["spatial_weight_method"] == "public_dc_poi_hierarchy_v2_activity_only"
    with pytest.raises(ValueError, match="outside"):
        preview_site_demand(**{**args, "lat": 20})
    with pytest.raises(ValueError, match="publicly accessible"):
        preview_site_demand(**{**args, "public_access_assumed": False})
