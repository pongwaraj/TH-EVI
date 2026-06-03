# AI Model Data Contract

Last updated: 2026-06-03

This document defines what a lower-cost AI is allowed to change and what it must preserve when working on TH-EVI data integration tasks.

**Read this file before touching any code or data.** If you are unsure whether a task is safe, stop and ask the human owner.

---

## You Are A Data Preparation Agent

Your job is to collect, clean, and stage data. You are not a model designer.

You may:
- Add or clean CSV seed files
- Normalize district names and coordinates
- Populate bounded weighting multipliers
- Write tests for deterministic transforms
- Update docs

You must not:
- Redesign the heat map formula
- Change `competitive_capture_share` semantics
- Change station recommendation logic
- Remove or rename any field in `/api/click-analysis` response
- Replace click-analysis explainability fields
- Alter mobile interaction behavior
- Write final truth-claims about model behavior without pointing to the exact code line

---

## Required Reading Order

Before starting any task, read these files in order:

1. `docs/data_injection_work_order.md` — task rules and per-province workflow
2. `docs/data_injection_progress.md` — current status of every province
3. `docs/dopa_injection_handoff.md` — DOPA population weighting spec
4. Pilot notes for the target province in `docs/*_pilot_notes.md` if available
5. Existing data files in `data/` for the target province

---

## Why This Contract Exists

TH-EVI has multiple scoring layers that interact:

1. Base traffic/adoption demand
2. POI attraction field
3. Hot-zone field
4. Competitor signal and penalty
5. District-node community coverage
6. Surface/access screening

Lower-cost models can prepare structured data, but must not freely modify the logic contract between these layers.

---

## Proof Requirement

**Do not describe behavior as changed unless you can point to the exact code path where the behavior changed.**

These are not the same thing:

| What you did | What it is NOT |
|---|---|
| Added a CSV loader | Activating a weight in scoring |
| Added CSV rows | Verifying a province layer |
| Passing tests | Confirming source provenance |

If your change only adds a loader but the scoring function does not call it, you must say "loader added, scoring not yet wired."

---

## API Fields That Must Be Preserved

For `/api/click-analysis`, never remove or rename these fields:

```
lat, lon, province, year, scenario, mode
location_type, aadt_used, fleet_ev_share_pct, charge_probability_pct
raw_base_sessions, base_sessions, gross_area_demand_sessions
zone_boost_sessions, poi_boost_sessions, district_boost_sessions
spatial_boost_sessions, competitor_penalty_sessions, net_sessions_per_day
daily_kwh, daily_revenue
top_zones, top_pois, top_districts, top_competitors
eligibility_status, surface_type, access_ok, urban_eligible
confidence, warnings
```

---

## Heat Map Modes That Must Be Preserved

For `/api/heatmap`, preserve both modes and their meaning:

**`mode=urban`** — city-scale hotspots using POI + hot zones + competitor signal

**`mode=community`** — broader coverage using district nodes + POI + hot zones + competitor signal

---

## Data File Conventions

### District node seed files

Pattern: `data/district_nodes_<province_slug>.csv`

Required columns:
```
node_id, district_name, name, node_type, lat, lon,
radius_km, confidence_multiplier, notes
```

### Other seed files

- `data/poi_<province_slug>_seed.csv`
- `data/hot_zones_<province_slug>.csv`
- `data/competitors_<province_slug>_seed.csv`
- `data/aadt_<province_slug>_seed.csv`

---

## Constraints On Weighting

Any new weighting from DOPA, DLT, or population data must be:

- **bounded**: use a min/max clamp, never open-ended multipliers
- **monotonic**: larger population = higher weight, no reversals
- **explainable**: one sentence should describe why the weight changes
- **reversible**: removing the weight restores the previous output

Recommended pattern:
```
new_weight = existing_weight * clamp(min, max, f(population))
```

Not allowed:
```
replace existing district scoring entirely with population-only logic
```

---

## Confidence Labels

Use exactly these labels. Never promote a row if a required field is guessed.

| Label | Meaning |
|---|---|
| `high` | Official source or direct Google Maps/network app verification with matching coordinates |
| `medium_high` | Strong public source but one technical field still uncertain |
| `medium` | Credible source, but coordinates or hardware need verification |
| `low` | Plausible but needs field check |
| `unknown` | Placeholder only, not proposal-ready |

Never use `high` confidence for:
- seed-estimated coordinates
- inferred station hardware (kW, gun count)
- unofficial AADT rewrites
- district matches with ambiguity

---

## Review Standard

After work from a lower-cost AI, a stronger model or human must confirm:

1. The patch stayed inside the requested scope
2. CSV schemas remain consistent with the column definitions above
3. Tests are focused and not trivially passing
4. No magical constants were introduced without explanation
5. App output is still explainable in proposal language
6. Progress log claims match the actual changed files and source rows
7. Official-source labels were cross-checked, not inferred
