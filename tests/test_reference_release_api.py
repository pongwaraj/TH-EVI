from __future__ import annotations

import json
from contextlib import contextmanager

from fastapi.testclient import TestClient

import th_evi.api as api
from th_evi.api import app
from th_evi.db import ReferenceDatasetRelease, create_session_factory


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


def _release(version: str, status: str = "published") -> ReferenceDatasetRelease:
    return ReferenceDatasetRelease(
        province="Chiang Mai",
        province_slug="chiang_mai",
        dataset_version=version,
        status=status,
        parity_passed=status == "published",
        manifest_json=json.dumps({"file_count": 3, "files": []}),
        parity_json=json.dumps(
            {
                "passed": status == "published",
                "layers": {"pois": {"passed": True, "expected_count": 2, "managed_db_count": 2}},
            }
        ),
    )


def test_reference_release_api_lists_and_publishes(monkeypatch, tmp_path):
    Session = create_session_factory(f"sqlite:///{(tmp_path / 'release_api.sqlite3').as_posix()}")
    with Session() as session:
        session.add(_release("published-v1"))
        session.commit()

    def fake_sync(session, slug, *, publish, actor):
        assert slug == "chiang_mai"
        assert publish is True
        assert actor == "qa_user"
        release = _release("published-v2")
        session.add(release)
        session.flush()
        return {
            "province": "Chiang Mai",
            "province_slug": slug,
            "dataset_version": release.dataset_version,
            "release_id": release.id,
            "status": "published",
            "parity": {"passed": True, "layers": {}},
        }

    monkeypatch.setattr(api, "session_scope", lambda: _session_scope_for(Session))
    monkeypatch.setattr(api, "sync_province_reference", fake_sync)
    monkeypatch.setattr(api, "_clear_reference_caches", lambda: None)
    client = TestClient(app)

    listed = client.get("/api/reference/releases", params={"province": "Chiang Mai"})
    assert listed.status_code == 200
    assert listed.json()["runtime_source"] == "database"
    assert listed.json()["active_release"]["dataset_version"] == "published-v1"

    published = client.post(
        "/api/reference/releases/sync",
        json={"province": "Chiang Mai", "publish": True, "actor": "qa_user"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["release"]["dataset_version"] == "published-v2"


def test_reference_release_api_requires_configured_token(monkeypatch, tmp_path):
    Session = create_session_factory(f"sqlite:///{(tmp_path / 'release_token.sqlite3').as_posix()}")
    monkeypatch.setattr(api, "session_scope", lambda: _session_scope_for(Session))
    monkeypatch.setenv("TH_EVI_ADMIN_TOKEN", "test-token")
    client = TestClient(app)

    denied = client.get("/api/reference/releases", params={"province": "Chiang Mai"})
    assert denied.status_code == 403

    accepted = client.get(
        "/api/reference/releases",
        params={"province": "Chiang Mai"},
        headers={"X-TH-EVI-Admin-Token": "test-token"},
    )
    assert accepted.status_code == 200
