import json
from math import isclose
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from scripts.validate_operations_energy import validate_mean_order_energy
from th_evi.api import app
from th_evi.charging_evidence import normalized_route_preview


ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def request_payload():
    return {"province": "Chiang Mai", "origin_id": "ornsirin_11",
            "destination_id": "thapae_gate", "outings_per_week": 5,
            "battery_kwh_per_km": 0.18, "home_access_share": 0.6,
            "home_energy_share_if_access": 0.8,
            "other_ac_share_of_remaining": 0.1,
            "dc_share_of_remaining": 0.7, "dc_vehicle_efficiency": 0.92}


def test_route_preview_conserves_energy_and_is_not_site_forecast():
    result = normalized_route_preview(**request_payload())
    assert result["route"]["round_trip_road_km"] == pytest.approx(30.5, abs=0.1)
    assert result["weekly_traction_battery_kwh_per_vehicle"] == pytest.approx(
        result["route"]["round_trip_road_km"] * 5 * 0.18)
    rows = result["home_access_sensitivity"]
    assert [row["case"] for row in rows] == [
        "lower_home_access", "input_home_access", "higher_home_access"]
    assert rows[0]["public_dc_connector_kwh"] > rows[1]["public_dc_connector_kwh"] > rows[2]["public_dc_connector_kwh"]
    for row in rows:
        assert isclose(sum(row[key] for key in (
            "home_battery_kwh", "other_ac_battery_kwh", "public_dc_battery_kwh",
            "unassigned_battery_kwh")), result["weekly_traction_battery_kwh_per_vehicle"], abs_tol=1e-8)
        assert row["balance_error_kwh"] == pytest.approx(0, abs=1e-8)
    assert result["housing_reference"]["ev_owner_housing_mix_known"] is False
    assert result["housing_reference"]["private_home_ac_rates_known"] is False
    assert result["forecast_enabled"] is False
    assert result["heatmap_changed"] is False
    assert result["session_energy_reference"]["station_demand_holdout_ready"] is False


def test_route_api_shows_only_province_evidence_and_rejects_missing_inputs():
    catalog = client.get("/api/charging-demand/route-evidence", params={"province": "Chiang Mai"})
    assert catalog.status_code == 200
    assert len(catalog.json()["routes"]) == 29
    assert catalog.json()["forecast_enabled"] is False
    assert client.get("/api/charging-demand/route-evidence", params={"province": "Chiang Rai"}).status_code == 404
    assert client.post("/api/charging-demand/evidence-preview", json=request_payload()).status_code == 200
    invalid = request_payload()
    invalid.pop("home_access_share")
    assert client.post("/api/charging-demand/evidence-preview", json=invalid).status_code == 422
    invalid = request_payload()
    invalid["province"] = "Chiang Rai"
    assert client.post("/api/charging-demand/evidence-preview", json=invalid).status_code == 422
    invalid = request_payload()
    invalid["destination_id"] = "unknown"
    assert client.post("/api/charging-demand/evidence-preview", json=invalid).status_code == 422


def test_temporal_holdout_records_conditional_error_only():
    full = {"averages": {"fullMonths": ["2026-07", "2026-08"], "excludedMonths": []},
            "range": {"from": "2026-06-30T17:00:00Z", "to": "2026-08-31T16:59:59Z"},
            "kpis": {"reportSessions": 1941, "reportKwh": 54553.11}}
    held = {"averages": {"fullMonths": ["2026-09"], "excludedMonths": []},
            "range": {"from": "2026-08-31T17:00:00Z", "to": "2026-09-30T16:59:59Z"},
            "kpis": {"reportSessions": 1206, "reportKwh": 31732.86}}
    result = validate_mean_order_energy(full, held)
    saved = json.loads((ROOT / "data/chiang_mai_operations_holdout_2026q3.json").read_text())
    assert result["train"]["mean_connector_kwh_per_order"] == pytest.approx(
        saved["train"]["mean_connector_kwh_per_order"])
    assert result["holdout"]["mean_connector_kwh_per_order"] == pytest.approx(26.31249, rel=1e-5)
    assert result["prediction_using_train_mean"]["absolute_percentage_error"] == pytest.approx(0.06815, rel=1e-4)
    assert result["prediction_using_train_mean"]["absolute_percentage_error"] < result[
        "illustrative_35_kwh_per_order_comparator"]["absolute_percentage_error"]
    assert result["forecast_enabled"] is False
    assert result["stations_in_evaluation"] == 1
    assert result["station_demand_holdout_ready"] is False
    full["averages"]["excludedMonths"] = ["2026-08"]
    with pytest.raises(ValueError, match="complete calendar"):
        validate_mean_order_energy(full, held)
