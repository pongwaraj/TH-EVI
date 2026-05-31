"""Quick test of TH-EVI model for Chiang Mai pilot."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from th_evi.adoption import EVAdoptionModel
from th_evi.location import LocationDemandModel, LANDMARK_DB

m = EVAdoptionModel('\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48')
print('=== EV Adoption \u2014 Chiang Mai ===')
for y in [2025, 2030, 2035, 2040]:
    print(f'  {y}: share={m.get_ev_share(y)*100:.1f}%, EVs={m.get_ev_population(y):,}')

d = LocationDemandModel('\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48')
print()
print('=== Location Demand (2035) ===')
for loc_id in LANDMARK_DB:
    r = d.estimate_from_db(loc_id, 2035)
    print(f'  {r["name"]}: {r["daily_ev_visits"]} evs/day, {r["daily_kwh"]} kWh/day')
