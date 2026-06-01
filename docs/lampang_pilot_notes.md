# Lampang Pilot Dataset Notes

This pilot dataset makes Lampang usable for first-pass EV charging demand
screening. It is not yet investment-grade.

## Current Coverage

- Province and district population are available from the HDX Thailand 2023
  population tables already in `data/`.
- DOH AADT data include Lampang rows in `data/aadt_2566.csv`. The highest current
  Lampang count in the seed extract is Route 1 Ko Kha - Samakkhi at 56,026 AADT.
- Public web listings confirm at least one Lampang province EV charging station
  with DC CCS 120 kW, CHAdeMO 60 kW, and AC Type2 22 kW at 163 Phahonyothin Road.
- Central/Tops public listing provides a coordinate anchor for Central Lampang:
  18.2821697, 99.4762164.

## Files Added

- `data/hot_zones_lampang.csv`
- `data/competitors_lampang_seed.csv`
- `data/poi_lampang_city_seed.csv`
- `data/aadt_lampang_seed.csv`

## Important Limitations

- Most charger competitors are placeholders until verified in Google Maps or
  operator apps.
- Exact kW, guns, open hours, and public availability for Lampang chargers still
  need field/app verification.
- Lampang province adoption constants are not yet calibrated from DLT data.
- Heat zones are expert screening assumptions, not observed session data.

## Next Verification Priorities

1. Verify all public DC chargers in Mueang Lampang and nearby corridors.
2. Confirm exact pins, guns, kW, open hours, network, and payment app.
3. Add site-level POIs around Central Lampang, Big C, Route 1, and the bypass.
4. Collect any operator utilization signal similar to the Spark Chiang Mai input.
