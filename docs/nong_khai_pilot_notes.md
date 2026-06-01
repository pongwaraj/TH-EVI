# Nong Khai Pilot Dataset Notes

This pilot dataset prepares Nong Khai for first-pass EV charging demand
screening and site comparison. It is not yet investment-grade.

## Current Coverage

- Province population is available in the existing HDX 2023 data:
  Nong Khai has 349,107 people in the province table.
- District population is available for 9 districts, including Mueang Nong Khai
  at 105,037 people.
- DOH AADT data include 16 Nong Khai rows in `data/aadt_2566.csv`.
- Highest current seed AADT point is Route 2 Nam Suai - Friendship Bridge at
  33,247 AADT, with a high heavy-vehicle share.
- Public sources confirm the First Thai-Lao Friendship Bridge as the key
  Nong Khai-Vientiane border gateway. Charger operator data still needs app-level
  verification.

## Files Added

- `data/hot_zones_nong_khai.csv`
- `data/poi_nong_khai_seed.csv`
- `data/aadt_nong_khai_seed.csv`
- `data/competitors_nong_khai_seed.csv`

## Important Limitations

- Charger competitor rows are placeholders until checked in operator apps or
  Google Maps.
- Exact public DC charger pins, guns, kW, open hours, price, and payment network
  must be verified before serious site-level capture modeling.
- Nong Khai province adoption constants are pilot assumptions, not DLT-calibrated
  province values.
- Hot zones are screening assumptions informed by POI, population, border role,
  and AADT, not observed station utilization.

## Next Verification Priorities

1. Audit PEA VOLTA, EV Station PluZ, EleXA, EA Anywhere, and MG Super Charge in
   Mueang Nong Khai and along Route 2 to the Friendship Bridge.
2. Verify gas-station DC chargers on the Nam Suai - Friendship Bridge approach.
3. Confirm bridge, border checkpoint, railway station, bus terminal, riverfront,
   hospital, Tha Bo, and Phon Phisai POI pins.
4. Collect any utilization/session signals where possible, especially for
   cross-border and Route 2 intercity demand.
