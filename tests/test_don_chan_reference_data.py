import pytest

from th_evi.area_engine import analyze_area_cell
from th_evi.competition import competitor_evidence
from th_evi.spatial import km_between, load_competitors_for_province, load_pois_for_province


def test_big_c_don_chan_is_a_single_supermarket_with_a_cited_location():
    rows = [p for p in load_pois_for_province('Chiang Mai') if p['poi_id'] == 'big_c_don_chan']
    assert len(rows) == 1
    row = rows[0]
    assert row['category'] == 'supermarket'
    assert '88497220' in row['notes']
    assert km_between(float(row['lat']), float(row['lon']), 18.771591, 99.028790) == pytest.approx(.555, abs=.03)


def test_thasala_site_remains_a_screening_score_not_a_customer_forecast():
    result = analyze_area_cell(18.771591, 99.028790, 'Chiang Mai', 2026, 'base', 'urban', 1)
    assert result['eligibility_status'] == 'screening_only'
    assert result['net_sessions_per_day'] is None
    assert result['forecast_available'] is False
    assert 'Big C Chiang Mai Don Chan' in result['pois']


@pytest.mark.parametrize('include_kml', [False, True])
def test_don_chan_pluz_is_one_station_without_invented_power(include_kml):
    aliases = {'ptt_ev_station_don_jan', 'chiang_mai_kml_09fc8e737fb2'}
    rows = load_competitors_for_province('Chiang Mai', include_nationwide_kml=include_kml)
    selected = [row for row in rows if row.get('station_id') in aliases]
    assert len(selected) == 1
    assert selected[0]['station_id'] == 'ptt_ev_station_don_jan'
    evidence = competitor_evidence(selected[0])
    assert evidence['max_kw'] is None
    assert evidence['guns'] is None
    assert evidence['direct_dc_eligible'] is False
