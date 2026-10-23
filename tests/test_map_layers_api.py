from fastapi.testclient import TestClient

from th_evi import api


def test_poi_map_endpoint_uses_shared_province_loader_and_only_public_fields(monkeypatch):
    seen = []

    def load(province):
        seen.append(province)
        return [{"poi_id": "retail", "name": "Retail", "lat": "18.8", "lon": "99.01",
                 "category": "community_mall", "verification_status": "verified",
                 "source_url": "https://example.com/retail", "notes": "private admin note", "weight": 30}]

    monkeypatch.setattr(api.spatial_module, "load_pois_for_province", load)
    response = TestClient(api.app).get("/api/pois", params={"province": "เชียงใหม่"})
    assert response.status_code == 200
    result = response.json()
    assert seen == ["เชียงใหม่"]
    assert result["province"] == "เชียงใหม่"
    assert result["poi_count"] == 1
    assert result["pois"][0]["lat"] == 18.8
    assert result["pois"][0]["category"] == "community_mall"
    assert "notes" not in result["pois"][0]
    assert "weight" not in result["pois"][0]


def test_poi_map_endpoint_skips_missing_nonfinite_and_out_of_country_coordinates(monkeypatch):
    monkeypatch.setattr(api.spatial_module, "load_pois_for_province", lambda province: [
        {"poi_id": "missing"}, {"lat": None, "lon": 99}, {"lat": float("nan"), "lon": 99},
        {"lat": 18, "lon": float("inf")}, {"lat": "invalid", "lon": 99},
        {"lat": 0, "lon": 0}, {"lat": 18.8, "lon": 99.01, "poi_id": "valid"},
    ])
    result = TestClient(api.app).get("/api/pois", params={"province": "Chiang Mai"}).json()
    assert result["poi_count"] == 1
    assert result["pois"][0]["name"] == "valid"


def test_poi_map_endpoint_empty_province_data_and_assets(monkeypatch):
    monkeypatch.setattr(api.spatial_module, "load_pois_for_province", lambda province: [])
    client = TestClient(api.app)
    assert client.get("/api/pois", params={"province": "Chiang Rai"}).json()["poi_count"] == 0
    assert client.get("/api/pois?province=").status_code == 422
    for page in ("/planning", "/analysis"):
        html = client.get(page).text
        assert '/static/map-layers.js' in html
        assert '/static/map-layers.css' in html
    for asset in ("map-layers.js", "map-layers.css"):
        assert client.get('/static/' + asset).status_code == 200
