"""Tests for site readiness, competition, ramp-up, and power sharing."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from th_evi.site import (
    CompetitiveCaptureModel,
    Competitor,
    SiteDemandCase,
    SiteReadiness,
    StationSpec,
    ramp_up_factor,
)


def test_roadside_surface_site_scores_higher_than_hidden_site():
    central_like = SiteReadiness(
        station_format="mall_surface_lot",
        visibility_from_road=0.95,
        access_ease=0.90,
        parking_capacity=50,
        roadside_frontage=True,
        signage_quality=0.85,
        tenant_strength=0.95,
    )
    hidden = SiteReadiness(
        station_format="inside_parking",
        visibility_from_road=0.30,
        access_ease=0.45,
        parking_capacity=6,
        inside_parking_structure=True,
        signage_quality=0.35,
        tenant_strength=0.50,
    )
    assert central_like.multiplier() > 1.25
    assert hidden.multiplier() < 0.90
    assert central_like.multiplier() > hidden.multiplier()


def test_ramp_up_increases_with_age():
    early = ramp_up_factor(20, "test_launch")
    month_6 = ramp_up_factor(180, "test_launch")
    mature = ramp_up_factor(365, "test_launch")
    assert early < month_6 < mature <= 1.0


def test_competitors_reduce_capture_share():
    model = CompetitiveCaptureModel()
    station = StationSpec(guns=4, total_site_kw=360, max_kw_per_gun=180)
    readiness = SiteReadiness(
        station_format="roadside_destination",
        visibility_from_road=0.8,
        access_ease=0.8,
        parking_capacity=20,
        roadside_frontage=True,
        signage_quality=0.8,
        tenant_strength=0.7,
    )
    no_competitor = model.capture_share(station, readiness, [])
    with_competitor = model.capture_share(
        station,
        readiness,
        [
            Competitor(
                name="Strong nearby hub",
                distance_km=0.5,
                guns=8,
                max_kw=240,
                brand_score=1.4,
                access_score=1.2,
                visibility_score=1.2,
            )
        ],
    )
    assert with_competitor < no_competitor


def test_power_sharing_for_720kw_12_guns():
    station = StationSpec(guns=12, total_site_kw=720, max_kw_per_gun=180)
    assert station.effective_kw(1) == 180
    assert station.effective_kw(4) == 180
    assert station.effective_kw(6) == 120
    assert station.effective_kw(12) == 60


def test_site_case_estimate_maps_raw_to_captured_sessions_and_revenue():
    model = CompetitiveCaptureModel()
    case = SiteDemandCase(
        name="Central Airport-like site",
        raw_daily_sessions=220,
        station=StationSpec(guns=12, total_site_kw=720, max_kw_per_gun=180),
        readiness=SiteReadiness(
            station_format="mall_surface_lot",
            visibility_from_road=0.95,
            access_ease=0.9,
            parking_capacity=50,
            roadside_frontage=True,
            signage_quality=0.85,
            tenant_strength=0.95,
        ),
        competitors=[
            Competitor("Nearby 125 kW", 0.18, guns=2, max_kw=125, brand_score=1.1),
            Competitor("Nearby 120 kW", 0.62, guns=4, max_kw=120, brand_score=1.0),
        ],
        opening_age_days=180,
    )
    result = model.estimate(case)
    assert result["captured_daily_sessions"] > 80
    assert result["captured_daily_sessions"] < result["raw_daily_sessions"]
    assert result["daily_revenue"] > 15000
