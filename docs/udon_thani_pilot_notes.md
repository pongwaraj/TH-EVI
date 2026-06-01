# Udon Thani Pilot Dataset Notes

This pilot dataset prepares Udon Thani for first-pass EV charging demand
screening and site comparison. It is not yet investment-grade.

## Current Coverage

- Province population is available in the existing HDX 2023 data:
  Udon Thani has 925,466 people in the province table.
- District population is available for 20 districts.
- DOH AADT data include 56 Udon Thani rows in `data/aadt_2566.csv`.
- Highest current seed AADT points include Route 22 Nong Kham - Nong Han
  at 33,979 AADT and Route 216 western ring road at 31,736 AADT.
- Public sources give strong POI anchors for Central Udon and UD Town.

## Files Added

- `data/hot_zones_udon_thani.csv`
- `data/poi_udon_thani_seed.csv`
- `data/aadt_udon_thani_seed.csv`
- `data/competitors_udon_thani_seed.csv`

## Important Limitations

- Charger competitor rows are mostly placeholders until checked in operator apps
  or Google Maps.
- Exact public DC charger pins, guns, kW, open hours, and payment network must
  be verified before serious site-level capture modeling.
- Udon Thani province adoption constants are pilot assumptions, not DLT-calibrated
  province values.
- Hot zones are screening assumptions informed by POI and AADT, not observed
  station utilization.

## Next Verification Priorities

1. Audit all public DC chargers in Mueang Udon Thani and along Route 2/22/216.
2. Verify mall charger presence at Central Udon and UD Town.
3. Confirm airport, bus, railway, hypermarket, and ring-road POI pins.
4. Collect operator utilization/session signals where possible.
