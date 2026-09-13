from th_evi.api import list_chargers
from th_evi.spatial import THAILAND_PROVINCE_PAIRS


def test_chargers_api_returns_selected_province_competitors():
    payload = list_chargers(province="Phitsanulok")

    assert payload["province"] == "Phitsanulok"
    assert payload["station_count"] >= 5
    station_names = {station["name"] for station in payload["stations"]}
    assert "สถานีชาร์จลานจอดรถพิษณุโลก" in station_names


def test_chargers_api_serves_nationwide_kml_provinces():
    assert len(THAILAND_PROVINCE_PAIRS) == 77

    saraburi = list_chargers(province="Saraburi")
    ayutthaya = list_chargers(province="Phra Nakhon Si Ayutthaya")

    assert saraburi["station_count"] >= 30
    assert ayutthaya["station_count"] >= 40
    assert all(
        station["verification_status"] == "public_listing_needs_operator_verification"
        for station in saraburi["stations"]
        if station["name"]
        and station["station_id"]
        and station["station_id"].startswith("saraburi_kml_")
    )
