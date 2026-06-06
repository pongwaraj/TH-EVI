"""Tests for DB-backed spatial reference loaders with CSV fallback."""

from __future__ import annotations

import csv

from th_evi.db import (
    BusinessAreaReference,
    ChargerCompetitor,
    DistrictNodeReference,
    HeatmapExclusionReference,
    HotZoneReference,
    POIReference,
    create_session_factory,
)
from th_evi import spatial


def _write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _clear_spatial_caches():
    spatial.load_pois_for_province.cache_clear()
    spatial.load_competitors_for_province.cache_clear()
    spatial.load_hot_zones_for_province.cache_clear()
    spatial.load_business_areas_for_province.cache_clear()
    spatial.load_heatmap_exclusions_for_province.cache_clear()
    spatial.load_district_nodes_for_province.cache_clear()
    spatial.load_enriched_district_nodes.cache_clear()


def test_spatial_reference_loaders_merge_db_and_csv(monkeypatch, tmp_path):
    Session = create_session_factory(f"sqlite:///{(tmp_path / 'refs.sqlite3').as_posix()}")
    with Session() as session:
        session.add(
            POIReference(
                poi_id="db_poi_1",
                province="Chiang Mai",
                name="DB Mall",
                category="shopping_mall",
                lat=18.8,
                lon=98.9,
                confidence="high",
            )
        )
        session.add(
            ChargerCompetitor(
                station_id="db_comp_1",
                province="Chiang Mai",
                name="DB Charger",
                network="PEA VOLTA",
                operator="PEA",
                lat=18.81,
                lon=98.91,
                gun_count=2,
                max_kw=120.0,
                verification_status="verified",
                confidence="high",
            )
        )
        session.add(
            BusinessAreaReference(
                business_area_id="db_biz_1",
                province="Chiang Mai",
                name="DB Growth Belt",
                area_type="urban_fringe",
                center_lat=18.82,
                center_lon=98.92,
                radius_km=3.4,
                demand_pool_base=120.0,
                confidence="high",
            )
        )
        session.add(
            HeatmapExclusionReference(
                exclusion_id="db_exc_1",
                province="Chiang Mai",
                name="DB Water",
                center_lat=18.83,
                center_lon=98.93,
                radius_km=2.0,
                exclusion_type="water",
                confidence="high",
            )
        )
        session.add(
            HotZoneReference(
                zone_id="db_zone_1",
                province="Chiang Mai",
                name="DB Airport Core",
                center_lat=18.84,
                center_lon=98.94,
                radius_km=3.0,
                heat_rank=1,
                demand_pool_base=200.0,
                confidence="high",
            )
        )
        session.add(
            DistrictNodeReference(
                node_id="db_node_1",
                province="Chiang Mai",
                district_name="Mueang Chiang Mai",
                name="DB district node",
                node_type="district_center",
                lat=18.85,
                lon=98.95,
                radius_km=4.0,
                confidence_multiplier=1.0,
                confidence="high",
            )
        )
        session.commit()

    _write_csv(
        tmp_path / "poi_chiang_mai_seed.csv",
        ["poi_id", "name", "category", "lat", "lon", "confidence"],
        [{"poi_id": "csv_poi_1", "name": "CSV Market", "category": "market_tourism", "lat": "18.7", "lon": "98.8", "confidence": "medium"}],
    )
    _write_csv(
        tmp_path / "competitors_chiang_mai_seed.csv",
        ["station_id", "name", "network", "operator", "lat", "lon", "verification_status", "confidence"],
        [{"station_id": "csv_comp_1", "name": "CSV Charger", "network": "EV Station PluZ", "operator": "OR", "lat": "18.71", "lon": "98.81", "verification_status": "seed_needs_verification", "confidence": "low"}],
    )
    _write_csv(
        tmp_path / "business_areas_chiang_mai.csv",
        ["business_area_id", "name", "area_type", "center_lat", "center_lon", "radius_km", "demand_pool_base", "confidence"],
        [{"business_area_id": "csv_biz_1", "name": "CSV Fringe", "area_type": "urban_fringe", "center_lat": "18.72", "center_lon": "98.82", "radius_km": "3.0", "demand_pool_base": "90", "confidence": "medium"}],
    )
    _write_csv(
        tmp_path / "heatmap_exclusions_chiang_mai.csv",
        ["exclusion_id", "name", "center_lat", "center_lon", "radius_km", "exclusion_type", "confidence", "reason"],
        [{"exclusion_id": "csv_exc_1", "name": "CSV Lake", "center_lat": "18.73", "center_lon": "98.83", "radius_km": "1.8", "exclusion_type": "water", "confidence": "high", "reason": "test"}],
    )
    _write_csv(
        tmp_path / "hot_zones_chiang_mai.csv",
        ["zone_id", "name", "center_lat", "center_lon", "radius_km", "heat_rank", "demand_pool_base", "confidence"],
        [{"zone_id": "csv_zone_1", "name": "CSV Retail Core", "center_lat": "18.74", "center_lon": "98.84", "radius_km": "3.1", "heat_rank": "2", "demand_pool_base": "150", "confidence": "medium"}],
    )
    _write_csv(
        tmp_path / "district_nodes_chiang_mai.csv",
        ["node_id", "district_name", "name", "node_type", "lat", "lon", "radius_km", "confidence_multiplier"],
        [{"node_id": "csv_node_1", "district_name": "San Sai", "name": "CSV district node", "node_type": "district_center", "lat": "18.75", "lon": "98.85", "radius_km": "3.6", "confidence_multiplier": "0.9"}],
    )

    monkeypatch.setattr(spatial, "DATA_DIR", tmp_path)
    monkeypatch.setattr(spatial, "get_session_factory", lambda: Session)
    _clear_spatial_caches()

    poi_rows = spatial.load_pois_for_province("เชียงใหม่")
    competitor_rows = spatial.load_competitors_for_province("เชียงใหม่")
    business_rows = spatial.load_business_areas_for_province("เชียงใหม่")
    exclusion_rows = spatial.load_heatmap_exclusions_for_province("เชียงใหม่")
    zone_rows = spatial.load_hot_zones_for_province("เชียงใหม่")
    node_rows = spatial.load_district_nodes_for_province("เชียงใหม่")

    assert {row["poi_id"] for row in poi_rows} == {"db_poi_1", "csv_poi_1"}
    assert {row["station_id"] for row in competitor_rows} == {"db_comp_1", "csv_comp_1"}
    assert {row["business_area_id"] for row in business_rows} == {"db_biz_1", "csv_biz_1"}
    assert {row["exclusion_id"] for row in exclusion_rows} == {"db_exc_1", "csv_exc_1"}
    assert {row["zone_id"] for row in zone_rows} == {"db_zone_1", "csv_zone_1"}
    assert {row["node_id"] for row in node_rows} == {"db_node_1", "csv_node_1"}
    _clear_spatial_caches()
