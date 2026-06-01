# Khon Kaen Pilot Dataset Notes

This pilot dataset prepares Khon Kaen for first-pass EV charging demand
screening and site comparison. It is not yet investment-grade.

## Current Coverage

- Province population is available in the existing HDX 2023 data:
  Khon Kaen has 1,569,539 people in the province table.
- District population is available, including Mueang Khon Kaen at 661,992
  people in the current HDX district table.
- DOH AADT data include 60 Khon Kaen rows in `data/aadt_2566.csv`.
- Highest current seed AADT points include Route 2 Khon Kaen - Hin Lat
  at 53,895 AADT and Route 2 Tha Phra - Khon Kaen at 47,304 AADT.
- Public sources indicate existing destination AC charging at Central Khon Kaen
  and at least one EV Station PluZ listing in Mueang Khon Kaen, but operator-app
  verification is still required for exact DC capacity and live availability.

## Files Added

- `data/hot_zones_khon_kaen.csv`
- `data/poi_khon_kaen_seed.csv`
- `data/aadt_khon_kaen_seed.csv`
- `data/competitors_khon_kaen_seed.csv`

## Important Limitations

- Charger competitor rows mix public listings and placeholders until checked in
  operator apps or Google Maps.
- Exact public DC charger pins, guns, kW, open hours, price, and payment network
  must be verified before serious site-level capture modeling.
- Khon Kaen province adoption constants are pilot assumptions, not DLT-calibrated
  province values.
- Hot zones are screening assumptions informed by POI, population, and AADT, not
  observed station utilization.

## Next Verification Priorities

1. Audit all public DC chargers in Mueang Khon Kaen, especially Route 2, Central,
   PEA VOLTA, EV Station PluZ, and dealer/hotel chargers.
2. Verify charger power, connector count, and 24-hour access in operator apps.
3. Confirm Central Khon Kaen, KKU/Srinagarind, airport, BKS3, railway station,
   Kaen Nakhon, Ton Tann, and ring-road POI pins.
4. Collect utilization/session signals from operators where possible.
