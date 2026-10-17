from dataclasses import replace

import pytest

from th_evi.charging_energy import (
    ChargingWindow, TravelCohort, allocate_energy_budget, calculate_daily_energy_budget,
)


OFF = ChargingWindow(0, 0, 1, 0)


def cohort(**kwargs):
    return TravelCohort(**{
        "cohort_id": "resident", "fleet_share": 1, "active_day_share": 1,
        "daily_km": 50, "battery_kwh_per_km": 0.2,
        "home": OFF, "work": OFF, "public_ac": OFF, **kwargs,
    })


def budget(cohorts=None, **kwargs):
    return calculate_daily_energy_budget(**{
        "bev_fleet": 100, "cohorts": [cohort()] if cohorts is None else cohorts,
        "average_dc_session_kwh": 20, "dc_vehicle_efficiency": 1,
        "dc_station_efficiency": 1, **kwargs,
    })


def test_energy_partition_and_conversion_boundaries():
    result = budget([cohort(
        home=ChargingWindow(2, 1, 1, 1),
        work=ChargingWindow(4, 1, 0.5, 1),
        public_ac=ChargingWindow(2, 1, 1, 0.5),
    )], dc_vehicle_efficiency=0.8, dc_station_efficiency=0.9)
    assert result["traction_battery_kwh"] == 1000
    assert result["home_battery_kwh"] == 200
    assert result["work_battery_kwh"] == 200
    assert result["public_ac_battery_kwh"] == 100
    assert result["public_dc_battery_kwh"] == 500
    assert result["public_dc_connector_kwh"] == 625
    assert result["public_dc_grid_kwh"] == pytest.approx(625 / 0.9)
    assert result["dc_session_equivalents_per_day"] == 31.25
    assert result["energy_balance_error_kwh"] == pytest.approx(0)


def test_home_coverage_removes_residual_dc_without_creating_energy():
    before = budget()
    after = budget([cohort(home=ChargingWindow(7, 8, 0.9, 1))])
    assert before["public_dc_battery_kwh"] == 1000
    assert after["public_dc_battery_kwh"] == 0
    assert after["home_battery_kwh"] == after["traction_battery_kwh"]


def test_dwell_time_limits_energy_and_public_ac_reduces_dc():
    short = cohort(work=ChargingWindow(10, 0.25, 1, 1))
    assert budget([short])["public_dc_battery_kwh"] == 750
    assert budget([replace(short, public_ac=ChargingWindow(10, 0.25, 1, 1))])["public_dc_battery_kwh"] == 500


def test_cohorts_partition_fleet_and_activity_not_charger_access():
    result = budget([
        cohort(cohort_id="home", fleet_share=0.6, active_day_share=0.5,
               home=ChargingWindow(7, 8, 0.9, 1)),
        cohort(cohort_id="no_home", fleet_share=0.4, active_day_share=0.25),
    ])
    assert result["active_vehicles"] == 40
    assert result["traction_battery_kwh"] == 400
    assert result["public_dc_battery_kwh"] == 100
    assert sum(c["fleet_vehicles"] for c in result["cohorts"]) == 100


def test_zero_fleet_or_no_active_travel_creates_no_demand():
    assert budget(bev_fleet=0)["dc_session_equivalents_per_day"] == 0
    assert budget([cohort(active_day_share=0)])["public_dc_grid_kwh"] == 0


@pytest.mark.parametrize("bad_cohorts", [[], [cohort(fleet_share=0.8)], [cohort(), cohort()]])
def test_missing_or_overlapping_fleet_cohorts_rejected(bad_cohorts):
    with pytest.raises(ValueError):
        budget(bad_cohorts)


@pytest.mark.parametrize("field,value", [
    ("bev_fleet", -1), ("bev_fleet", float("nan")), ("bev_fleet", True),
    ("average_dc_session_kwh", 0), ("dc_vehicle_efficiency", 0),
    ("dc_station_efficiency", 1.1), ("dc_station_efficiency", float("inf")),
])
def test_invalid_energy_inputs_rejected(field, value):
    with pytest.raises(ValueError):
        budget(**{field: value})


@pytest.mark.parametrize("kwargs", [
    {"daily_km": -1}, {"battery_kwh_per_km": 0}, {"cohort_id": " "},
    {"fleet_share": 1.1}, {"active_day_share": 1.1}, {"home": None},
    {"home": ChargingWindow(7, 20, 0.9, 1), "work": ChargingWindow(7, 8, 0.9, 1)},
])
def test_invalid_cohort_rejected(kwargs):
    with pytest.raises(ValueError):
        cohort(**kwargs)


@pytest.mark.parametrize("args", [(7, -1, 1, 1), (7, 25, 1, 1), (7, 8, 0, 1), (7, 8, 1, 1.1)])
def test_invalid_charging_window_rejected(args):
    with pytest.raises(ValueError):
        ChargingWindow(*args)


def test_allocation_preserves_outside_option_and_capacity_shortfall():
    result = allocate_energy_budget(
        energy_kwh=1000, destination_weights={"existing": 3, "proposed": 1},
        coverage_fraction=0.8, capacity_kwh={"existing": 100, "proposed": 200},
    )
    assert result["allocated_kwh"] == 300
    assert result["unserved_kwh"] == 500
    assert result["outside_coverage_kwh"] == 200
    assert result["balance_error_kwh"] == 0
    assert result["allocations"][1]["served_kwh"] == 200


def test_weights_and_display_aggregation_cannot_create_energy():
    def allocate(weights):
        return allocate_energy_budget(energy_kwh=1000, destination_weights=weights, coverage_fraction=0.75)

    coarse = allocate({"a": 3, "b": 1})
    rescaled = allocate({"a": 30, "b": 10})
    fine = allocate({"a1": 1, "a2": 2, "b": 1})
    assert coarse["allocations"] == rescaled["allocations"]
    assert sum(r["served_kwh"] for r in fine["allocations"] if r["destination_id"].startswith("a")) == coarse["allocations"][0]["served_kwh"]
    assert coarse["allocated_kwh"] == fine["allocated_kwh"] == 750
    assert coarse["capacity_enforced"] is False


def test_empty_allocation_requires_all_energy_outside():
    result = allocate_energy_budget(energy_kwh=100, destination_weights={}, coverage_fraction=0)
    assert result["outside_coverage_kwh"] == 100
    with pytest.raises(ValueError):
        allocate_energy_budget(energy_kwh=100, destination_weights={}, coverage_fraction=1)


@pytest.mark.parametrize("kwargs", [
    {"coverage_fraction": 1.1}, {"destination_weights": {"a": -1}},
    {"capacity_kwh": {}}, {"capacity_kwh": {"a": -1}},
    {"energy_kwh": float("inf")},
])
def test_invalid_allocation_rejected(kwargs):
    with pytest.raises(ValueError):
        allocate_energy_budget(**{
            "energy_kwh": 100, "destination_weights": {"a": 1}, "coverage_fraction": 1, **kwargs,
        })
