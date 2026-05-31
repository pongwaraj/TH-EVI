"""
TH-EVI Model Recalibration & Re-analysis

Fixes three bugs:
1. DLT parser column indexing (was reading empty cells for BEV)
2. S-curve calibrated to 0.35% instead of real ~24% BEV share
3. Traffic model applied to dedicated charging hub (needs fleet-based model)
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from th_evi.adoption import EVAdoptionModel, estimate_fleet_ev_share
from th_evi.location import StationDemandModel


def show_calibration():
    print("=" * 68)
    print("MODEL CALIBRATION  --  THAILAND BEV SHARE OF NEW PASSENGER CARS")
    print("=" * 68)
    print(f"  {'Year':>4}  {'National%':>10}  {'CM new car%':>12}  {'Fleet EV%':>10}  {'CM EV Pop':>10}")
    print("-" * 68)

    national = EVAdoptionModel(province="default", use_fleet_model=False)
    cm = EVAdoptionModel(province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48")
    cm_new_only = EVAdoptionModel(province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48", use_fleet_model=False)

    for y in range(2023, 2037):
        nat = national.get_ev_share(y) * 100
        cm_share = cm.get_ev_share(y) * 100
        fleet = estimate_fleet_ev_share(y, "\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48") * 100
        ev_pop = cm.get_ev_population(y)  # fleet-accumulated
        print(f"  {y:>4}  {nat:>9.1f}%  {cm_share:>11.1f}%  {fleet:>9.3f}%  {ev_pop:>10,}")


def show_station_forecasts():
    print("\n" + "=" * 68)
    print("CM CULTURAL CENTER EV SUPER HUB  --  12 stalls, 720kW")
    print("Forecast: Daily sessions and kWh (peak season)")
    print("=" * 68)

    sm = StationDemandModel(province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48")
    scenarios = ["low", "base", "best"]
    years = [2026, 2027, 2028, 2030, 2032, 2035]

    header = f"  {'Year':>4}"
    for s in scenarios:
        header += f"  {s:>5}sess  {s:>5}kWh"
    header += f"  {'Util%':>6}"
    print(header)
    print("-" * len(header))

    for y in years:
        line = f"  {y:>4}"
        for s in scenarios:
            r = sm.estimate(year=y, scenario=s, stalls=12)
            line += f"  {r['daily_sessions']:>5}  {r['daily_kwh']:>5,.0f}"
        line += f"  {r['utilization_pct']:>5.1f}%"
        print(line)


def show_annual_summary():
    print("\n" + "=" * 68)
    print("ANNUAL ENERGY FORECAST  --  CM SUPER HUB (Base case)")
    print("=" * 68)
    print(f"  {'Year':>4}  {'Daily kWh':>10}  {'Annual MWh':>11}  {'Util%':>6}")
    print("-" * 68)

    sm = StationDemandModel(province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48")
    for y in range(2026, 2037):
        r = sm.estimate(year=y, scenario="base", stalls=12)
        annual_mwh = r['daily_kwh'] * 365 / 1000
        print(f"  {y:>4}  {r['daily_kwh']:>8,.0f}  {annual_mwh:>9,.1f}  {r['utilization_pct']:>5.1f}%")


def compare_old_vs_new():
    print("\n" + "=" * 68)
    print("OLD vs NEW MODEL COMPARISON  (2026)")
    print("=" * 68)

    old_national = lambda y: 0.50 / (1 + np.exp(-0.55 * (y - 2035)))
    old_share = old_national(2026) * 100

    new_national = EVAdoptionModel(province="default", use_fleet_model=False)
    new_nat_share = new_national.get_ev_share(2026) * 100

    cm_model = EVAdoptionModel(province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48")
    cm_new_share = cm_model.get_ev_share(2026) * 100

    fleet_ev_share = estimate_fleet_ev_share(2026, "\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48") * 100
    cm_ev_pop = cm_model.get_ev_population(2026)

    print(f"  National new-car BEV share:")
    print(f"    OLD (wrong DLT):  {old_share:.2f}%")
    print(f"    NEW (FTI data):   {new_nat_share:.1f}%")
    print(f"    FTI actual 2025:  23.9%")
    print(f"  CM new-car BEV share: {cm_new_share:.1f}%")
    print(f"  CM fleet EV share:    {fleet_ev_share:.3f}%")
    print(f"  CM fleet EV population: {cm_ev_pop:,}")
    print(f"  CM fleet size:          350,000 (passenger cars)")
    sm = StationDemandModel(province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48")
    print(f"  Station (Base) daily:   {sm.estimate(year=2026, scenario='base', stalls=12)['daily_sessions']} sessions")


def show_scenario_matrix():
    print("\n" + "=" * 68)
    print("SCENARIO MATRIX  --  Daily sessions at CM Super Hub")
    print("=" * 68)
    print(f"  {'Year':>4}  {'Low sess':>9}  {'Base sess':>10}  {'Best sess':>10}  {'Best/Util':>9}")
    print("-" * 68)

    sm = StationDemandModel(province="\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48")
    for y in [2026, 2027, 2028, 2029, 2030, 2032, 2035]:
        low = sm.estimate(year=y, scenario="low", stalls=12)
        base = sm.estimate(year=y, scenario="base", stalls=12)
        best = sm.estimate(year=y, scenario="best", stalls=12)
        print(f"  {y:>4}  {low['daily_sessions']:>8}  {base['daily_sessions']:>9}  {best['daily_sessions']:>9}  {best['utilization_pct']:>7.1f}%")


if __name__ == "__main__":
    show_calibration()
    show_station_forecasts()
    show_annual_summary()
    compare_old_vs_new()
    show_scenario_matrix()
