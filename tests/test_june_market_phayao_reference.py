import pytest

from th_evi.spatial import km_between, load_pois_for_province


def test_june_market_and_corrected_city_anchors_have_evidence():
    pois = {p['poi_id']: p for p in load_pois_for_province('Phayao')}
    market = pois['june_market_phayao']
    assert market['category'] == 'market_tourism'
    assert float(market['lat']) == pytest.approx(19.178148)
    assert float(market['lon']) == pytest.approx(99.888549)
    assert 'phayaocoffeeroaster.com' in market['notes']
    for poi_id, expected_lat, expected_lon, source_id in (
        ('tops_plaza_phayao', 19.1865827, 99.8935929, '1030605852'),
        ('phayao_bus_terminal', 19.1727424, 99.8982347, '534387041'),
        ('phayao_hospital', 19.1906557, 99.8766073, '7770128'),
    ):
        poi = pois[poi_id]
        assert km_between(float(poi['lat']), float(poi['lon']), expected_lat, expected_lon) < .01
        assert source_id in poi['notes']
