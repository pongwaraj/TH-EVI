from copy import deepcopy
import json
from pathlib import Path

import pytest

import th_evi.charging_profiles as profiles


ROOT = Path(__file__).resolve().parents[1]


def test_observed_two_station_reference_is_order_weighted_not_station_weighted():
    result = profiles.resolve_dc_session_energy("Chiang Mai")
    assert result["average_session_kwh"] == 27
    assert result["pooled_orders"] == 3218
    assert result["pooled_connector_kwh"] == pytest.approx(88014.72)
    assert result["pooled_mean_kwh"] == pytest.approx(27.35075201988813)
    assert len(result["stations"]) == 2
    assert result["forecast_validated"] is False
    meta = json.loads((ROOT / "data/chiang_mai_operations_behavior_2026q3.json").read_text(encoding="utf-8"))
    station = result["stations"][0]
    assert station["meaningful_orders"] == meta["meaningful_orders"]["count"]
    assert station["connector_kwh"] == meta["meaningful_orders"]["connector_kwh"]
    assert result == profiles.resolve_dc_session_energy("เชียงใหม่")


def test_chiang_mai_reference_does_not_close_unrelated_behaviour_gaps():
    status = profiles.charging_basis_status("Chiang Mai")
    assert status["dc_session_energy"]["available"] is True
    assert "average_dc_session_kwh" not in status["missing_energy_inputs"]
    assert "evidence.energy_per_session" not in status["missing_energy_inputs"]
    assert "cohorts" in status["missing_energy_inputs"]
    assert "dc_vehicle_efficiency" in status["missing_energy_inputs"]
    assert status["status"] == "inputs_required"
    assert status["energy_budget_enforced_in_heatmap"] is False


def test_no_cross_province_fallback_and_explicit_override_remains_available():
    with pytest.raises(ValueError, match="province-local"):
        profiles.resolve_dc_session_energy("Chiang Rai")
    for province in ("Chiang Mai", "Chiang Rai"):
        result = profiles.resolve_dc_session_energy(province, 24.3)
        assert result["average_session_kwh"] == 24.3
        assert result["source"] == "caller_override"


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "27"])
def test_invalid_override_cannot_produce_event_equivalents(value):
    with pytest.raises(ValueError):
        profiles.resolve_dc_session_energy("Chiang Mai", value)


@pytest.mark.parametrize("mutation", [
    lambda e: e.update(pooled_connector_kwh=99000),
    lambda e: e.update(pooled_mean_connector_kwh=35),
    lambda e: e.update(default_session_kwh=35),
    lambda e: e.update(definition="All orders including retries"),
    lambda e: e["stations"].append(deepcopy(e["stations"][0])),
    lambda e: e["stations"][0].update(meaningful_orders=0),
    lambda e: e["stations"][0].update(connector_kwh=float("nan")),
    lambda e: e.update(stations=None),
    lambda e: e.update(pooled_mean_connector_kwh="27"),
])
def test_inconsistent_evidence_fails_closed(monkeypatch, mutation):
    evidence = deepcopy(profiles.load_pilot_evidence("Chiang Mai", "dc_session_energy"))
    mutation(evidence)
    monkeypatch.setattr(profiles, "load_pilot_evidence", lambda *args: evidence)
    with pytest.raises(ValueError):
        profiles.resolve_dc_session_energy("Chiang Mai")
    assert profiles.dc_session_energy_status("Chiang Mai")["available"] is False


def test_missing_evidence_does_not_fall_back_to_a_legacy_constant(monkeypatch):
    monkeypatch.setattr(profiles, "load_pilot_evidence", lambda *args: None)
    with pytest.raises(ValueError, match="evidence"):
        profiles.resolve_dc_session_energy("Chiang Mai")
