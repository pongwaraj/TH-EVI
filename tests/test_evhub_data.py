from th_evi.data import (
    get_evhub_dlt_fleet,
    get_evhub_population,
    get_sinexcel_package,
    load_evhub_dopa_population,
)


PHRAE = "\u0e41\u0e1e\u0e23\u0e48"
DEN_CHAI = "\u0e40\u0e14\u0e48\u0e19\u0e0a\u0e31\u0e22"
CHIANG_RAI = "\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e23\u0e32\u0e22"


def test_evhub_dopa_has_phrae_and_den_chai():
    phrae = get_evhub_population(PHRAE)
    den_chai = get_evhub_population(PHRAE, DEN_CHAI)

    assert phrae["population"] == 417480
    assert phrae["households"] == 187264
    assert den_chai["population"] == 19154
    assert den_chai["households"] == 8753


def test_evhub_dopa_can_filter_area_type():
    districts = load_evhub_dopa_population(province=PHRAE, area_type="district")

    assert not districts.empty
    assert districts["area_name"].str.contains(DEN_CHAI, regex=False).any()


def test_evhub_dlt_has_phrae_passenger_car_fleet():
    fleet = get_evhub_dlt_fleet(PHRAE)

    assert fleet["vehicle_segment"] == "ror1_passenger_car"
    assert fleet["total_vehicles"] == 51702
    assert fleet["bev"] == 426
    assert round(fleet["bev_share"], 6) == 0.00824


def test_evhub_dopa_and_dlt_have_chiang_rai_base_data():
    population = get_evhub_population(CHIANG_RAI)
    fleet = get_evhub_dlt_fleet(CHIANG_RAI)

    assert population["population"] == 1295922
    assert population["households"] == 603627
    assert fleet["vehicle_segment"] == "ror1_passenger_car"
    assert fleet["total_vehicles"] == 178675
    assert fleet["bev"] == 3545
    assert fleet["phev_gasoline"] == 403
    assert fleet["phev_diesel"] == 1


def test_sinexcel_package_prices_are_normalized():
    package = get_sinexcel_package("INT-S-2-180")

    assert package["charger_power_kw"] == 180
    assert package["parking_stalls"] == 2
    assert package["customer_capex_thb"] == 2163300
