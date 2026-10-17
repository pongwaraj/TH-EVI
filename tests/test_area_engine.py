from math import fsum

from fastapi.testclient import TestClient
import pytest

from th_evi.api import app, _clear_reference_caches
from th_evi import area_engine as engine
from th_evi.competition import competitor_evidence, dc_competition_pressure


def competitor(**kwargs):
    return {"station_id": "dc", "lat": 18.005, "lon": 99.005, "max_kw": 120,
            "guns": 2, "connector_summary": "2 CCS2 DC heads", **kwargs}


def point(lat=18.005, lon=99.005, **kwargs):
    return {"lat": lat, "lon": lon, "model_sessions": 10, "poi_score": 4,
            "zone_score": 6, "business_area_score": 3, "district_score": 0,
            "pois": ["Cafe"], **kwargs}


@pytest.mark.parametrize("field", ["max_kw", "power_kw", "kw"])
def test_missing_power_is_never_assumed_to_be_120(field):
    row = competitor(max_kw=None, **({field: ""} if field != "max_kw" else {}))
    evidence = competitor_evidence(row)
    assert evidence["max_kw"] is None
    assert evidence["direct_dc_eligible"] is False


def test_no_implicit_gun_count():
    evidence = competitor_evidence(competitor(guns=None, connector_summary="DC CCS2"))
    assert evidence["guns"] is None


def test_assumed_numeric_power_in_existing_data_is_not_verified_evidence():
    evidence = competitor_evidence(competitor(max_kw=50, power_summary="Interim modeling assumption: 1 DC gun at 50 kW"))
    assert evidence["power_evidence"] == "assumed_not_verified"
    assert evidence["max_kw"] is None
    assert evidence["guns"] is None


@pytest.mark.parametrize("text", ["updated 2026; 12 ports", "720 kW total reported", "900 kW site power"])
def test_dates_and_site_total_cannot_become_per_gun_kw(text):
    assert competitor_evidence(competitor(max_kw=None, power_summary=text))["max_kw"] is None


def test_explicit_kw_and_connector_type_are_parsed():
    item = competitor_evidence(competitor(max_kw=None, power_summary="Up to 180 kW DC"))
    assert item["max_kw"] == 180
    assert item["direct_dc_eligible"]


def test_ac_does_not_directly_compete_for_dc_and_unknown_is_disclosed():
    ac = competitor(station_id="ac", connector_summary="AC Type 2", max_kw=22)
    unknown = competitor(station_id="unknown", connector_summary="unknown", max_kw=None)
    result = dc_competition_pressure(18.005, 99.005, [ac, unknown])
    assert result["pressure"] == 0
    assert result["unknown_station_ids"] == ["unknown"]
    assert result["competition_share_missing_data_bounds"] == [0, 1]


def test_low_power_has_no_floor_and_distance_matters():
    low = dc_competition_pressure(18.005, 99.005, [competitor(max_kw=25)])
    high = dc_competition_pressure(18.005, 99.005, [competitor(max_kw=120)])
    far = dc_competition_pressure(18.05, 99.005, [competitor(max_kw=120)])
    assert low["pressure"] / high["pressure"] == pytest.approx(25 / 120)
    assert far["pressure"] < high["pressure"]


def test_strong_competition_can_exceed_legacy_62_percent_ceiling():
    result = dc_competition_pressure(18.005, 99.005, [competitor(max_kw=240, guns=12)])
    assert 0.62 < result["competition_share"] < 1


@pytest.mark.parametrize("row", [competitor(public_access="private"), competitor(verification_status="closed")])
def test_non_public_or_closed_stations_do_not_apply_pressure(row):
    assert dc_competition_pressure(18.005, 99.005, [row])["pressure"] == 0


def test_missing_coordinates_are_not_silently_located():
    result = dc_competition_pressure(18, 99, [{"station_id": "missing"}])
    assert result["skipped_without_coordinates"] == 1
    assert result["pressure"] == 0


def test_unknown_specs_produce_missing_data_envelope_not_zero_competition_claim():
    surface = engine.allocate_support([point()], [competitor(max_kw=None)])
    row = surface["points"][0]
    assert row["competition_score_bounds"] == [0, 100]
    assert row["net_opportunity_score_bounds"] == [0, 100]
    display = engine.aggregate_support(surface["points"], 0.01, 0.01, 0.5)
    assert fsum(p["competition_score_bounds"][1] for p in display) == pytest.approx(100)


def test_poi_changes_weights_not_screening_total_or_explicit_energy_budget():
    before = engine.allocate_support([point(), point(18.015)], [])
    after = engine.allocate_support([point(poi_score=10000), point(18.015)], [])
    assert before["accounting"]["gross_allocated"] == pytest.approx(100)
    assert after["accounting"]["gross_allocated"] == pytest.approx(100)
    assert before["points"][0]["demand_score"] < after["points"][0]["demand_score"]
    physical = engine.allocate_support([point(), point(18.015)], [], energy_kwh=1000, coverage_fraction=0.6)
    assert physical["accounting"]["gross_allocated"] == 600
    assert physical["accounting"]["outside_coverage"] == 400
    assert physical["accounting"]["energy_budget_enforced"] is True
    assert before["points"][0]["daily_kwh"] is None
    with pytest.raises(ValueError):
        engine.allocate_support([point()], [], energy_kwh=1000)


@pytest.mark.parametrize("resolution", [0.25, 0.5, 0.7, 1, 1.5, 2, 5])
def test_all_resolutions_preserve_gross_competition_and_available_mass(resolution):
    source = engine.allocate_support([point(), point(18.015), point(18.025, 99.015)], [competitor()])
    display = engine.aggregate_support(source["points"], 0.01, 0.01, resolution)
    for field in ("demand_score", "competition_score", "net_opportunity_score"):
        assert fsum(p[field] for p in display) == pytest.approx(fsum(p[field] for p in source["points"]), abs=1e-7)
    for p in display:
        assert p["demand_score"] == pytest.approx(p["competition_score"] + p["net_opportunity_score"])
        assert p["coverage_fragments"]


@pytest.fixture
def fixed_pilot(monkeypatch):
    source = engine.allocate_support([point(district_name="A"), point(18.025, district_name="B")], [competitor()])
    source.update(lat_step_deg=0.01, lon_step_deg=0.01, bounds={
        "lat_min": 18, "lat_max": 18.03, "lon_min": 99, "lon_max": 99.01,
    }, zones=[], source_metadata={})
    monkeypatch.setattr(engine, "fixed_surface", lambda *args: source)
    engine.generate_area_surface.cache_clear()
    yield source
    engine.generate_area_surface.cache_clear()


@pytest.mark.parametrize("resolution", [0.5, 1, 2, 5])
def test_api_heatmap_and_click_return_identical_cell_values(fixed_pilot, resolution):
    client = TestClient(app)
    result = client.get("/api/heatmap", params={"province": "Chiang Mai", "resolution_km": resolution}).json()
    target = result["points"][0]
    ((s, w), (n, e)) = target.get("coverage_fragments", [[
        [target["lat"] - result["lat_step_deg"] / 2, target["lon"] - result["lon_step_deg"] / 2],
        [target["lat"] + result["lat_step_deg"] / 2, target["lon"] + result["lon_step_deg"] / 2],
    ]])[0]
    response = client.post("/api/click-analysis", json={
        "lat": (s+n)/2, "lon": (w+e)/2, "province": "Chiang Mai", "year": 2030,
        "resolution_km": resolution,
    })
    assert response.status_code == 200
    clicked = response.json()
    assert clicked["cell_id"] == target["cell_id"]
    for key in ("demand_score", "competition_score", "net_opportunity_score"):
        assert clicked[key] == target[key]
    assert clicked["net_sessions_per_day"] is None
    assert clicked["daily_kwh"] is None
    assert clicked["forecast_available"] is False
    assert result["metadata"]["energy_budget_enforced"] is False


def test_coarse_display_does_not_fill_support_holes(fixed_pilot):
    result = engine.analyze_area_cell(18.015, 99.005, "Chiang Mai", 2030, "base", "urban", 5)
    assert result["eligibility_status"] == "outside_support"
    assert result["demand_score"] == 0


def test_district_summaries_preserve_the_same_support_totals(fixed_pilot):
    result = engine.generate_area_surface("Chiang Mai", 2030, "base", 2, "district")
    assert {row["district_name"] for row in result["district_summaries"]} == {"A", "B"}
    assert fsum(row["demand_score"] for row in result["district_summaries"]) == pytest.approx(100)


def test_pilot_is_selected_only_for_configured_province():
    assert engine.use_pilot("Chiang Mai")
    assert not engine.use_pilot("Chiang Rai")
    assert not engine.use_pilot("Chiang Mai", "legacy")
    assert engine.use_pilot("Chiang Rai", "pilot")


def test_invalid_resolution_returns_400(fixed_pilot):
    response = TestClient(app).get("/api/heatmap", params={"province": "Chiang Mai", "resolution_km": 0.1})
    assert response.status_code == 400
    alias = TestClient(app).get("/api/heatmap/chiang-mai", params={"resolution_km": 0.1})
    assert alias.status_code == 400


def test_charger_inventory_does_not_present_assumptions_as_known_kw(monkeypatch):
    import th_evi.api as api
    monkeypatch.setattr(api.spatial_module, "load_competitors_for_province", lambda *args, **kwargs: [
        competitor(max_kw=50, power_summary="Interim modeling assumption: 1 DC gun at 50 kW"),
    ])
    station = api.list_chargers("Chiang Mai")["stations"][0]
    assert station["max_kw"] is None
    assert station["guns"] is None
    assert station["capacity"] is None
    assert station["power_evidence"] == "assumed_not_verified"


def test_admin_invalidation_clears_pilot_caches():
    engine.generate_area_surface.cache_clear()
    _clear_reference_caches()
    assert engine.generate_area_surface.cache_info().currsize == 0


def test_configured_physical_budget_is_wired_to_fixed_support(monkeypatch):
    import th_evi.charging_profiles as profiles
    import th_evi.heatmap as heatmap
    import th_evi.spatial as spatial

    off = {"effective_kw": 0, "available_hours": 0, "efficiency": 1, "use_fraction": 0}
    profile = {
        "spatial_energy_enabled": True, "spatial_coverage_fraction": 0.6,
        "cohorts": [{"cohort_id": "test", "fleet_share": 1, "active_day_share": 1,
                     "daily_km": 50, "battery_kwh_per_km": 0.2,
                     "home": off, "work": off, "public_ac": off}],
        "average_dc_session_kwh": 20, "dc_vehicle_efficiency": 1, "dc_station_efficiency": 1,
        "evidence": {key: "test-only evidence" for key in profiles.EVIDENCE_FIELDS},
    }
    monkeypatch.setattr(profiles, "profile_for_province", lambda p: profile)
    monkeypatch.setattr(profiles, "observed_bev_fleet", lambda p: {"bev": 100, "source_month": "2569-09"})
    monkeypatch.setattr(heatmap, "generate_province_heatmap", lambda *args, **kwargs: {
        "points": [point()], "lat_step_deg": 0.01, "lon_step_deg": 0.01,
        "bounds": {"lat_min": 18.005, "lon_min": 99.005}, "zones": [], "metadata": {},
    })
    monkeypatch.setattr(spatial, "load_competitors_for_province", lambda *args, **kwargs: [])
    engine.clear_caches()
    try:
        current = engine.fixed_surface("Chiang Mai", 2026, "base", "urban")
        assert current["accounting"]["gross_allocated"] == 600
        assert current["accounting"]["outside_coverage"] == 400
        assert current["accounting"]["energy_budget_enforced"]
        assert current["points"][0]["area_available_connector_kwh"] == 600
        future = engine.fixed_surface("Chiang Mai", 2030, "base", "urban")
        assert not future["accounting"]["energy_budget_enforced"]
        assert future["accounting"]["unit"] == "screening_share_percent"
        profile["evidence"] = {}
        with pytest.raises(ValueError, match="evidence"):
            profiles.configured_spatial_budget("Chiang Mai", 2026)
    finally:
        engine.clear_caches()
