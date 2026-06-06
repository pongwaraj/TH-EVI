from th_evi.heatmap import generate_chiang_mai_heatmap, generate_province_heatmap


def test_heatmap_includes_grid_step_metadata():
    result = generate_chiang_mai_heatmap(year=2026, scenario="base", resolution_km=1.0)

    assert result["resolution_km"] == 1.0
    assert result["lat_step_deg"] > 0
    assert result["lon_step_deg"] > 0
    assert result["point_count"] > 0


def test_province_heatmap_supports_non_chiang_mai():
    result = generate_province_heatmap("Udon Thani", year=2026, scenario="base", resolution_km=1.0)

    assert result["province"] == "Udon Thani"
    assert result["point_count"] > 0
    assert result["metadata"]["poi_count"] > 0
    assert "business_area_count" in result["metadata"]
    assert result["metadata"]["urban_mask"] == "poi_zone_competitor"
    assert all(point["context_score"] >= 5.0 for point in result["points"])


def test_community_heatmap_supports_district_node_only_province():
    result = generate_province_heatmap(
        "Lamphun",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="community",
    )

    assert result["mode"] == "community"
    assert result["point_count"] > 0
    assert result["metadata"]["district_node_count"] > 0
    assert result["metadata"]["heatmap_mode"] == "community"
    assert result["metadata"]["urban_mask"] == "district_poi_zone_competitor"
    assert max(point["district_score"] for point in result["points"]) > 0


def test_district_heatmap_normalizes_within_each_district():
    result = generate_chiang_mai_heatmap(
        year=2026,
        scenario="base",
        resolution_km=2.0,
        mode="district",
    )

    assert result["metadata"]["normalization"] == "within_district_weighted_by_province_potential"
    assert result["district_summaries"]
    assert all(summary["lat"] is not None for summary in result["district_summaries"])
    assert all(summary["lon"] is not None for summary in result["district_summaries"])
    fang_points = [point for point in result["points"] if point["district_name"] == "Fang"]
    assert fang_points
    assert max(point["local_intensity"] for point in fang_points) == 1.0
    assert max(point["display_intensity"] for point in fang_points) >= 0.55


def test_chiang_mai_district_mode_covers_all_25_districts():
    result = generate_chiang_mai_heatmap(
        year=2026,
        scenario="base",
        resolution_km=2.0,
        mode="district",
    )

    district_names = {summary["district_name"] for summary in result["district_summaries"]}
    assert len(district_names) == 25
    assert {
        "Chai Prakan",
        "Galyani Vadhana",
        "Mae Chaem",
        "Omkoi",
        "Wiang Haeng",
    }.issubset(district_names)


def test_chiang_mai_urban_mode_reaches_key_border_corridors():
    result = generate_chiang_mai_heatmap(
        year=2026,
        scenario="base",
        resolution_km=2.0,
        mode="urban",
    )

    district_names = {point["district_name"] for point in result["points"] if point.get("district_name")}
    assert {"Doi Saket", "Saraphi", "Chai Prakan", "Chiang Dao", "Mae Ai", "Phrao"}.issubset(district_names)


def test_chiang_mai_heatmap_includes_business_area_signal():
    result = generate_chiang_mai_heatmap(
        year=2026,
        scenario="base",
        resolution_km=2.0,
        mode="urban",
    )

    assert result["metadata"]["business_area_count"] >= 6
    assert any(point["business_area_score"] > 0 for point in result["points"])


def test_chiang_rai_heatmap_filters_remote_tourism_only_mountain_points():
    result = generate_province_heatmap(
        "Chiang Rai",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    flagged_points = [
        point for point in result["points"]
        if {"Mae Fah Luang Garden", "Doi Tung Royal Villa"} & set(point.get("pois", []))
        and not point.get("business_areas")
        and not point.get("districts")
        and not point.get("competitors")
    ]

    assert flagged_points == []


def test_chiang_rai_heatmap_keeps_mae_chan_growth_corridor():
    result = generate_province_heatmap(
        "Chiang Rai",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    mae_chan_points = [
        point for point in result["points"]
        if 20.08 <= point["lat"] <= 20.18 and 99.84 <= point["lon"] <= 99.96
    ]

    assert mae_chan_points


def test_lampang_heatmap_includes_business_area_signal():
    result = generate_province_heatmap(
        "Lampang",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    assert result["metadata"]["business_area_count"] >= 5
    assert any(point["business_area_score"] > 0 for point in result["points"])


def test_lampang_heatmap_excludes_mae_moh_mine_core():
    result = generate_province_heatmap(
        "Lampang",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    mine_core_points = [
        point for point in result["points"]
        if 18.24 <= point["lat"] <= 18.35 and 99.64 <= point["lon"] <= 99.72
    ]

    assert result["metadata"]["heatmap_exclusion_count"] >= 1
    assert mine_core_points == []


def test_lampang_heatmap_keeps_mae_moh_town_edges_outside_mine_core():
    result = generate_province_heatmap(
        "Lampang",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    mae_moh_town_points = [
        point for point in result["points"]
        if 18.27 <= point["lat"] <= 18.31 and 99.73 <= point["lon"] <= 99.77
    ]

    assert mae_moh_town_points


def test_phayao_heatmap_includes_business_area_signal():
    result = generate_province_heatmap(
        "Phayao",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    assert result["metadata"]["business_area_count"] >= 4
    assert any(point["business_area_score"] > 0 for point in result["points"])


def test_phayao_heatmap_excludes_kwan_phayao_open_water_core():
    result = generate_province_heatmap(
        "Phayao",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    water_core_points = [
        point for point in result["points"]
        if 19.16 <= point["lat"] <= 19.19 and 99.91 <= point["lon"] <= 99.93
    ]

    assert result["metadata"]["heatmap_exclusion_count"] >= 1
    assert water_core_points == []


def test_phayao_heatmap_excludes_broader_kwan_phayao_water_body():
    result = generate_province_heatmap(
        "Phayao",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    broad_water_points = [
        point for point in result["points"]
        if 19.145 <= point["lat"] <= 19.20 and 99.912 <= point["lon"] <= 99.945
    ]

    assert broad_water_points == []


def test_lamphun_heatmap_includes_business_area_signal_near_jampha_chatuchak():
    result = generate_province_heatmap(
        "Lamphun",
        year=2026,
        scenario="base",
        resolution_km=0.5,
        mode="urban",
    )

    east_lamphun_points = [
        point for point in result["points"]
        if 18.54 <= point["lat"] <= 18.56 and 99.02 <= point["lon"] <= 99.04
    ]

    assert result["metadata"]["business_area_count"] >= 2
    assert east_lamphun_points
    assert any(
        "Jampha Shopping Mall Lamphun" in point.get("pois", [])
        or "Lamphun Chatuchak Market" in point.get("pois", [])
        for point in east_lamphun_points
    )


def test_phrae_heatmap_includes_business_area_signal():
    result = generate_province_heatmap(
        "Phrae",
        year=2026,
        scenario="base",
        resolution_km=0.5,
        mode="urban",
    )

    assert result["metadata"]["business_area_count"] >= 4
    assert any(point["business_area_score"] > 0 for point in result["points"])


def test_phrae_heatmap_strengthens_den_chai_gateway_cluster():
    result = generate_province_heatmap(
        "Phrae",
        year=2026,
        scenario="base",
        resolution_km=0.5,
        mode="urban",
    )

    den_chai_points = [
        point for point in result["points"]
        if 17.97 <= point["lat"] <= 17.99 and 100.04 <= point["lon"] <= 100.07
    ]

    assert den_chai_points
    assert any(
        "Den Chai Crown Prince Hospital" in point.get("pois", [])
        or "Den Chai route and rail gateway" in point.get("business_areas", [])
        for point in den_chai_points
    )


def test_nan_heatmap_includes_business_area_signal():
    result = generate_province_heatmap(
        "Nan",
        year=2026,
        scenario="base",
        resolution_km=0.5,
        mode="urban",
    )

    assert result["metadata"]["business_area_count"] >= 4
    assert any(point["business_area_score"] > 0 for point in result["points"])


def test_nan_heatmap_keeps_wiang_sa_and_tha_wang_pha_service_towns_visible():
    result = generate_province_heatmap(
        "Nan",
        year=2026,
        scenario="base",
        resolution_km=0.5,
        mode="urban",
    )

    wiang_sa_points = [
        point for point in result["points"]
        if 18.56 <= point["lat"] <= 18.60 and 100.72 <= point["lon"] <= 100.75
    ]
    tha_wang_pha_points = [
        point for point in result["points"]
        if 18.84 <= point["lat"] <= 18.86 and 100.77 <= point["lon"] <= 100.79
    ]

    assert wiang_sa_points
    assert tha_wang_pha_points


def test_mae_hong_son_heatmap_includes_business_area_signal():
    result = generate_province_heatmap(
        "Mae Hong Son",
        year=2026,
        scenario="base",
        resolution_km=0.5,
        mode="urban",
    )

    assert result["metadata"]["business_area_count"] >= 4
    assert any(point["business_area_score"] > 0 for point in result["points"])


def test_mae_hong_son_heatmap_keeps_khun_yuam_and_mae_sariang_service_corridors_visible():
    result = generate_province_heatmap(
        "Mae Hong Son",
        year=2026,
        scenario="base",
        resolution_km=0.5,
        mode="urban",
    )

    khun_yuam_points = [
        point for point in result["points"]
        if 18.82 <= point["lat"] <= 18.84 and 97.93 <= point["lon"] <= 97.95
    ]
    mae_sariang_points = [
        point for point in result["points"]
        if 18.15 <= point["lat"] <= 18.17 and 97.92 <= point["lon"] <= 97.94
    ]

    assert khun_yuam_points
    assert mae_sariang_points
