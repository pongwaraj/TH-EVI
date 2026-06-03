"""Tests for reference-data ingestion behavior."""

from __future__ import annotations

import csv

from th_evi import ingest
from th_evi.db import (
    AADTSegment,
    ChargerCompetitor,
    POIReference,
    ProvinceIngestionRun,
    ReferenceSource,
    create_session_factory,
)


def _write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_ingest_preserves_sources_and_rerun_status(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "PROVINCE_SLUGS", ["test_province"])
    monkeypatch.setattr(ingest, "SLUG_TO_NAME", {"test_province": "Test Province"})
    ingest._official_aadt_keys.cache_clear()

    _write_csv(
        tmp_path / "tha_pop_adm2_2023.csv",
        ["ADM1_EN", "ADM2_EN", "T_TL", "M_TL", "F_TL", "year"],
        [{"ADM1_EN": "Test Province", "ADM2_EN": "Test District", "T_TL": "12345", "M_TL": "6000", "F_TL": "6345", "year": "2566"}],
    )
    _write_csv(
        tmp_path / "aadt_2566.csv",
        ["route", "control", "name", "km", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10", "total", "heavy_pct", "moto", "bike", "office", "province"],
        [{"route": "1", "control": "100", "name": "Official Segment", "km": "10+000", "c1": 0, "c2": 0, "c3": 0, "c4": 0, "c5": 0, "c6": 0, "c7": 0, "c8": 0, "c9": 0, "c10": 0, "total": 12345, "heavy_pct": 12.5, "moto": 0, "bike": 0, "office": "Test", "province": "Test Province"}],
    )
    _write_csv(
        tmp_path / "aadt_test_province_seed.csv",
        ["year_be", "route", "name", "km", "aadt", "heavy_vehicle_pct", "province", "source", "notes"],
        [{"year_be": "2566", "route": "1", "name": "Official Segment", "km": "10+000", "aadt": "12345", "heavy_vehicle_pct": "12.5", "province": "Test Province", "source": "DOH aadt_2566.csv", "notes": "matched official"}],
    )
    _write_csv(
        tmp_path / "poi_test_province_seed.csv",
        ["poi_id", "name", "category", "lat", "lon", "source", "confidence", "notes"],
        [{"poi_id": "poi_1", "name": "Test Mall", "category": "shopping_mall", "lat": "18.1", "lon": "99.1", "source": "OpenStreetMap + public listing", "confidence": "high", "notes": "test"}],
    )
    _write_csv(
        tmp_path / "competitors_test_province_seed.csv",
        ["station_id", "name", "operator", "network", "lat", "lon", "source_type", "verification_status", "confidence", "notes"],
        [{"station_id": "comp_1", "name": "Test Charger", "operator": "PEA", "network": "PEA VOLTA", "lat": "18.2", "lon": "99.2", "source_type": "osm", "verification_status": "seed_needs_verification", "confidence": "low", "notes": "test"}],
    )

    Session = create_session_factory(f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    with Session() as session:
        source_map = ingest.seed_reference_sources(session)
        ingest.ingest_district_population(session, source_map)
        ingest.ingest_province(session, source_map, "test_province")
        session.commit()

    with Session() as session:
        source_by_id = {row.id: row.source_name for row in session.query(ReferenceSource).all()}
        poi = session.query(POIReference).one()
        competitor = session.query(ChargerCompetitor).one()
        run = session.query(ProvinceIngestionRun).one()
        assert source_by_id[poi.source_id] == "OpenStreetMap"
        assert source_by_id[competitor.source_id] == "OpenStreetMap"
        assert run.status == "imported_db"
        assert "No seed files found" not in (run.notes or "")

    with Session() as session:
        source_map = ingest.seed_reference_sources(session)
        ingest.ingest_district_population(session, source_map)
        ingest.ingest_province(session, source_map, "test_province")
        session.commit()

    with Session() as session:
        runs = session.query(ProvinceIngestionRun).order_by(ProvinceIngestionRun.id).all()
        assert len(runs) == 2
        assert runs[-1].status == "imported_db"
        assert "No seed files found" not in (runs[-1].notes or "")
        assert session.query(POIReference).count() == 1
        assert session.query(ChargerCompetitor).count() == 1
        assert session.query(AADTSegment).count() == 1


def test_aadt_official_crosscheck_downgrades_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "SLUG_TO_NAME", {"test_province": "Test Province"})
    ingest._official_aadt_keys.cache_clear()

    _write_csv(
        tmp_path / "aadt_2566.csv",
        ["route", "control", "name", "km", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10", "total", "heavy_pct", "moto", "bike", "office", "province"],
        [{"route": "1", "control": "100", "name": "Official Segment", "km": "10+000", "c1": 0, "c2": 0, "c3": 0, "c4": 0, "c5": 0, "c6": 0, "c7": 0, "c8": 0, "c9": 0, "c10": 0, "total": 12345, "heavy_pct": 12.5, "moto": 0, "bike": 0, "office": "Test", "province": "Test Province"}],
    )
    _write_csv(
        tmp_path / "aadt_test_province_seed.csv",
        ["year_be", "route", "name", "km", "aadt", "heavy_vehicle_pct", "province", "source", "notes", "confidence"],
        [{"year_be": "2566", "route": "1", "name": "Mismatch Segment", "km": "99+999", "aadt": "54321", "heavy_vehicle_pct": "8.0", "province": "Test Province", "source": "DOH aadt_2566.csv", "notes": "bad claim", "confidence": "high"}],
    )

    Session = create_session_factory(f"sqlite:///{(tmp_path / 'mismatch.sqlite3').as_posix()}")
    with Session() as session:
        source_map = ingest.seed_reference_sources(session)
        stats = ingest.ingest_aadt_segments(session, source_map, "test_province")
        session.commit()
        row = session.query(AADTSegment).one()
        source_by_id = {ref.id: ref.source_name for ref in session.query(ReferenceSource).all()}
        assert stats["crosscheck_failures"] == 1
        assert row.confidence == "low"
        assert source_by_id[row.source_id] == "seed_estimate"
        assert "cross-check failed" in (row.notes or "").lower()
