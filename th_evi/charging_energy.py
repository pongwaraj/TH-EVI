"""Province-independent representative-day charging energy accounting.

This is an aggregate energy balance, not the NREL EVI-Pro trip/SOC simulator.
Behavioural inputs must be supplied explicitly; POIs never create energy here.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose, isfinite
from typing import Mapping, Sequence


def _number(name: str, value: float, minimum: float = 0.0, maximum: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside its permitted range")


def _efficiency(name: str, value: float) -> None:
    _number(name, value, 0.0, 1.0)
    if value == 0:
        raise ValueError(f"{name} must be greater than zero")


@dataclass(frozen=True)
class ChargingWindow:
    """One charging opportunity for a homogeneous vehicle cohort.

    effective_kw is the usable input power, already limited by the vehicle and
    connection. efficiency converts that input energy into battery energy.
    use_fraction is chosen use of the available time, not population access.
    Vehicles with different access belong in separate cohorts.
    """

    effective_kw: float
    available_hours: float
    efficiency: float
    use_fraction: float

    def __post_init__(self) -> None:
        _number("effective_kw", self.effective_kw)
        _number("available_hours", self.available_hours, 0.0, 24.0)
        _efficiency("efficiency", self.efficiency)
        _number("use_fraction", self.use_fraction, 0.0, 1.0)

    @property
    def battery_capacity_kwh(self) -> float:
        return self.effective_kw * self.available_hours * self.efficiency * self.use_fraction


@dataclass(frozen=True)
class TravelCohort:
    cohort_id: str
    fleet_share: float
    active_day_share: float
    daily_km: float
    battery_kwh_per_km: float
    home: ChargingWindow
    work: ChargingWindow
    public_ac: ChargingWindow

    def __post_init__(self) -> None:
        if not isinstance(self.cohort_id, str) or not self.cohort_id.strip():
            raise ValueError("cohort_id must not be empty")
        _number("fleet_share", self.fleet_share, 0.0, 1.0)
        _number("active_day_share", self.active_day_share, 0.0, 1.0)
        _number("daily_km", self.daily_km)
        _number("battery_kwh_per_km", self.battery_kwh_per_km)
        if self.battery_kwh_per_km == 0:
            raise ValueError("battery_kwh_per_km must be greater than zero")
        if not all(isinstance(w, ChargingWindow) for w in (self.home, self.work, self.public_ac)):
            raise ValueError("home, work and public_ac must be ChargingWindow inputs")
        if fsum(w.available_hours for w in (self.home, self.work, self.public_ac)) > 24:
            raise ValueError("Total charging opportunity hours must not exceed a 24-hour day")


def calculate_daily_energy_budget(
    *,
    bev_fleet: float,
    cohorts: Sequence[TravelCohort],
    average_dc_session_kwh: float,
    dc_vehicle_efficiency: float,
    dc_station_efficiency: float,
) -> dict:
    """Allocate daily battery energy to home, work, public AC, then public DC.

    The balance represents a repeating average day. It does not guarantee that
    a trip can be completed before a later charging opportunity. A separate
    itinerary/SOC simulation is required to establish that chronology.
    Session equivalents are charging events, not distinct vehicles or a site
    forecast. No charging behaviour or fleet value has an implicit default.
    """
    _number("bev_fleet", bev_fleet)
    _number("average_dc_session_kwh", average_dc_session_kwh)
    if average_dc_session_kwh == 0:
        raise ValueError("average_dc_session_kwh must be greater than zero")
    _efficiency("dc_vehicle_efficiency", dc_vehicle_efficiency)
    _efficiency("dc_station_efficiency", dc_station_efficiency)
    if not cohorts or not all(isinstance(c, TravelCohort) for c in cohorts):
        raise ValueError("Explicit travel cohorts are required")
    if len({c.cohort_id for c in cohorts}) != len(cohorts):
        raise ValueError("cohort_id values must be unique")
    if not isclose(fsum(c.fleet_share for c in cohorts), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("fleet_share must sum to one; cohorts partition the same fleet")

    details = []
    for cohort in cohorts:
        active_vehicles = bev_fleet * cohort.fleet_share * cohort.active_day_share
        per_vehicle_energy = cohort.daily_km * cohort.battery_kwh_per_km
        remaining = per_vehicle_energy
        allocations = {}
        for name in ("home", "work", "public_ac"):
            supplied = min(remaining, getattr(cohort, name).battery_capacity_kwh)
            allocations[f"{name}_battery_kwh"] = supplied * active_vehicles
            remaining -= supplied
        details.append({
            "cohort_id": cohort.cohort_id,
            "fleet_vehicles": bev_fleet * cohort.fleet_share,
            "active_vehicles": active_vehicles,
            "traction_battery_kwh": per_vehicle_energy * active_vehicles,
            **allocations,
            "public_dc_battery_kwh": remaining * active_vehicles,
        })

    fields = ("active_vehicles", "traction_battery_kwh", "home_battery_kwh",
              "work_battery_kwh", "public_ac_battery_kwh", "public_dc_battery_kwh")
    totals = {field: fsum(row[field] for row in details) for field in fields}
    dc_connector_kwh = totals["public_dc_battery_kwh"] / dc_vehicle_efficiency
    energy_balance_error = totals["traction_battery_kwh"] - fsum(
        totals[key] for key in ("home_battery_kwh", "work_battery_kwh", "public_ac_battery_kwh", "public_dc_battery_kwh")
    )
    grid_kwh = dc_connector_kwh / dc_station_efficiency
    session_equivalents = dc_connector_kwh / average_dc_session_kwh
    for name, value in {**totals, "grid_kwh": grid_kwh, "sessions": session_equivalents}.items():
        _number(name, value)
    return {
        "method": "representative_day_energy_balance_v1",
        "scope": "registered_bev_fleet_reference_day",
        "bev_fleet": bev_fleet,
        **totals,
        "public_dc_connector_kwh": dc_connector_kwh,
        "public_dc_grid_kwh": grid_kwh,
        "dc_session_equivalents_per_day": session_equivalents,
        "average_dc_session_kwh": average_dc_session_kwh,
        "dc_vehicle_efficiency": dc_vehicle_efficiency,
        "dc_station_efficiency": dc_station_efficiency,
        "energy_balance_error_kwh": energy_balance_error,
        "cohorts": details,
        "limitations": [
            "No itinerary, battery SOC or trip-order simulation.",
            "Registered fleet does not establish where its daily travel occurs.",
            "Incoming vehicles must be modelled separately without duplicating fleet cohorts.",
            "Session equivalents do not predict a station's customer count.",
        ],
    }


def allocate_energy_budget(
    *,
    energy_kwh: float,
    destination_weights: Mapping[str, float],
    coverage_fraction: float,
    capacity_kwh: Mapping[str, float] | None = None,
) -> dict:
    """Distribute a fixed budget while retaining outside and unserved energy.

    Apply this to a fixed spatial support, then aggregate allocations for map
    display. Re-sampling a heat raster is not a new source of charging demand.
    Capacity-limited energy is retained as unserved, never gifted to our site.
    """
    _number("energy_kwh", energy_kwh)
    _number("coverage_fraction", coverage_fraction, 0.0, 1.0)
    for key, weight in destination_weights.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Destination IDs must not be empty")
        _number("destination weight", weight)
    weight_sum = fsum(destination_weights.values())
    covered_energy = energy_kwh * coverage_fraction
    if covered_energy > 0 and weight_sum == 0:
        raise ValueError("Positive covered energy requires positive destination weights")
    if capacity_kwh is not None:
        if set(capacity_kwh) != set(destination_weights):
            raise ValueError("Explicit capacity is required for every destination")
        for capacity in capacity_kwh.values():
            _number("capacity_kwh", capacity)

    allocations = []
    for key, weight in destination_weights.items():
        desired = covered_energy * weight / weight_sum if weight_sum else 0.0
        served = min(desired, capacity_kwh[key]) if capacity_kwh is not None else desired
        allocations.append({"destination_id": key, "assigned_kwh": desired,
                            "served_kwh": served, "unserved_kwh": desired - served})
    allocated = fsum(row["served_kwh"] for row in allocations)
    unserved = fsum(row["unserved_kwh"] for row in allocations)
    outside = energy_kwh - covered_energy
    return {
        "energy_kwh": energy_kwh,
        "allocated_kwh": allocated,
        "outside_coverage_kwh": outside,
        "unserved_kwh": unserved,
        "capacity_enforced": capacity_kwh is not None,
        "balance_error_kwh": energy_kwh - fsum((allocated, unserved, outside)),
        "allocations": allocations,
    }
