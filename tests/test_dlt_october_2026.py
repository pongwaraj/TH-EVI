import csv
from pathlib import Path

from th_evi.charging_profiles import observed_bev_fleet


ROOT = Path(__file__).resolve().parents[1]


def test_october_fleet_rows_are_province_unique_and_numerically_consistent():
    with (ROOT / 'data/evhub_dlt_fleet_2569_10.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 152
    assert len({(row['province'], row['vehicle_segment']) for row in rows}) == 152
    assert {row['source_month'] for row in rows} == {'2569-10'}
    assert {row['vehicle_segment'] for row in rows} == {'ror1_passenger_car', 'all_vehicle_law'}
    for row in rows:
        total, bev = int(row['total_vehicles']), int(row['bev'])
        assert 0 <= bev <= total
        assert abs(float(row['bev_share']) - bev / total) < 1e-9
    lookup = {(row['province'], row['vehicle_segment']): row for row in rows}
    assert int(lookup['เชียงใหม่', 'all_vehicle_law']['total_vehicles']) == 1683232
    assert int(lookup['เชียงใหม่', 'ror1_passenger_car']['bev']) == 17538
    assert int(lookup['พะเยา', 'ror1_passenger_car']['bev']) == 571
    assert observed_bev_fleet('Chiang Mai')['source_month'] == '2569-10'
    assert observed_bev_fleet('Chiang Mai')['bev'] == 17538


def test_october_private_summary_has_76_provinces_and_matches_component_totals():
    with (ROOT / 'data/dlt_ev_province_20261031.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len({row['province'] for row in rows}) == 76
    assert all(row['as_of_be'] == '2569-10-31' for row in rows)
    assert all(int(r['plugin_total']) == int(r['bev']) + int(r['phev']) for r in rows)
    phayao = next(row for row in rows if row['province'] == 'พะเยา')
    assert int(phayao['bev']) == 572
    assert int(phayao['phev']) == 104
