"""Per-vehicle route and charging-opportunity sensitivity from pilot evidence.

The route distance and mean observed order energy are evidence. Daily travel
frequency, energy intensity and access/choice shares remain explicit scenario
inputs; the result is not a provincial or site customer forecast.
"""

from math import fsum, isclose

from .charging_energy import _efficiency, _number
from .charging_profiles import load_pilot_evidence


def route_evidence_catalog(province: str) -> dict | None:
    routes = load_pilot_evidence(province, "travel_routes")
    if routes is None:
        return None
    return {"province": routes["province"], "source": routes["source"],
            "attribution": routes["attribution"], "origins": routes["origins"],
            "destinations": routes["destinations"], "routes": routes["routes"],
            "forecast_enabled": False}


def normalized_route_preview(*, province: str, origin_id: str, destination_id: str,
                             outings_per_week: float, battery_kwh_per_km: float,
                             home_access_share: float, home_energy_share_if_access: float,
                             other_ac_share_of_remaining: float, dc_share_of_remaining: float,
                             dc_vehicle_efficiency: float) -> dict:
    for key, value, maximum in (
        ("outings_per_week", outings_per_week, 7),
        ("battery_kwh_per_km", battery_kwh_per_km, 1),
        ("home_access_share", home_access_share, 1),
        ("home_energy_share_if_access", home_energy_share_if_access, 1),
        ("other_ac_share_of_remaining", other_ac_share_of_remaining, 1),
        ("dc_share_of_remaining", dc_share_of_remaining, 1),
    ):
        _number(key, value, 0, maximum)
    if battery_kwh_per_km == 0:
        raise ValueError("battery_kwh_per_km must be greater than zero")
    _efficiency("dc_vehicle_efficiency", dc_vehicle_efficiency)
    routes = load_pilot_evidence(province, "travel_routes")
    operations = load_pilot_evidence(province, "observed_station_behavior")
    holdout = load_pilot_evidence(province, "observed_station_holdout")
    housing = load_pilot_evidence(province, "housing_and_home_charging")
    if not all((routes, operations, holdout, housing)):
        raise ValueError("Province has no complete route and station pilot evidence")
    route = next((row for row in routes["routes"] if row["origin_id"] == origin_id
                  and row["destination_id"] == destination_id), None)
    if route is None or route["round_trip_road_km"] is None:
        raise ValueError("Unknown or unsupported road route for this province")
    train_mean = holdout["train"]["mean_connector_kwh_per_order"]
    if train_mean <= 0 or operations["meaningful_orders"]["mean_connector_kwh"] <= 0:
        raise ValueError("Observed order energy must be positive")

    traction = route["round_trip_road_km"] * outings_per_week * battery_kwh_per_km

    def allocation(access_share: float) -> dict:
        home = traction * access_share * home_energy_share_if_access
        other_ac = (traction - home) * other_ac_share_of_remaining
        residual = traction - home - other_ac
        dc_battery = residual * dc_share_of_remaining
        unassigned = residual - dc_battery
        connector = dc_battery / dc_vehicle_efficiency
        balance = traction - fsum((home, other_ac, dc_battery, unassigned))
        if not isclose(balance, 0, abs_tol=1e-8, rel_tol=0):
            raise ValueError("Route energy balance does not close")
        return {"home_battery_kwh": home, "other_ac_battery_kwh": other_ac,
                "public_dc_battery_kwh": dc_battery,
                "unassigned_battery_kwh": unassigned,
                "public_dc_connector_kwh": connector,
                "meta_mall_meaningful_order_equivalents": connector / train_mean,
                "balance_error_kwh": balance}

    sensitivity = []
    for label, access in (("lower_home_access", max(0.0, home_access_share - 0.2)),
                          ("input_home_access", home_access_share),
                          ("higher_home_access", min(1.0, home_access_share + 0.2))):
        sensitivity.append({"case": label, "home_access_share": access, **allocation(access)})
    return {
        "status": "assumption_sensitivity_not_calibrated", "forecast_enabled": False,
        "heatmap_changed": False, "province": routes["province"],
        "scope": "one_vehicle_one_selected_round_trip_on_each_assumed_outing_day",
        "route": route,
        "scenario_inputs": {"outings_per_week": outings_per_week,
                            "battery_kwh_per_km": battery_kwh_per_km,
                            "home_access_share": home_access_share,
                            "home_energy_share_if_access": home_energy_share_if_access,
                            "other_ac_share_of_remaining": other_ac_share_of_remaining,
                            "dc_share_of_remaining": dc_share_of_remaining,
                            "dc_vehicle_efficiency": dc_vehicle_efficiency},
        "weekly_traction_battery_kwh_per_vehicle": traction,
        "home_access_sensitivity": sensitivity,
        "session_energy_reference": {
            "station": operations["station_scope"],
            "train_mean_connector_kwh_per_meaningful_order": train_mean,
            "holdout_mean_connector_kwh_per_meaningful_order": holdout["holdout"]["mean_connector_kwh_per_order"],
            "holdout_absolute_percentage_error": holdout["prediction_using_train_mean"]["absolute_percentage_error"],
            "station_demand_holdout_ready": holdout["station_demand_holdout_ready"],
            "all_q3_mean_connector_kwh_per_meaningful_order": operations["meaningful_orders"]["mean_connector_kwh"],
            "order_definition": operations["meaningful_orders"]["definition"]},
        "housing_reference": {"year": housing["survey_housing"]["year"],
                              "population": housing["survey_housing"]["population"],
                              "ev_owner_housing_mix_known": housing["ev_owner_housing_mix"] is not None,
                              "private_home_ac_rates_known": all(
                                  value is not None for key, value in housing["private_home_ac_access"].items()
                                  if key.endswith("_probability"))},
        "limitations": [
            "Route is an example, not observed destination choice or travel frequency.",
            "Home/other AC/DC shares and vehicle energy use are caller assumptions, not fitted probabilities.",
            "Energy allocation is averaged per week; no trip-order or SOC feasibility is checked here.",
            "Order equivalents are based on Meta Mall observed charging size, not unique vehicles or site capture.",
            "No provincial fleet scaling, station choice, queues or competitor allocation is performed.",
        ],
    }
