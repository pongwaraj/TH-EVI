from th_evi import spatial


def test_published_inactive_record_cannot_return_via_csv_fallback(monkeypatch):
    monkeypatch.setattr(spatial, '_has_published_database_release', lambda _: True)
    rows = spatial._merge_reference_rows('Chiang Mai',
        [{'id': 'retired', 'name': 'CSV old'}, {'id': 'active', 'name': 'CSV old active'}],
        [{'id': 'retired', 'active': False}, {'id': 'active', 'active': True, 'name': 'DB reviewed'}], 'id')
    assert rows == [{'id': 'active', 'name': 'DB reviewed'}]


def test_unpublished_db_cannot_retire_a_csv_record(monkeypatch):
    monkeypatch.setattr(spatial, '_has_published_database_release', lambda _: False)
    rows = spatial._merge_reference_rows('Chiang Mai', [{'id': 'csv', 'name': 'CSV authority'}],
        [{'id': 'csv', 'active': False}, {'id': 'db_only_inactive', 'active': False}], 'id')
    assert rows == [{'id': 'csv', 'name': 'CSV authority'}]
