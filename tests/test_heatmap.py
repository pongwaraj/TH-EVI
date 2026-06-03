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
