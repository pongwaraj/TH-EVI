# EV Hub Migration Notes

Date: 2026-06-02

This note records the useful parts imported from the old `D:\Work\EV Hub` project into TH-EVI.

## Imported

- `data/evhub_dopa_population_2568.csv`
  - Source: EV Hub DOPA 2568 population files.
  - Use: current province and district population/household baseline.
  - Example: Phrae province population 417,480; Den Chai district population 19,154.

- `data/evhub_dlt_fleet_2569_04.csv`
  - Source: DLT fuel/fleet workbook dated April 2026.
  - Use: province-level vehicle fleet and BEV share calibration.
  - Example: Phrae Ror.1 passenger cars 51,702; BEV 426; BEV share 0.824%.

- `data/evhub_sinexcel_price_list.csv`
  - Source: SINEXEL charger package price list from EV Hub.
  - Use: CAPEX selection for investor/owner/TCE scenarios.
  - Example: `INT-S-2-180` customer CAPEX 2,163,300 baht; `SP-M-4-360` customer CAPEX 5,589,500 baht.

- `th_evi/demand_streams.py`
  - Source idea: EV Hub core demand model.
  - Use: separate demand into community, corridor, and fleet streams, plus a corridor conversion guard rail.

## Not Imported Yet

- Old proposal/result workbooks.
  - Reason: case-specific and may contain assumptions that are stale or too optimistic for current TCE investment analysis.

- EV Hub competitor/POI rows outside provinces already supported by TH-EVI.
  - Reason: useful schema, but no ready Phrae/Den Chai competitor set was found. Competitors around Den Chai still need a fresh audit before being used in a realistic investment case.

- AADT geocoding templates.
  - Reason: useful workflow, but most rows are proxy/mapping templates. For Den Chai, use current TH-EVI AADT seeds plus fresh route verification before final investment use.

## Modeling Impact

The imported datasets are available through loaders in `th_evi.data`, but they do not automatically overwrite existing province constants yet. This keeps existing reports stable while giving the model stronger inputs for the next calibration pass.
