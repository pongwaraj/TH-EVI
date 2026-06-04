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
