"""Tests for location demand model."""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from th_evi.location import LocationDemandModel, LANDMARK_DB


def test_demand_increases_with_year():
    demand = LocationDemandModel()
    r2025 = demand.estimate_from_db('cm_superhighway', 2025)
    r2035 = demand.estimate_from_db('cm_superhighway', 2035)
    assert r2025['daily_ev_visits'] < r2035['daily_ev_visits']

def test_highway_more_than_city():
    demand = LocationDemandModel()
    highway = demand.estimate_from_db('cm_superhighway', 2030)
    city = demand.estimate_from_db('cm_thaphae', 2030)
    assert highway['aadt_used'] > city['aadt_used']

def test_all_locations_return_results():
    demand = LocationDemandModel()
    for loc_id in LANDMARK_DB:
        r = demand.estimate_from_db(loc_id, 2030)
        assert r['daily_ev_visits'] >= 0
        assert r['daily_kwh'] >= 0

def test_energy_per_type():
    demand = LocationDemandModel()
    r = demand.estimate(18.795, 99.010, 2030, location_type='highway')
    assert r['daily_kwh'] > 0

if __name__ == '__main__':
    test_demand_increases_with_year()
    test_highway_more_than_city()
    test_all_locations_return_results()
    test_energy_per_type()
    print("OK: All location tests passed")
