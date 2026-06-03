# Province Data Injection Work Order

Last updated: 2026-06-03

This work order is for AI agents that collect, clean, stage, and inject missing province data into TH-EVI.

**You are a data preparation agent. Your job ends at clean CSV or DB upsert. Do not redesign the demand model.**

---

## Start Here — Before Any Work

Read these files first, in order:

1. `docs/data_injection_progress.md` — find the target province and its current status
2. `docs/ai_model_data_contract.md` — rules you must not break
3. `docs/dopa_injection_handoff.md` — DOPA population weighting spec
4. `docs/*_pilot_notes.md` for the target province, if available
5. Existing `data/` files for the target province

Then answer these questions before writing any file:

- What already exists for this province?
- What is staged as CSV but not in DB?
- What is missing entirely?
- What is blocked?

If you cannot answer these from the files, stop and re-read.

---

## Non-Negotiable Rules

These rules override all convenience. Follow them exactly.

1. **Do not claim a formula changed** unless the code path actually changed and you can point to the file and function name.
2. **Do not claim a source is official** if the row was inferred, estimated, or rewritten from memory.
3. **Do not mark a province layer as `verified`** if any core evidence is still placeholder-only.
4. **Do not write progress notes from memory.** Read the changed files first, then write the log entry.
5. **Do not treat passing tests as proof that data is correct.** Tests only prove that current checks passed.
6. **If a source cross-check fails, stop.** Mark the batch `blocked` or `partial_csv` and explain why.
7. **If competitor rows are guessed**, label them `verification_status=seed_needs_verification`, `confidence=low`.

---

## Batch Scope Limit

Work on **one province and one data layer at a time** unless explicitly told otherwise.

If the task asks for "all layers", do them sequentially and log each layer separately. Do not bundle all layers into one progress log entry unless all layers are equally complete.

---

## Evidence Standard

Every material claim in a work log must be backed by one of:

- a changed file (name the file)
- a reproducible command or test (paste the exact command)
- a direct row count from a CSV or DB table (state the count)
- a source URL or named source file

If a claim cannot be backed by one of those, do not write it.

**Required examples:**

- If you say "DOPA weighting is active" → show the exact function name and line where `population_weight` multiplies the score.
- If you say "AADT rows came from DOH" → confirm route, km, and AADT values match the DOH source rows.
- If you say "province verified" → list every checklist item that passed with evidence.

---

## Per-Province Workflow

Work through these steps in order. Do not skip steps.

### Step 1 — Inventory existing files

Check which files already exist for the target province:

```
data/aadt_<province_slug>_seed.csv
data/poi_<province_slug>_seed.csv
data/competitors_<province_slug>_seed.csv
data/hot_zones_<province_slug>.csv
data/district_nodes_<province_slug>.csv
```

Also check global files:
```
data/evhub_dopa_population_2568.csv
data/evhub_dlt_fleet_2569_04.csv
data/tha_pop_adm2_2023.csv
```

### Step 2 — Identify gaps by layer

For each layer (AADT, DLT, DOPA, POI, Competitors, District Nodes), note:
- Does the file exist?
- How many rows?
- What is the confidence level of existing rows?
- What is missing?

### Step 3 — Collect from approved sources

Use the highest-quality source available. See the Source Priority section below.

### Step 4 — Normalize into expected CSV schema

Follow the column definitions in `docs/ai_model_data_contract.md`.

Validate before saving:
- Coordinates are valid lat/lon for the province
- No duplicate IDs in the same file
- Source and confidence fields are present on every row
- No null coordinates unless the row is explicitly a placeholder

### Step 5 — Validate with tests

For code or CSV changes:
```powershell
pytest tests\test_heatmap.py tests\test_spatial_click_analysis.py
```

For broader changes:
```powershell
pytest tests\test_heatmap.py tests\test_spatial_click_analysis.py tests\test_evhub_data.py tests\test_db_schema.py
```

Record the exact command and result in the log.

### Step 6 — Self-audit before writing the log

Before writing a progress log entry:

1. Re-open every file you changed.
2. Confirm the log describes only what is actually in those files.
3. Downgrade any claim that is only partially true.
4. Separate what is code-proven from what is CSV-only from what is still estimated.

### Step 7 — Write the progress log

Use the Required Finish Report format below. Update `docs/data_injection_progress.md`.

---

## Source Priority

### AADT

Preferred sources in order:
1. DOH official AADT data (`aadt_2566.csv`)
2. Official highway or transport reports
3. Existing project seed data

Required fields per row:
- route number
- segment name
- year
- AADT value
- coordinate or defensible segment midpoint
- source name
- confidence label

**AADT Cross-Check Gate:** For any seed file that claims DOH origin, cross-check every row against the DOH source file on `route + km + aadt`. Record the match count. If not all rows match, do not label unmatched rows as DOH-derived. Downgrade them to `seed_estimate` or block the batch.

If coordinates are inferred from segment names only, mark confidence no higher than `medium`.

---

### DLT

Preferred sources in order:
1. DLT official registration tables
2. Existing EV Hub normalized DLT files (`evhub_dlt_fleet_2569_04.csv`)
3. Publicly cited EV registration reports only if official table is not available

Required fields per row:
- province
- year/month
- vehicle segment
- BEV or fuel type count
- source
- confidence

Do not mix new registrations and active fleet in the same field without a clear column name distinguishing them.

---

### DOPA

Preferred sources in order:
1. `data/tha_pop_adm2_2023.csv` (English district names, use first)
2. `data/evhub_dopa_population_2568.csv` (Thai district names, use as fallback or cross-check)
3. Official DOPA files if new data is collected

Required fields per row:
- province
- district
- year
- population
- households if available
- source
- confidence

Do not delete district nodes when a name match is uncertain. Keep the row and set `population_weight` to default `1.0`.

---

### POI

Preferred sources in order:
1. Official venue website
2. Official government or transport page
3. Google Maps verification
4. OpenStreetMap or Wikidata
5. Existing project seed files

Required POI categories (use at least the relevant ones per province):
```
airport, railway_station, bus_terminal, mall, hospital,
university, government_center, tourist_destination, market,
hotel_convention, industrial_estate, transport_corridor,
border_crossing (where relevant)
```

Every POI row needs a `demand_role`. Use one of:
```
ride_hail_anchor, retail_destination, intercity_gateway,
local_community_anchor, tourism_anchor, commuter_anchor
```

---

### Competitors

Preferred sources in order:
1. Google Maps live station listing
2. Charging network app or official station locator
3. Operator website
4. OpenStreetMap
5. Field observation or user insider data

Required fields per row:
- station name
- network/operator
- lat/lon
- DC fast or AC only (`dc_fast`: true/false)
- gun count if verified (leave null if not)
- max kW if verified (leave null if not)
- source
- verification_date
- confidence

**Do not invent values for `max_kw`, `total_site_kw`, or `gun_count`.** Leave null if unknown.

Competitor seed rows must always be labeled:
```
verification_status=seed_needs_verification
confidence=low
```
unless a stronger source has been confirmed.

---

## DB Injection Rules

The current DB stores: candidate sites, site assumptions, site-specific competitors, analysis runs, analysis results, EV model/fleet mix tables, and the 6 reference tables added in the 2026-06-03 batch.

**Do not use the site-linked `competitors` table for province-wide public charger competitors.** That table is linked to a candidate site. Province-wide competitors go in `charger_competitors`.

If injecting into DB:
1. Use natural keys for upsert — `(province, station_id)` for competitors, `(province, poi_id)` for POI, `(province, route_number, segment_name, year_be)` for AADT.
2. Upsert, never blindly insert.
3. Attach `source_id` to every row.
4. Record an ingestion run in `province_ingestion_runs`.
5. Never delete old rows. Use `status=inactive` or `verification_status=obsolete` instead.

---

## Validation Checklist

A province batch is not closeable until all of these pass:

1. Required CSV columns exist and match the schema.
2. Coordinates are valid lat/lon.
3. No duplicate IDs inside the same file.
4. At least one source is recorded for every row.
5. Confidence label is present for every row.
6. POI and competitor rows have plausible province coordinates.
7. Heat map renders the province without errors.
8. Click-analysis at a known urban point returns nonzero `gross_area_demand_sessions`.
9. Missing data degrades safely — no crashes, no false precision.

---

## Review Gate Before Closing A Batch

Answer all six questions explicitly before marking a batch done. If any answer is missing, the batch is not ready.

1. What changed in **code**? (file name + function name)
2. What changed in **CSV only**? (file name + row count)
3. Which claims are **source-verified**? (name the source)
4. Which claims remain **estimated**? (be specific)
5. What did **tests prove**? (exact command + pass count)
6. What did **tests not prove**? (data accuracy, source provenance, etc.)

---

## Forbidden Progress Log Claims

Do not write any of these unless you have direct evidence:

| Forbidden | Use instead |
|---|---|
| "active in scoring" | "runtime loader added; scoring wire-up not yet confirmed" |
| "verified" | "rows staged; cross-check pending" |
| "official-source derived" | "source labeled as DOH; cross-check match rate: X/Y rows" |
| "complete coverage" | "partial coverage; gaps remain in [list]" |
| "all provinces load correctly with population weights" | "tests passed for provinces X, Y, Z; scoring activation not confirmed" |
| "competition verified" | "competitor seeds staged; verification_status=seed_needs_verification" |

---

## AI Agent Boundaries

You may:
- Collect sources
- Normalize CSV files
- Add new province seed rows
- Write deterministic import scripts if requested
- Add simple validation tests
- Update progress docs

You must not:
- Change the meaning of `net_sessions_per_day`
- Change the meaning of `gross_area_demand_sessions`
- Change or remove API field names
- Rewrite the heat map formula
- Rewrite competitor capture logic
- Push directly to production DB without review

---

## Required Finish Report

At the end of each province batch, update `docs/data_injection_progress.md` with this template:

```text
### YYYY-MM-DD — <Province> — <Agent/Model>

- Scope: (one province, one or more layers — be specific)
- Files changed: (list every file)
- Sources added: (name each source)
- Rows added or updated: (count per file)
- DB tables touched: (none / list tables)
- Test command run: (exact command)
- Test result: (X/Y passed)
- Evidence level: code / csv / source-verified / mixed
- Official-source cross-check: (match rate or "not applicable")
- Still estimated: (list what remains unverified)
- Blockers: (none / describe)
- Next action: (specific next step with file names)
```

---

## Suggested Prompt For Data Agents

Use this prompt verbatim when starting a lower-cost AI on a province task:

```text
You are a lower-cost data preparation agent working on TH-EVI province data injection.
You are not authorized to change scoring logic, API contracts, or heat map formulas.

Before doing anything:
1. Read docs/data_injection_work_order.md
2. Read docs/data_injection_progress.md
3. Read docs/ai_model_data_contract.md
4. Inspect existing data files for the target province in data/

Task:
Work on exactly one province: [PROVINCE NAME].
Work on exactly one layer at a time: [LAYER NAME].
Collect and normalize the missing data. Stage clean CSV first.
Inject to DB only if the reference schema exists or the task explicitly asks you to add it.

Rules:
- Do not redesign model formulas.
- Do not remove or rename API fields.
- Do not invent coordinates, kW, plug counts, or live station status.
- Mark uncertain data with lower confidence.
- Do not write "verified" unless you can name the source file and row.
- Update docs/data_injection_progress.md when finished using the Required Finish Report template.
```
