# Phrae Pilot Dataset Notes

This pilot dataset prepares Phrae for first-pass EV charging demand screening
and site comparison, with special attention to Den Chai. It is not yet
investment-grade.

## Current Coverage

- Province population is available in the existing HDX 2023 data:
  Phrae has 303,327 people in the province table.
- District population is available for 8 Phrae districts, including Mueang
  Phrae at 94,583 people and Den Chai at 18,468 people.
- DOH AADT data include 29 Phrae rows in `data/aadt_2566.csv`.
- Highest current seed AADT point is Route 101 Na Laem - Nong Ha at 19,509 AADT.
- Den Chai's local AADT count is not the highest, but Den Chai is strategically
  important because Route 11 and Route 101 traverse the area and Den Chai Railway
  Station serves as the rail gateway for Phrae province.
- Public web listings indicate PEA VOLTA Phrae #2 and broader PEA VOLTA network
  coverage, but operator-app verification is required for exact DC capacity and
  live availability.

## Public Source Cues

- PEA public EV charging information describes PEA VOLTA as an app-based charging
  network and lists supported AC/DC connector standards and charging power ranges.
- PEA fleet/green-energy public information states PEA VOLTA has nationwide
  coverage across most Thai provinces and supports quick-charge use on main routes.
- TripNiceDay public listings show PEA VOLTA Phrae #1 and #2 at/around PEA
  Mueang Phrae, but they must be treated as public-listing evidence only until
  verified in the PEA VOLTA app.
- Public railway references identify Den Chai Railway Station as the main railway
  station serving Phrae province; Thailand.go.th also frames the Den Chai -
  Chiang Rai - Chiang Khong dual-track railway as a future northern logistics
  corridor.

Useful URLs for follow-up:

- https://www.pea.co.th/en/knowledge/ev-charging
- https://www.pea.co.th/about-pea/sgi/green-energy/ev-fleet
- https://www.tripniceday.com/place/pea-volta-%E0%B9%81%E0%B8%9E%E0%B8%A3%E0%B9%88-1
- https://www.tripniceday.com/en/place/pea-volta-%E0%B9%81%E0%B8%9E%E0%B8%A3%E0%B9%88-2
- https://www.thailand.go.th/public/index.php/issue-focus-detail/001_08_022

## Files Added

- `data/hot_zones_phrae.csv`
- `data/poi_phrae_seed.csv`
- `data/aadt_phrae_seed.csv`
- `data/competitors_phrae_seed.csv`

## Important Limitations

- Charger competitor rows are public-listing or placeholder records until checked
  in operator apps or Google Maps.
- Exact public DC charger pins, guns, kW, open hours, price, and payment network
  must be verified before serious site-level capture modeling.
- Phrae province adoption constants are pilot assumptions, not DLT-calibrated
  province values.
- Hot zones are screening assumptions informed by POI, population, route role,
  rail-gateway role, and AADT, not observed station utilization.

## Den Chai Interpretation

Den Chai should not be evaluated only by district population. Its investment
case depends on:

1. Route 11 / Route 101 through-travel.
2. Rail-gateway demand from Den Chai Railway Station.
3. Roadside amenities and access around the main corridor.
4. Existing DC charger coverage on nearby gas-station routes.

## Next Verification Priorities

1. Audit PEA VOLTA, EV Station PluZ, EleXA, and dealer chargers in Mueang Phrae,
   Den Chai, and Route 11/101 gas stations.
2. Verify whether Den Chai has active public DC chargers near the railway station,
   route junctions, or major rest stops.
3. Confirm Den Chai railway station, Route 11/101 corridor, Phrae city core,
   Route 101 high-AADT axis, and Route 129 bypass POI pins.
4. Collect utilization/session signals where possible, especially for Den Chai
   route-stop demand versus Phrae city destination demand.
