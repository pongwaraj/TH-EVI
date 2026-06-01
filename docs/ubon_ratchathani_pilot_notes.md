# Ubon Ratchathani Pilot Dataset Notes

This pilot dataset prepares Ubon Ratchathani for first-pass EV charging demand
screening and site comparison. It is not yet investment-grade.

## Current Coverage

- Province population is available in the existing HDX 2023 data:
  Ubon Ratchathani has 1,536,681 people in the province table.
- District population is available for 25 districts, including Mueang Ubon
  Ratchathani at 238,145 people and Warin Chamrap at 162,245 people.
- DOH AADT data include 65 Ubon Ratchathani rows in `data/aadt_2566.csv`.
- Highest current seed AADT points include Route 231 Ubon ring road at 44,325
  AADT and Route 2050 Ubon - Trakan Phuet Phon at 41,822 AADT.
- Public web listings indicate PEA VOLTA Ubon Ratchathani #2, multiple PTT/EV
  Station PluZ-like listings, EA Anywhere, and EleXA candidates, but operator-app
  verification is required for exact DC capacity and live availability.

## Files Added

- `data/hot_zones_ubon_ratchathani.csv`
- `data/poi_ubon_ratchathani_seed.csv`
- `data/aadt_ubon_ratchathani_seed.csv`
- `data/competitors_ubon_ratchathani_seed.csv`

## Important Limitations

- Charger competitor rows mix public listings and placeholders until checked in
  operator apps or Google Maps.
- Exact public DC charger pins, guns, kW, open hours, price, and payment network
  must be verified before serious site-level capture modeling.
- Ubon Ratchathani province adoption constants are pilot assumptions, not
  DLT-calibrated province values.
- Hot zones are screening assumptions informed by POI, population, border role,
  and AADT, not observed station utilization.

## Next Verification Priorities

1. Audit PEA VOLTA, EV Station PluZ/PTT, EA Anywhere, EleXA, and dealer chargers
   around Central Ubon, Route 231 ring road, Warin Chamrap, and Route 24.
2. Verify charger power, connector count, 24-hour access, and live app status.
3. Confirm Central Ubon, ring road, airport, railway station, Warin Chamrap,
   Route 2050, Det Udom, Sirindhorn, and Chong Mek POI pins.
4. Collect utilization/session signals where possible, especially city ring-road
   versus Route 24 and Chong Mek border/tourism demand.
