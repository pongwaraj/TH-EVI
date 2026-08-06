from th_evi.heatmap import generate_province_heatmap
from th_evi.spatial import load_competitors_for_province, load_pois_for_province


def test_chon_buri_sattahip_reference_data_generates_land_heatmap():
    pois = load_pois_for_province("Chon Buri")
    competitors = load_competitors_for_province("Chon Buri")

    assert any(poi["poi_id"] == "sattahip_fleet_command_frontage" for poi in pois)
    assert len(competitors) >= 7

    result = generate_province_heatmap(
        "Chon Buri",
        year=2026,
        scenario="base",
        resolution_km=1.0,
        mode="urban",
    )

    assert result["point_count"] > 0
    # Explicit Gulf exclusions must keep the generated surface off open water.
    assert not any(point["lat"] < 12.64 and point["lon"] < 100.94 for point in result["points"])
