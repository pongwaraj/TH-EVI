import pytest


@pytest.fixture
def offline_surface_lookup(monkeypatch):
    """Spatial unit tests must not depend on live Overpass uptime or timeouts."""
    from th_evi import spatial

    water, building = spatial.lookup_water_surface, spatial.lookup_building_surface
    water.cache_clear()
    building.cache_clear()
    monkeypatch.setattr(spatial, "_post_json", lambda *args, **kwargs: {"elements": []})
    yield
    water.cache_clear()
    building.cache_clear()
