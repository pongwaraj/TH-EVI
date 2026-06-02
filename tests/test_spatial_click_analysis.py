from fastapi.testclient import TestClient

from th_evi.api import app
from th_evi.spatial import (
    analyze_click_location,
    competitor_penalty_field,
    poi_attraction_field,
)

UDON_THANI = "\u0e2d\u0e38\u0e14\u0e23\u0e18\u0e32\u0e19\u0e35"


def test_poi_attraction_decays_with_distance():
    pois = [
        {
            "name": "Strong Mall",
            "category": "shopping_mall",
            "lat": "18.0",
            "lon": "99.0",
            "confidence": "high",
        }
    ]

    near, near_rows = poi_attraction_field(18.0, 99.0, pois)
    far, far_rows = poi_attraction_field(18.08, 99.08, pois)

    assert near > far
    assert near_rows[0]["name"] == "Strong Mall"
    assert far_rows == [] or far_rows[0]["sessions"] < near_rows[0]["sessions"]


def test_competitor_penalty_decays_with_distance_and_skips_missing_coordinates():
    competitors = [
        {
            "name": "Nearby DC Hub",
            "lat": "18.0",
            "lon": "99.0",
            "guns": "6",
            "max_kw": "240",
            "verification_status": "verified",
        },
        {
            "name": "Unpinned station",
            "lat": "",
            "lon": "",
            "verification_status": "seed_needs_verification",
        },
    ]

    near, near_rows, skipped = competitor_penalty_field(18.0, 99.0, competitors)
    far, _, _ = competitor_penalty_field(18.08, 99.08, competitors)

    assert skipped == 1
    assert near > far
    assert near_rows[0]["name"] == "Nearby DC Hub"


def test_click_analysis_combines_base_poi_and_competitor_fields():
    result = analyze_click_location(
        lat=17.4058,
        lon=102.7998,
        province=UDON_THANI,
        year=2030,
        scenario="base",
        avg_kwh_per_session=28,
        price_per_kwh=6.8,
    )

    assert result["net_sessions_per_day"] > 0
    assert result["poi_boost_sessions"] > 0
    assert result["daily_kwh"] == round(result["net_sessions_per_day"] * 28, 1)
    assert result["top_pois"]


def test_click_analysis_api_returns_explainable_components():
    response = TestClient(app).post(
        "/api/click-analysis",
        json={
            "lat": 17.4058,
            "lon": 102.7998,
            "province": UDON_THANI,
            "year": 2030,
            "scenario": "base",
            "avg_kwh_per_session": 28,
            "price_per_kwh": 6.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "base_sessions" in payload
    assert "poi_boost_sessions" in payload
    assert "competitor_penalty_sessions" in payload
    assert "top_pois" in payload
    assert "top_competitors" in payload
