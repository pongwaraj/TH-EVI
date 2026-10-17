from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest

from th_evi.api import app
from th_evi.charging_profiles import charging_basis_status, observed_bev_fleet
import th_evi.charging_profiles as profiles


client = TestClient(app)


def preview_payload(province="Chiang Mai"):
    off = {"effective_kw": 0, "available_hours": 0, "efficiency": 1, "use_fraction": 0}
    return {
        "province": province,
        "cohorts": [{
            "cohort_id": "illustrative_only", "fleet_share": 1, "active_day_share": 1,
            "daily_km": 50, "battery_kwh_per_km": 0.2,
            "home": deepcopy(off), "work": deepcopy(off), "public_ac": deepcopy(off),
        }],
        "average_dc_session_kwh": 20, "dc_vehicle_efficiency": 1, "dc_station_efficiency": 1,
    }


def test_pilot_reports_missing_behaviour_without_fake_defaults():
    result = client.get("/api/charging-demand/basis", params={"province": "Chiang Mai"})
    assert result.status_code == 200
    data = result.json()
    assert data["pilot_configured"] is True
    assert data["status"] == "inputs_required"
    assert "cohorts" in data["missing_energy_inputs"]
    assert "evidence.travel_distance" in data["missing_energy_inputs"]
    assert data["observed_fleet"]["bev"] > 0
    assert data["observed_fleet"]["vehicle_segment"] == "ror1_passenger_car"
    assert data["energy_budget_enforced_in_heatmap"] is False
    assert data["validation_status"] == "not_validated_for_station_forecasting"


def test_other_province_does_not_borrow_chiang_mai_behaviour():
    result = charging_basis_status("Chiang Rai")
    assert result["pilot_configured"] is False
    assert result["status"] == "not_configured"
    assert "cohorts" in result["missing_energy_inputs"]
    assert result["observed_fleet"]["bev"] != observed_bev_fleet("Chiang Mai")["bev"]


@pytest.mark.parametrize("province", ["Chiang Mai", "Chiang Rai"])
def test_shared_preview_uses_each_provinces_observed_fleet(province):
    result = client.post("/api/charging-demand/preview", json=preview_payload(province))
    assert result.status_code == 200
    data = result.json()
    fleet = observed_bev_fleet(province)
    assert data["status"] == "assumption_preview_not_calibrated"
    assert data["heatmap_changed"] is False
    assert data["observed_fleet"] == fleet
    assert data["energy_budget"]["traction_battery_kwh"] == fleet["bev"] * 10
    assert data["energy_budget"]["dc_session_equivalents_per_day"] == fleet["bev"] / 2
    assert data["energy_budget"]["energy_balance_error_kwh"] == 0


def test_unknown_province_has_no_fleet_fallback():
    response = client.post("/api/charging-demand/preview", json=preview_payload("not-a-province"))
    assert response.status_code == 422
    assert "No observed DLT" in response.json()["detail"]


@pytest.mark.parametrize("field", ["cohorts", "average_dc_session_kwh", "dc_vehicle_efficiency", "dc_station_efficiency"])
def test_preview_requires_explicit_behaviour(field):
    payload = preview_payload()
    del payload[field]
    assert client.post("/api/charging-demand/preview", json=payload).status_code == 422


def test_preview_rejects_duplicate_or_incomplete_fleet_partition():
    payload = preview_payload()
    payload["cohorts"][0]["fleet_share"] = 0.5
    assert client.post("/api/charging-demand/preview", json=payload).status_code == 422
    payload["cohorts"].append(deepcopy(payload["cohorts"][0]))
    response = client.post("/api/charging-demand/preview", json=payload)
    assert response.status_code == 422
    assert "unique" in response.json()["detail"]


def test_preview_rejects_overlapping_opportunity_hours():
    payload = preview_payload()
    payload["cohorts"][0]["home"]["available_hours"] = 20
    payload["cohorts"][0]["work"]["available_hours"] = 8
    assert client.post("/api/charging-demand/preview", json=payload).status_code == 422


@pytest.mark.parametrize("path", ["request", "cohort", "window"])
def test_preview_rejects_misspelled_inputs(path):
    payload = preview_payload()
    target = payload if path == "request" else payload["cohorts"][0]
    if path == "window":
        target = target["home"]
    target["unknown_field"] = 1
    assert client.post("/api/charging-demand/preview", json=payload).status_code == 422


@pytest.mark.parametrize("share,expected", [(0.5, "invalid_inputs"), (1, "inputs_supplied")])
def test_registry_checks_arithmetic_before_reporting_inputs_supplied(monkeypatch, tmp_path, share, expected):
    profile = preview_payload()
    profile["province"] = observed_bev_fleet("Chiang Mai")["province"]
    profile["cohorts"][0]["fleet_share"] = share
    profile["evidence"] = {key: {"source_url": "https://example.org/test-only"}
                           for key in profiles.EVIDENCE_FIELDS}
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"schema_version": 1, "profiles": [profile]}), encoding="utf-8")
    monkeypatch.setattr(profiles, "PROFILE_PATH", path)
    status = charging_basis_status("Chiang Mai")
    assert status["status"] == expected
    assert bool(status["input_errors"]) is (expected == "invalid_inputs")
    assert status["energy_budget_enforced_in_heatmap"] is False
