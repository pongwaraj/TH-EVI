# Chiang Mai Hot Area and Heat Map Notes

These notes capture working assumptions for Chiang Mai EV charging heat-map
analysis. They are meant to explain the logic behind the machine-readable hot
zone dataset in `data/hot_zones_chiang_mai.csv`.

## Core Logic

A hot zone is not the same as a good station site.

The model should separate two layers:

1. Area heat: total addressable charging demand around a zone.
2. Point capture: the share a specific pinned site can win after accounting for
   access, visibility, parking, station power, brand, price, and competitors.

This prevents the model from overestimating weak sites in hot corridors. Punn
Suk San Kamphaeng is the current cautionary example: the corridor has demand,
but the exact site readiness is not strong enough to inherit the full heat-map
signal.

## Executive Heat Map Output

For CEO-level screening, the map should show three views:

- Heat: total local demand pool.
- Competition: demand already absorbed by existing chargers.
- Capture: estimated sessions/day if a new pin is placed at that point.

The output for a pinned point should include conservative, base, and upside
sessions/day, plus the key reason for the score.

## Ground-Truth Anchors

### Super EV Hub / Old Chiang Mai Cultural Center

Field exploration indicates:

- Typical volume: about 130 charging sessions/day.
- Peak high-season volume: about 300 sessions/day.

This is a major calibration anchor for the Airport-Central-Cultural Center
zone. It proves that the surrounding heat is real, not only inferred from POI
density.

### PEA Volta Nong Hoi

User-provided insider information indicates:

- Revenue: about 30,000 THB/day.
- Implied sessions: about 130 sessions/day, depending on kWh/session and tariff.

This site should not be used as a pure location benchmark because PEA may have
material electricity-cost advantages. It is still useful as a proof point for
city-side high-throughput demand.

## Current Hot Area Ranking

### 1. Airport / Central Airport / Cultural Center

Very hot. Demand comes from airport traffic, Central Chiang Mai Airport,
hotels, local traffic, tourist/rental vehicles, ride-hailing, and hospital
traffic on the Mahidol side.

Existing competition is strong: Super EV Hub, EleXA PT Chiang Mai 8,
ReverSharger Mahidol, EA Anywhere, EV Station PluZ, and nearby brand chargers.

Central Airport with 720 kW distributed power and 12 guns should be modeled as
a strong capture site if it has clear roadside visibility, easy access, and
surface parking.

Working Central Airport estimate:

- Conservative: 100-120 sessions/day.
- Confident base: 140-170 sessions/day.
- High-season / strong execution: 200-260 sessions/day.
- Extreme peak day: possible near 300 sessions/day, but not a base case.

### 2. Fa Ham / Central Festival / Big C Extra / Green Park

Major retail and corridor cluster. Strong POI density, residential growth, and
Route 118/Superhighway traffic. Competition is already dense: Tesla Big C
Extra, EA My Hip Condo, Green Park/Fair Super Charge, Meta Mall, and related
city-north chargers.

This area is attractive, but a new site must beat incumbents on access,
visibility, and parking confidence.

### 3. Nimman / Maya / One Nimman / CMU / Suan Dok

Lifestyle, tourist, expat, student, condo, and hospital demand. The heat signal
is strong, but DC hub execution is difficult because parking and access are
often constrained.

Good for destination or compact urban charging if the site has exceptional
parking control.

### 4. Hang Dong / Kad Farang / Route 108 / Mae Hia

Affluent residential and tourism corridor. Competition appears less dense than
the inner-city airport/Fa Ham clusters. Route 108 has strong traffic potential.

A true roadside site with food, restroom, and easy access may perform well.

### 5. Mae Rim / Chotana / Route 107

Tourism corridor with resorts, cafes, family trips, and north-side residential
demand. Weekday demand may be weaker than Airport or Fa Ham, but weekend and
holiday demand can be strong.

### 6. San Sai / Mae Jo / Route 118

Strong residential growth and Route 118 traffic. However, existing chargers are
already shaping the catchment: EleXA Route 118, Evolt San Sai, Meta Mall, and
Green Park/Fair Super Charge.

Site-level capture is sensitive to exact road frontage and ease of entry.

### 7. San Kamphaeng / Bo Sang / Mae On

Corridor demand exists from residential growth and tourism toward Bo Sang, Mae
On, hot springs, and Mae Kampong. However, the Punn Suk case shows that heat
alone can overstate performance if the project is not yet a strong destination
or lacks immediate road pull.

Use conservative capture assumptions unless the site has strong frontage and
clear amenities.

### 8. Old City / Tha Phae / Night Bazaar

Tourist and hotel density is high, but DC fast-charging execution is hard:
limited parking, narrow streets, and access friction. Often better suited to
destination AC or small-format charging than high-throughput DC hubs.

## Data Collection Priorities

For each candidate zone, collect:

- Existing charger coordinates, guns, kW, brand, opening hours, and public
  availability.
- Field-observed sessions/day where possible.
- Parking layout, ingress/egress, visibility, signage, and queue area.
- POI density by type: mall, airport, hospital, hotel, university, residential,
  tourist attraction, food/restroom anchor.
- Traffic proxies: AADT, corridor type, directionality, peak season uplift.
- Price and tariff assumptions where known.

## Database Threshold

Store as database-ready CSV/JSON once a data point affects repeatable scoring:

- A station has verified lat/lon, guns, and power.
- A POI is used in hot-zone scoring.
- A field observation changes a calibration anchor.
- A candidate site has a scenario estimate used for investor or executive
  discussion.

Keep narrative interpretation in this document and structured values in CSV.
