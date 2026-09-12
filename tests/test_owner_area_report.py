from pathlib import Path
from zipfile import ZipFile

from th_evi.owner_area_report import (
    OwnerAreaReportRequest,
    _projection_rows,
    _report_station_spec,
    _choose_tile_zoom,
    create_owner_area_analysis_pdf,
    create_owner_area_analysis_report,
)


def test_report_uses_station_spec_to_cap_served_sessions(monkeypatch):
    import th_evi.spatial as spatial

    monkeypatch.setattr(
        spatial,
        "analyze_click_location",
        lambda **kwargs: {
            "net_sessions_per_day": 100.0,
            "daily_kwh": 3500.0,
        },
    )
    request = OwnerAreaReportRequest(
        site_name="Capacity test",
        province="Chiang Mai",
        lat=18.8,
        lon=98.9,
        start_year=2026,
        end_year=2026,
        station_guns=2,
        station_total_site_kw=60.0,
        station_max_kw_per_gun=30.0,
    )

    row = _projection_rows(request)[0]

    assert row["served_sessions_per_day"] < row["net_sessions_per_day"]
    assert row["served_sessions_per_day"] == row["service_capacity_sessions_per_day"]
    assert row["capacity_limited"] is True


def test_report_parses_legacy_recommended_spec():
    request = OwnerAreaReportRequest(
        site_name="Legacy spec",
        province="Chiang Mai",
        lat=18.8,
        lon=98.9,
        recommended_spec="180 kW | 2 ตู้ | 4 ช่องจอด",
    )

    spec = _report_station_spec(request)

    assert spec.guns == 4
    assert spec.total_site_kw == 360
    assert spec.max_kw_per_gun == 180


def test_owner_area_report_includes_generated_map_image(tmp_path, monkeypatch):
    import th_evi.owner_area_report as owner_report

    monkeypatch.setattr(owner_report, "REPORT_OUTPUT_DIR", tmp_path)

    report_path = create_owner_area_analysis_report(
        OwnerAreaReportRequest(
            site_name="The Kad Farang Mae Rim",
            province="Chiang Mai",
            lat=18.902150,
            lon=98.948371,
            report_type="owner-area-analysis",
            recommended_spec="180 kW | 2 ตู้ | 4 ช่องจอด",
        )
    )

    assert report_path.exists()
    png_files = list(tmp_path.glob("*.png"))
    assert len(png_files) >= 2

    with ZipFile(report_path) as zf:
        names = zf.namelist()
        media_files = [name for name in names if name.startswith("word/media/")]
        assert len(media_files) >= 2


def test_owner_area_report_generates_pdf(tmp_path, monkeypatch):
    import th_evi.owner_area_report as owner_report

    monkeypatch.setattr(owner_report, "REPORT_OUTPUT_DIR", tmp_path)

    pdf_path = create_owner_area_analysis_pdf(
        OwnerAreaReportRequest(
            site_name="The Kad Farang Mae Rim",
            province="Chiang Mai",
            lat=18.902150,
            lon=98.948371,
            report_type="owner-area-analysis",
            recommended_spec="180 kW | 2 ตู้ | 4 ช่องจอด",
        )
    )

    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_choose_tile_zoom_steps_down_when_bounds_are_large():
    zoom = _choose_tile_zoom(
        lat_min=18.81215,
        lat_max=18.99215,
        lon_min=98.858371,
        lon_max=99.038371,
        preferred_zoom=14,
        min_zoom=11,
        max_tiles=24,
    )
    assert zoom < 14
    assert zoom >= 11
