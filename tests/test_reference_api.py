from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient

import th_evi.api as api
from th_evi.api import app
from th_evi.db import BusinessAreaReference, POIReference, create_session_factory


@contextmanager
def _session_scope_for(Session):
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_reference_api_can_list_create_and_update(monkeypatch, tmp_path):
    Session = create_session_factory(f"sqlite:///{(tmp_path / 'reference_api.sqlite3').as_posix()}")

    with Session() as session:
        session.add(
            POIReference(
                poi_id="poi_test_1",
                province="Chiang Mai",
                name="Initial POI",
                category="shopping_mall",
                lat=18.8,
                lon=98.9,
                confidence="high",
                source_url="https://example.com/poi",
                verification_note="seed note",
                updated_by="seed_user",
            )
        )
        session.commit()

    monkeypatch.setattr(api, "session_scope", lambda: _session_scope_for(Session))
    monkeypatch.setattr(api, "_clear_reference_caches", lambda: None)
    client = TestClient(app)

    meta = client.get("/api/reference/meta")
    assert meta.status_code == 200
    assert "poi" in meta.json()["layers"]
    assert "hot-zones" in meta.json()["layers"]

    listed = client.get("/api/reference/poi", params={"province": "Chiang Mai"})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["poi_id"] == "poi_test_1"
    assert items[0]["updated_by"] == "seed_user"

    created = client.post(
        "/api/reference/business-areas",
        json={
            "values": {
                "business_area_id": "biz_test_1",
                "province": "Chiang Mai",
                "name": "Airport frontage",
                "area_type": "urban_fringe",
                "center_lat": 18.76,
                "center_lon": 98.97,
                "radius_km": 3.2,
                "demand_pool_base": 180,
                "source_url": "https://example.com/business-area",
                "verification_note": "first pass",
                "updated_by": "tester",
                "active": True,
            }
        },
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["business_area_id"] == "biz_test_1"
    assert created_payload["updated_by"] == "tester"

    updated = client.put(
        f"/api/reference/business-areas/{created_payload['id']}",
        json={"values": {"name": "Airport frontage updated", "active": False, "updated_by": "reviewer"}},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Airport frontage updated"
    assert updated.json()["active"] is False
    assert updated.json()["updated_by"] == "reviewer"

    listed_business = client.get("/api/reference/business-areas", params={"province": "Chiang Mai"})
    assert listed_business.status_code == 200
    assert listed_business.json()["items"][0]["business_area_id"] == "biz_test_1"

    searched = client.get("/api/reference/business-areas", params={"province": "Chiang Mai", "q": "Airport"})
    assert searched.status_code == 200
    assert searched.json()["count"] == 1

    duplicated = client.post(f"/api/reference/business-areas/{created_payload['id']}/duplicate")
    assert duplicated.status_code == 200
    duplicated_payload = duplicated.json()
    assert duplicated_payload["business_area_id"] == "biz_test_1_copy"
    assert duplicated_payload["name"].endswith("(Copy)")

    deleted = client.delete(f"/api/reference/business-areas/{duplicated_payload['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deactivated"]["business_area_id"] == "biz_test_1_copy"
    assert deleted.json()["deactivated"]["active"] is False

    inactive_only = client.get(
        "/api/reference/business-areas",
        params={"province": "Chiang Mai", "active_state": "inactive"},
    )
    assert inactive_only.status_code == 200
    assert inactive_only.json()["count"] == 2

    with Session() as session:
        saved = session.query(BusinessAreaReference).filter_by(business_area_id="biz_test_1").one()
        assert saved.name == "Airport frontage updated"
        assert saved.active is False
        assert saved.source_url == "https://example.com/business-area"
        assert saved.verification_note == "first pass"
        assert saved.updated_by == "reviewer"
        duplicated_saved = session.query(BusinessAreaReference).filter_by(business_area_id="biz_test_1_copy").one()
        assert duplicated_saved.active is False
        assert duplicated_saved.updated_by == "local_admin"


def test_frontend_routes_include_main_and_admin_pages():
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    assert '/admin' in home.text

    admin = client.get("/admin")
    assert admin.status_code == 200
    assert "TH-EVI | Data Admin" in admin.text
