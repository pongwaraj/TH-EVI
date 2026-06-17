from pathlib import Path
from zipfile import ZipFile

from th_evi.owner_area_report import (
    OwnerAreaReportRequest,
    create_owner_area_analysis_pdf,
    create_owner_area_analysis_report,
)


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
