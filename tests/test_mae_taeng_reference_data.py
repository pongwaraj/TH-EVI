import pytest

from th_evi.area_engine import analyze_area_cell, generate_area_surface
from th_evi.competition import competitor_evidence, dc_competition_pressure
from th_evi.spatial import km_between, load_competitors_for_province, load_district_nodes_for_province, load_pois_for_province


MAE_TAENG_IDS = {'chiang_mai_kml_3e4855a17614', 'chiang_mai_kml_cd15dd0662e3', 'chiang_mai_kml_2a2096722c21'}


def test_mae_taeng_reference_pins_follow_actual_town_and_poi_hierarchy():
    pois = {row['poi_id']: row for row in load_pois_for_province('Chiang Mai')}
    town = pois['mae_taeng_city_center']
    assert town['category'] == 'neighborhood_center'
    assert km_between(float(town['lat']), float(town['lon']), 19.1220439, 98.9434277) < .05
    assert km_between(float(town['lat']), float(town['lon']), 19.1448, 98.8819) > 6
    node = next(row for row in load_district_nodes_for_province('Chiang Mai') if row['node_id'] == 'cm_mae_taeng')
    assert float(node['radius_km']) <= 2.4
    assert km_between(float(node['lat']), float(node['lon']), float(town['lat']), float(town['lon'])) < .05
    assert pois['lotus_mae_taeng']['category'] == 'supermarket'
    assert pois['mae_malai_market']['category'] == 'local_market'
    assert pois['mae_malai_busstop']['category'] == 'transport_corridor'
    assert pois['mae_taeng_hospital']['category'] == 'hospital'
    assert pois['dantewada_mae_taeng']['category'] == 'tourism'
    assert pois['air_diamond_mae_taeng']['category'] == 'tourism'


def test_air_diamond_is_a_real_venue_not_an_airport_or_a_zero_demand_claim():
    pois = {row['poi_id']: row for row in load_pois_for_province('Chiang Mai')}
    venue = pois['air_diamond_mae_taeng']
    assert 'tatstar.org' in venue['source']
    assert float(venue['lat']) == pytest.approx(19.072965)
    assert float(venue['lon']) == pytest.approx(98.938715)
    result = analyze_area_cell(19.072965, 98.938715, 'Chiang Mai', 2026, 'base', 'urban', 1)
    assert result['eligibility_status'] == 'screening_only'
    assert result['demand_score'] > result['net_opportunity_score'] > 0
    assert result['net_sessions_per_day'] is None


@pytest.mark.parametrize('include_kml', [False, True])
def test_mae_taeng_competitors_are_not_duplicated_or_given_a_power_floor(include_kml):
    rows = load_competitors_for_province('Chiang Mai', include_nationwide_kml=include_kml)
    for station_id in MAE_TAENG_IDS:
        assert sum(row['station_id'] == station_id for row in rows) == 1
    selected = {row['station_id']: row for row in rows if row['station_id'] in MAE_TAENG_IDS}
    pluz = competitor_evidence(selected['chiang_mai_kml_3e4855a17614'])
    office = competitor_evidence(selected['chiang_mai_kml_cd15dd0662e3'])
    caltex = competitor_evidence(selected['chiang_mai_kml_2a2096722c21'])
    assert pluz['max_kw'] == 180 and pluz['guns'] == 2
    assert office['max_kw'] == 26 and office['guns'] == 1
    assert caltex['max_kw'] == 120 and caltex['guns'] == 2
    assert all(row['direct_dc_eligible'] for row in (pluz, office, caltex))
    row = selected['chiang_mai_kml_2a2096722c21']
    near = dc_competition_pressure(float(row['lat']), float(row['lon']), [row])['pressure']
    at_lotus = dc_competition_pressure(19.0904836, 98.9359157, [row])['pressure']
    assert 0 <= at_lotus < near * .002


def test_mae_malai_heatmap_has_evidence_without_inventing_customers_or_a_western_hotspot():
    surface = generate_area_surface('Chiang Mai', 2026, 'base', 1, 'urban')
    lotus = analyze_area_cell(19.0904836, 98.9359157, 'Chiang Mai', 2026, 'base', 'urban', 1)
    assert lotus['eligibility_status'] == 'screening_only'
    assert 0 < lotus['net_opportunity_score'] < lotus['demand_score']
    assert lotus['competition_score'] > 0
    assert lotus['net_sessions_per_day'] is None
    assert lotus['forecast_available'] is False
    ghost = analyze_area_cell(19.1448, 98.8819, 'Chiang Mai', 2026, 'base', 'urban', 1)
    assert ghost['eligibility_status'] == 'outside_support'
    assert surface['metadata']['accounting']['gross_allocated'] == pytest.approx(100)
    assert surface['metadata']['accounting']['competition_balance_error'] == pytest.approx(0)
    area = [p for p in surface['points'] if 19.04 <= p['lat'] <= 19.19 and 98.82 <= p['lon'] <= 99.05]
    assert any(p['intensity_layers']['demand'] >= .3 for p in area)
    assert max(p['intensity_layers']['demand'] for p in area) < .6
