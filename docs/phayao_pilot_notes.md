# Phayao Pilot Dataset Notes

This pilot dataset prepares Phayao for first-pass EV charging demand screening
and site comparison. It is not yet investment-grade.

## Current Coverage

- Province population is available in the existing HDX 2023 data:
  Phayao has 280,153 people in the province table.
- District population is available for 9 districts, including Mueang Phayao at
  79,811 people.
- DOH AADT data include 33 Phayao rows in `data/aadt_2566.csv`.
- Highest current seed AADT point is Route 1 Mae Ka - Pratu Chai at 37,625 AADT.
- Public web listings indicate PEA VOLTA Phayao #1 and a nearby PEA VOLTA Phayao
  #2 reference, but operator-app verification is required for exact DC capacity,
  live availability, and public access.

## Files Added

- `data/hot_zones_phayao.csv`
- `data/poi_phayao_seed.csv`
- `data/aadt_phayao_seed.csv`
- `data/competitors_phayao_seed.csv`

## Important Limitations

- Charger competitor rows are mostly public-listing or placeholder records until
  checked in operator apps or Google Maps.
- Exact public DC charger pins, guns, kW, open hours, price, and payment network
  must be verified before serious site-level capture modeling.
- Phayao province adoption constants are pilot assumptions, not DLT-calibrated
  province values.
- Hot zones are screening assumptions informed by POI, population, and AADT, not
  observed station utilization.

## Next Verification Priorities

1. Verify PEA VOLTA Phayao #1 and #2 in the PEA VOLTA app, including exact pins,
   connectors, kW, and live status.
2. Audit Route 1 gas stations/rest stops around Mae Ka, Pratu Chai, and city
   approach areas for DC chargers.
3. Confirm Kwan Phayao, city core, University of Phayao, bus terminal, hospital,
   Mae Chai, Dok Khamtai, and Chiang Kham POI pins.
4. Collect utilization/session signals where possible, especially for Route 1
   travel demand versus local destination charging.
