from fastapi.testclient import TestClient

from th_evi.api import app
import th_evi.spatial as spatial
from th_evi.spatial import (
    analyze_click_location,
    assess_surface_access,
    competitor_penalty_field,
    load_competitors_for_province,
    load_pois_for_province,
    poi_attraction_field,
    zone_influence_field,
)

UDON_THANI = "\u0e2d\u0e38\u0e14\u0e23\u0e18\u0e32\u0e19\u0e35"
CHIANG_MAI = "Chiang Mai"


def test_poi_attraction_decays_with_distance():
    pois = [
        {
            "name": "Strong Mall",
            "category": "shopping_mall",
            "lat": "18.0",
            "lon": "99.0",
            "confidence": "high",
        }
    ]

    near, near_rows = poi_attraction_field(18.0, 99.0, pois)
    far, far_rows = poi_attraction_field(18.08, 99.08, pois)

    assert near > far
    assert near_rows[0]["name"] == "Strong Mall"
    assert far_rows == [] or far_rows[0]["sessions"] < near_rows[0]["sessions"]


def test_competitor_penalty_decays_with_distance_and_skips_missing_coordinates():
    competitors = [
        {
            "name": "Nearby DC Hub",
            "lat": "18.0",
            "lon": "99.0",
            "guns": "6",
            "max_kw": "240",
            "verification_status": "verified",
        },
        {
            "name": "Unpinned station",
            "lat": "",
            "lon": "",
            "verification_status": "seed_needs_verification",
        },
    ]

    near, near_rows, skipped = competitor_penalty_field(18.0, 99.0, competitors)
    far, _, _ = competitor_penalty_field(18.08, 99.08, competitors)

    assert skipped == 1
    assert near > far
    assert near_rows[0]["name"] == "Nearby DC Hub"


def test_zone_influence_decays_and_feeds_click_sessions():
    zones = [
        {
            "name": "Hot Retail Zone",
            "center_lat": "18.0",
            "center_lon": "99.0",
            "radius_km": "4.0",
            "demand_pool_base": "200",
            "competition_pressure": "medium",
            "confidence": "high",
        }
    ]

    near_score, near_rows = zone_influence_field(18.0, 99.0, zones, scenario="base")
    far_score, _ = zone_influence_field(18.08, 99.08, zones, scenario="base")

    assert near_score > far_score
    assert near_rows[0]["name"] == "Hot Retail Zone"


def test_click_analysis_combines_base_poi_and_competitor_fields():
    result = analyze_click_location(
        lat=17.4058,
        lon=102.7998,
        province=UDON_THANI,
        year=2030,
        scenario="base",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["net_sessions_per_day"] > 0
    assert result["zone_boost_sessions"] > 0
    assert result["poi_boost_sessions"] > 0
    assert result["spatial_boost_sessions"] >= max(
        result["zone_boost_sessions"],
        result["poi_boost_sessions"],
    )
    assert result["gross_area_demand_sessions"] >= result["net_sessions_per_day"]
    assert result["competitor_penalty_sessions"] <= result["raw_competitor_penalty_sessions"]
    assert result["net_sessions_per_day"] > result["base_sessions"]
    assert result["daily_kwh"] == round(result["net_sessions_per_day"] * 28, 1)
    assert result["top_pois"]
    assert result["top_zones"]
    assert result["eligibility_status"] == "eligible"
    assert result["access_ok"] is True
    assert result["urban_eligible"] is True


def test_click_analysis_rejects_isolated_point_without_access_signal():
    result = analyze_click_location(
        lat=17.05,
        lon=102.15,
        province=UDON_THANI,
        year=2030,
        scenario="base",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["eligibility_status"] == "rejected"
    assert result["access_ok"] is False
    assert result["urban_eligible"] is False
    assert result["surface_type"] == "isolated_land"
    assert result["net_sessions_per_day"] == 0.0
    assert result["eligibility_reason"]


def test_surface_access_uses_low_relevance_for_weak_but_real_context(monkeypatch):
    monkeypatch.setattr(
        spatial,
        "lookup_water_surface",
        lambda lat, lon: {
            "is_water": False,
            "surface_type": "land_or_unclassified",
            "reason": None,
            "warning": None,
            "feature_name": None,
        },
    )
    monkeypatch.setattr(
        spatial,
        "lookup_building_surface",
        lambda lat, lon: {
            "is_building": False,
            "surface_type": "land_or_unclassified",
            "reason": None,
            "warning": None,
            "feature_name": None,
        },
    )

    pois = [
        {"name": "Remote Mall", "category": "shopping_mall", "lat": "18.0000", "lon": "99.0435"},
        {"name": "Hospital", "category": "hospital", "lat": "18.0000", "lon": "99.0322"},
    ]
    zones = [
        {"name": "Urban Zone", "center_lat": "18.0000", "center_lon": "99.0438"},
    ]
    competitors = [
        {"name": "Competitor", "lat": "18.0000", "lon": "99.0329"},
    ]

    result = assess_surface_access(
        18.0,
        99.0,
        pois=pois,
        competitors=competitors,
        zones=zones,
        zone_score=8.0,
        poi_field_score=6.0,
    )

    assert result["status"] == "low_relevance"
    assert result["access_ok"] is False
    assert result["urban_eligible"] is False


def test_click_analysis_scales_down_low_relevance_points(monkeypatch):
    monkeypatch.setattr(
        spatial,
        "assess_surface_access",
        lambda *args, **kwargs: {
            "status": "low_relevance",
            "surface_type": "road_access_candidate",
            "access_ok": True,
            "urban_eligible": False,
            "reason": "Road access looks plausible, but the point is still outside a strong urban demand cluster.",
            "feature_name": None,
            "surface_warning": None,
            "nearest_access_anchor_km": 0.8,
            "nearest_urban_anchor_km": 1.9,
            "nearest_competitor_km": None,
            "nearest_zone_center_km": 2.0,
        },
    )

    result = analyze_click_location(
        lat=17.4058,
        lon=102.7998,
        province=UDON_THANI,
        year=2026,
        scenario="base",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["eligibility_status"] == "low_relevance"
    assert result["raw_base_sessions"] > result["base_sessions"]
    assert result["base_sessions"] <= 6.0
    assert result["spatial_boost_sessions"] < result["raw_spatial_boost_sessions"]
    assert result["net_sessions_per_day"] <= 6.0


def test_click_analysis_community_mode_uses_district_nodes():
    result = analyze_click_location(
        lat=18.5758,
        lon=99.0090,
        province="Lamphun",
        year=2026,
        scenario="base",
        mode="community",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["mode"] == "community"
    assert result["district_boost_sessions"] > 0
    assert result["top_districts"]


def test_click_analysis_fang_uses_new_pois_and_verified_competitor():
    result = analyze_click_location(
        lat=19.9163,
        lon=99.2143,
        province=CHIANG_MAI,
        year=2026,
        scenario="base",
        mode="district",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["eligibility_status"] == "eligible"
    assert result["access_ok"] is True
    assert result["net_sessions_per_day"] > 0
    assert result["top_pois"]
    assert any("Fang" in item["name"] for item in result["top_pois"])
    assert result["top_competitors"]
    assert "PEA Electric vehicle charging station VOLTA" in result["top_competitors"][0]["name"]


def test_chiang_mai_poi_loader_covers_ring_road_anchor_areas():
    pois = load_pois_for_province(CHIANG_MAI)
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "cmu_main_campus",
        "maya_lifestyle_mall",
        "big_c_mae_hia",
        "kad_farang_village",
        "meechok_plaza",
        "theppanya_hospital",
    }.issubset(poi_ids)


def test_chiang_mai_poi_loader_covers_west_121_anchor_areas():
    pois = load_pois_for_province(CHIANG_MAI)
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "cmu_main_campus",
        "maya_lifestyle_mall",
        "chiang_mai_zoo",
        "chiang_mai_convention_center",
        "chiang_mai_700_stadium",
        "ton_payom_market",
        "big_c_mae_hia",
        "mae_hia_market",
    }.issubset(poi_ids)


def test_chiang_mai_competitor_loader_dedupes_known_duplicate_sites():
    competitors = load_competitors_for_province(CHIANG_MAI)
    station_ids = {row["station_id"] for row in competitors}

    assert "green_bus_thailand_chiangmai" not in station_ids
    assert "pea_volta_nong_hoi_cmh" not in station_ids
    assert len({
        "pea_volta_hub_chiang_mai",
        "pea_volta_hub_chiangmai_gmaps",
    } & station_ids) == 1
    assert len({
        "charging_station_cmu",
        "egat_cmu_area_osm",
    } & station_ids) == 1
    assert len({
        "pea_volta_doi_saket",
        "pea_volta_doi_saket_side_osm",
    } & station_ids) == 1


def test_click_analysis_rejects_water_surface(monkeypatch):
    monkeypatch.setattr(
        spatial,
        "lookup_water_surface",
        lambda lat, lon: {
            "is_water": True,
            "surface_type": "water",
            "reason": "Point falls inside an OSM water polygon.",
            "warning": None,
            "feature_name": "City Lake",
        },
    )
    monkeypatch.setattr(
        spatial,
        "lookup_building_surface",
        lambda lat, lon: {
            "is_building": False,
            "surface_type": "land_or_unclassified",
            "reason": None,
            "warning": None,
            "feature_name": None,
        },
    )

    result = analyze_click_location(
        lat=17.4058,
        lon=102.7998,
        province=UDON_THANI,
        year=2030,
        scenario="base",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["eligibility_status"] == "rejected"
    assert result["surface_type"] == "water"
    assert result["surface_feature_name"] == "City Lake"
    assert result["net_sessions_per_day"] == 0.0


def test_click_analysis_rejects_building_surface(monkeypatch):
    monkeypatch.setattr(
        spatial,
        "lookup_water_surface",
        lambda lat, lon: {
            "is_water": False,
            "surface_type": "land_or_unclassified",
            "reason": None,
            "warning": None,
            "feature_name": None,
        },
    )
    monkeypatch.setattr(
        spatial,
        "lookup_building_surface",
        lambda lat, lon: {
            "is_building": True,
            "surface_type": "building",
            "reason": "Point falls inside an OSM building footprint.",
            "warning": None,
            "feature_name": "Retail Podium",
        },
    )

    result = analyze_click_location(
        lat=17.4058,
        lon=102.7998,
        province=UDON_THANI,
        year=2030,
        scenario="base",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["eligibility_status"] == "rejected"
    assert result["surface_type"] == "building"
    assert result["surface_feature_name"] == "Retail Podium"
    assert result["net_sessions_per_day"] == 0.0


def test_water_lookup_fallback_when_service_unavailable(monkeypatch):
    def fail(url, data, timeout=4.0):
        raise OSError("network down")

    spatial.lookup_water_surface.cache_clear()
    monkeypatch.setattr(spatial, "_post_json", fail)

    result = spatial.lookup_water_surface(18.0, 99.0)

    assert result["is_water"] is False
    assert result["surface_type"] == "unknown"
    assert "unavailable" in result["warning"].lower()


def test_building_lookup_fallback_when_service_unavailable(monkeypatch):
    def fail(url, data, timeout=4.0):
        raise OSError("network down")

    spatial.lookup_building_surface.cache_clear()
    monkeypatch.setattr(spatial, "_post_json", fail)

    result = spatial.lookup_building_surface(18.0, 99.0)

    assert result["is_building"] is False
    assert result["surface_type"] == "unknown"
    assert "unavailable" in result["warning"].lower()


def test_click_analysis_api_returns_explainable_components():
    response = TestClient(app).post(
        "/api/click-analysis",
        json={
            "lat": 17.4058,
            "lon": 102.7998,
            "province": UDON_THANI,
            "year": 2030,
            "scenario": "base",
            "avg_kwh_per_session": 28,
            "price_per_kwh": 6.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "base_sessions" in payload
    assert "raw_base_sessions" in payload
    assert "gross_area_demand_sessions" in payload
    assert "aadt_used" in payload
    assert "fleet_ev_share_pct" in payload
    assert "charge_probability_pct" in payload
    assert "zone_boost_sessions" in payload
    assert "poi_boost_sessions" in payload
    assert "district_boost_sessions" in payload
    assert "raw_spatial_boost_sessions" in payload
    assert "spatial_boost_sessions" in payload
    assert "raw_competitor_penalty_sessions" in payload
    assert "competitor_penalty_sessions" in payload
    assert "top_zones" in payload
    assert "top_pois" in payload
    assert "top_districts" in payload
    assert "top_competitors" in payload
    assert "eligibility_status" in payload
    assert "surface_type" in payload
    assert "access_ok" in payload
