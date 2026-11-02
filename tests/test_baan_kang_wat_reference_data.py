import pytest

from th_evi.area_engine import analyze_area_cell
from th_evi.spatial import km_between, load_pois_for_province


def test_baan_kang_wat_is_one_tourism_destination():
    rows = [p for p in load_pois_for_province('Chiang Mai') if p['poi_id'] == 'baan_kang_wat_suthep']
    assert len(rows) == 1
    assert rows[0]['category'] == 'tourism'
    assert '11806550394' in rows[0]['notes']
    assert km_between(float(rows[0]['lat']), float(rows[0]['lon']), 18.765242, 98.945552) == pytest.approx(1.31, abs=.03)


def test_bba_screening_never_presents_area_score_as_vehicles():
    cell = analyze_area_cell(18.765242, 98.945552, 'Chiang Mai', 2026, 'base', 'urban', 1)
    assert cell['eligibility_status'] == 'screening_only'
    assert cell['forecast_available'] is False
    assert cell['net_sessions_per_day'] is None
