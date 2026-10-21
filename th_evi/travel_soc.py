"""Explicit-input, repeating-itinerary SOC feasibility preview.

This is not EVI-Pro or a calibrated station-choice model. No driver behaviour,
vehicle characteristics or rescue charging is inferred from a province/POI.
DC charging integrates caller-supplied piecewise-constant acceptance bands.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose

from .charging_energy import _efficiency, _number


EPS = 1e-9
KINDS = ("home", "work", "public_ac", "public_dc")


def _label(name, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class DCPowerBand:
    soc_from: float
    soc_to: float
    connector_kw: float

    def __post_init__(self):
        _number("soc_from", self.soc_from, 0, 1)
        _number("soc_to", self.soc_to, 0, 1)
        _number("connector_kw", self.connector_kw)
        if self.soc_to <= self.soc_from:
            raise ValueError("DC bands must have positive SOC width")


@dataclass(frozen=True)
class VehicleSpec:
    usable_battery_kwh: float
    battery_kwh_per_km: float
    initial_soc: float
    reserve_soc: float
    ac_max_kw: float
    dc_bands: tuple[DCPowerBand, ...]

    def __post_init__(self):
        for key in ("usable_battery_kwh", "battery_kwh_per_km"):
            _number(key, getattr(self, key))
            if getattr(self, key) == 0:
                raise ValueError(f"{key} must be greater than zero")
        for key in ("initial_soc", "reserve_soc"):
            _number(key, getattr(self, key), 0, 1)
        if self.initial_soc < self.reserve_soc:
            raise ValueError("initial_soc must not be below reserve_soc")
        _number("ac_max_kw", self.ac_max_kw)
        if not isinstance(self.dc_bands, (tuple, list)) or len(self.dc_bands) > 20:
            raise ValueError("Provide zero to 20 explicit DC power bands")
        boundary = 0.0
        for band in self.dc_bands:
            if not isinstance(band, DCPowerBand) or not isclose(band.soc_from, boundary, abs_tol=EPS, rel_tol=0):
                raise ValueError("DC bands must be ordered, contiguous and start at zero")
            boundary = band.soc_to
        if self.dc_bands and not isclose(boundary, 1, abs_tol=EPS, rel_tol=0):
            raise ValueError("DC bands must cover SOC through one; an empty curve means no DC capability")


@dataclass(frozen=True)
class ChargeOpportunity:
    charger_id: str
    kind: str
    connector: str
    connector_kw: float
    vehicle_efficiency: float
    station_efficiency: float
    trigger_soc: float
    target_soc: float
    plug_overhead_hours: float

    def __post_init__(self):
        _label("charger_id", self.charger_id)
        if self.kind not in KINDS or self.connector not in {"ac", "dc"}:
            raise ValueError("Invalid charging kind or connector")
        if self.kind == "public_ac" and self.connector != "ac" or self.kind == "public_dc" and self.connector != "dc":
            raise ValueError("Public charging kind must match its connector")
        _number("connector_kw", self.connector_kw)
        _efficiency("vehicle_efficiency", self.vehicle_efficiency)
        _efficiency("station_efficiency", self.station_efficiency)
        _number("trigger_soc", self.trigger_soc, 0, 1)
        _number("target_soc", self.target_soc, 0, 1)
        if self.target_soc < self.trigger_soc:
            raise ValueError("target_soc must be at least trigger_soc")
        _number("plug_overhead_hours", self.plug_overhead_hours, 0, 24)


@dataclass(frozen=True)
class TravelEvent:
    event_id: str
    kind: str
    start_hour: float
    end_hour: float
    origin: str
    destination: str
    distance_km: float
    charging: ChargeOpportunity | None

    def __post_init__(self):
        for key in ("event_id", "origin", "destination"):
            _label(key, getattr(self, key))
        if self.kind not in {"trip", "dwell"}:
            raise ValueError("Event kind must be trip or dwell")
        _number("start_hour", self.start_hour, 0, 24)
        _number("end_hour", self.end_hour, 0, 24)
        _number("distance_km", self.distance_km)
        if self.end_hour <= self.start_hour:
            raise ValueError("Events must have positive duration")
        if self.charging is not None and not isinstance(self.charging, ChargeOpportunity):
            raise ValueError("charging must be an explicit ChargeOpportunity or null")
        if self.kind == "trip" and self.charging is not None:
            raise ValueError("No charging while driving in this simulator")
        if self.kind == "trip" and self.distance_km == 0:
            raise ValueError("Trips must have positive distance")
        if self.kind == "dwell" and (self.distance_km != 0 or self.origin != self.destination):
            raise ValueError("Dwell must stay at one location with zero travel distance")


def validate_itinerary(events, repeat_days):
    if not events or len(events) > 96 or not all(isinstance(e, TravelEvent) for e in events):
        raise ValueError("Provide 1 to 96 explicit travel/dwell events per day")
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("event_id values must be unique within a day")
    boundary, location = 0.0, events[0].origin
    for event in events:
        if not isclose(event.start_hour, boundary, abs_tol=EPS, rel_tol=0):
            raise ValueError("Ordered events must cover 24 hours without gaps or overlaps")
        if event.origin != location:
            raise ValueError("Event locations must join without teleporting")
        boundary, location = event.end_hour, event.destination
    if not isclose(boundary, 24, abs_tol=EPS, rel_tol=0):
        raise ValueError("Itinerary must cover the full 24-hour day")
    if repeat_days > 1 and location != events[0].origin:
        raise ValueError("Repeating itinerary must end at its starting location")


def charge_window(vehicle, opportunity, battery_kwh, hours):
    """Integrate connector power over battery SOC bands, without a time step."""
    _number("battery_kwh", battery_kwh, 0, vehicle.usable_battery_kwh)
    _number("hours", hours, 0, 24)
    target = min(opportunity.target_soc * vehicle.usable_battery_kwh, vehicle.usable_battery_kwh)
    current, elapsed = battery_kwh, 0.0
    bands = vehicle.dc_bands if opportunity.connector == "dc" else (DCPowerBand(0, 1, vehicle.ac_max_kw),)
    for band in bands:
        upper = min(target, band.soc_to * vehicle.usable_battery_kwh)
        if upper <= current + EPS:
            continue
        kw = min(opportunity.connector_kw, band.connector_kw)
        if kw == 0 or elapsed >= hours:
            break
        battery_kw = kw * opportunity.vehicle_efficiency
        gain = min(upper - current, (hours - elapsed) * battery_kw)
        current += gain
        elapsed += gain / battery_kw
        if current >= target - EPS:
            break
    gain = current - battery_kwh
    connector_kwh = gain / opportunity.vehicle_efficiency
    for name, value in {"battery_kwh": current, "connector_kwh": connector_kwh,
                        "grid_kwh": connector_kwh / opportunity.station_efficiency}.items():
        _number(name, value)
    return {"battery_kwh": gain, "connector_kwh": connector_kwh,
            "grid_kwh": connector_kwh / opportunity.station_efficiency, "hours": elapsed}


def simulate_travel_soc(*, vehicle: VehicleSpec, itinerary: list[TravelEvent], days: int, warmup_days: int, trace_limit: int = 500) -> dict:
    """Stop at the first infeasible trip; later opportunities cannot rescue it.

    Warm-up days are real simulated days and are reported separately. They do
    not reset SOC or prove independence of initial SOC. All inputs describe one
    vehicle, not the provincial fleet and not a proposed station's customers.
    """
    if not isinstance(vehicle, VehicleSpec):
        raise ValueError("Explicit VehicleSpec is required")
    for key, value, low, high in (("days", days, 1, 90), ("warmup_days", warmup_days, 0, 30), ("trace_limit", trace_limit, 0, 2000)):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"{key} must be an integer from {low} to {high}")
    validate_itinerary(itinerary, days + warmup_days)
    capacity = vehicle.usable_battery_kwh
    initial = battery = capacity * vehicle.initial_soc
    reserve = capacity * vehicle.reserve_soc
    start_measured = None
    trace, daily, sessions = [], [], []
    continuation = None
    failure = None
    trace_count = 0
    for day in range(days + warmup_days):
        measured = day >= warmup_days
        if day == warmup_days:
            start_measured = battery
        day_initial = battery
        driving = 0.0
        energy = {kind: {key: 0.0 for key in ("battery_kwh", "connector_kwh", "grid_kwh")} for kind in KINDS}
        for event in itinerary:
            if failure is not None:
                break
            before = battery
            start, end = day * 24 + event.start_hour, day * 24 + event.end_hour
            row = {"day": day, "warmup": not measured, "event_id": event.event_id,
                   "kind": event.kind, "start_hour": start, "end_hour": end,
                   "origin": event.origin, "destination": event.destination,
                   "start_soc": before / capacity, "battery_charge_kwh": 0.0,
                   "traction_battery_kwh": 0.0}
            if event.kind == "trip":
                continuation = None
                needed = event.distance_km * vehicle.battery_kwh_per_km
                _number("trip_battery_kwh", needed)
                if battery + EPS < needed + reserve:
                    failure = {"day": day, "warmup": not measured, "event_id": event.event_id,
                               "departure_hour": start, "origin": event.origin,
                               "required_battery_kwh": needed,
                               "missing_battery_kwh_to_preserve_reserve": needed + reserve - battery,
                               "reason": "insufficient_soc_at_departure_no_rescue_charging"}
                    row["status"] = "trip_not_started"
                else:
                    battery = max(reserve, battery - needed)
                    driving += needed
                    row.update(traction_battery_kwh=needed, status="completed")
            else:
                op = event.charging
                previous = continuation
                continuing = previous is not None and previous["opportunity"] == op and previous["location"] == event.origin and isclose(previous["end"], start, abs_tol=EPS, rel_tol=0)
                continuation = None
                row["status"] = "parked_without_charging"
                if op is not None and (continuing or battery / capacity < op.trigger_soc):
                    overhead = previous["overhead_remaining"] if continuing else op.plug_overhead_hours
                    available = max(0.0, end - start - overhead)
                    result = charge_window(vehicle, op, battery, available)
                    battery += result["battery_kwh"]
                    for key in energy[op.kind]:
                        energy[op.kind][key] += result[key]
                    if result["battery_kwh"] > 0:
                        actual_start = start + overhead
                        actual_end = actual_start + result["hours"]
                        if continuing and sessions and isclose(sessions[-1]["end_hour"], actual_start, abs_tol=EPS, rel_tol=0):
                            sessions[-1]["end_hour"] = actual_end
                            for key in ("battery_kwh", "connector_kwh", "grid_kwh"):
                                sessions[-1][key] += result[key]
                        else:
                            sessions.append({"charger_id": op.charger_id, "kind": op.kind,
                                             "start_hour": actual_start, "end_hour": actual_end,
                                             **{key: result[key] for key in ("battery_kwh", "connector_kwh", "grid_kwh")}})
                        row.update(status="charged", battery_charge_kwh=result["battery_kwh"],
                                   charging_kind=op.kind, connector_kwh=result["connector_kwh"], grid_kwh=result["grid_kwh"])
                    overhead_remaining = max(0.0, overhead - (end - start))
                    used_window = overhead >= end - start or isclose(start + overhead + result["hours"], end, abs_tol=EPS, rel_tol=0)
                    if used_window and battery < op.target_soc * capacity - EPS:
                        continuation = {"opportunity": op, "location": event.origin, "end": end,
                                        "overhead_remaining": overhead_remaining}
            row["end_soc"] = battery / capacity
            trace_count += 1
            if len(trace) < trace_limit:
                trace.append(row)
        day_charged = fsum(values["battery_kwh"] for values in energy.values())
        daily.append({"day": day, "warmup": not measured, "start_soc": day_initial / capacity,
                      "end_soc": battery / capacity, "traction_battery_kwh": driving,
                      "charging": energy, "energy_balance_error_kwh": day_initial + day_charged - driving - battery,
                      "complete": failure is None})
        if failure is not None:
            break
    measured_rows = [row for row in daily if not row["warmup"]]
    start_measured = battery if start_measured is None else start_measured
    boundary = warmup_days * 24
    summary = {kind: {key: fsum(row["charging"][kind][key] for row in measured_rows)
                      for key in ("battery_kwh", "connector_kwh", "grid_kwh")} for kind in KINDS}
    traction = fsum(row["traction_battery_kwh"] for row in measured_rows)
    charged = fsum(values["battery_kwh"] for values in summary.values())
    measured_complete = len(measured_rows) == days and all(row["complete"] for row in measured_rows)
    stable = len(daily) >= 3 and all(row["complete"] and abs(row["end_soc"] - row["start_soc"]) < 1e-6 for row in daily[-3:])
    return {
        "method": "explicit_itinerary_soc_v1", "status": "assumption_preview_not_calibrated",
        "scope": "one_vehicle_repeating_day_not_provincial_or_site_forecast",
        "requested_days": days, "warmup_days": warmup_days,
        "measured_days_simulated": len(measured_rows), "all_requested_travel_feasible": measured_complete,
        "failure": failure, "initial_soc": vehicle.initial_soc, "final_soc": battery / capacity,
        "periodic_daily_energy_balance_reached": stable,
        "initial_soc_independence_validated": False,
        "measurement": {
            "start_battery_kwh": start_measured, "end_battery_kwh": battery,
            "traction_battery_kwh": traction, "charging": summary,
            "net_battery_drawdown_kwh": start_measured - battery,
            "energy_balance_error_kwh": start_measured + charged - traction - battery,
            "charging_events_started": sum(boundary <= row["start_hour"] < boundary + days * 24 for row in sessions),
            "charging_events_overlapping": sum(row["end_hour"] > boundary and row["start_hour"] < boundary + days * 24 for row in sessions),
        },
        "days": daily, "trace": trace, "trace_rows_total": trace_count, "trace_truncated": trace_count > len(trace),
        "charging_events": sessions[:trace_limit], "charging_events_truncated": len(sessions) > trace_limit,
        "charging_events_scope": "entire_simulation_including_warmup",
        "heatmap_changed": False, "forecast_available": False,
        "limitations": [
            "Caller-supplied repeating itinerary and threshold charging policy, not observed Chiang Mai behaviour.",
            "No automatic emergency charging, trip rescheduling or relocation after an infeasible trip.",
            "No route choice, weather, price optimisation, shared-site queue, degradation or fleet scaling.",
            "Warm-up is not proof of independence from initial SOC or validation against station logs.",
        ],
    }
