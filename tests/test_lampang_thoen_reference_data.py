import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from th_evi import data
from th_evi.adoption import estimate_fleet_ev_population, estimate_fleet_ev_share
from th_evi.competition import competitor_evidence, dc_competition_pressure
from th_evi.location import LocationDemandModel
from th_evi.poi_policy import poi_rule
from th_evi.spatial import (
    km_between, load_competitors_for_province, load_district_nodes_for_province,
    load_pois_for_province,
)


ROOT = Path(__file__).resolve().parents[1]
TARGET = (17.650561, 99.249117)
CURATED_IDS = {"lampang_kml_90495e222126", "lampang_kml_df7d4acdcf4a",
               "spark_bcp_thoen_napha_0641"}


def test_shell_tha_pha_pin_and_poi_hierarchy_do_not_invent_a_mall():
    pois = {row["poi_id"]: row for row in load_pois_for_province("Lampang")}
    shell = pois["shell_tha_pha_thoen"]
    assert shell["category"] == "highway_service_area"
    assert poi_rule(shell["category"]).weight == poi_rule("gas_station").weight
    assert "12849483" in shell["source"]
    assert "find.shell.com" in shell["source_url"]
    assert shell["district"] == "Thoen"
    assert km_between(*TARGET, float(shell["lat"]), float(shell["lon"])) < .05
    assert pois["thoen_hospital"]["category"] == "hospital"
    assert pois["thoen_intercity_bus_stop"]["category"] == "transport_corridor"
    assert "central_lampang" in pois
    assert not any("maple" in key.lower() for key in pois)
    node = next(r for r in load_district_nodes_for_province("Lampang") if r["node_id"] == "lp_thoen")
    assert float(node["radius_km"]) <= 2.4
    assert km_between(float(node["lat"]), float(node["lon"]), 17.621402, 99.236659) < .01


@pytest.mark.parametrize("province", ["Lampang", "ลำปาง"])
def test_lampang_observed_dlt_anchor_uses_passenger_bevs_not_all_ev_types(province):
    assert estimate_fleet_ev_population(2026, province) == 1725
    assert estimate_fleet_ev_share(2026, province) == pytest.approx(1725 / 100950)


def test_tha_pha_aadt_uses_a_bounded_2568_corridor_proxy():
    with (ROOT / "data/aadt_2568.csv").open(encoding="utf-8-sig", newline="") as handle:
        source = next(r for r in csv.DictReader(handle) if r["ทางหลวงสาย"] == "1"
                      and r["ตอนควบคุม"] == "1102" and r["จุดสำรวจ"] == "617+097")
    assert int(source["รวม"]) == 13337
    assert LocationDemandModel._find_nearest_highway(*TARGET, "Lampang") == int(source["รวม"])
    assert LocationDemandModel._find_nearest_highway(*TARGET, "ลำปาง") == 13337
    assert LocationDemandModel._find_nearest_highway(17.68, 99.28, "Lampang") != 13337


def test_tha_pha_click_and_heat_grid_share_highway_classification():
    from th_evi.heatmap import _location_type_for_heat
    from th_evi.spatial import _spatial_location_type, poi_attraction_field

    _, evidence = poi_attraction_field(*TARGET, load_pois_for_province("Lampang"))
    click_type = _spatial_location_type(evidence)
    heat_type = _location_type_for_heat(evidence, [], [])
    assert click_type == heat_type == "highway"
    assert LocationDemandModel("Lampang").estimate(*TARGET, 2026, location_type=heat_type)["aadt_used"] == 13337


@pytest.mark.parametrize("include_kml", [False, True])
def test_curated_thoen_competitors_are_unique_and_preserve_supplied_specs(include_kml):
    rows = load_competitors_for_province("Lampang", include_nationwide_kml=include_kml)
    for station_id in CURATED_IDS:
        assert sum(r["station_id"] == station_id for r in rows) == 1
    selected = {r["station_id"]: r for r in rows if r["station_id"] in CURATED_IDS}
    assert competitor_evidence(selected["lampang_kml_90495e222126"])["max_kw"] == 120
    assert competitor_evidence(selected["lampang_kml_df7d4acdcf4a"])["max_kw"] == 150
    spark = competitor_evidence(selected["spark_bcp_thoen_napha_0641"])
    assert spark["guns"] == 4
    assert spark["max_kw"] == 240 and spark["direct_dc_eligible"]
    assert selected["spark_bcp_thoen_napha_0641"]["cabinet_count"] == "2"
    assert "project coordinator" in selected["spark_bcp_thoen_napha_0641"]["notes"]
    pending = next(r for r in rows if r["station_id"] == "elex_pt_thoen_pending_pin")
    assert competitor_evidence(pending)["max_kw"] == 124
    assert not pending["lat"] and not pending["lon"]
    pressure = dc_competition_pressure(*TARGET, rows)
    assert pressure["pressure"] > 0
    assert "spark_bcp_thoen_napha_0641" not in pressure["unknown_station_ids"]
    assert pressure["skipped_without_coordinates"] >= 1


@pytest.mark.parametrize("province", ["Lampang", "ลำปาง"])
def test_lampang_dopa_includes_municipalities_and_reconciles_to_province(province):
    populations = data.load_district_population_for_province(province).set_index("district")["population"]
    assert len(populations) == 13
    assert populations["Thoen"] == 31978 + 9941 + 13299 == 55218
    assert populations.sum() == 697679


@pytest.mark.parametrize("invalid", ["overlap", "missing", "duplicate_district", "balance"])
def test_dopa_reviewed_mapping_rejects_incomplete_or_double_counted_population(monkeypatch, tmp_path, invalid):
    mappings = pd.read_csv(ROOT / "data/dopa_district_components.csv", dtype=str)
    if invalid == "overlap":
        mappings.loc[0, "area_codes"] += "|5208"
    elif invalid == "missing":
        mappings.loc[7, "area_codes"] = "5208|5283"
    elif invalid == "duplicate_district":
        mappings.loc[1, "district"] = mappings.loc[0, "district"]
    mappings.to_csv(tmp_path / "dopa_district_components.csv", index=False)
    dopa = pd.read_csv(ROOT / "data/evhub_dopa_population_2568.csv")
    if invalid == "balance":
        dopa.loc[(dopa["province"] == "ลำปาง") & (dopa["area_type"] == "province"), "population"] += 1
    dopa.to_csv(tmp_path / "evhub_dopa_population_2568.csv", index=False)
    monkeypatch.setattr(data, "DATA_DIR", tmp_path)
    with pytest.warns(RuntimeWarning):
        assert data._load_reviewed_dopa_district_population("Lampang").empty


def test_reference_csv_rows_have_matching_columns():
    for name in ("poi_lampang_city_seed.csv", "competitors_lampang_seed.csv",
                 "competitors_lampang_detailed.csv", "aadt_lampang_seed.csv",
                 "district_nodes_lampang.csv", "dopa_district_components.csv"):
        with (ROOT / "data" / name).open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        assert all(len(row) == len(rows[0]) for row in rows), name


def test_lampang_can_be_ingested_without_losing_source_or_supplied_spark_power():
    from th_evi.db import ChargerCompetitor, POIReference, create_session_factory
    from th_evi.ingest import ingest_province, seed_reference_sources

    factory = create_session_factory("sqlite:///:memory:")
    with factory() as session:
        ingest_province(session, seed_reference_sources(session), "lampang")
        shell = session.query(POIReference).filter_by(poi_id="shell_tha_pha_thoen").one()
        assert shell.category == "highway_service_area"
        assert shell.verification_status == "operator_location_verified"
        assert shell.source_url.startswith("https://find.shell.com/")
        spark = session.query(ChargerCompetitor).filter_by(station_id="spark_bcp_thoen_napha_0641").one()
        assert spark.max_kw == 240 and spark.gun_count == 4
        assert "project coordinator" in spark.notes


def test_shell_tha_pha_handoff_has_portable_inputs_and_matching_competitor_specs():
    inputs = json.loads((ROOT / "data/site_analysis/shell_thapha_thoen_20261027.json").read_text(encoding="utf-8"))
    assert inputs["financial_assumptions"]["capex_thb"] == 2300500
    assert inputs["click_analysis"]["net_sessions_per_day"] == 2
    assert inputs["station"] == {"cabinets": 1, "cabinet_kw": 180, "bays": 2}
    assert all((ROOT / name).is_file() for name in inputs["current_data_files"])
    rows = {r["station_id"]: r for r in load_competitors_for_province("Lampang", False)}
    for update in inputs["project_coordinator_competitor_updates"]:
        assert float(rows[update["station_id"]]["max_kw"]) == update["cabinet_kw"]
    assert (ROOT / "artifacts/report_assets/tce_brand_logo.png").is_file()
    assert (ROOT / "outputs/shell_thapha_owner_area_analysis/site_context_map.png").is_file()
