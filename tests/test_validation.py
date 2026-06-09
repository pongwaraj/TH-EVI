from th_evi.validation import (
    load_station_ground_truth,
    load_station_to_collect,
    station_calibration_summary,
)


def test_station_ground_truth_csv_is_loaded():
    rows = load_station_ground_truth()

    assert rows
    assert rows[0]["id"] == "cm_cultural_center_hub"
    assert rows[0]["obs_daily"] == 130.0


def test_station_calibration_summary_reports_readiness():
    summary = station_calibration_summary()

    assert summary["ground_truth_points"] >= 1
    assert summary["calibration_factor"] > 0
    assert isinstance(summary["next_to_collect"], list)
    assert load_station_to_collect()
