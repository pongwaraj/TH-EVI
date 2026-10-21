from math import fsum

import pytest

from th_evi.area_engine import allocate_support
from th_evi.heatmap import _location_type_for_heat
from th_evi.poi_policy import POI_CAPTURE_FACTOR, POI_POLICY_VERSION, poi_rule, screening_weight
from th_evi.spatial import (
    _spatial_location_type, compose_area_demand, load_pois_for_province,
    poi_attraction_field, zone_influence_field,
)


def poi(category, **fields):
    return {"poi_id": category, "name": category, "category": category,
            "lat": 18.0, "lon": 99.0, "confidence": "high", **fields}


def contribution(category, distance=0, **fields):
    return {"category": category, "distance_km": distance, **fields}


def test_dc_relevance_hierarchy_is_not_just_institution_size():
    weights = [poi_rule(category).weight for category in
               ("airport", "shopping_mall", "supermarket", "hospital", "local_market", "school", "housing_estate")]
    assert weights == sorted(weights, reverse=True)
    assert poi_rule("university").weight > poi_rule("school").weight
    assert poi_rule("apartment").weight < poi_rule("hotel").weight
    assert poi_rule("unrecognised").weight < poi_rule("local_market").weight


@pytest.mark.parametrize("category", ["school", "education", "university", "office", "apartment",
                                      "neighborhood_center", "district_center", "city_center", "local_market"])
def test_context_or_long_dwell_alone_does_not_classify_as_city_or_dc_destination(category):
    rows = [contribution(category)]
    assert _location_type_for_heat(rows, [], []) == "suburban"
    assert _spatial_location_type(rows) == "suburban"


def test_city_core_needs_commercial_corroboration_and_zero_distance_is_valid():
    rows = [contribution("city_center"), contribution("shopping_mall", 0.2)]
    assert _location_type_for_heat(rows, [], []) == "city_center"
    assert _spatial_location_type(rows) == "city_center"


@pytest.mark.parametrize("category", ["shopping_mall", "community_mall", "airport", "bus_station", "railway_station", "hospital"])
def test_real_local_destinations_remain_destinations(category):
    rows = [contribution(category, 0.1)]
    assert _location_type_for_heat(rows, [], []) == "destination"
    assert _spatial_location_type(rows) == "destination"


def test_minor_tenants_cannot_hide_destination_outside_top_three():
    rows = [contribution("school") for _ in range(5)] + [contribution("shopping_mall", 0.5)]
    assert _location_type_for_heat(rows, [], []) == "destination"


def test_distant_business_or_district_label_cannot_upgrade_a_local_road():
    business = [{"area_type": "urban_fringe", "suggested_location_type": "destination", "distance_km": 6.2}]
    districts = [{"node_type": "district_center", "suggested_location_type": "destination", "distance_km": 0.5}]
    assert _location_type_for_heat([contribution("school")], business, districts) == "suburban"
    assert _location_type_for_heat([contribution("transport_corridor", 3)], [], []) == "suburban"


def test_nearby_corridor_remains_highway():
    assert _location_type_for_heat([contribution("transport_corridor", 0.2)], [], []) == "highway"


@pytest.mark.parametrize("fields", [{"verification_status": "planned"}, {"verification_status": "closed"}, {"public_access": "private"}])
def test_unavailable_destinations_do_not_generate_evidence(fields):
    assert poi_attraction_field(18, 99, [poi("shopping_mall", **fields)]) == (0, [])
    assert _spatial_location_type([contribution("shopping_mall", **fields)]) == "suburban"


def test_candidate_pin_still_cannot_create_demand():
    assert poi_attraction_field(18, 99, [poi("target_site", source="user_supplied_coordinate")]) == (0, [])


def test_unverified_seed_cannot_claim_high_coordinate_confidence():
    high, _ = poi_attraction_field(18, 99, [poi("hospital", source="official location")])
    seed, rows = poi_attraction_field(18, 99, [poi("hospital", source="public facts + seed coordinate")])
    assert seed < high
    assert rows[0]["evidence_multiplier"] == 0.62
    assert rows[0]["tier"] == "service"
    assert rows[0]["score_semantics"] == "relative_poi_evidence_not_sessions"


def test_same_destination_tenants_are_bounded_and_order_independent():
    mall = poi("shopping_mall")
    rows = [mall] + [poi("supermarket", poi_id=f"tenant-{i}", lat=18.0001) for i in range(30)]
    alone, _ = poi_attraction_field(18, 99, [mall])
    combined, evidence = poi_attraction_field(18, 99, rows)
    reversed_score, reversed_evidence = poi_attraction_field(18, 99, list(reversed(rows)))
    assert alone < combined <= alone * 1.25
    assert combined == reversed_score
    assert evidence == reversed_evidence
    assert len({row["cluster_id"] for row in evidence}) == 1
    assert fsum(row["effective_score"] for row in evidence) == pytest.approx(combined, abs=0.05)


def test_exact_duplicate_pin_does_not_add_weight():
    mall = poi("shopping_mall")
    assert poi_attraction_field(18, 99, [mall, mall]) == poi_attraction_field(18, 99, [mall])


@pytest.mark.parametrize("lat,lon", [(float("nan"), 99), (18, float("inf")), (91, 99), (18, 181)])
def test_invalid_poi_coordinates_cannot_contaminate_the_field(lat, lon):
    assert poi_attraction_field(18, 99, [poi("shopping_mall", lat=lat, lon=lon)]) == (0, [])


def test_poi_kernel_has_a_finite_range():
    score, rows = poi_attraction_field(18.04, 99, [poi("school")])
    assert score == 0
    assert rows == []


def test_hot_zone_does_not_extend_beyond_its_declared_radius():
    zone = {"center_lat": 18, "center_lon": 99, "radius_km": 2, "demand_pool_base": 100, "confidence": "high"}
    assert zone_influence_field(18, 99, [zone])[0] == 100
    assert zone_influence_field(18.019, 99, [zone]) == (0, [])


def test_assumed_aadt_cannot_dominate_local_activity_or_compound_context():
    args = dict(poi_score=4, zone_score=100, business_area_score=100, district_score=100)
    a = screening_weight(model_prior=40, **args)
    b = screening_weight(model_prior=100000, **args)
    assert a == b
    assert a["weight"] == pytest.approx(6.8 / POI_CAPTURE_FACTOR)
    assert a["components"]["poi_activity"] > a["components"]["bounded_traffic_prior"]
    assert a["method"] == POI_POLICY_VERSION
    assert not a["calibrated"]
    assert screening_weight(model_prior=100000, poi_score=0, zone_score=1000,
                            business_area_score=1000, district_score=1000)["weight"] <= 0.35 / POI_CAPTURE_FACTOR


def test_allocation_uses_the_same_policy_and_keeps_screening_units():
    cells = [dict(lat=18, lon=99, model_sessions=10000, poi_score=1, zone_score=1000),
             dict(lat=18.01, lon=99, model_sessions=10, poi_score=10)]
    result = allocate_support(cells, [])
    assert result["points"][0]["demand_score"] < result["points"][1]["demand_score"]
    assert result["accounting"]["gross_allocated"] == pytest.approx(100)
    assert all(row["daily_kwh"] is None and row["forecast_available"] is False for row in result["points"])


def test_yang_noeng_reference_corrections_and_neighborhood_classification():
    pois = {row["poi_id"]: row for row in load_pois_for_province("Chiang Mai")}
    assert float(pois["saraphi_hospital"]["lat"]) == pytest.approx(18.68117016)
    assert float(pois["saraphi_hospital"]["lon"]) == pytest.approx(99.043176)
    assert float(pois["yang_noeng_market"]["lat"]) == pytest.approx(18.7149701)
    assert pois["yang_noeng_market"]["category"] == "local_market"
    assert pois["saraphi_city_center"]["category"] == "neighborhood_center"
    _, evidence = poi_attraction_field(18.7149701, 99.0344717, list(pois.values()))
    assert _location_type_for_heat(evidence, [], []) == "suburban"
    assert pois["chongfah_sinseung_school"]["category"] == "school"
    assert pois["cmu_main_campus"]["category"] == "university"


def test_local_market_evidence_is_weaker_than_commercial_magnet():
    def boost(category):
        value, _ = poi_attraction_field(18, 99, [poi(category)])
        return compose_area_demand(base_sessions_per_day=1, zone_score=0,
                                   business_area_score=0, poi_score=value, district_score=0)["poi_boost_sessions"]
    assert boost("school") < boost("local_market") < boost("shopping_mall")


def test_chiang_mai_pilot_retains_commercial_priorities_without_yang_noeng_hotspot():
    from th_evi.area_engine import fixed_surface
    from th_evi.spatial import km_between

    surface = fixed_surface("Chiang Mai", 2026, "base", "urban")
    assert surface["source_metadata"]["poi_policy_version"] == POI_POLICY_VERSION
    assert surface["accounting"]["gross_allocated"] == pytest.approx(100)
    assert not surface["accounting"]["energy_budget_enforced"]

    def nearby_score(lat, lon):
        cells = [row for row in surface["points"] if km_between(lat, lon, row["lat"], row["lon"]) < 1]
        return max((row["demand_score"] for row in cells), default=0)

    yang_noeng = nearby_score(18.7149701, 99.0344717)
    central = nearby_score(18.806, 99.018)
    nimman = nearby_score(18.800, 98.968)
    kad_farang = nearby_score(18.90215, 98.948371)
    assert 0 < yang_noeng < central * 0.4
    assert min(central, nimman, kad_farang) > yang_noeng * 2
    assert nearby_score(18.737333, 99.034533) < central * 0.25
    assert all(row["forecast_available"] is False and row["daily_kwh"] is None for row in surface["points"])
