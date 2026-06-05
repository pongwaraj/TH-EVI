Tonight's work is isolated on a dedicated branch so it can be merged safely with the unpushed office machine work.

Recommended office flow tomorrow:

1. On the office machine, inspect and preserve the existing work first.
   - Confirm the current branch.
   - Commit the office changes before pulling anything.

2. Fetch the branch created from tonight's machine.
   - Branch name: `codex/chiangmai-city-data-audit`

3. Merge strategy on the office machine:
   - If the office work is the main line, stay on that branch and merge `codex/chiangmai-city-data-audit`.
   - If the office work is still on `master`, commit it first, then merge the branch.

4. If conflicts appear, expect them mainly in:
   - `data/poi_chiang_mai_seed.csv`
   - `data/competitors_chiang_mai_detailed.csv`
   - `th_evi/spatial.py`
   - `tests/test_spatial_click_analysis.py`

5. After resolving conflicts:
   - Run `python -m pytest tests\\test_spatial_click_analysis.py tests\\test_heatmap.py -q`
   - Push the merged result to GitHub.

What this branch contains:
- Chiang Mai city-core POI expansion
- Airport-side demand anchors
- Chiang Mai city competitor expansion and cleanup
- Loader and test updates for the new data
