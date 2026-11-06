from pathlib import Path

from th_evi.heatmap import generate_province_heatmap
from th_evi.spatial import load_competitors_for_province, load_pois_for_province


def test_khlung_pilot_loads_in_thai_and_english():
    for province in ("จันทบุรี", "Chanthaburi"):
        assert any(p["poi_id"] == "khlung_market_heritage" for p in load_pois_for_province(province))
        result = generate_province_heatmap(province, year=2026, resolution_km=1)
        assert result["points"]
        assert any(abs(p["lat"] - 12.459514) < .03 and abs(p["lon"] - 102.230454) < .03 for p in result["points"])


def test_competitors_show_without_kml_duplicates():
    items = load_competitors_for_province("Chanthaburi")
    ids = [c["station_id"] for c in items]
    for station in ("chanthaburi_kml_9f67c8630121", "chanthaburi_kml_33e955e798d3", "chanthaburi_igreen_shell_khlung"):
        assert ids.count(station) == 1
    shell = next(c for c in items if c["station_id"] == "chanthaburi_igreen_shell_khlung")
    assert not shell.get("max_kw")
    assert shell["verification_status"] == "public_listing_needs_operator_verification"


def test_planning_selectable():
    html = (Path(__file__).resolve().parents[1] / "th_evi/static/planning.html").read_text(encoding="utf-8")
    assert '<option value="จันทบุรี">จันทบุรี</option>' in html
    assert '"จันทบุรี": "Chanthaburi"' in html
