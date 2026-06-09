from th_evi.api import list_chargers


def test_chargers_api_returns_selected_province_competitors():
    payload = list_chargers(province="Phitsanulok")

    assert payload["province"] == "Phitsanulok"
    assert payload["station_count"] >= 5
    assert all(station["lat"] and station["lon"] for station in payload["stations"])
    station_networks = {station["network"] for station in payload["stations"]}
    assert "EV Station PluZ" in station_networks
