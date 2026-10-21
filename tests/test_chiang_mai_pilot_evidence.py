import json
from pathlib import Path

import pytest

from scripts.build_operations_evidence import build_evidence
from scripts.build_travel_route_evidence import route_rows
from th_evi.charging_profiles import pilot_evidence_status


ROOT = Path(__file__).resolve().parents[1]


def test_operational_aggregates_reconcile_and_exclude_identifiers():
    period = {"from": "2026-07-01", "to": "2026-09-30"}
    overview = {"range": period, "coverage": {}, "kpis": {
        "sessions": 3421, "energyKwh": 86755.14, "avgDurationMinutes": 24.24, "shortSessions": 162,
    }, "peakHours": [{"hour": 12, "sessions": 2000}, {"hour": 18, "sessions": 1421}]}
    meaningful = {"range": period, "kpis": {"reportSessions": 3147, "reportKwh": 86285.97}}
    evidence = build_evidence(overview, meaningful)
    assert evidence["normal_orders"]["count"] == 3421
    assert evidence["meaningful_orders"]["count"] == 3147
    assert evidence["meaningful_orders"]["excluded_count"] == 274
    assert evidence["meaningful_orders"]["mean_connector_kwh"] == pytest.approx(27.41848, rel=1e-5)
    assert sum(row["share"] for row in evidence["hourly_normal_order_share"]) == pytest.approx(1)
    assert evidence["soc_distribution"] is None
    assert evidence["forecast_enabled"] is False
    def keys(value):
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert not {"customer_id", "vin", "order_id", "device_id"} & keys(evidence)
    saved = json.loads((ROOT / "data/chiang_mai_operations_behavior_2026q3.json").read_text())
    assert saved["meaningful_orders"]["mean_connector_kwh"] == pytest.approx(
        evidence["meaningful_orders"]["mean_connector_kwh"])


def test_operational_builder_rejects_mismatched_periods():
    overview = {"range": {"from": "a", "to": "b"}}
    meaningful = {"range": {"from": "c", "to": "d"}}
    with pytest.raises(ValueError, match="same time range"):
        build_evidence(overview, meaningful)


def test_route_rows_preserve_direction_and_reject_far_snap():
    points = [{"id": "home"}, {"id": "centre"}]
    matrix = {"code": "Ok", "distances": [[0, 5000], [6000, 0]],
              "durations": [[0, 600], [720, 0]],
              "sources": [{"distance": 12}, {"distance": 20}]}
    row = route_rows(points[:1], points[1:], matrix)[0]
    assert row["round_trip_road_km"] == 11
    assert row["outbound_road_km"] == 5
    assert row["return_road_km"] == 6
    assert row["trip_frequency_per_vehicle_day"] is None
    matrix["sources"][1]["distance"] = 260
    assert route_rows(points[:1], points[1:], matrix)[0]["round_trip_road_km"] is None
    matrix["fallback_speed_cells"] = [[0, 1]]
    with pytest.raises(ValueError, match="fallback"):
        route_rows(points[:1], points[1:], matrix)


def test_housing_context_does_not_equate_all_households_to_ev_owners():
    evidence = json.loads((ROOT / "data/chiang_mai_home_charging_evidence.json").read_text())
    assert sum(evidence["survey_housing"]["percent"].values()) == pytest.approx(100)
    assert evidence["survey_housing"]["population"] == "all_households_not_ev_owners"
    assert evidence["ev_owner_housing_mix"] is None
    assert evidence["private_home_ac_access"]["detached_house_ev_owner_probability"] is None
    assert evidence["forecast_enabled"] is False


def test_pilot_evidence_rejects_cross_province_file(tmp_path, monkeypatch):
    evidence = tmp_path / "wrong.json"
    evidence.write_text('{"province":"Chiang Rai"}', encoding="utf-8")
    import th_evi.charging_profiles as profiles
    monkeypatch.setattr(profiles, "ROOT", tmp_path)
    status = pilot_evidence_status({"province": "เชียงใหม่", "pilot_evidence": {"travel_routes": "wrong.json"}})
    assert status["available"] is False
    assert status["sources"]["travel_routes"]["status"] == "province_mismatch"
