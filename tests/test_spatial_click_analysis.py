from fastapi.testclient import TestClient

from th_evi.api import app
import th_evi.spatial as spatial
from th_evi.spatial import (
    analyze_click_location,
    assess_surface_access,
    business_area_field,
    competitor_penalty_field,
    load_business_areas_for_province,
    load_competitors_for_province,
    load_pois_for_province,
    poi_attraction_field,
    zone_influence_field,
)

UDON_THANI = "\u0e2d\u0e38\u0e14\u0e23\u0e18\u0e32\u0e19\u0e35"
CHIANG_MAI = "Chiang Mai"
PHITSANULOK = "Phitsanulok"
NAKHON_NAYOK = "Nakhon Nayok"
NAKHON_RATCHASIMA = "Nakhon Ratchasima"


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


def test_business_area_field_supports_urban_fringe_and_corridor_context():
    areas = [
        {
            "name": "Ring 2 urban fringe",
            "area_type": "urban_fringe",
            "center_lat": "18.74",
            "center_lon": "98.94",
            "radius_km": "4.0",
            "demand_pool_base": "120",
            "confidence": "high",
        }
    ]

    near_score, near_rows = business_area_field(18.74, 98.94, areas, scenario="base")
    far_score, _ = business_area_field(18.84, 99.14, areas, scenario="base")

    assert near_score > far_score
    assert near_rows[0]["area_type"] == "urban_fringe"


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


def test_samut_prakan_bang_pu_click_analysis_has_area_signals(monkeypatch):
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
    result = analyze_click_location(
        lat=13.5230,
        lon=100.7060,
        province="Samut Prakan",
        year=2026,
        scenario="base",
        mode="urban",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["net_sessions_per_day"] > 0
    assert result["zone_boost_sessions"] > 0
    assert result["business_area_boost_sessions"] > 0
    assert result["top_pois"]
    assert result["eligibility_status"] in {"eligible", "low_relevance"}


def test_rayong_pluak_daeng_click_analysis_has_industrial_area_signals(monkeypatch):
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
    result = analyze_click_location(
        lat=13.0280,
        lon=101.2130,
        province="Rayong",
        year=2026,
        scenario="base",
        mode="urban",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["net_sessions_per_day"] > 0
    assert result["zone_boost_sessions"] > 0
    assert result["business_area_boost_sessions"] > 0
    assert result["top_pois"]
    assert result["eligibility_status"] in {"eligible", "low_relevance"}


def test_nakhon_nayok_click_analysis_has_city_and_medical_area_signals(monkeypatch):
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
    result = analyze_click_location(
        lat=14.1078,
        lon=100.9915,
        province=NAKHON_NAYOK,
        year=2026,
        scenario="base",
        mode="urban",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["net_sessions_per_day"] > 0
    assert result["zone_boost_sessions"] > 0
    assert result["business_area_boost_sessions"] > 0
    assert result["top_pois"]
    assert result["eligibility_status"] in {"eligible", "low_relevance"}


def test_nakhon_ratchasima_click_analysis_has_city_and_retail_area_signals(monkeypatch):
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
    result = analyze_click_location(
        lat=14.9799,
        lon=102.0977,
        province=NAKHON_RATCHASIMA,
        year=2026,
        scenario="base",
        mode="urban",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["net_sessions_per_day"] > 0
    assert result["zone_boost_sessions"] > 0
    assert result["business_area_boost_sessions"] > 0
    assert result["top_pois"]
    assert result["eligibility_status"] in {"eligible", "low_relevance"}


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
        business_areas=[],
        zone_score=8.0,
        business_area_score=0.0,
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
        "central_chiangmai_airport",
        "chiang_mai_airport",
        "chiang_mai_airport_arrivals_pickup",
        "chiang_mai_airport_rental_car_cluster",
        "mahidol_airport_frontage",
        "rajavej_hospital",
        "mahachok_park",
        "punn_suk_park",
    }.issubset(poi_ids)


def test_chiang_mai_poi_loader_covers_city_core_and_inner_ring_anchors():
    pois = load_pois_for_province(CHIANG_MAI)
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "nimman_commercial_spine",
        "kad_na_mor_market",
        "chiang_mai_ram_hospital",
        "chiang_mai_gate_market",
        "warorot_market",
        "chiang_mai_night_bazaar",
        "anusarn_market",
        "thapae_gate",
        "airport_operations_support_cluster",
        "bangkok_hospital_chiang_mai",
        "chiang_mai_business_park",
        "chiang_mai_bus_terminal_3",
        "central_festival_chiangmai",
        "big_c_extra_chiang_mai",
        "lanna_hospital",
        "nakornping_hospital",
        "lotus_kham_tiang",
        "makro_chiang_mai",
        "mccormick_hospital",
        "prince_royal_college",
    }.issubset(poi_ids)


def test_chiang_mai_business_area_loader_covers_ring2_and_ring3():
    business_areas = load_business_areas_for_province(CHIANG_MAI)
    business_area_ids = {row["business_area_id"] for row in business_areas}

    assert {
        "cm_ring2_mae_hia_hang_dong",
        "cm_ring2_fa_ham_san_sai",
        "cm_ring2_sankamphaeng_saraphi",
        "cm_ring3_hang_dong_saraphi",
        "cm_ring3_doi_saket_sankamphaeng",
        "cm_ring3_sansai_maerim",
    }.issubset(business_area_ids)


def test_click_analysis_ring3_corridor_keeps_business_area_signal():
    result = analyze_click_location(
        lat=18.8275,
        lon=99.1595,
        province=CHIANG_MAI,
        year=2026,
        scenario="base",
        mode="urban",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["business_area_boost_sessions"] > 0
    assert result["top_business_areas"]
    assert any("Ring 3" in item["name"] for item in result["top_business_areas"])


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


def test_chiang_mai_poi_loader_excludes_site_specific_noise_categories():
    pois = load_pois_for_province(CHIANG_MAI)
    categories = {str(row["category"]).strip() for row in pois}

    assert "residential" not in categories
    assert "restaurant" not in categories
    assert "hotel" not in categories
    assert "hotel_condo" not in categories


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
        "greenbus_fair_super_charge",
        "fair_super_charge_greenbus",
        "ev_station_pluz_green_park",
    } & station_ids) == 1
    assert len({
        "pea_volta_doi_saket",
        "pea_volta_doi_saket_side_osm",
    } & station_ids) == 1


def test_chiang_mai_competitor_loader_keeps_verified_city_fast_charge_sites():
    competitors = load_competitors_for_province(CHIANG_MAI)
    station_ids = {row["station_id"] for row in competitors}

    assert {
        "pea_volta_hub_chiangmai_gmaps",
        "tesla_supercharger_big_c_extra",
        "ea_anywhere_my_hip_condo",
        "fair_super_charge_greenbus",
        "elexa_pt_chiangmai8",
    }.issubset(station_ids)


def test_chiang_mai_competitor_loader_keeps_named_city_sites_beyond_google_verified():
    competitors = load_competitors_for_province(CHIANG_MAI)
    station_ids = {row["station_id"] for row in competitors}

    assert {
        "ptt_ev_station_mahidon",
        "ptt_ev_station_nong_hoi",
        "ptt_ev_station_don_jan",
        "ptt_ev_station_ruamchock",
        "chargenow_airport_plaza",
        "super_ev_hub_cultural_center",
        "elex_max_chiangmai_ram",
        "ev_egat_one_nimman",
        "onion_maya",
        "ginka_star_avenue",
        "onion_centralfestival",
        "shell_recharge_mahidol",
        "pea_volta_bangchak_superhighway",
        "altervim_lotus_khamtieng",
        "ea_anywhere_chanasin",
        "ea_anywhere_cbp",
        "evolt_thung_hotel",
        "ev_charger_wasabi_parkc",
        "ptt_ev_station_payap",
    }.issubset(station_ids)


def test_chiang_mai_competitor_loader_drops_generic_unknown_osm_points():
    competitors = load_competitors_for_province(CHIANG_MAI)
    station_ids = {row["station_id"] for row in competitors}

    assert "osm_ev_charging_sansai_near_1" not in station_ids
    assert "osm_ev_charging_faham_near_1" not in station_ids
    assert "osm_ev_station_north_1" not in station_ids
    assert "moose_hotel_ac" not in station_ids
    assert "ptt_ev_city_osm" not in station_ids
    assert "ptt_ev_don_chan_osm" not in station_ids
    assert "byd_city_osm" not in station_ids
    assert "mg_supercharge_city_osm" not in station_ids


def test_phitsanulok_loader_has_minimum_heatmap_anchor_sets():
    poi_ids = {row["poi_id"] for row in load_pois_for_province(PHITSANULOK)}
    competitor_ids = {row["station_id"] for row in load_competitors_for_province(PHITSANULOK)}
    business_area_ids = {row["business_area_id"] for row in load_business_areas_for_province(PHITSANULOK)}

    assert {
        "central_phitsanulok",
        "phitsanulok_airport",
        "naresuan_university",
        "buddhachinaraj_hospital",
        "phitsanulok_bus_terminal_2",
    }.issubset(poi_ids)
    assert {
        "pea_volta_bangchak_central",
        "elexa_tha_pho",
        "mg_supercharge_city",
    }.issubset(competitor_ids)
    assert {
        "phs_central_h12_fringe",
        "phs_old_city_medical_band",
        "phs_samo_khae_bypass_connector",
    }.issubset(business_area_ids)


def test_phitsanulok_competitor_loader_prefers_named_city_and_gateway_stations():
    competitor_ids = {row["station_id"] for row in load_competitors_for_province(PHITSANULOK)}

    assert {
        "ptt_charging_station_phitsanulok",
        "ptt_charging_station_phitsanulok_1",
        "ptt_charging_station_phitsanulok_2",
        "ptt_charging_station_phitsanulok_3",
        "sharge_phitsanulok",
    }.issubset(competitor_ids)
    assert "ev_station_pluz_city_seed" not in competitor_ids
    assert "ev_station_pluz_bypass_seed" not in competitor_ids
    assert "ea_anywhere_city_seed" not in competitor_ids
    assert "homepro_partner_eleX_seed" not in competitor_ids


def test_phitsanulok_click_analysis_supports_central_retail_core():
    result = analyze_click_location(
        lat=16.8385,
        lon=100.2385,
        province=PHITSANULOK,
        year=2026,
        scenario="base",
        mode="urban",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["eligibility_status"] == "eligible"
    assert result["net_sessions_per_day"] > 0
    assert result["top_pois"]
    assert result["top_competitors"]
    assert result["top_business_areas"]


def test_nakhon_nayok_loader_has_minimum_heatmap_anchor_sets():
    poi_ids = {row["poi_id"] for row in load_pois_for_province(NAKHON_NAYOK)}
    competitor_ids = {row["station_id"] for row in load_competitors_for_province(NAKHON_NAYOK)}
    business_area_ids = {row["business_area_id"] for row in load_business_areas_for_province(NAKHON_NAYOK)}

    assert {
        "nky_nakhon_nayok_town_center",
        "nky_nakhon_nayok_hospital",
        "nky_lotuss_nakhon_nayok",
        "nky_swu_ongkharak",
        "nky_swu_medical_center",
        "nky_ban_na_town_center",
    }.issubset(poi_ids)
    assert {
        "nky_ev_station_pluz_nakhon_nayok_seed",
        "nky_pea_volta_ongkharak_seed",
    }.issubset(competitor_ids)
    assert {
        "nky_nakhon_nayok_retail_civic_band",
        "nky_ongkharak_medical_education_band",
        "nky_route_305_growth_axis",
    }.issubset(business_area_ids)


def test_nakhon_ratchasima_loader_has_minimum_heatmap_anchor_sets():
    poi_ids = {row["poi_id"] for row in load_pois_for_province(NAKHON_RATCHASIMA)}
    competitor_ids = {row["station_id"] for row in load_competitors_for_province(NAKHON_RATCHASIMA)}
    business_area_ids = {row["business_area_id"] for row in load_business_areas_for_province(NAKHON_RATCHASIMA)}

    assert {
        "nrm_korat_city_center",
        "nrm_the_mall_korat",
        "nrm_terminal21_korat",
        "nrm_maharat_hospital",
        "nrm_suranaree_university",
        "nrm_pak_chong_town_center",
    }.issubset(poi_ids)
    assert {
        "nrm_pea_volta_korat_city_seed",
        "ptt_charging_station_korat_1",
        "pea_volta_khok_kruat",
        "elex_by_egat_pak_chong",
    }.issubset(competitor_ids)
    assert {
        "nrm_korat_retail_civic_band",
        "nrm_mittraphap_modern_retail_spine",
        "nrm_pakchong_mittraphap_gateway",
    }.issubset(business_area_ids)


def test_airport_core_competitors_include_super_ev_hub():
    result = analyze_click_location(
        lat=18.7682469,
        lon=98.9760292,
        province=CHIANG_MAI,
        year=2026,
        scenario="base",
        mode="urban",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    competitor_names = {item["name"] for item in result["top_competitors"]}
    assert "Super EV Hub Chiang Mai Cultural Center" in competitor_names


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


def test_chiang_rai_poi_loader_prioritizes_ban_du_and_mae_chan_growth_areas():
    pois = load_pois_for_province("Chiang Rai")
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "ban_du_growth_axis",
        "ban_du_municipal_market",
        "chiang_rai_rajabhat_university",
        "mae_fah_luang_university",
        "mae_chan_town_center",
        "lotus_mae_chan",
        "mae_chan_hospital",
    }.issubset(poi_ids)


def test_chiang_rai_competitor_loader_includes_confirmed_central_tesla():
    competitors = load_competitors_for_province("Chiang Rai")
    stations = {row["station_id"]: row for row in competitors}

    assert "tesla_supercharger_central_chiang_rai" in stations
    assert stations["tesla_supercharger_central_chiang_rai"]["verification_status"] == "verified"
    assert stations["tesla_supercharger_central_chiang_rai"]["network"] == "Tesla Supercharger"


def test_lampang_poi_loader_covers_retail_gateway_and_mae_mo_growth_areas():
    pois = load_pois_for_province("Lampang")
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "lotus_lampang",
        "makro_lampang",
        "lampang_superhighway_gateway",
        "hang_chat_town_center",
        "mae_mo_town_center",
        "mae_mo_hospital",
    }.issubset(poi_ids)


def test_phayao_poi_loader_covers_city_retail_route1_and_chiang_kham():
    pois = load_pois_for_province("Phayao")
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "tops_plaza_phayao",
        "lotus_phayao",
        "phayao_university_medical_center",
        "chiang_kham_hospital",
        "lotus_chiang_kham",
    }.issubset(poi_ids)


def test_lamphun_poi_loader_includes_jampha_and_chatuchak_market():
    pois = load_pois_for_province("Lamphun")
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "jampha_shopping_mall_lamphun",
        "lamphun_chatuchak_market",
    }.issubset(poi_ids)


def test_phrae_poi_loader_covers_city_retail_and_den_chai_gateway():
    pois = load_pois_for_province("Phrae")
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "big_c_supercenter_phrae",
        "global_house_phrae",
        "makro_phrae",
        "den_chai_yupparaj_hospital",
        "ptt_den_chai_gateway",
    }.issubset(poi_ids)


def test_nan_poi_loader_covers_city_retail_and_north_service_towns():
    pois = load_pois_for_province("Nan")
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "makro_nan",
        "cad_nan_lifestyle",
        "wiang_sa_hospital",
        "lotus_pua",
        "tha_wang_pha_hospital",
    }.issubset(poi_ids)


def test_mae_hong_son_poi_loader_covers_mid_and_south_service_towns():
    pois = load_pois_for_province("Mae Hong Son")
    poi_ids = {row["poi_id"] for row in pois}

    assert {
        "khun_yuam_center",
        "khun_yuam_hospital",
        "mae_la_noi_center",
        "mae_la_noi_hospital",
    }.issubset(poi_ids)


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
