# TH-EVI Status Checkpoint — 2026-06-18

## Snapshot
- Repo: `TH-EVI`
- Branch: `master`
- Synced commit: `e61096416b885ba2953eee114530af25276e77dd`
- Working tree status at review time: clean and in sync with `origin/master`

## Product State Summary
TH-EVI has moved beyond a pure analysis prototype. The current codebase already supports an end-to-end planning workflow for EV charging site screening:

1. **Planning workspace (`/planning`)**
   - Province heatmap view
   - Urban / community / district modes
   - Point click analysis
   - Recommendation by station tier/spec
   - Open Google Maps / Street View from selected point
   - Personal shortlist in browser storage
   - Shared team shortlist via API
   - Report generation from selected map point

2. **Analysis workspace (`/analysis`)**
   - Separate advanced analysis page exists in static frontend

3. **Admin workspace (`/admin`)**
   - Reference-data admin page exists
   - Backend includes CRUD-style reference APIs for planning layers

4. **Reporting / proposal outputs**
   - Saved analysis JSON endpoint exists
   - Human-readable HTML report exists
   - V2 executive location report route exists
   - Owner-area report export endpoints exist for DOCX and PDF
   - Report templates include:
     - `owner-area-analysis`
     - `owner-gp-opportunity`
     - `investor-case`

5. **Recent feature direction confirmed by latest commits**
   - `c73b19d` Improve planning workflow and competitor data coverage
   - `473273d` Add planning report exports and PDF generation
   - `784fe70` Render report maps on real basemap tiles
   - `e610964` Auto-select basemap zoom for heatmap snapshots

## What Is Essentially Done
- Planning UI exists and is wired to backend routes
- Heatmap API exists and supports non-Chiang-Mai provinces
- Shared shortlist workflow exists
- Report generation flow exists in product surface
- Proposal/report templates have already been introduced
- Basemap-backed report imagery has been added recently

## What Is Still In Progress / Not Fully Proven
1. **Test status is not fully green**
   - Targeted test run result:
     - `tests/test_heatmap.py` + `tests/test_frontend_encoding.py`
     - Result: `40 passed, 1 failed`
   - Failing test:
     - `tests/test_heatmap.py::test_province_heatmap_supports_non_chiang_mai`
   - Failure meaning:
     - Some generated Udon Thani points have `context_score < 5.0`, so non-Chiang-Mai heatmap calibration/filtering still needs review.

2. **Report/reference test coverage is blocked by environment**
   - Current `.venv` is missing importable modules required by parts of the app/test suite:
     - `httpx`
     - `docx` / `python-docx`
     - `reportlab`
     - `Pillow`
   - `.venv` also does not currently expose `pip` (`No module named pip` during check)
   - As a result, some API/report-related tests cannot currently be verified end-to-end in this environment.

3. **Province data quality is still provisional in many places**
   - `docs/data_injection_progress.md` marks most province layers as `provisional`
   - Competitor data in several areas remains seed-level and still needs verification
   - Heatmap/data validation against real-world sources is still an active follow-up area

4. **Mae Hong Son remains blocked**
   - The progress tracker explicitly says AADT provenance for Mae Hong Son must be cross-checked against DOH `aadt_2566.csv` before it should be treated as reliable reference data.

5. **Runtime data-source direction is not fully settled**
   - Open architectural question remains whether DB-backed reference tables should become the main runtime source, or whether CSV should remain the primary runtime layer for now.

## Practical Interpretation
TH-EVI is already usable as a **heatmap + planning + shortlist + proposal/report preparation tool**, especially for early sales screening and owner/investor-facing proposal generation.

However, it is **not yet fully closed out as a verified production-grade planning system** because:
- one targeted heatmap test still fails,
- report/test dependencies are incomplete in the reviewed environment,
- province data verification is still incomplete,
- and at least one province data stream (Mae Hong Son AADT) remains explicitly blocked.

## Suggested Next Actions
1. Fix the failing non-Chiang-Mai heatmap expectation (`context_score` threshold / filtering behavior).
2. Repair the local test environment so report/reference tests can run fully.
3. Decide whether DB-backed reference loaders or CSV should be the canonical runtime source.
4. Continue province-level verification, especially competitor and POI accuracy.
5. Resolve Mae Hong Son AADT provenance before using it as reference-grade data.

## Notes
This file is intended as a point-in-time checkpoint, not evergreen truth. Revalidate against code, tests, and latest commits before using it as a final status report.
