import json

from fastapi.testclient import TestClient
import pytest

from th_evi import api, place_search as search
from th_evi.db import CandidateSite, POIReference, ReferenceDatasetRelease, create_session_factory


def point(record_id='store', **extra):
    return dict(record_id=record_id, name='Test Store', province='Chiang Mai', kind='poi',
                lat=18.8, lon=99.01, **extra)


@pytest.fixture(autouse=True)
def reset_cache():
    search.clear_cache()
    yield
    search.clear_cache()


@pytest.fixture
def csv_only(monkeypatch):
    monkeypatch.setattr(search, 'reference_catalog', lambda: (
        search.merge_catalog(search.csv_catalog(), [], set()), False))
    monkeypatch.setattr(search, 'saved_sites', lambda: ([], False))


@pytest.mark.parametrize('query,record_id', [
    ('กาดฝรั่ง แม่ริม', 'the_kad_farang_mae_rim'),
    ('KAD FARANG MAE RIM', 'the_kad_farang_mae_rim'),
    ('เดอะ โลคอล สันกำแพง', 'the_local_sankamphaeng'),
    ('The Local San Kamphaeng', 'the_local_sankamphaeng'),
    ('มหาโชค ปาร์ค', 'mahachok_park'), ('Maha Chok Park', 'mahachok_park'),
    ('สนามบินเชียงใหม่', 'chiang_mai_airport'), ('แอร์ไดมอนด์', 'air_diamond_mae_taeng'),
])
def test_bilingual_aliases_resolve_existing_places(csv_only, query, record_id):
    result = search.search_places(query, 'เชียงใหม่')
    assert result['results'][0]['id'] == f'Chiang Mai/poi/{record_id}'
    assert result['results'][0]['province_th'] == 'เชียงใหม่'


def test_all_aliases_reference_real_places_not_new_demand_records():
    ids = {f"{row['province']}/{row['kind']}/{row['record_id']}" for row in search.csv_catalog()}
    assert set(search.aliases()) <= ids
    assert search.normalize('กาดฝรั่ง แม่ริม') == search.normalize('กาดฝรั่งแม่ริม')
    assert search.normalize('ＭＡＹＡ') == 'maya'


def test_published_admin_overrides_and_inactive_records_are_respected():
    csv_rows = [point(), point('deleted')]
    db_rows = [dict(point(), name='Renamed', lat=18.9), dict(point('deleted'), active=False)]
    result = search.merge_catalog(csv_rows, db_rows, {'Chiang Mai'})
    assert len(result) == 1 and result[0]['name'] == 'Renamed' and result[0]['lat'] == 18.9
    result = search.merge_catalog(csv_rows, db_rows, set())
    assert len(result) == 2 and result[0]['name'] == 'Test Store'


def test_bad_coordinates_are_never_search_results():
    rows = [dict(point('nan'), lat=float('nan')), dict(point('missing'), lon=None),
            dict(point('outside'), lat=0, lon=0), point()]
    assert len(search.merge_catalog(rows, [], set())) == 1


def test_cross_province_lookup_bias_limit_and_empty(monkeypatch):
    rows = [dict(point('cm'), name='Mall', province='Chiang Mai'),
            dict(point('cr'), name='Mall', province='Chiang Rai')]
    monkeypatch.setattr(search, 'reference_catalog', lambda: (rows, False))
    monkeypatch.setattr(search, 'saved_sites', lambda: ([], False))
    assert search.search_places('Mall', 'เชียงราย', 1)['results'][0]['province'] == 'Chiang Rai'
    assert search.search_places('Mall เชียงราย', 'Chiang Mai')['results'][0]['province'] == 'Chiang Rai'
    assert search.search_places('not-a-place')['results'] == []
    assert search.search_places('%')['results'] == []


def test_partial_search_retains_results_without_claiming_complete(monkeypatch):
    monkeypatch.setattr(search, 'reference_catalog', lambda: ([point()], True))
    monkeypatch.setattr(search, 'saved_sites', lambda: ([], False))
    result = search.search_places('Test Store')
    assert result['partial'] and len(result['results']) == 1


def test_real_database_search_is_read_only_and_excludes_private_notes(monkeypatch, tmp_path):
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'places.sqlite3').as_posix()}")
    monkeypatch.setattr(search, 'get_session_factory', lambda: factory)
    monkeypatch.setattr(search, 'csv_catalog', lambda: [])
    with factory() as session:
        session.add(POIReference(poi_id='shop', province='Chiang Mai', name='Bilingual Shop', category='retail',
                                 lat=18.8, lon=99, active=True, notes='private note'))
        session.add(CandidateSite(name='ลูกค้า Test Shop', province='เชียงใหม่', lat=18.81, lon=99.01,
                                  active=True, notes='private survey', created_by='Sales Person'))
        session.add(CandidateSite(name='Hidden Shop', province='เชียงใหม่', lat=18.81, lon=99.01, active=False))
        session.commit()
    result = TestClient(api.app).get('/api/place-search', params={'q': 'Shop'}).json()
    assert len(result['results']) == 2
    assert {r['kind'] for r in result['results']} == {'poi', 'saved'}
    assert not any(word in json.dumps(result) for word in ('private', 'Sales Person', 'notes', 'created_by'))
    with factory() as session:
        assert session.query(CandidateSite).count() == 2
        assert session.query(POIReference).count() == 1
    with factory() as session:
        session.query(CandidateSite).filter_by(name='ลูกค้า Test Shop').update({'name': 'New Saved Name'})
        session.commit()
    assert TestClient(api.app).get('/api/place-search', params={'q': 'New Saved Name'}).json()['results']


def test_endpoint_validation_and_public_config_are_explicit(monkeypatch, csv_only):
    client = TestClient(api.app)
    for params in ({'q': 'a'}, {'q': 'a' * 161}, {'q': 'mall', 'limit': 11}):
        assert client.get('/api/place-search', params=params).status_code == 422
    assert client.get('/api/place-search', params={'q': 'zznotaplacezz'}).json()['results'] == []
    monkeypatch.delenv('TH_EVI_MAPTILER_PUBLIC_KEY', raising=False)
    monkeypatch.setenv('GOOGLE_MAPS_API_KEY', 'must-not-be-exposed')
    assert client.get('/api/place-search/config').json() == {'external': None}
    monkeypatch.setenv('TH_EVI_MAPTILER_PUBLIC_KEY', 'restricted-public-search-key')
    assert client.get('/api/place-search/config').json()['external'] == {
        'provider': 'maptiler', 'public_key': 'restricted-public-search-key'}


def test_reference_admin_invalidation_clears_search_cache(monkeypatch):
    search.aliases()
    assert search.aliases.cache_info().currsize == 1
    api._clear_reference_caches()
    assert search.aliases.cache_info().currsize == 0
