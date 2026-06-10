from th_evi.api import list_chargers


def test_chargers_api_returns_selected_province_competitors():
    payload = list_chargers(province="Phitsanulok")

    assert payload["province"] == "Phitsanulok"
    assert payload["station_count"] >= 5
    station_names = {station["name"] for station in payload["stations"]}
    assert "PEA VOLTA Charging Station (Singhawat / Phlai Chumphon)" in station_names
