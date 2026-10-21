from fastapi.testclient import TestClient
from th_evi.api import app


def test_coordinate_assets_are_served_locally_for_both_workspaces():
    with TestClient(app) as client:
        for route in ('/', '/planning', '/analysis'):
            response = client.get(route)
            assert response.status_code == 200
            assert 'id="coordinate-search"' in response.text
            assert '/static/map-coordinates.js' in response.text
            assert '/static/map-coordinates.css' in response.text
        for asset, mime in [('map-coordinates.js', 'javascript'), ('map-coordinates.css', 'text/css')]:
            response = client.get('/static/' + asset)
            assert response.status_code == 200
            assert mime in response.headers['content-type']
        assert client.get('/static/does-not-exist.js').status_code == 404
        assert client.get('/static/%2E%2E/api.py').status_code == 404
