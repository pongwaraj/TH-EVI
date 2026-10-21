# Public DC POI Hierarchy V2

Policy: `public_dc_poi_hierarchy_v2` (2026-10-21).

## Purpose and Scope

One shared policy is used by heat-map generation, legacy click classification,
and fixed-support allocation. Chiang Mai is the data-review pilot; reference
data for other provinces has not been re-surveyed. No UI, fleet-growth curve,
energy-per-session observation, competitor inventory, or investment forecast
is changed by this policy.

These weights are explicit screening assumptions, not calibrated vehicles/day,
observed charging events, or coefficients published by NREL. An airport's
presence does not establish observed taxi charging demand. Home-charging
access, travel patterns, public access and actual utilization still require
separate evidence. `forecast_available=false` remains enforced in the pilot.

## Hierarchy

| Relevance | Examples | Relative anchor weight | Kernel scale (km) |
| --- | --- | ---: | ---: |
| Mobility | Airport; bus/rail station; taxi rank | 26-40 | 1.8-3.0 |
| Commercial destinations | Shopping mall; community mall; supermarket | 24-38 | 1.6-2.5 |
| Services and long-dwell context | Hospital; university; hotel | 8-14 | 1.1-1.5 |
| Local supporting activity | Local market; cafe; office; school | 2-8 | 0.6-1.1 |
| Area labels / residential context | Neighborhood centre; apartment; housing estate | 0-6 | 0.5-1.2 |

`city_center` is a context label (10 points), not an independent DC demand
magnet. Unknown categories receive 2 points, not the previous implicit 14.
Generic `education` is deliberately weak until its subtype is known. A
university is distinguished from a primary/secondary school, but neither
automatically becomes a public-DC destination. Apartments are not hotels.

## Classification and Spatial Overlap

- Both heat-map and click analysis use the same classifier, including at zero
  distance. It examines all local evidence, not just the strongest three pins.
- City-core classification requires a nearby `city_center` label AND a nearby
  commercial destination. A neighborhood, district, school or office label
  alone stays suburban. Nearby transport-corridor evidence may establish a
  highway context, but a distant road or broad business-area halo may not.
- POI classification distance is bounded by the smaller of its kernel scale
  and 1.5 km. A POI kernel stops at twice its scale; this is not a road-distance
  or route-access model.
- Exact duplicate pins do not add weight. Pins within 350 m of the strongest
  anchor share a destination cluster: strongest pin + 10% of secondary pins,
  with the secondary contribution capped at 25% of the strongest pin.
- Other destination clusters contribute at 25%, and the full POI field is
  capped at 175% of its strongest cluster. Effective contributions are exposed
  separately from raw per-pin evidence. Clustering is deterministic and does
  not chain adjacent shops into an arbitrarily long corridor.
- Known seed-coordinate sources cannot claim a confidence multiplier above
  0.62 simply because a row's confidence label says high. Planned, closed,
  inactive and explicitly private POIs do not create public-DC attraction.
- Hot-zone `radius_km` is now the actual boundary of its decaying field; the
  old implicit 1.8-times extension is removed. Business-area envelopes remain
  contextual and cannot override the local classifier just by proximity.

## Screening Weight

For each support cell, let P be capture-adjusted POI evidence, T the legacy
traffic-model prior, and Z/B/D the capture-adjusted zone/business/district
context. The new relative weight is:

```
activity = max(P, 0)
traffic_prior = min(max(T, 0), activity)
context = min(max(Z, B, D, 0), max(1, activity))
weight = (activity + 0.35 * traffic_prior + 0.35 * context) / 0.22
```

The divisor reverses the legacy POI capture conversion into relative POI
points, keeping screening thresholds in comparable units. It is not a demand
uplift. Fixed-support allocation still normalizes the same total to 100%; it
does not create an energy budget. Zone, business and district labels use their
maximum, not a sum of multiple descriptions of the same catchment. Assumed
AADT cannot independently turn a weak neighborhood into a hotspot.
The minimum visibility weight is 1 point after the existing context/access
checks, so low-evidence areas can remain faint instead of disappearing just
because the scoring scale changed. Visibility is not proof of high demand.
An independent POI field of at least 5 relative activity points also passes
the context gate, even without a pre-labelled hot zone. This keeps a real
local hospital or retail destination visible without restoring an assumed
traffic floor or requiring it to sit inside a hand-authored zone.

District summaries retain administrative coverage, with zero heat and
`insufficient_evidence` where no support cells qualify. They do not manufacture
heat merely to cover every district.

## Chiang Mai Reference Corrections

- Saraphi Hospital: `18.68117016, 99.043176`, replacing a seed approximately
  3.38 km northwest. Coordinate source: [Healthcare Accreditation Institute](https://www.ha.or.th/TH/Hospitals/นโยบายเว็บไซต์/Details/1092);
  address corroboration: [Saraphi Hospital](https://sarapeehospital.go.th/).
- Yang Noeng Market: `18.7149701, 99.0344717`, replacing a seed approximately
  0.95 km south; category `local_market` rather than `market_tourism`.
  Source: [CMHY directory](https://www.cmhy.city/place/18089-Yang-Neang-Market).
- Saraphi town-centre seed: `neighborhood_center`, retaining the estimate flag.
- Chongfah and Prince Royal's College: `school`; CMU main campus: `university`.
- Grand Siri: `apartment`; Central Chiang Mai Airport: `shopping_mall`;
  Mahachok Park: `community_mall`; Starbucks at Kad Farang Mae Rim:
  `restaurant_cafe` sharing the mall catchment.

DLT Ror.1 BEV stock remains 17,002 / 460,081 passenger vehicles, checked against
the [DLT workbook dated 30 September 2026](https://web.dlt.go.th/statistics/load_file_select_new_car.php?t=3&data_file=1302).
This provincial share is not evidence of local public-charging customers.
No AADT count is invented or replaced with a nearby arterial maximum here.
The Chiang Mai population loader's older ADM2 fallback is a separate remaining
data issue; DOPA municipal and non-municipal coverage must be reconciled before
replacing it with an apparent district total.

## Evidence and Limitations

The qualitative distinction between public DC needs and long-dwell charging
is consistent with [DOE AFDC public charging guidance](https://afdc.energy.gov/fuels/electricity-charging-public)
and [infrastructure procurement guidance](https://afdc.energy.gov/fuels/electricity-infrastructure-development).
The numerical weights, 350 m grouping, radii and overlap factors are local
engineering assumptions and still need sensitivity analysis and out-of-sample
station validation. Similar neighboring businesses may serve distinct trips;
spatial clustering is only a bounded overlap heuristic, not proof of shared
visitors. Known private/planned states are excluded; unknown access is not
silently declared verified.

CSV changes must be ingested and parity-checked as a new reference release
before publishing to a DB-led deployment. This work does not modify the live
database or production deployment.
