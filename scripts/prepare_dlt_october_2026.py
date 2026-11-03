"""Normalize DLT's 31 October 2026 fuel workbook without changing older snapshots."""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SOURCE_URL = 'https://web.dlt.go.th/statistics/load_file_select_new_car.php?t=3&data_file=1340'
ALIASES = {'สุราษฯ': 'สุราษฎร์ธานี', 'นครศรีฯ': 'นครศรีธรรมราช'}
FLEET_FIELDS = ('source_project', 'source_file', 'source_month', 'source_year_be', 'province',
                'vehicle_segment', 'total_vehicles', 'gasoline', 'diesel', 'bev', 'hev_gasoline',
                'hev_diesel', 'phev_gasoline', 'phev_diesel', 'bev_share')
SUMMARY_FIELDS = ('province', 'as_of_be', 'registered_private_cars_vans_pickups_ror1_3',
                  'bev', 'phev', 'plugin_total', 'plugin_share_pct', 'source_url', 'source_scope', 'notes')


def extract(path: Path):
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    fleet, summary = [], []
    try:
        for sheet_name in workbook.sheetnames:
            if sheet_name.strip() in {'ทั่วประเทศ', 'ส่วนกลาง', 'ภูมิภาค'}:
                continue
            ws = workbook[sheet_name]
            date = str(ws.cell(3, 1).value or '')
            if '31 ตุลาคม 2569' not in date:
                raise ValueError(f'Unexpected date in {sheet_name}: {date}')
            if 'รวมรถตามกฎหมายว่าด้วยรถยนต์' not in str(ws.cell(7, 1).value or ''):
                raise ValueError(f'Unexpected motor-vehicle row in {sheet_name}')
            for idx, prefix in ((8, 'รย.1'), (9, 'รย.2'), (10, 'รย.3')):
                if not str(ws.cell(idx, 1).value or '').startswith(prefix):
                    raise ValueError(f'Unexpected vehicle segment row {idx} in {sheet_name}')
            if str(ws.cell(5, 14).value or '') != 'ไฟฟ้า':
                raise ValueError(f'Unexpected BEV column in {sheet_name}')
            def val(row, col):
                raw = ws.cell(row, col).value
                if raw is None: return 0
                if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw < 0 or int(raw) != raw:
                    raise ValueError(f'Unexpected numeric value {sheet_name}!{row},{col}: {raw!r}')
                return int(raw)
            province = ALIASES.get(sheet_name.strip(), sheet_name.strip())
            for segment, row in (('all_vehicle_law', 7), ('ror1_passenger_car', 8)):
                total, bev = val(row, 2), val(row, 14)
                if total <= 0 or bev > total: raise ValueError(f'Invalid fleet total for {province}')
                fleet.append(dict(source_project='TH-EVI', source_file='fuel31Oct26_W.xlsx',
                    source_month='2569-10', source_year_be=2569, province=province, vehicle_segment=segment,
                    total_vehicles=total, gasoline=val(row, 3), diesel=val(row, 4), bev=bev,
                    hev_gasoline=val(row, 15), hev_diesel=val(row, 16),
                    phev_gasoline=val(row, 19)+val(row, 21), phev_diesel=val(row, 20)+val(row, 22),
                    bev_share=round(bev/total, 10)))
            total = sum(val(r, 2) for r in (8, 9, 10))
            bev = sum(val(r, 14) for r in (8, 9, 10))
            phev = sum(val(r, c) for r in (8, 9, 10) for c in (19, 20, 21, 22))
            summary.append(dict(province=province, as_of_be='2569-10-31',
                registered_private_cars_vans_pickups_ror1_3=total, bev=bev, phev=phev,
                plugin_total=bev+phev, plugin_share_pct=round((bev+phev)/total*100, 8),
                source_url=SOURCE_URL, source_scope='DLT cumulative private vehicles under Motor Vehicle Act, Ror.1-Ror.3; BEV plus plug-in hybrid categories only; excludes HEV, motorcycles, and transport-law vehicles',
                notes='Province tab in official fuel31Oct26_W.xlsx; totals rows Ror.1-Ror.3. Provincial registration stock, not site catchment or charging demand.'))
    finally:
        workbook.close()
    if len(summary) != 76 or len({x['province'] for x in summary}) != 76:
        raise ValueError('Expected 76 unique provincial sheets; central office is not Bangkok province')
    return fleet, summary


def write(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    source = Path(sys.argv[1])
    fleet, summary = extract(source)
    write(DATA / 'evhub_dlt_fleet_2569_10.csv', FLEET_FIELDS, fleet)
    write(DATA / 'dlt_ev_province_20261031.csv', SUMMARY_FIELDS, summary)
    print('sha256', hashlib.sha256(source.read_bytes()).hexdigest())
    print('province_rows', len(summary), 'fleet_rows', len(fleet))
