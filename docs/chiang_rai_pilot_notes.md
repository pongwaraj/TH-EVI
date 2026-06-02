# Chiang Rai Pilot Dataset Notes

This pilot dataset prepares Chiang Rai for first-pass EV charging demand
screening and site comparison. Chiang Rai is stronger than many northern pilot
provinces because it has a large population base, higher verified EV stock, an
airport, major tourism corridors, and border-gateway flows to Mae Sai and
Chiang Khong.

## Current Coverage

- Verified DOPA 2568 province population: 1,295,922 people and 603,627
  households.
- Key DOPA district rows include Mueang Chiang Rai 109,804 people, Phan 107,623,
  Mae Suai 78,879, Mae Sai 77,498, Mae Fa Luang 77,387, Mae Chan 69,678, and
  Chiang Khong 24,898.
- Verified DLT April 2026 รย.1 passenger-car fleet: 178,675 vehicles, with
  3,545 BEV and 404 PHEV. Chargeable EV stock is 3,949 vehicles, or about
  2.21% of the รย.1 passenger-car fleet.
- DOH AADT 2566 has 78 Chiang Rai rows. Highest seed point is Route 1
  Rong Khun - Mae Korn at 31,773 AADT.
- Key corridors are Route 1 city/Rong Khun/Mae Sai, Route 118 Chiang
  Mai-Phayao-Chiang Rai, Route 131 city bypass, Route 1020 to Chiang Khong,
  and tourism corridors around Doi Tung / Golden Triangle.

## Files Added

- `data/chiang_rai_market_profile.csv`
- `data/aadt_chiang_rai_seed.csv`
- `data/poi_chiang_rai_seed.csv`
- `data/competitors_chiang_rai_seed.csv`
- `data/hot_zones_chiang_rai.csv`

## POI / Competitor Sweep

The seed POI layer includes Central Chiang Rai, Robinson, Big C, Mae Fah Luang
Chiang Rai Airport, Chiang Rai Bus Terminal 1 and 2, Wat Rong Khun, Singha Park,
Baan Dam Museum, Wat Rong Suea Ten, Saturday Walking Street, Mae Sai, Chiang
Khong, Doi Tung, Golden Triangle, and healthcare anchors.

The current charger competitor layer is still audit-oriented:

- OSM identifies 3 charging-station records in Chiang Rai province, including a
  24/7 candidate near the Central Chiang Rai city core, one Route 118 / Mae Kha
  Chan corridor candidate, and a BYD-branded northern corridor candidate.
- PEA VOLTA, EV Station PluZ, EA Anywhere, EleXA, and MG Super Charge should be
  checked in their operator apps before being treated as confirmed competitors.
- Exact pin, live status, connector count, DC kW, access, and opening hours are
  not yet investment-grade unless explicitly listed in an operator source.

## Interpretation

Chiang Rai should be modeled as a multi-core province rather than a single city:

1. City retail/destination core around Central Chiang Rai.
2. Route 1 high-AADT and tourism flow around Wat Rong Khun / Mae Korn.
3. Route 118 intercity charging from Chiang Mai / Phayao.
4. Airport-Ban Du-Mae Fah Luang University corridor.
5. Mae Sai and Chiang Khong border-gateway corridors.
6. Doi Tung / Golden Triangle tourism corridor.

## Next Verification Priorities

1. Audit charger competitors in PEA VOLTA, EV Station PluZ, EleXA, EA Anywhere,
   MG Super Charge, and Google Maps.
2. Verify whether Central Chiang Rai / Big C / Route 1 / Route 118 chargers are
   public, DC-capable, and live.
3. Confirm candidate site pins and parking/access conditions for Central Chiang
   Rai, Route 1/Rong Khun, Route 118, airport, Mae Sai, and Chiang Khong.
4. Collect utilization/session/kWh signals from operators if possible.
