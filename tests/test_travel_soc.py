from dataclasses import asdict, replace
from random import Random

from fastapi.testclient import TestClient
import pytest

from th_evi.api import app
from th_evi.travel_soc import (
    ChargeOpportunity, DCPowerBand, TravelEvent, VehicleSpec, charge_window, simulate_travel_soc,
)


def vehicle(**kwargs):
    return VehicleSpec(**{
        "usable_battery_kwh": 60, "battery_kwh_per_km": 0.2,
        "initial_soc": 0.5, "reserve_soc": 0.1, "ac_max_kw": 7,
        "dc_bands": (DCPowerBand(0, 0.8, 100), DCPowerBand(0.8, 1, 20)), **kwargs,
    })


def opportunity(**kwargs):
    return ChargeOpportunity(**{
        "charger_id": "test-only", "kind": "home", "connector": "ac", "connector_kw": 7,
        "vehicle_efficiency": 1, "station_efficiency": 1,
        "trigger_soc": 1, "target_soc": 1, "plug_overhead_hours": 0, **kwargs,
    })


def dwell(start, end, where="H", charging=None, event_id="park"):
    return TravelEvent(event_id, "dwell", start, end, where, where, 0, charging)


def commute(home=None, work=None):
    return [dwell(0, 8, charging=home, event_id="night"),
            TravelEvent("out", "trip", 8, 9, "H", "W", 50, None),
            dwell(9, 17, "W", work, "work"),
            TravelEvent("back", "trip", 17, 18, "W", "H", 50, None),
            dwell(18, 24, charging=home, event_id="evening")]


def simulate(v=None, plan=None, **kwargs):
    return simulate_travel_soc(**{
        "vehicle": v or vehicle(), "itinerary": plan or commute(opportunity()),
        "days": 3, "warmup_days": 2, **kwargs,
    })


def test_multiday_soc_is_carried_and_warmup_energy_is_not_billed_in_measurement():
    result = simulate()
    assert result["all_requested_travel_feasible"]
    assert result["periodic_daily_energy_balance_reached"]
    assert result["initial_soc_independence_validated"] is False
    assert result["measurement"]["traction_battery_kwh"] == 60
    assert result["measurement"]["charging"]["home"]["battery_kwh"] == pytest.approx(60)
    assert result["measurement"]["charging_events_started"] == 3
    assert result["measurement"]["energy_balance_error_kwh"] == pytest.approx(0)
    assert result["days"][0]["charging"]["home"]["battery_kwh"] == pytest.approx(50)
    assert result["measurement"]["start_battery_kwh"] == 60
    assert all(abs(day["energy_balance_error_kwh"]) < 1e-8 for day in result["days"])


def test_later_charging_cannot_rescue_an_earlier_infeasible_departure():
    plan = commute()
    plan[-1] = replace(plan[-1], charging=opportunity())
    result = simulate(vehicle(initial_soc=0.2), plan, warmup_days=0)
    assert result["failure"]["event_id"] == "out"
    assert result["failure"]["missing_battery_kwh_to_preserve_reserve"] == pytest.approx(4)
    assert result["measurement"]["traction_battery_kwh"] == 0
    assert result["measurement"]["charging"]["home"]["battery_kwh"] == 0
    assert result["final_soc"] == 0.2
    assert not result["all_requested_travel_feasible"]


def test_initial_battery_energy_does_not_reset_at_midnight_or_hide_future_failure():
    result = simulate(vehicle(initial_soc=0.9), commute(), warmup_days=0, days=4)
    assert result["failure"]["day"] == 2
    assert result["measurement"]["traction_battery_kwh"] == 40
    assert result["measurement"]["net_battery_drawdown_kwh"] == pytest.approx(40)
    assert result["measurement"]["energy_balance_error_kwh"] == pytest.approx(0)
    assert result["measured_days_simulated"] == 3


def test_warmup_failure_is_reported_without_fabricated_measurement_days():
    result = simulate(vehicle(initial_soc=0.2), commute(), warmup_days=2)
    assert result["failure"]["warmup"]
    assert result["measured_days_simulated"] == 0
    assert result["measurement"]["traction_battery_kwh"] == 0
    assert result["measurement"]["energy_balance_error_kwh"] == 0


def test_dc_taper_is_integrated_and_charger_rating_is_limited_by_vehicle():
    v = vehicle()
    op = opportunity(kind="public_dc", connector="dc", connector_kw=240)
    result = charge_window(v, op, 30, 24)
    assert result["hours"] == pytest.approx(18/100 + 12/20)
    assert result["battery_kwh"] == pytest.approx(30)
    assert charge_window(v, replace(op, connector_kw=120), 30, 24) == result
    slow = charge_window(v, replace(op, connector_kw=30), 30, 24)
    assert slow["hours"] == pytest.approx(18/30 + 12/20)
    assert charge_window(v, op, 30, 0.3)["battery_kwh"] == pytest.approx(20.4)


def test_efficiencies_are_applied_at_distinct_energy_boundaries():
    op = opportunity(kind="public_dc", connector="dc", connector_kw=100,
                     vehicle_efficiency=0.9, station_efficiency=0.8)
    result = charge_window(vehicle(), op, 30, 0.05)
    assert result["battery_kwh"] == pytest.approx(4.5)
    assert result["connector_kwh"] == pytest.approx(5)
    assert result["grid_kwh"] == pytest.approx(6.25)


def test_ac_limits_overhead_and_actual_dwell_are_enforced():
    op = opportunity(connector_kw=100, plug_overhead_hours=0.25)
    plan = [dwell(0, 0.3, charging=op, event_id="charge"), dwell(0.3, 24)]
    result = simulate(plan=plan, warmup_days=0, days=1)
    assert result["measurement"]["charging"]["home"]["battery_kwh"] == pytest.approx(0.35)
    assert result["charging_events"][0]["start_hour"] == 0.25


def test_no_dc_capability_or_zero_power_does_not_create_charging():
    v = vehicle(dc_bands=())
    op = opportunity(kind="public_dc", connector="dc", connector_kw=240)
    assert charge_window(v, op, 30, 24)["battery_kwh"] == 0
    assert charge_window(vehicle(), replace(op, connector_kw=0), 30, 24)["battery_kwh"] == 0
    blocked_curve = vehicle(dc_bands=(DCPowerBand(0, 0.8, 100), DCPowerBand(0.8, 1, 0)))
    assert charge_window(blocked_curve, op, 30, 24)["battery_kwh"] == pytest.approx(18)


def test_midnight_does_not_reapply_trigger_overhead_or_split_one_charging_event():
    v = vehicle(initial_soc=0, reserve_soc=0)
    op = opportunity(connector_kw=1, trigger_soc=0.3, target_soc=1, plug_overhead_hours=2)
    result = simulate(v, [dwell(0, 24, charging=op)], warmup_days=1, days=2)
    assert len(result["charging_events"]) == 1
    assert result["charging_events"][0]["start_hour"] == 2
    assert result["charging_events"][0]["end_hour"] == pytest.approx(62)
    assert result["measurement"]["charging_events_started"] == 0
    assert result["measurement"]["charging_events_overlapping"] == 1
    assert result["measurement"]["charging"]["home"]["battery_kwh"] == pytest.approx(38)


def test_pending_plug_overhead_carries_across_contiguous_dwell_fragments():
    op = opportunity(connector_kw=1, plug_overhead_hours=2)
    plan = [dwell(0, 1, charging=op, event_id="first"),
            dwell(1, 3, charging=op, event_id="second"), dwell(3, 24)]
    result = simulate(plan=plan, days=1, warmup_days=0)
    assert result["charging_events"][0]["start_hour"] == 2
    assert result["measurement"]["charging"]["home"]["battery_kwh"] == pytest.approx(1)


def test_randomized_explicit_inputs_preserve_energy_and_soc_bounds():
    rng = Random(42)
    for _ in range(100):
        capacity = rng.uniform(30, 100)
        reserve = rng.uniform(0, 0.2)
        v = vehicle(usable_battery_kwh=capacity, reserve_soc=reserve,
                    initial_soc=rng.uniform(reserve, 1), battery_kwh_per_km=rng.uniform(0.1, 0.3))
        op = opportunity(connector_kw=rng.uniform(1, 22), vehicle_efficiency=rng.uniform(0.7, 1),
                         station_efficiency=rng.uniform(0.7, 1), plug_overhead_hours=rng.uniform(0, 2))
        result = simulate(v, commute(op), days=10, warmup_days=2)
        assert abs(result["measurement"]["energy_balance_error_kwh"]) < 1e-8
        for row in result["trace"]:
            assert reserve - 1e-9 <= row["end_soc"] <= 1 + 1e-9
        for row in result["days"]:
            assert abs(row["energy_balance_error_kwh"]) < 1e-8
            for energy in row["charging"].values():
                assert energy["battery_kwh"] <= energy["connector_kwh"] + 1e-9
                assert energy["connector_kwh"] <= energy["grid_kwh"] + 1e-9


def test_work_or_public_ac_replenishment_reduces_subsequent_public_dc_need():
    dc = opportunity(kind="public_dc", connector="dc", connector_kw=120)
    ac = opportunity(kind="public_ac", connector="ac", connector_kw=7)
    without = simulate(plan=commute(dc), days=2, warmup_days=2)
    with_ac = simulate(plan=commute(dc, ac), days=2, warmup_days=2)
    assert with_ac["measurement"]["charging"]["public_dc"]["battery_kwh"] < without["measurement"]["charging"]["public_dc"]["battery_kwh"]
    assert with_ac["measurement"]["charging"]["public_ac"]["battery_kwh"] > 0


def test_no_travel_or_charging_need_produces_zero_sessions():
    result = simulate(plan=[dwell(0, 24)], warmup_days=0)
    assert result["measurement"]["charging_events_started"] == 0
    assert result["measurement"]["traction_battery_kwh"] == 0


def test_trace_limit_does_not_change_simulation_results():
    full = simulate()
    limited = simulate(trace_limit=0)
    assert limited["measurement"] == full["measurement"]
    assert limited["trace"] == [] and limited["trace_truncated"]
    assert limited["charging_events_truncated"]


@pytest.mark.parametrize("kwargs", [
    {"days": 0}, {"days": 91}, {"days": True}, {"warmup_days": -1}, {"warmup_days": 31},
    {"trace_limit": -1}, {"trace_limit": 2001},
])
def test_invalid_simulation_limits(kwargs):
    with pytest.raises(ValueError):
        simulate(**kwargs)


@pytest.mark.parametrize("kwargs", [
    {"initial_soc": 1.1}, {"initial_soc": 0.05}, {"reserve_soc": -1},
    {"usable_battery_kwh": 0}, {"battery_kwh_per_km": float("nan")},
    {"dc_bands": (DCPowerBand(0.1, 1, 100),)},
    {"dc_bands": (DCPowerBand(0, 0.5, 100), DCPowerBand(0.6, 1, 20))},
    {"dc_bands": (DCPowerBand(0, 0.9, 100),)},
])
def test_invalid_vehicle(kwargs):
    with pytest.raises(ValueError):
        vehicle(**kwargs)


@pytest.mark.parametrize("kwargs", [
    {"kind": "public_ac", "connector": "dc"}, {"vehicle_efficiency": 0},
    {"station_efficiency": 1.1}, {"target_soc": 0.5, "trigger_soc": 0.8},
    {"plug_overhead_hours": -1}, {"charger_id": " "},
])
def test_invalid_charging_inputs(kwargs):
    with pytest.raises(ValueError):
        opportunity(**kwargs)


def test_gaps_overlaps_teleportation_and_open_daily_loops_are_rejected():
    plans = [
        [dwell(1, 24)], [dwell(0, 12, event_id="a"), dwell(11, 24, event_id="b")],
        [dwell(0, 12, event_id="a"), dwell(12, 24, "W", event_id="b")],
        [TravelEvent("out", "trip", 0, 1, "H", "W", 10, None), dwell(1, 24, "W")],
        [dwell(0, 12), dwell(12, 24)],
    ]
    for plan in plans:
        with pytest.raises(ValueError):
            simulate(plan=plan)


def payload():
    return {"province": "Chiang Mai", "vehicle": asdict(vehicle()),
            "itinerary": [asdict(event) for event in commute(opportunity())], "days": 3, "warmup_days": 2}


def test_travel_api_is_a_working_preview_not_a_provincial_forecast():
    response = TestClient(app).post("/api/charging-demand/travel-preview", json=payload())
    assert response.status_code == 200
    result = response.json()
    assert result["method"] == "explicit_itinerary_soc_v1"
    assert result["status"] == "assumption_preview_not_calibrated"
    assert result["all_requested_travel_feasible"]
    assert result["heatmap_changed"] is False and result["forecast_available"] is False
    assert result["measurement"]["traction_battery_kwh"] == 60
    other = payload()
    other["province"] = "Chiang Rai"
    assert TestClient(app).post("/api/charging-demand/travel-preview", json=other).json()["measurement"] == result["measurement"]


@pytest.mark.parametrize("field", ["initial_soc", "reserve_soc", "dc_bands", "ac_max_kw"])
def test_api_does_not_fill_missing_vehicle_assumptions(field):
    data = payload()
    del data["vehicle"][field]
    assert TestClient(app).post("/api/charging-demand/travel-preview", json=data).status_code == 422


def test_api_rejects_unknown_fields_and_missing_charging_choice():
    data = payload()
    del data["itinerary"][0]["charging"]
    assert TestClient(app).post("/api/charging-demand/travel-preview", json=data).status_code == 422
    data = payload()
    data["vehicle"]["estimated_bev_fleet"] = 17002
    assert TestClient(app).post("/api/charging-demand/travel-preview", json=data).status_code == 422


def test_api_returns_validation_error_for_unphysical_sequence():
    data = payload()
    data["itinerary"][1]["origin"] = "not-at-home"
    response = TestClient(app).post("/api/charging-demand/travel-preview", json=data)
    assert response.status_code == 422
    assert "teleporting" in response.json()["detail"]
