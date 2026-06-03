# DOPA Injection Handoff

Last updated: 2026-06-03

This document is a handoff spec for using a lower-cost AI to inject DOPA district population data into TH-EVI without changing core demand logic.

**Read this alongside `docs/data_injection_work_order.md` and `docs/ai_model_data_contract.md`.**

---

## Your Role

You are a data integration agent. Your job is to:

1. Load existing population files
2. Match district names to district nodes
3. Derive a bounded `population_weight` multiplier
4. Apply that multiplier only inside district-node scoring
5. Add tests
6. Write a finish report

You are not redesigning the model. If you find yourself changing `LocationDemandModel`, `competitive_capture_share`, or any API field, stop immediately.

---

## What Already Exists (as of 2026-06-03)

The DOPA weighting work was completed in the 2026-06-03 batch. These functions were added:

**`th_evi/data.py`**
- `_load_adm2_district_population()`
- `load_district_population_for_province(province_en: str) -> pd.DataFrame`

**`th_evi/spatial.py`**
- `POPULATION_WEIGHT_MIN` = 0.75
- `POPULATION_WEIGHT_MAX` = 1.35
- `_compute_population_weight(population, all_populations)`
- `enrich_district_nodes_with_population(province, rows)`
- `load_enriched_district_nodes(province)`
- `district_node_field()` updated to multiply by `population_weight`
- `analyze_click_location()` updated to use enriched nodes

**`th_evi/heatmap.py`**
- Updated to call `load_enriched_district_nodes` instead of raw loader

**Status:** DOPA weighting is implemented in code. However, the progress log entry that claimed "all 12 provinces load correctly with population weights" has been marked `provisional` because the scoring activation claim was not confirmed with a code-line reference at the time of writing.

**Before doing any further DOPA work, verify that `population_weight` is actually multiplied inside the scoring path by reading `th_evi/spatial.py` → `district_node_field()` and tracing the call.**

---

## Goal For New Work

If DOPA weighting is confirmed active in code, the remaining tasks are:

1. Verify district name matching quality for each province
2. Identify districts where `population_weight` fell back to default `1.0` due to failed matching
3. Fix those name mismatches in the CSV or add a normalization alias
4. Confirm the multiplier bounds are still appropriate

If DOPA weighting is not yet confirmed active in code, complete the wire-up first before doing any province-level matching work.

---

## Data Sources

Primary source for English district names:
- `data/tha_pop_adm2_2023.csv`

Fallback / cross-check for Thai district names:
- `data/evhub_dopa_population_2568.csv`

Province slug mapping example:
- "Chiang Mai" → `chiang_mai`
- "Lamphun" → `lamphun`
- "Mae Hong Son" → `mae_hong_son`

---

## Implementation Pattern

### Loader (`th_evi/data.py`)

```python
def load_district_population_for_province(province_en: str) -> pd.DataFrame:
    """Returns DataFrame with columns: province_en, district_en, population, households, source"""
    ...
```

Output columns after normalization:
- `province_en`
- `district_en`
- `population`
- `households` (may be null)
- `source`

### Enrichment (`th_evi/spatial.py`)

```python
def enrich_district_nodes_with_population(
    province: str, rows: list[dict]
) -> list[dict]:
    ...
```

Matching rules — apply in order:
1. Exact English district name match
2. Normalized string match (lowercase, strip spaces and special chars)
3. If no match found: keep the row, set `population=null`, set `population_weight=1.0`

**Never silently assign a wrong district if multiple matches are plausible.** Log the ambiguity and use the default weight.

### Scoring (`th_evi/spatial.py` → `district_node_field()`)

```python
population_weight = clamp(POPULATION_WEIGHT_MIN, POPULATION_WEIGHT_MAX, f(population))
district_sessions = base_sessions * confidence_multiplier * population_weight * distance_weight
```

**Do not replace the existing district scoring.** Only add the multiplier.

Population weight normalization:
1. Compute percentile of each district's population within the province
2. Map percentile linearly to range `[POPULATION_WEIGHT_MIN, POPULATION_WEIGHT_MAX]`

This avoids explosive scaling for provinces where one district dominates.

---

## What You Must Not Change

- `LocationDemandModel` — leave untouched
- EV adoption curves in `adoption.py` — leave untouched
- Competitor capture logic in `site.py` — leave untouched
- Any public API field name — leave untouched
- `gross_area_demand_sessions` or `net_sessions_per_day` meaning — leave untouched

---

## Acceptance Criteria

The task is complete only when all of these are true:

1. Community heat map renders for the target province without errors.
2. Existing tests still pass.
3. New tests cover:
   - District name matching (exact and normalized)
   - Fallback when no match exists (default weight = 1.0)
   - Bounded population weighting (weights stay within 0.75–1.35)
   - Two otherwise identical district nodes with different `population_weight` produce different district session output in the correct direction (larger population → higher output)
4. No API response fields are removed or renamed.
5. The finish report points to the exact function and line where `population_weight` affects district sessions.

---

## Province Order

Recommended order for DOPA matching verification:

1. Chiang Mai (confirm activation first)
2. Lamphun
3. Lampang
4. Chiang Rai
5. Phayao
6. Phrae
7. Nan
8. Khon Kaen
9. Udon Thani
10. Ubon Ratchathani
11. Nong Khai
12. Mae Hong Son (currently `blocked` — AADT cross-check must be resolved first)

---

## Required Finish Report

Use the standard template from `docs/data_injection_work_order.md`. Additionally include:

- **Scoring activation confirmed:** yes/no + file:line reference
- **Match rate:** X out of Y district nodes matched with real population data
- **Fallback count:** how many districts used default weight 1.0
- **Weight range observed:** min and max `population_weight` values seen at runtime

---

## Review Checklist For Human Or Stronger Model

Before accepting DOPA work from a lower-cost AI:

1. No unrelated files were changed.
2. No broad formatting or refactoring churn.
3. Population multiplier is bounded between 0.75 and 1.35.
4. Missing district matches degrade safely to weight 1.0, not 0.
5. Community heat map does not overfill the province with false hotspots.
6. Chiang Mai district outputs remain plausible compared to pre-DOPA baseline.
7. The code, tests, and progress log all agree about whether weighting is active.
8. The finish report includes a specific code-line reference for the scoring activation.
