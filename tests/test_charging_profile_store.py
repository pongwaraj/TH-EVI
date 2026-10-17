import csv
import json

from sqlalchemy import text

from th_evi import spatial
from th_evi.charging_profile_store import backfill_competitor_evidence, persist_profile_snapshot
from th_evi.charging_profiles import profile_for_province
from th_evi.competition import competitor_evidence
from th_evi.db import ChargerCompetitor, ChargingBehaviorProfileSnapshot, create_session_factory


def test_snapshot_is_idempotent_and_retains_history():
    factory = create_session_factory("sqlite:///:memory:")
    profile = profile_for_province("Chiang Mai")
    with factory() as session:
        first = persist_profile_snapshot(session, profile, engine_version="test", actor="test")
        repeat = persist_profile_snapshot(session, profile, engine_version="test", actor="test")
        assert first["created"] and not repeat["created"]
        assert first["id"] == repeat["id"]
        changed = {**profile, "notes": "new evidence under review"}
        second = persist_profile_snapshot(session, changed, engine_version="test", actor="test")
        assert second["profile_sha256"] != first["profile_sha256"]
        assert session.query(ChargingBehaviorProfileSnapshot).count() == 2
        assert json.loads(session.get(ChargingBehaviorProfileSnapshot, first["id"]).profile_json) == profile


def test_evidence_backfill_preserves_existing_data_and_other_provinces(tmp_path, monkeypatch):
    factory = create_session_factory("sqlite:///:memory:")
    path = tmp_path / "competitors.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["station_id", "connector_summary", "power_summary"])
        writer.writeheader()
        writer.writerows([
            {"station_id": "missing", "connector_summary": "DC CCS2", "power_summary": "Interim modeling assumption: 50 kW DC"},
            {"station_id": "admin", "power_summary": "50 kW DC"},
        ])
    with factory() as session:
        for province, station, summary in [("Chiang Mai", "missing", None), ("Chiang Mai", "admin", "Operator confirmed 180 kW DC"), ("เชียงราย", "missing", None)]:
            session.add(ChargerCompetitor(province=province, station_id=station, name=station,
                                          lat=18.8, lon=99, max_kw=50, gun_count=2, power_summary=summary))
        session.commit()
        result = backfill_competitor_evidence(session, "เชียงใหม่", [path])
        assert len(result["updated"]) == 1
        assert len(result["preserved_conflicts"]) == 1
        assert session.query(ChargerCompetitor).filter_by(province="เชียงราย").one().power_summary is None
        row = session.query(ChargerCompetitor).filter_by(province="Chiang Mai", station_id="missing").one()
        assert row.max_kw == 50 and row.gun_count == 2
        session.commit()
    monkeypatch.setattr(spatial, "get_session_factory", lambda: factory)
    rows = spatial._load_db_competitors_for_province("Chiang Mai")
    evidence = competitor_evidence(next(row for row in rows if row["station_id"] == "missing"))
    assert evidence["power_evidence"] == "assumed_not_verified"
    assert evidence["max_kw"] is None


def test_existing_sqlite_schema_gets_additive_evidence_columns(tmp_path):
    path = tmp_path / "old.sqlite3"
    url = f"sqlite:///{path.as_posix()}"
    factory = create_session_factory(url)
    engine = factory.kw["bind"]
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE charger_competitors DROP COLUMN connector_summary"))
        conn.execute(text("ALTER TABLE charger_competitors DROP COLUMN power_summary"))
    updated = create_session_factory(url)
    with updated() as session:
        assert session.query(ChargerCompetitor).count() == 0
