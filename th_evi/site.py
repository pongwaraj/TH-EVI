"""Site readiness, competition, ramp-up, and power-sharing layer.

This module sits after the raw location/station demand models.  It answers the
question: "Of the demand in this area, how much can this exact site capture?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, exp


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


STATION_FORMAT_WEIGHTS = {
    "highway_hub": 1.18,
    "roadside_destination": 1.15,
    "urban_hub": 1.10,
    "mall_surface_lot": 1.08,
    "community_mall": 1.00,
    "inside_parking": 0.86,
    "test_launch": 0.78,
}


@dataclass(frozen=True)
class StationSpec:
    """Physical station configuration."""

    guns: int
    total_site_kw: float
    max_kw_per_gun: float

    def effective_kw(self, active_guns: int | None = None) -> float:
        """Usable kW per active gun after site-level power sharing."""
        if self.guns <= 0 or self.total_site_kw <= 0 or self.max_kw_per_gun <= 0:
            raise ValueError("guns, total_site_kw, and max_kw_per_gun must be positive")
        if active_guns is None:
            active_guns = self.guns
        if active_guns <= 0:
            raise ValueError("active_guns must be positive")
        return min(self.max_kw_per_gun, self.total_site_kw / active_guns)

    def effective_kw_at_utilization(self, utilization: float) -> float:
        active_guns = max(1, ceil(self.guns * _clamp(utilization, 0.0, 1.0)))
        return self.effective_kw(active_guns)


@dataclass(frozen=True)
class SiteReadiness:
    """How ready the exact site is to convert local demand into sessions.

    Scores use 0..1 unless otherwise noted. Parking capacity is actual bays
    available around the charger, not just EV charging bays.
    """

    station_format: str = "community_mall"
    visibility_from_road: float = 0.5
    access_ease: float = 0.5
    parking_capacity: int = 8
    roadside_frontage: bool = False
    signage_quality: float = 0.5
    tenant_strength: float = 0.5
    inside_parking_structure: bool = False

    def multiplier(self) -> float:
        visibility = _clamp(self.visibility_from_road, 0.0, 1.0)
        access = _clamp(self.access_ease, 0.0, 1.0)
        signage = _clamp(self.signage_quality, 0.0, 1.0)
        tenant = _clamp(self.tenant_strength, 0.0, 1.0)

        score = (
            0.34 * visibility
            + 0.28 * access
            + 0.18 * signage
            + 0.20 * tenant
        )

        multiplier = 0.70 + score * 0.58
        multiplier *= STATION_FORMAT_WEIGHTS.get(self.station_format, 1.0)

        if self.roadside_frontage:
            multiplier *= 1.08
        if self.parking_capacity >= 40:
            multiplier *= 1.08
        elif self.parking_capacity >= 20:
            multiplier *= 1.04
        elif self.parking_capacity < 8:
            multiplier *= 0.92
        if self.inside_parking_structure:
            multiplier *= 0.90

        return round(_clamp(multiplier, 0.55, 1.50), 3)


def ramp_up_factor(opening_age_days: int | None, station_format: str = "community_mall") -> float:
    """Expected share of mature demand reached at this opening age."""
    if opening_age_days is None:
        return 1.0
    days = max(0, opening_age_days)

    if station_format in {"highway_hub", "roadside_destination", "mall_surface_lot"}:
        floor = 0.38
        speed_days = 150.0
    elif station_format == "test_launch":
        floor = 0.22
        speed_days = 240.0
    else:
        floor = 0.30
        speed_days = 190.0

    factor = floor + (1.0 - floor) * (1.0 - exp(-days / speed_days))
    return round(_clamp(factor, floor, 1.0), 3)


@dataclass(frozen=True)
class Competitor:
    """Nearby charging competitor used in the capture-share model."""

    name: str
    distance_km: float
    guns: int = 2
    max_kw: float = 120.0
    brand_score: float = 1.0
    price_score: float = 1.0
    access_score: float = 1.0
    visibility_score: float = 1.0
    same_corridor: bool = True

    def attractiveness(self) -> float:
        guns_factor = max(0.5, self.guns) ** 0.55
        power_factor = _clamp(self.max_kw / 120.0, 0.45, 2.20) ** 0.45
        quality_factor = (
            _clamp(self.brand_score, 0.2, 2.0)
            * _clamp(self.price_score, 0.4, 1.6)
            * _clamp(self.access_score, 0.2, 1.8)
            * _clamp(self.visibility_score, 0.2, 1.8)
        ) ** 0.25
        distance_decay = exp(-max(0.0, self.distance_km) / 3.0)
        corridor_factor = 1.15 if self.same_corridor else 0.82
        return guns_factor * power_factor * quality_factor * distance_decay * corridor_factor


@dataclass(frozen=True)
class SiteDemandCase:
    """Inputs for converting area demand into captured site demand."""

    name: str
    raw_daily_sessions: float
    station: StationSpec
    readiness: SiteReadiness
    competitors: list[Competitor] = field(default_factory=list)
    opening_age_days: int | None = None
    avg_kwh_per_session: float = 32.0
    price_per_kwh: float = 6.5


class CompetitiveCaptureModel:
    """Estimate what share of local demand a site can win from competitors."""

    def __init__(self, min_capture: float = 0.12, max_capture: float = 0.92):
        self.min_capture = min_capture
        self.max_capture = max_capture

    def station_attractiveness(self, station: StationSpec, readiness: SiteReadiness) -> float:
        guns_factor = max(0.5, station.guns) ** 0.55
        power_factor = _clamp(station.max_kw_per_gun / 120.0, 0.45, 2.20) ** 0.45
        return guns_factor * power_factor * readiness.multiplier()

    def capture_share(
        self,
        station: StationSpec,
        readiness: SiteReadiness,
        competitors: list[Competitor] | None = None,
    ) -> float:
        competitors = competitors or []
        our_score = self.station_attractiveness(station, readiness)
        competitor_score = sum(c.attractiveness() for c in competitors)
        if competitor_score <= 0:
            return round(_clamp(0.78 * readiness.multiplier(), self.min_capture, self.max_capture), 3)
        share = our_score / (our_score + competitor_score)
        return round(_clamp(share, self.min_capture, self.max_capture), 3)

    def estimate(self, case: SiteDemandCase) -> dict:
        readiness_multiplier = case.readiness.multiplier()
        ramp = ramp_up_factor(
            case.opening_age_days,
            station_format=case.readiness.station_format,
        )
        capture = self.capture_share(case.station, case.readiness, case.competitors)
        mature_sessions = case.raw_daily_sessions * readiness_multiplier * capture
        captured_sessions = mature_sessions * ramp
        utilization = _clamp(captured_sessions / max(1.0, case.station.guns * 22.0), 0.0, 1.0)
        effective_kw = case.station.effective_kw_at_utilization(utilization)

        return {
            "name": case.name,
            "raw_daily_sessions": round(case.raw_daily_sessions, 1),
            "readiness_multiplier": readiness_multiplier,
            "competitive_capture_share": capture,
            "ramp_up_factor": ramp,
            "mature_daily_sessions": round(mature_sessions, 1),
            "captured_daily_sessions": round(captured_sessions, 1),
            "daily_kwh": round(captured_sessions * case.avg_kwh_per_session, 1),
            "daily_revenue": round(captured_sessions * case.avg_kwh_per_session * case.price_per_kwh, 0),
            "effective_kw_at_expected_load": round(effective_kw, 1),
            "competitor_count": len(case.competitors),
        }
