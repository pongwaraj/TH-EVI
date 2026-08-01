"""Reference release tests: CSV remains authoritative until DB parity is published."""

from __future__ import annotations

import csv

from th_evi import ingest, spatial
from th_evi.db import POIReference, create_session_factory
from th_evi.reference_sync import sync_province_reference


def _write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _clear_spatial_caches():
    spatial._has_published_database_release.cache_clear()
    spatial.load_pois_for_province.cache_clear()
    spatial.load_competitors_for_province.cache_clear()
    spatial.load_hot_zones_for_province.cache_clear()
    spatial.load_business_areas_for_province.cache_clear()
    spatial.load_heatmap_exclusions_for_province.cache_clear()
    spatial.load_district_nodes_for_province.cache_clear()


def _write_reference_files(tmp_path):
    _write_csv(
        tmp_path / "poi_chiang_mai_seed.csv",
        ["poi_id", "province", "name", "category", "lat", "lon", "confidence"],
        [{"poi_id": "poi_csv", "province": "Chiang Mai", "name": "CSV Mall", "category": "shopping_mall", "lat": "18.80", "lon": "98.98", "confidence": "high"}],
    )
    _write_csv(
        tmp_path / "competitors_chiang_mai_seed.csv",
        ["station_id", "province", "name", "lat", "lon", "guns", "max_kw", "verification_status", "confidence"],
        [{"station_id": "comp_csv", "province": "Chiang Mai", "name": "CSV Charger", "lat": "18.81", "lon": "98.99", "guns": "2", "max_kw": "120", "verification_status": "verified", "confidence": "high"}],
    )
    _write_csv(
        tmp_path / "business_areas_chiang_mai.csv",
        ["business_area_id", "province", "name", "area_type", "center_lat", "center_lon", "radius_km", "demand_pool_base", "confidence"],
        [{"business_area_id": "biz_csv", "province": "Chiang Mai", "name": "CSV Area", "area_type": "urban_fringe", "center_lat": "18.82", "center_lon": "99.00", "radius_km": "2.5", "demand_pool_base": "100", "confidence": "high"}],
    )
    _write_csv(
        tmp_path / "heatmap_exclusions_chiang_mai.csv",
        ["exclusion_id", "province", "name", "center_lat", "center_lon", "radius_km", "exclusion_type", "confidence"],
        [{"exclusion_id": "exc_csv", "province": "Chiang Mai", "name": "CSV Water", "center_lat": "18.83", "center_lon": "99.01", "radius_km": "1.2", "exclusion_type": "water", "confidence": "high"}],
    )
    _write_csv(
        tmp_path / "hot_zones_chiang_mai.csv",
        ["zone_id", "province", "name", "center_lat", "center_lon", "radius_km", "heat_rank", "demand_pool_base", "confidence"],
        [{"zone_id": "zone_csv", "province": "Chiang Mai", "name": "CSV Zone", "center_lat": "18.84", "center_lon": "99.02", "radius_km": "2.0", "heat_rank": "1", "demand_pool_base": "160", "confidence": "high"}],
    )
    _write_csv(
        tmp_path / "district_nodes_chiang_mai.csv",
        ["node_id", "province", "district_name", "name", "node_type", "lat", "lon", "radius_km", "confidence_multiplier", "confidence"],
        [{"node_id": "node_csv", "province": "Chiang Mai", "district_name": "Mueang Chiang Mai", "name": "CSV Node", "node_type": "district_center", "lat": "18.85", "lon": "99.03", "radius_km": "2.5", "confidence_multiplier": "1", "confidence": "high"}],
    )


def test_sync_publishes_verified_release_and_switches_to_database(monkeypatch, tmp_path):
    _write_reference_files(tmp_path)
    Session = create_session_factory(f"sqlite:///{(tmp_path / 'refs.sqlite3').as_posix()}")
    monkeypatch.setattr(ingest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(spatial, "DATA_DIR", tmp_path)
    monkeypatch.setattr(spatial, "get_session_factory", lambda: Session)

    with Session() as session:
        session.add(
            POIReference(
                poi_id="retired_ingest_row",
                province="Chiang Mai",
                name="Stale row",
                category="shopping_mall",
                lat=18.7,
                lon=98.8,
                updated_by="ingest",
                active=True,
            )
        )
        session.commit()

        result = sync_province_reference(session, "chiang_mai", publish=True, actor="test")
        session.commit()
        assert result["status"] == "published"
        assert result["parity"]["passed"] is True
        assert session.query(POIReference).filter_by(poi_id="retired_ingest_row").one().active is False

        poi = session.query(POIReference).filter_by(poi_id="poi_csv").one()
        poi.name = "DB reviewed mall"
        poi.updated_by = "data_admin"
        session.commit()

    _clear_spatial_caches()
    rows = spatial.load_pois_for_province("Chiang Mai")
    assert [row["name"] for row in rows if row["poi_id"] == "poi_csv"] == ["DB reviewed mall"]
    assert "retired_ingest_row" not in {row["poi_id"] for row in rows}
    _clear_spatial_caches()
