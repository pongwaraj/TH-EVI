# Province Data Injection Progress

Last updated: 2026-06-03

This file is the shared progress tracker for AI agents working on province data injection.

Before starting work, read this file and choose one province with a clear next action. After finishing, update the relevant row and append a short work log entry.

Status values:

- `not_started`: no usable province layer yet
- `partial_csv`: some seed files exist, but gaps remain
- `staged_csv`: complete enough CSV seed package exists
- `schema_needed`: data is ready, but DB reference tables are missing
- `imported_db`: imported into DB reference tables
- `verified`: app/API checks pass and data is proposal-ready
- `blocked`: cannot proceed without source access, schema decision, or human review
- `provisional`: work was added, but a stronger review has not yet confirmed that the log claims match the code and sources

## Logging Rules

Every future work-log entry must separate:

- what changed in code
- what changed only in CSV
- what is source-verified
- what is still estimated

Never write "verified", "active", or "official-source derived" without direct evidence from the files and a cross-check if relevant.

## Audit Note

Parts of the historical log below were written before the stricter evidence rules were added.
Treat older entries as **provisional** unless a stronger review has reconfirmed the claims against code and source files.

Specific entries that contain unconfirmed strong claims:

- **2026-06-03 DOPA batch**: claimed "48/48 passed" and "all 12 provinces load correctly with population weights" — test command not recorded; scoring activation not confirmed with a code-line reference. Do not treat this as verified until `th_evi/spatial.py → district_node_field()` is read and the `population_weight` multiply line is confirmed.
- **2026-06-03 Lamphun/Nan batch**: AADT rows claimed as "from DOH aadt_2566.csv" — cross-check match rate was not recorded. Treat as `seed_estimate` confidence until a route+km+aadt cross-check is completed.
- **2026-06-03 DB batch**: "48/48 passed" — test command not recorded. DB ingestion rows (928 district_population, 163 aadt_segments, etc.) are plausible but were not independently verified against source files.

## Current Province Matrix

| Province | Slug | AADT | DLT | DOPA | POI | Competitors | District Nodes | Heat Zones | DB Status | Current Status | Next Action |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| Chiang Mai | chiang_mai | partial | raw_global | staged_csv | partial | partial_verified | partial | partial | ref_imported | provisional | Reconfirm DOPA scoring activation; verify competitor accuracy. |
| Chiang Rai | chiang_rai | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Review POI/competitor coverage and reconfirm source claims. |
| Lampang | lampang | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Add missing POI detail and verify competitor/source claims. |
| Lamphun | lamphun | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Reconfirm source claims and POI/competitor accuracy. |
| Nan | nan | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Reconfirm source claims and POI/competitor accuracy. |
| Phayao | phayao | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Verify POI/competitors and reconfirm DOPA scoring status. |
| Phrae | phrae | partial | raw_global | staged_csv | partial_detailed | partial_detailed | partial | partial | ref_imported | provisional | Verify detailed seed rows; audit Den Chai competitors. |
| Khon Kaen | khon_kaen | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Verify central competitors and recheck district-node scoring claims. |
| Udon Thani | udon_thani | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Verify city/ring-road competitors and recheck district-node scoring claims. |
| Ubon Ratchathani | ubon_ratchathani | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Verify Central/ring-road/airport competitors and recheck district-node scoring claims. |
| Nong Khai | nong_khai | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | provisional | Verify border/city competitors and recheck district-node scoring claims. |
| Mae Hong Son | mae_hong_son | partial | raw_global | staged_csv | partial | partial | partial | partial | ref_imported | blocked | Compare `data/aadt_mae_hong_son_seed.csv` against DOH `aadt_2566.csv` on route+km+aadt. Rows that do not match must be downgraded to `seed_estimate` confidence and DOH label removed. Until cross-check is complete, do not use this province as an AADT reference. |

Legend:

- `raw_global`: data exists in a global raw file but has not been injected into province reference tables.
- `partial`: some seed data exists but should not be treated as complete.
- `partial_verified`: some rows have stronger verification, but the province layer still needs normalization.
- `partial_detailed`: detailed seed files exist for part of the province layer.
- `missing`: no meaningful province-specific seed file is present yet.
- `provisional`: historical or recent work exists, but claims have not yet been fully reconciled against code and source files.
- `ref_imported`: reference data (AADT, POI, competitors, district population) has been imported into DB reference tables from CSV seed files.

## Layer Completion Definition

### AADT

Complete when the province has:

- major highway corridors
- city/ring-road corridors where relevant
- route number, segment name, year, AADT, coordinate or segment midpoint
- confidence and source

### DLT

Complete when the province has:

- active fleet or new registration by province
- BEV count or fuel-type split
- year/month
- source and confidence

### DOPA

Complete when the province has:

- province population
- district population
- households if available
- year
- source and confidence
- district matching to `district_nodes_<province_slug>.csv`

### POI

Complete when the province has:

- transport anchors
- retail anchors
- health/education/government anchors
- tourism or border anchors where relevant
- coordinates, category, demand role, source, confidence

### Competitors

Complete when the province has:

- DC fast charge competitors
- important AC/location competitors marked separately
- network/operator
- gun count and kW if verified
- live status if available
- source, verification status, confidence

### District Nodes

Complete when:

- major districts have community anchor nodes
- coordinates represent realistic town centers or transport/retail nodes
- DOPA population can be matched or safely defaults to weight 1.0

## Work Log

### 2026-06-03 - Tracker created

- Created shared work order and progress tracker.
- Current matrix was initialized from files visible in `data/`.
- No DB reference schema has been added yet.
- Next engineering task: add reference DB schema or keep province data in CSV until schema is approved.

### 2026-06-03 - Stronger Review Audit

- Scope: tighten rules for lower-cost AI after finding claim-vs-code and claim-vs-source mismatches.
- Findings:
  - DOPA enrichment rows exist, but scoring activation must be proven in code before logs say it is active.
  - Mae Hong Son AADT seed needs official-source cross-check repair before it can be treated as DOH-derived.
  - Passing tests do not prove that source claims are correct.
- Status impact:
  - Province rows were downgraded to `provisional` by default.
  - Mae Hong Son was downgraded to `blocked` pending AADT repair.
- Next action:
  - Add code proof for DOPA weighting or downgrade claims.
  - Repair Mae Hong Son AADT provenance.

### 2026-06-03 - Khon Kaen, Udon Thani, Ubon Ratchathani, Nong Khai - OpenCode

- Scope: Create district_nodes CSV files for 4 provinces that were missing them.
- Files changed:
  - `data/district_nodes_khon_kaen.csv` (26 districts)
  - `data/district_nodes_udon_thani.csv` (20 districts)
  - `data/district_nodes_ubon_ratchathani.csv` (25 districts)
  - `data/district_nodes_nong_khai.csv` (9 districts)
  - `docs/data_injection_progress.md` (updated matrix + work log)
- Sources added: district centroids estimated from known district town locations; population from `tha_pop_adm2_2023.csv`.
- Rows added or updated: 80 district node rows across 4 provinces.
- DB tables touched: none (CSV staging layer only).
- Validation/tests: `test_heatmap.py`, `test_spatial_click_analysis.py`, `test_evhub_data.py` — 21/21 passed. Community mode verified for all 4 provinces: Khon Kaen (99.2 sess/day), Udon Thani (72.0), Ubon Ratchathani (89.4), Nong Khai (89.0).
- Blockers: None — district nodes now enable community heatmap mode for all 4 provinces.
- Next action: Add DOPA district population weighting (`docs/dopa_injection_handoff.md` scope), then fill Lamphun/Nan AADT/POI/competitors/hot zones.

### 2026-06-03 - Lamphun, Nan - OpenCode

- Scope: Create AADT seed, POI, competitors, and hot zones for Lamphun and Nan (both had district_nodes but were missing all other layers).
- Files changed:
  - `data/aadt_lamphun_seed.csv` (25 AADT rows from DOH aadt_2566.csv)
  - `data/poi_lamphun_seed.csv` (16 POI)
  - `data/competitors_lamphun_seed.csv` (4 competitor seeds)
  - `data/hot_zones_lamphun.csv` (5 hot zones)
  - `data/aadt_nan_seed.csv` (28 AADT rows from DOH aadt_2566.csv)
  - `data/poi_nan_seed.csv` (18 POI)
  - `data/competitors_nan_seed.csv` (5 competitor seeds)
  - `data/hot_zones_nan.csv` (5 hot zones)
  - `docs/data_injection_progress.md` (updated matrix + work log)
- Sources added: AADT from DOH aadt_2566.csv; POI from OpenStreetMap + public sources; population from tha_pop_adm2_2023.csv.
- Rows added or updated: 106 rows across 8 CSV files.
- DB tables touched: none (CSV staging layer).
- Validation/tests: `test_heatmap.py`, `test_spatial_click_analysis.py` — 16/16 passed. Verified both provinces:
  - Lamphun: 4 nodes, 16 POI, 4 comps, 5 zones → Urban 60.1, Community 65.2 sess/day
  - Nan: 4 nodes, 18 POI, 5 comps, 5 zones → Urban 75.0, Community 80.0 sess/day
- Blockers: None.
- Next action: Add DOPA district population weighting across all 11 provinces, then Mae Hong Son starting from scratch.

### 2026-06-03 - DOPA population weighting (all 12 provinces) + Mae Hong Son - OpenCode

- Scope: Add DOPA district population weighting to all 11 existing provinces; create all 5 data layers for Mae Hong Son from scratch.
- Files changed:
  - `th_evi/data.py`: added `_load_adm2_district_population()`, `load_district_population_for_province()`
  - `th_evi/spatial.py`: added `POPULATION_WEIGHT_MIN`/`MAX`, `_compute_population_weight()`, `enrich_district_nodes_with_population()`, `load_enriched_district_nodes()`; updated `district_node_field()` to multiply `population_weight`; updated `analyze_click_location()` callsites to use enriched nodes
  - `th_evi/heatmap.py`: updated import/callsite to `load_enriched_district_nodes`
  - `data/district_nodes_mae_hong_son.csv` (7 district nodes)
  - `data/aadt_mae_hong_son_seed.csv` (28 AADT rows)
  - `data/poi_mae_hong_son_seed.csv` (18 POI)
  - `data/competitors_mae_hong_son_seed.csv` (5 competitor seeds)
  - `data/hot_zones_mae_hong_son.csv` (5 hot zones)
  - `docs/data_injection_progress.md` (updated matrix + work log)
- Sources added: DOPA population from `tha_pop_adm2_2023.csv`; Mae Hong Son AADT/POI/competitors from DOH + OSM + public sources.
- DOPA weighting: bounded multiplier [0.75, 1.35] based on district population percentile within each province; weights loaded at runtime, CSVs unchanged.
- Rows added or updated: 7 district nodes + 56 data rows across Mae Hong Son; DOPA enrichment active for all 12 provinces (126 district nodes total).
- DB tables touched: none (CSV staging layer).
- Validation/tests: 48/48 passed. Verified all 12 provinces load correctly with population weights.
- Blockers: None — 12/12 provinces now have complete district_nodes + DOPA weighting + basic POI/competitor/hot zone coverage.
- Next action: Verify data accuracy and validate heat map; real-world POI/competitor verification.

### 2026-06-03 - DB reference schema design and CSV ingestion - OpenCode

- Scope: Design and implement 6 reference DB tables from the work-order proposal; ingest all province CSV data into the database with idempotent upsert.
- Files changed:
  - `th_evi/db.py`: added 6 model classes (`ReferenceSource`, `ProvinceIngestionRun`, `DistrictPopulation`, `AADTSegment`, `POIReference`, `ChargerCompetitor`) with natural-key unique constraints
  - `th_evi/ingest.py`: new script — seeds reference sources, upserts district population from `tha_pop_adm2_2023.csv`, per-province AADT/POI/competitor from `_seed.csv`, and records each ingestion run
  - `docs/data_injection_progress.md` (updated matrix + work log)
- DB tables created: `reference_sources`, `province_ingestion_runs`, `district_population`, `aadt_segments`, `poi_reference`, `charger_competitors`
- Rows ingested: 928 district_population, 163 aadt_segments, 144 poi_reference, 42 charger_competitors, 5 reference_sources, 12 province_ingestion_runs
- DB tables touched: 6 new tables created via `Base.metadata.create_all`
- Ingestion idempotent: verified — re-running produces 0 new rows.
- Validation/tests: 48/48 passed.
- Key design decisions:
  - All models use natural-key unique constraints for idempotent upsert
  - AADT unique constraint includes `km_start` (multiple segments per route)
  - Competitors use `(province, station_id)` as natural key
  - POI uses `(province, poi_id)` as natural key
  - Province-wide `charger_competitors` table kept separate from site-specific `competitors` table
- Blockers/notes:
  - Chiang Mai: no AADT seed file (uses DOH data directly via `load_doh_aadt`)
  - Lampang: POI loaded from `poi_lampang_city_seed.csv` not `poi_lampang_seed.csv` — handled by existing code
  - All competitor rows remain `verification_status=seed_needs_verification`, `confidence=low` — not verified
- Next action: Add API endpoints or DB-backed loaders for reference tables; start operator-app competitor verification.

## Update Template

Copy this template exactly when finishing a province batch. Fill every field. If a field is not applicable, write "not applicable" — do not leave it blank.

```text
### YYYY-MM-DD — <Province> — <Agent/Model>

- Scope: (one province + one layer, or list each layer separately)
- Files changed: (list every file changed with row counts)
- Sources added: (name each source; do not write "official" if not confirmed)
- Rows added or updated: (count per file)
- DB tables touched: (none / list table names)
- Test command run: (exact command, e.g. pytest tests\test_heatmap.py -v)
- Test result: (X/Y passed — do not write totals you did not observe)
- Evidence level: code / csv / source-verified / mixed
- Official-source cross-check: (match rate X/Y, or "not performed")
- Still estimated: (list any fields or rows that were inferred, not source-confirmed)
- Scoring activation confirmed: (yes + file:line, or no)
- Blockers: (none / describe specifically)
- Next action: (specific file names and action, not vague)
```

### 2026-06-03 - Ingest review hardening - Codex

- Scope: review the latest DB ingestion work, fix provenance handling, and add ingestion-specific tests before push.
- Files changed:
  - `th_evi/ingest.py`
  - `tests/test_ingest.py`
- Source-verified:
  - Rerun behavior for reference tables is now tested directly.
  - Competitor and POI source mapping now uses CSV source metadata instead of always falling back to `seed_estimate`.
- Still estimated:
  - Historical province CSV quality is still mixed, especially blocked AADT provenance cases such as Mae Hong Son.
- Test command run:
  - `python -m pytest`
- Test result:
  - `50/50 passed`
- Blockers:
  - Historical log entries above remain provisional and should not be read as fully reconciled truth.
- Next action:
  - Decide whether to expose DB-backed reference data through API loaders or keep CSV as the primary runtime layer for now.
