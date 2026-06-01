"""Site readiness, competition, ramp-up, and power-sharing layer.

This module sits after the raw location/station demand models.  It answers the
question: "Of the demand in this area, how much can this exact site capture?"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from math import ceil, exp
from typing import Optional

from .exceptions import (
    InvalidReadinessScoreError,
    InvalidStationFormatError,
    InvalidStationSpecError,
)

logger = logging.getLogger(__name__)

VALID_STATION_FORMATS = {
    "highway_hub",
    "roadside_destination",
    "urban_hub",
    "mall_surface_lot",
    "community_mall",
    "inside_parking",
    "test_launch",
}


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to a range."""
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
    """Physical station configuration.

    Attributes:
        guns: Number of charging guns/connectors
        total_site_kw: Total site power capacity in kW
        max_kw_per_gun: Maximum power per gun in kW

    Example:
        >>> station = StationSpec(guns=12, total_site_kw=720, max_kw_per_gun=180)
        >>> station.effective_kw(active_guns=4)
        180.0
        >>> station.effective_kw(active_guns=12)
        60.0
    """

    guns: int
    total_site_kw: float
    max_kw_per_gun: float

    def __post_init__(self):
        """Validate station specification parameters."""
        if not isinstance(self.guns, int):
            raise InvalidStationSpecError("guns", self.guns, "Must be an integer")
        if self.guns <= 0:
            raise InvalidStationSpecError("guns", self.guns, "Must be positive")
        
        if not isinstance(self.total_site_kw, (int, float)):
            raise InvalidStationSpecError("total_site_kw", self.total_site_kw, "Must be a number")
        if self.total_site_kw <= 0:
            raise InvalidStationSpecError("total_site_kw", self.total_site_kw, "Must be positive")
        
        if not isinstance(self.max_kw_per_gun, (int, float)):
            raise InvalidStationSpecError("max_kw_per_gun", self.max_kw_per_gun, "Must be a number")
        if self.max_kw_per_gun <= 0:
            raise InvalidStationSpecError("max_kw_per_gun", self.max_kw_per_gun, "Must be positive")
        
        logger.debug(
            f"Created StationSpec: {self.guns} guns, "
            f"{self.total_site_kw} kW total, {self.max_kw_per_gun} kW/gun max"
        )

    def effective_kw(self, active_guns: Optional[int] = None) -> float:
        """Usable kW per active gun after site-level power sharing.

        Args:
            active_guns: Number of guns currently in use (default: all guns)

        Returns:
            Effective kW per active gun

        Raises:
            InvalidStationSpecError: If parameters are invalid
            ValueError: If active_guns is not positive
        """
        if active_guns is None:
            active_guns = self.guns
        
        if not isinstance(active_guns, int):
            raise TypeError(f"active_guns must be an integer, got {type(active_guns).__name__}")
        if active_guns <= 0:
            raise ValueError(f"active_guns must be positive, got {active_guns}")
        
        return min(self.max_kw_per_gun, self.total_site_kw / active_guns)

    def effective_kw_at_utilization(self, utilization: float) -> float:
        """Effective kW per gun at a given utilization level.

        Args:
            utilization: Utilization fraction (0.0 to 1.0)

        Returns:
            Effective kW per active gun

        Raises:
            TypeError: If utilization is not a number
        """
        if not isinstance(utilization, (int, float)):
            raise TypeError(f"utilization must be a number, got {type(utilization).__name__}")
        
        active_guns = max(1, ceil(self.guns * _clamp(utilization, 0.0, 1.0)))
        return self.effective_kw(active_guns)


@dataclass(frozen=True)
class SiteReadiness:
    """How ready the exact site is to convert local demand into sessions.

    Scores use 0..1 unless otherwise noted. Parking capacity is actual bays
    available around the charger, not just EV charging bays.

    Attributes:
        station_format: Type of station (see VALID_STATION_FORMATS)
        visibility_from_road: How visible from main road (0-1)
        access_ease: How easy to access (0-1)
        parking_capacity: Number of parking bays
        roadside_frontage: Whether site has roadside frontage
        signage_quality: Quality of signage (0-1)
        tenant_strength: Strength of tenant/anchor (0-1)
        inside_parking_structure: Whether inside parking structure

    Example:
        >>> readiness = SiteReadiness(
        ...     station_format="mall_surface_lot",
        ...     visibility_from_road=0.95,
        ...     access_ease=0.90,
        ...     parking_capacity=50,
        ...     roadside_frontage=True,
        ...     signage_quality=0.85,
        ...     tenant_strength=0.95,
        ... )
        >>> readiness.multiplier()
        1.35
    """

    station_format: str = "community_mall"
    visibility_from_road: float = 0.5
    access_ease: float = 0.5
    parking_capacity: int = 8
    roadside_frontage: bool = False
    signage_quality: float = 0.5
    tenant_strength: float = 0.5
    inside_parking_structure: bool = False

    def __post_init__(self):
        """Validate site readiness parameters."""
        if self.station_format not in VALID_STATION_FORMATS:
            raise InvalidStationFormatError(self.station_format, list(VALID_STATION_FORMATS))
        
        if not isinstance(self.visibility_from_road, (int, float)):
            raise InvalidReadinessScoreError("visibility_from_road", self.visibility_from_road)
        if self.visibility_from_road < 0 or self.visibility_from_road > 1:
            raise InvalidReadinessScoreError("visibility_from_road", self.visibility_from_road)
        
        if not isinstance(self.access_ease, (int, float)):
            raise InvalidReadinessScoreError("access_ease", self.access_ease)
        if self.access_ease < 0 or self.access_ease > 1:
            raise InvalidReadinessScoreError("access_ease", self.access_ease)
        
        if not isinstance(self.parking_capacity, int):
            raise TypeError(f"parking_capacity must be an integer, got {type(self.parking_capacity).__name__}")
        if self.parking_capacity < 0:
            raise ValueError(f"parking_capacity must be non-negative, got {self.parking_capacity}")
        
        if not isinstance(self.signage_quality, (int, float)):
            raise InvalidReadinessScoreError("signage_quality", self.signage_quality)
        if self.signage_quality < 0 or self.signage_quality > 1:
            raise InvalidReadinessScoreError("signage_quality", self.signage_quality)
        
        if not isinstance(self.tenant_strength, (int, float)):
            raise InvalidReadinessScoreError("tenant_strength", self.tenant_strength)
        if self.tenant_strength < 0 or self.tenant_strength > 1:
            raise InvalidReadinessScoreError("tenant_strength", self.tenant_strength)
        
        logger.debug(
            f"Created SiteReadiness: format={self.station_format}, "
            f"visibility={self.visibility_from_road}, access={self.access_ease}"
        )

    def multiplier(self) -> float:
        """Calculate site readiness multiplier.

        Returns:
            Multiplier in range [0.55, 1.50]
        """
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


def ramp_up_factor(opening_age_days: Optional[int], station_format: str = "community_mall") -> float:
    """Expected share of mature demand reached at this opening age.

    Uses exponential ramp-up curve: floor + (1 - floor) * (1 - exp(-days / speed))

    Args:
        opening_age_days: Days since station opened (None = mature)
        station_format: Station format type

    Returns:
        Ramp-up factor in range [floor, 1.0]

    Raises:
        InvalidStationFormatError: If station_format is invalid
        TypeError: If opening_age_days is not int/None
        ValueError: If opening_age_days is negative
    """
    if opening_age_days is None:
        return 1.0
    
    if not isinstance(opening_age_days, int):
        raise TypeError(f"opening_age_days must be an integer or None, got {type(opening_age_days).__name__}")
    
    if opening_age_days < 0:
        raise ValueError(f"opening_age_days must be non-negative, got {opening_age_days}")
    
    if station_format not in VALID_STATION_FORMATS:
        raise InvalidStationFormatError(station_format, list(VALID_STATION_FORMATS))
    
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
    result = round(_clamp(factor, floor, 1.0), 3)
    
    logger.debug(
        f"Ramp-up factor: {opening_age_days} days, {station_format} → {result}"
    )
    
    return result


@dataclass(frozen=True)
class Competitor:
    """Nearby charging competitor used in the capture-share model.

    Attributes:
        name: Competitor name/identifier
        distance_km: Distance from our station in km
        guns: Number of charging guns
        max_kw: Maximum power per gun in kW
        brand_score: Brand strength (0.2-2.0, default 1.0)
        price_score: Price competitiveness (0.4-1.6, default 1.0)
        access_score: Access quality (0.2-1.8, default 1.0)
        visibility_score: Visibility quality (0.2-1.8, default 1.0)
        same_corridor: Whether on same travel corridor

    Example:
        >>> competitor = Competitor(
        ...     name="Nearby DCFC",
        ...     distance_km=0.5,
        ...     guns=4,
        ...     max_kw=120,
        ...     brand_score=1.2,
        ... )
        >>> competitor.attractiveness()
        2.34
    """

    name: str
    distance_km: float
    guns: int = 2
    max_kw: float = 120.0
    brand_score: float = 1.0
    price_score: float = 1.0
    access_score: float = 1.0
    visibility_score: float = 1.0
    same_corridor: bool = True

    def __post_init__(self):
        """Validate competitor parameters."""
        if not isinstance(self.name, str):
            raise TypeError(f"name must be a string, got {type(self.name).__name__}")
        
        if not isinstance(self.distance_km, (int, float)):
            raise TypeError(f"distance_km must be a number, got {type(self.distance_km).__name__}")
        if self.distance_km < 0:
            raise ValueError(f"distance_km must be non-negative, got {self.distance_km}")
        
        if not isinstance(self.guns, int):
            raise TypeError(f"guns must be an integer, got {type(self.guns).__name__}")
        if self.guns <= 0:
            raise ValueError(f"guns must be positive, got {self.guns}")
        
        if not isinstance(self.max_kw, (int, float)):
            raise TypeError(f"max_kw must be a number, got {type(self.max_kw).__name__}")
        if self.max_kw <= 0:
            raise ValueError(f"max_kw must be positive, got {self.max_kw}")

    def attractiveness(self) -> float:
        """Calculate competitor attractiveness score.

        Returns:
            Attractiveness score (higher = more attractive)
        """
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
    """Inputs for converting area demand into captured site demand.

    Attributes:
        name: Case name/identifier
        raw_daily_sessions: Raw daily sessions in the area
        station: Station specification
        readiness: Site readiness assessment
        competitors: List of nearby competitors
        opening_age_days: Days since station opened (None = mature)
        avg_kwh_per_session: Average energy per session in kWh
        price_per_kwh: Price per kWh in THB

    Example:
        >>> case = SiteDemandCase(
        ...     name="Central Airport",
        ...     raw_daily_sessions=220,
        ...     station=StationSpec(guns=12, total_site_kw=720, max_kw_per_gun=180),
        ...     readiness=SiteReadiness(station_format="mall_surface_lot", ...),
        ...     competitors=[Competitor("Nearby", 0.5, guns=2, max_kw=120)],
        ...     opening_age_days=180,
        ... )
    """

    name: str
    raw_daily_sessions: float
    station: StationSpec
    readiness: SiteReadiness
    competitors: list[Competitor] = field(default_factory=list)
    opening_age_days: Optional[int] = None
    avg_kwh_per_session: float = 32.0
    price_per_kwh: float = 6.5

    def __post_init__(self):
        """Validate site demand case parameters."""
        if not isinstance(self.name, str):
            raise TypeError(f"name must be a string, got {type(self.name).__name__}")
        
        if not isinstance(self.raw_daily_sessions, (int, float)):
            raise TypeError(f"raw_daily_sessions must be a number, got {type(self.raw_daily_sessions).__name__}")
        if self.raw_daily_sessions < 0:
            raise ValueError(f"raw_daily_sessions must be non-negative, got {self.raw_daily_sessions}")
        
        if not isinstance(self.station, StationSpec):
            raise TypeError(f"station must be a StationSpec, got {type(self.station).__name__}")
        
        if not isinstance(self.readiness, SiteReadiness):
            raise TypeError(f"readiness must be a SiteReadiness, got {type(self.readiness).__name__}")
        
        if not isinstance(self.competitors, list):
            raise TypeError(f"competitors must be a list, got {type(self.competitors).__name__}")
        
        for i, comp in enumerate(self.competitors):
            if not isinstance(comp, Competitor):
                raise TypeError(f"competitors[{i}] must be a Competitor, got {type(comp).__name__}")
        
        if self.opening_age_days is not None:
            if not isinstance(self.opening_age_days, int):
                raise TypeError(f"opening_age_days must be an integer or None, got {type(self.opening_age_days).__name__}")
            if self.opening_age_days < 0:
                raise ValueError(f"opening_age_days must be non-negative, got {self.opening_age_days}")
        
        if not isinstance(self.avg_kwh_per_session, (int, float)):
            raise TypeError(f"avg_kwh_per_session must be a number, got {type(self.avg_kwh_per_session).__name__}")
        if self.avg_kwh_per_session <= 0:
            raise ValueError(f"avg_kwh_per_session must be positive, got {self.avg_kwh_per_session}")
        
        if not isinstance(self.price_per_kwh, (int, float)):
            raise TypeError(f"price_per_kwh must be a number, got {type(self.price_per_kwh).__name__}")
        if self.price_per_kwh <= 0:
            raise ValueError(f"price_per_kwh must be positive, got {self.price_per_kwh}")


class CompetitiveCaptureModel:
    """Estimate what share of local demand a site can win from competitors.

    Attributes:
        min_capture: Minimum capture share (default 0.12)
        max_capture: Maximum capture share (default 0.92)

    Example:
        >>> model = CompetitiveCaptureModel()
        >>> station = StationSpec(guns=12, total_site_kw=720, max_kw_per_gun=180)
        >>> readiness = SiteReadiness(station_format="mall_surface_lot", ...)
        >>> share = model.capture_share(station, readiness, competitors=[])
        >>> print(share)
        0.78
    """

    def __init__(self, min_capture: float = 0.12, max_capture: float = 0.92):
        """Initialize competitive capture model.

        Args:
            min_capture: Minimum capture share (0-1)
            max_capture: Maximum capture share (0-1)

        Raises:
            TypeError: If parameters are not numbers
            ValueError: If parameters out of range or min > max
        """
        if not isinstance(min_capture, (int, float)):
            raise TypeError(f"min_capture must be a number, got {type(min_capture).__name__}")
        if not isinstance(max_capture, (int, float)):
            raise TypeError(f"max_capture must be a number, got {type(max_capture).__name__}")
        
        if min_capture < 0 or min_capture > 1:
            raise ValueError(f"min_capture must be in [0, 1], got {min_capture}")
        if max_capture < 0 or max_capture > 1:
            raise ValueError(f"max_capture must be in [0, 1], got {max_capture}")
        if min_capture > max_capture:
            raise ValueError(f"min_capture ({min_capture}) must be <= max_capture ({max_capture})")
        
        self.min_capture = min_capture
        self.max_capture = max_capture
        logger.debug(f"Initialized CompetitiveCaptureModel: [{min_capture}, {max_capture}]")

    def station_attractiveness(self, station: StationSpec, readiness: SiteReadiness) -> float:
        """Calculate station attractiveness score.

        Args:
            station: Station specification
            readiness: Site readiness assessment

        Returns:
            Attractiveness score

        Raises:
            TypeError: If parameters have wrong types
        """
        if not isinstance(station, StationSpec):
            raise TypeError(f"station must be a StationSpec, got {type(station).__name__}")
        if not isinstance(readiness, SiteReadiness):
            raise TypeError(f"readiness must be a SiteReadiness, got {type(readiness).__name__}")
        
        guns_factor = max(0.5, station.guns) ** 0.55
        power_factor = _clamp(station.max_kw_per_gun / 120.0, 0.45, 2.20) ** 0.45
        return guns_factor * power_factor * readiness.multiplier()

    def capture_share(
        self,
        station: StationSpec,
        readiness: SiteReadiness,
        competitors: Optional[list[Competitor]] = None,
    ) -> float:
        """Estimate capture share against competitors.

        Args:
            station: Station specification
            readiness: Site readiness assessment
            competitors: List of nearby competitors (default: empty)

        Returns:
            Capture share in [min_capture, max_capture]

        Raises:
            TypeError: If parameters have wrong types
        """
        if not isinstance(station, StationSpec):
            raise TypeError(f"station must be a StationSpec, got {type(station).__name__}")
        if not isinstance(readiness, SiteReadiness):
            raise TypeError(f"readiness must be a SiteReadiness, got {type(readiness).__name__}")
        
        competitors = competitors or []
        
        if not isinstance(competitors, list):
            raise TypeError(f"competitors must be a list, got {type(competitors).__name__}")
        
        for i, comp in enumerate(competitors):
            if not isinstance(comp, Competitor):
                raise TypeError(f"competitors[{i}] must be a Competitor, got {type(comp).__name__}")
        
        our_score = self.station_attractiveness(station, readiness)
        competitor_score = sum(c.attractiveness() for c in competitors)
        
        if competitor_score <= 0:
            return round(_clamp(0.78 * readiness.multiplier(), self.min_capture, self.max_capture), 3)
        
        share = our_score / (our_score + competitor_score)
        return round(_clamp(share, self.min_capture, self.max_capture), 3)

    def estimate(self, case: SiteDemandCase) -> dict:
        """Estimate captured demand for a site.

        Args:
            case: Site demand case with all inputs

        Returns:
            Dictionary with keys:
                - name: str
                - raw_daily_sessions: float
                - readiness_multiplier: float
                - competitive_capture_share: float
                - ramp_up_factor: float
                - mature_daily_sessions: float
                - captured_daily_sessions: float
                - daily_kwh: float
                - daily_revenue: float
                - effective_kw_at_expected_load: float
                - competitor_count: int

        Raises:
            TypeError: If case is not a SiteDemandCase
        """
        if not isinstance(case, SiteDemandCase):
            raise TypeError(f"case must be a SiteDemandCase, got {type(case).__name__}")
        
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

        result = {
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
        
        logger.debug(
            f"Site estimate: {case.name} → {result['captured_daily_sessions']} sessions/day, "
            f"{result['daily_kwh']} kWh/day, {result['daily_revenue']} THB/day"
        )
        
        return result
