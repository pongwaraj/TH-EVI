# DLT cumulative fleet snapshot 31 October 2026

- Source: https://web.dlt.go.th/statistics/m1_collect_new_car.php
- Official fuel workbook: https://web.dlt.go.th/statistics/load_file_select_new_car.php?t=3&data_file=1340
- Original workbook SHA-256: `c56e3650f63a3fd64c5b5b9aff50cd2263db09f092b854a77ea2586e94a29f86`
- Extractor: `python scripts/prepare_dlt_october_2026.py <official-workbook.xlsx>`
- 76 province sheets yield 152 segment rows and 76 Ror.1–Ror.3 summary rows. The separate central-office sheet was not equated to Bangkok province. No October province value was invented for Bangkok.
- `ror1_passenger_car` uses Ror.1, row 8. `all_vehicle_law` uses the total under the Motor Vehicle Act, row 7, not the grand total including the Land Transport Act on row 6. The older September `all_vehicle_law` extract used row 6, so the change in this specific segment across months is not a like-for-like change. Historical files have not been rewritten.
- PHEV includes the separate plug-in gasoline/diesel categories; ordinary HEV is not PHEV. Ror.1–Ror.3 includes passenger cars, vans and private pickups, not motorcycles.
- 31 October: Chiang Mai Ror.1 461,068 vehicles, 17,538 BEV. Phayao Ror.1 51,599 vehicles, 571 BEV. These are provincial registration stocks, not local traffic or public-charger sessions.
- The runtime file loader chooses the latest snapshot per province and vehicle segment. Provinces without an October row retain their previously available input; consumers must inspect `source_month`.
- Updating DLT improves the currency of registration inputs; it does not validate station-level demand, calibrate POI/competitor effects, or resolve the Kwan Phayao water exclusion.
