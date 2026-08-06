"""
Location Demand Model — Given a lat/lon in Thailand, estimate daily EV visits.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from . import constants as C
from .adoption import EVAdoptionModel, estimate_fleet_ev_share, estimate_fleet_ev_population
from .data import get_cm_highway_aadt, load_doh_aadt
from .exceptions import (
    InvalidCoordinatesError,
    InvalidLocationTypeError,
    InvalidYearError,
    UnknownLocationError,
)

logger = logging.getLogger(__name__)

CHIANG_MAI_HIGHWAY_AADT = None
HIGHWAY_AADT_BY_PROVINCE = {}

PROVINCE_AADT_ALIASES = {
    "Chiang Mai": "เชียงใหม่",
    "เชียงใหม่": "เชียงใหม่",
    "Phitsanulok": "พิษณุโลก",
    "พิษณุโลก": "พิษณุโลก",
    "Phuket": "ภูเก็ต",
    "ภูเก็ต": "ภูเก็ต",
    "Chon Buri": "ชลบุรี",
    "ชลบุรี": "ชลบุรี",
}

ROUTE_BBOXES_BY_PROVINCE = {
    "เชียงใหม่": [
        (1141, (18.76, 18.80, 98.94, 98.98)),
        # Saraphi / Chai Sathan sits beside the Ring 3 - Highway 11 interface.
        # Use Route 121 as the nearest mapped arterial context here, before the
        # much broader Route 118 box can incorrectly assign north-east traffic.
        (121, (18.70, 18.75, 99.00, 99.07)),
        (121, (18.75, 18.90, 98.90, 99.10)),
        (1001, (18.80, 19.00, 98.85, 99.00)),
        (107, (18.80, 19.50, 98.80, 99.10)),
        (108, (18.20, 18.80, 98.60, 99.00)),
        (118, (18.70, 19.30, 98.95, 99.50)),
        (11, (18.60, 18.85, 98.85, 99.20)),
    ],
    "ภูเก็ต": [
        (4024, (7.84, 7.94, 98.34, 98.40)),
        (402, (7.93, 8.13, 98.31, 98.37)),
        (4020, (7.88, 7.92, 98.32, 98.37)),
        (4021, (7.82, 7.89, 98.33, 98.38)),
        (4025, (7.96, 8.02, 98.29, 98.36)),
        (4026, (8.08, 8.13, 98.29, 98.33)),
        (4027, (7.97, 8.07, 98.35, 98.39)),
        (4028, (7.81, 7.86, 98.30, 98.35)),
        (4029, (7.88, 7.92, 98.28, 98.34)),
        (4030, (7.78, 8.02, 98.30, 98.35)),
        (4031, (8.06, 8.12, 98.30, 98.36)),
        (4302, (8.10, 8.18, 98.30, 98.36)),
    ],
    "พิษณุโลก": [
        # Target-side urban corridor: Route 117 is Si Harat Decho Chai Road.
        # The DOT's Phitsanulok public-transport study identifies this road as
        # Route 117; the broad box avoids projecting its AADT across the bypass.
        (117, (16.775, 16.835, 100.205, 100.255)),
        (12, (16.810, 16.875, 100.245, 100.335)),
        (126, (16.795, 16.890, 100.280, 100.370)),
        (1058, (16.800, 16.830, 100.240, 100.275)),
        (1061, (16.810, 16.860, 100.200, 100.240)),
    ],
    "ชลบุรี": [
        # Keep Sattahip town distinct from the much busier Pattaya corridor.
        (3573, (12.62, 12.70, 100.86, 100.94)),
        (3126, (12.66, 12.75, 100.94, 101.02)),
        (331, (12.67, 12.79, 100.93, 101.03)),
        (332, (12.67, 12.76, 100.96, 101.08)),
        (3, (12.72, 12.87, 100.88, 100.95)),
    ],
}

# Local-road pockets that fall inside a deliberately broad route bounding box.
# These are not measured AADT segments; they prevent a nearby arterial's maximum
# AADT from being projected onto a residential or riverside access road.
LOCAL_ACCESS_AADT_BBOXES_BY_PROVINCE = {
    "เชียงใหม่": [
        # Mueang Kaeo east of Route 107 / Ring 3: riverside resorts, flower
        # gardens, and village roads rather than the Route 121 carriageway.
        ((18.86, 18.90, 98.965, 98.990), 8_000),
    ],
    "ชลบุรี": [
        # Waterfront access near Fleet Command is a local destination road.
        ((12.63, 12.69, 100.88, 100.94), 6_500),
    ],
}

LOCATION_TYPE_AADT_SHARE = {
    "highway": 1.0,
    "destination": 0.55,
    "city_center": 0.35,
    "suburban": 0.45,
}

VALID_LOCATION_TYPES = {"highway", "city_center", "destination", "suburban"}

LANDMARK_DB = {
    "cm_superhighway": {
        "name": "Superhighway เชียงใหม่-ลำปาง",
        "lat": 18.795, "lon": 99.010,
        "type": "highway", "route": 11, "aadt": 69988,
    },
    "cm_thaphae": {
        "name": "ประตูท่าแพ (เมือง)",
        "lat": 18.788, "lon": 98.993,
        "type": "city_center", "aadt": 12000,
    },
    "cm_central_festival": {
        "name": "Central Festival Chiang Mai",
        "lat": 18.805, "lon": 99.001,
        "type": "destination", "aadt": 8000,
    },
    "cm_airport": {
        "name": "สนามบินเชียงใหม่",
        "lat": 18.766, "lon": 98.962,
        "type": "destination", "aadt": 5000,
    },
    "cm_maya": {
        "name": "Maya Lifestyle Shopping Center",
        "lat": 18.797, "lon": 98.969,
        "type": "destination", "aadt": 7000,
    },
    "cm_hwy107": {
        "name": "ทางหลวง 107 (เชียงใหม่-ฝาง)",
        "lat": 18.907, "lon": 98.942,
        "type": "highway", "route": 107, "aadt": 39929,
    },
    "cm_hwy108": {
        "name": "ทางหลวง 108 (เชียงใหม่-ฮอด)",
        "lat": 18.685, "lon": 98.919,
        "type": "highway", "route": 108, "aadt": 60644,
    },
    "cm_hwy118": {
        "name": "ทางหลวง 118 (เชียงใหม่-เชียงราย)",
        "lat": 18.937, "lon": 99.049,
        "type": "highway", "route": 118, "aadt": 78356,
    },
    "cm_hwy121": {
        "name": "ทางหลวง 121 (รอบเมือง)",
        "lat": 18.827, "lon": 98.972,
        "type": "highway", "route": 121, "aadt": 40555,
    },
    "cm_airport_rd": {
        "name": "ทางหลวง 1141 (ถนนสนามบิน)",
        "lat": 18.776, "lon": 98.969,
        "type": "highway", "route": 1141, "aadt": 118853,
    },
    "cm_meechok_plaza": {
        "name": "มีโชคพลาซ่า คอมมูนิตี้มอลล์",
        "lat": 18.824, "lon": 99.010,
        "type": "destination", "aadt": 6000,
    },
}


class LocationDemandModel:
    """Estimate daily EV charging demand for general locations using a traffic-based model.

    Formula: EVs/day = Traffic_Volume × Fleet_EV_Share(year) × P(charge)

    Attributes:
        adoption: EVAdoptionModel instance for province
        province: Province name

    Example:
        >>> model = LocationDemandModel(province="เชียงใหม่")
        >>> result = model.estimate(18.795, 99.010, 2035, location_type="highway")
        >>> print(result["daily_ev_visits"])
        42
    """

    CHARGE_PROB = {
        "highway": 0.06,
        "city_center": 0.12,
        "destination": 0.20,
        "suburban": 0.08,
    }

    DIRECTIONAL_FACTOR = 0.50

    def __init__(self, province: str = "เชียงใหม่"):
        """Initialize location demand model for a province.

        Args:
            province: Province name (default: เชียงใหม่)

        Raises:
            TypeError: If province is not a string
        """
        if not isinstance(province, str):
            raise TypeError(f"Province must be a string, got {type(province).__name__}")
        
        self.adoption = EVAdoptionModel(province=province)
        self.province = province
        logger.debug(f"Initialized LocationDemandModel for {province}")

    def estimate(
        self,
        lat: float,
        lon: float,
        year: int,
        location_type: Optional[str] = None,
        aadt: Optional[int] = None,
    ) -> dict:
        """Estimate daily EV charging demand at a specific location.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            year: Forecast year (2018-2050)
            location_type: One of "highway", "city_center", "destination", "suburban"
                          If None, auto-classified from coordinates
            aadt: Annual Average Daily Traffic. If None, estimated from location

        Returns:
            Dictionary with keys:
                - location_type: str
                - aadt_used: int
                - fleet_ev_share_pct: float
                - charge_probability_pct: float
                - daily_ev_visits: int
                - daily_kwh: float
                - charging_sessions_per_day: int

        Raises:
            InvalidCoordinatesError: If lat/lon out of valid range
            InvalidYearError: If year out of valid range [2018, 2050]
            InvalidLocationTypeError: If location_type is invalid
            TypeError: If parameters have wrong types
        """
        if not isinstance(lat, (int, float)):
            raise TypeError(f"lat must be a number, got {type(lat).__name__}")
        if not isinstance(lon, (int, float)):
            raise TypeError(f"lon must be a number, got {type(lon).__name__}")
        if not isinstance(year, int):
            raise TypeError(f"year must be an integer, got {type(year).__name__}")
        
        if lat < -90 or lat > 90:
            raise InvalidCoordinatesError(lat, lon)
        if lon < -180 or lon > 180:
            raise InvalidCoordinatesError(lat, lon)
        
        from .adoption import _validate_year
        _validate_year(year)
        
        if location_type is not None:
            if not isinstance(location_type, str):
                raise TypeError(f"location_type must be a string, got {type(location_type).__name__}")
            if location_type not in VALID_LOCATION_TYPES:
                raise InvalidLocationTypeError(location_type, list(VALID_LOCATION_TYPES))
        else:
            location_type = self._classify_location(lat, lon)

        if aadt is not None:
            if not isinstance(aadt, int):
                raise TypeError(f"aadt must be an integer, got {type(aadt).__name__}")
            if aadt < 0:
                logger.warning(f"Negative AADT provided: {aadt}, using 0")
                aadt = 0
        else:
            aadt = self._estimate_aadt(lat, lon, location_type)

        fleet_ev_share = estimate_fleet_ev_share(year, self.province)
        p_charge = self.CHARGE_PROB.get(location_type, 0.05)

        daily_ev_visits = int(aadt * fleet_ev_share * p_charge)
        avg_kwh = self._avg_energy_per_session(location_type)
        daily_kwh = daily_ev_visits * avg_kwh

        result = {
            "location_type": location_type,
            "aadt_used": aadt,
            "fleet_ev_share_pct": round(fleet_ev_share * 100, 3),
            "charge_probability_pct": round(p_charge * 100, 1),
            "daily_ev_visits": daily_ev_visits,
            "daily_kwh": round(daily_kwh, 1),
            "charging_sessions_per_day": max(1, daily_ev_visits),
        }
        
        logger.debug(
            f"Location estimate: lat={lat}, lon={lon}, year={year} → "
            f"{daily_ev_visits} EV visits/day, {daily_kwh:.1f} kWh/day"
        )
        
        return result

    def estimate_from_db(self, location_id: str, year: int) -> dict:
        """Estimate demand at a predefined landmark from the database.

        Args:
            location_id: Landmark ID from LANDMARK_DB
            year: Forecast year (2018-2050)

        Returns:
            Dictionary with landmark name and demand estimates

        Raises:
            UnknownLocationError: If location_id not in LANDMARK_DB
            InvalidYearError: If year out of valid range
            TypeError: If parameters have wrong types
        """
        if not isinstance(location_id, str):
            raise TypeError(f"location_id must be a string, got {type(location_id).__name__}")
        if not isinstance(year, int):
            raise TypeError(f"year must be an integer, got {type(year).__name__}")
        
        if location_id not in LANDMARK_DB:
            raise UnknownLocationError(location_id, list(LANDMARK_DB.keys()))
        
        loc = LANDMARK_DB[location_id]
        return {
            "name": loc["name"],
            **self.estimate(loc["lat"], loc["lon"], year, loc["type"], loc["aadt"]),
        }

    def _classify_location(self, lat: float, lon: float) -> str:
        """Classify location type based on coordinates.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Location type string
        """
        if 18.770 <= lat <= 18.810 and 98.960 <= lon <= 99.010:
            return "city_center"
        return "highway"

    def _estimate_aadt(self, lat: float, lon: float, loc_type: str) -> int:
        """Estimate AADT for a location based on type and coordinates.

        Args:
            lat: Latitude
            lon: Longitude
            loc_type: Location type

        Returns:
            Estimated AADT value
        """
        # AADT in the source file belongs to a surveyed road segment, not the
        # entire rectangle around that segment. Applying it to every nearby
        # destination makes airport and mountain-side cells inherit arterial
        # traffic they cannot physically capture. Use it only for a cell that
        # the spatial layer has classified as a genuine through-traffic route.
        if loc_type == "highway":
            highway_aadt = self._find_nearest_highway(lat, lon, self.province)
            if highway_aadt:
                return max(self._fallback_aadt(loc_type), highway_aadt)

        return self._fallback_aadt(loc_type)

    @staticmethod
    def _fallback_aadt(loc_type: str) -> int:
        if loc_type == "city_center":
            return 10000
        if loc_type == "destination":
            return 5000
        if loc_type == "suburban":
            return 8000
        return 20000

    @staticmethod
    def _load_highway_aadt_for_province(province: str) -> dict[int, dict]:
        global CHIANG_MAI_HIGHWAY_AADT
        canonical_province = PROVINCE_AADT_ALIASES.get(province, province)
        if canonical_province == "เชียงใหม่":
            if CHIANG_MAI_HIGHWAY_AADT is None:
                CHIANG_MAI_HIGHWAY_AADT = get_cm_highway_aadt()
            return CHIANG_MAI_HIGHWAY_AADT

        if canonical_province in HIGHWAY_AADT_BY_PROVINCE:
            return HIGHWAY_AADT_BY_PROVINCE[canonical_province]

        df = load_doh_aadt(year_be=2566, province=canonical_province)
        if df.empty:
            HIGHWAY_AADT_BY_PROVINCE[canonical_province] = {}
            return {}

        total_col = df.columns[14]
        route_col = df.columns[0]
        name_col = df.columns[2]
        km_col = df.columns[3]
        result = {}
        for _, row in df.iterrows():
            route = int(row[route_col])
            aadt = int(row[total_col])
            if route not in result or aadt > result[route]["aadt"]:
                result[route] = {
                    "name": row[name_col],
                    "aadt": aadt,
                    "km": row[km_col],
                }
        HIGHWAY_AADT_BY_PROVINCE[canonical_province] = result
        return result

    @staticmethod
    def _find_nearest_highway(lat: float, lon: float, province: str = "เชียงใหม่") -> Optional[int]:
        """Find AADT for nearest highway segment.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            AADT value or None if no highway found
        """
        canonical_province = PROVINCE_AADT_ALIASES.get(province, province)
        for (lat_min, lat_max, lon_min, lon_max), local_aadt in LOCAL_ACCESS_AADT_BBOXES_BY_PROVINCE.get(canonical_province, []):
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return local_aadt
        highway_aadt = LocationDemandModel._load_highway_aadt_for_province(canonical_province)
        if not highway_aadt:
            return None
        route_bboxes = ROUTE_BBOXES_BY_PROVINCE.get(canonical_province, [])
        for route, (lat_min, lat_max, lon_min, lon_max) in route_bboxes:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                entry = highway_aadt.get(route)
                if entry:
                    return entry["aadt"]
        return None

    @staticmethod
    def _avg_energy_per_session(loc_type: str) -> float:
        """Get average energy per charging session by location type.

        Args:
            loc_type: Location type

        Returns:
            Average kWh per session
        """
        energy_map = {
            "highway": 30.0,
            "destination": 15.0,
            "city_center": 12.0,
            "suburban": 10.0,
        }
        return energy_map.get(loc_type, 15.0)


class StationDemandModel:
    """Fleet-based demand model for dedicated EV charging stations.

    Three demand components:
    1. Resident EV charging: CM_EV_pop × public_need × sessions/week × capture
    2. Ride-hailing fleet:     drivers × EV% × daily_sessions × capture
    3. Tourist EV rentals:     arrivals × rental% × EV% × avg_days × sessions/day × public_frac × capture

    This model is calibrated for the CM Cultural Center Super Hub location.
    For other locations, override params accordingly.

    Attributes:
        province: Province name

    Example:
        >>> model = StationDemandModel(province="เชียงใหม่")
        >>> result = model.estimate(year=2030, scenario="base", stalls=12)
        >>> print(result["daily_sessions"])
        130
    """

    VALID_SCENARIOS = {"low", "base", "best"}

    def __init__(self, province: str = "เชียงใหม่"):
        """Initialize station demand model for a province.

        Args:
            province: Province name (default: เชียงใหม่)

        Raises:
            TypeError: If province is not a string
        """
        if not isinstance(province, str):
            raise TypeError(f"Province must be a string, got {type(province).__name__}")
        
        self.province = province
        logger.debug(f"Initialized StationDemandModel for {province}")

    def estimate_cm_ev_population(self, year: int) -> int:
        """Estimate EV population for the province.

        Args:
            year: Target year (2018-2050)

        Returns:
            Estimated EV population

        Raises:
            InvalidYearError: If year out of valid range
            TypeError: If year is not an integer
        """
        return estimate_fleet_ev_population(year, self.province)

    def estimate(
        self,
        year: int,
        scenario: str = "base",
        stalls: int = 12,
        station_capture_rate: Optional[float] = None,
        sessions_per_stall_per_day_peak: Optional[float] = None,
        calibration_factor: float = 1.0,
    ) -> dict:
        """Estimate daily sessions and energy for a charging station.

        Args:
            year: Forecast year (2018-2050)
            scenario: One of "low", "base", "best"
            stalls: Number of charging stalls at the station (1-100)
            station_capture_rate: Override capture rate for residents (0-1)
            sessions_per_stall_per_day_peak: Override max sessions per stall per day
            calibration_factor: Multiplier to fit model to observed data (default 1.0)

        Returns:
            Dictionary with keys:
                - year: int
                - scenario: str
                - stalls: int
                - cm_ev_population: int
                - daily_sessions: int
                - daily_sessions_peak: int
                - daily_kwh: float
                - daily_kwh_peak: float
                - max_sessions_per_day: int
                - utilization_pct: float
                - components: dict with resident, ride_hail, tourist, transit

        Raises:
            InvalidYearError: If year out of valid range
            TypeError: If parameters have wrong types
            ValueError: If scenario is invalid or parameters out of range
        """
        if not isinstance(year, int):
            raise TypeError(f"year must be an integer, got {type(year).__name__}")
        if not isinstance(scenario, str):
            raise TypeError(f"scenario must be a string, got {type(scenario).__name__}")
        if not isinstance(stalls, int):
            raise TypeError(f"stalls must be an integer, got {type(stalls).__name__}")
        if not isinstance(calibration_factor, (int, float)):
            raise TypeError(f"calibration_factor must be a number, got {type(calibration_factor).__name__}")
        
        from .adoption import _validate_year
        _validate_year(year)
        
        if scenario not in self.VALID_SCENARIOS:
            raise ValueError(
                f"Invalid scenario: '{scenario}'. "
                f"Valid scenarios: {', '.join(sorted(self.VALID_SCENARIOS))}"
            )
        
        if stalls < 1 or stalls > 100:
            raise ValueError(f"stalls must be between 1 and 100, got {stalls}")
        
        if calibration_factor <= 0:
            raise ValueError(f"calibration_factor must be positive, got {calibration_factor}")
        
        if station_capture_rate is not None:
            if not isinstance(station_capture_rate, (int, float)):
                raise TypeError(f"station_capture_rate must be a number, got {type(station_capture_rate).__name__}")
            if station_capture_rate < 0 or station_capture_rate > 1:
                raise ValueError(f"station_capture_rate must be in [0, 1], got {station_capture_rate}")
        
        if sessions_per_stall_per_day_peak is not None:
            if not isinstance(sessions_per_stall_per_day_peak, (int, float)):
                raise TypeError(
                    f"sessions_per_stall_per_day_peak must be a number, "
                    f"got {type(sessions_per_stall_per_day_peak).__name__}"
                )
            if sessions_per_stall_per_day_peak <= 0:
                raise ValueError(
                    f"sessions_per_stall_per_day_peak must be positive, "
                    f"got {sessions_per_stall_per_day_peak}"
                )
        
        params = self._scenario_params(scenario)
        if station_capture_rate is not None:
            params["capture_resident"] = station_capture_rate
        if sessions_per_stall_per_day_peak is not None:
            params["sessions_per_stall"] = sessions_per_stall_per_day_peak

        ev_pop = self.estimate_cm_ev_population(year)

        # ── Component 1: Resident EV charging ──
        resident_daily = (
            ev_pop
            * params["public_charge_frac"]
            * params["sessions_per_week"]
            / 7
            * params["capture_resident"]
        )

        # ── Component 2: Ride-hailing fleet ──
        ride_hail_daily = (
            params["ride_hail_drivers"]
            * params["ride_hail_ev_pct"]
            * params["ride_hail_sessions"]
            * params["capture_ride_hail"]
        )

        # ── Component 3: Tourist EV rentals ──
        # Active rentals = arrivals × rental% × avg_days
        active_rentals = (
            params["tourist_arrivals_daily"]
            * params["rental_pct"]
            * params["avg_rental_days"]
        )
        tourist_daily = (
            active_rentals
            * params["rental_ev_pct"]
            * params["rental_sessions_per_day"]
            * params["rental_public_frac"]
            * params["capture_tourist"]
        )

        # ── Component 4: Transit EVs ──
        transit_daily = (
            params["transit_ev_daily"]
            * params["capture_transit"]
        )

        # Total normal and peak
        # calibration_factor is a single free multiplier fitted to observed
        # ground-truth station-days (see th_evi/validation.py). It absorbs
        # structural bias so that scenario params keep their physical meaning
        # instead of being silently over/under-tuned to compensate.
        total_daily = (resident_daily + ride_hail_daily + tourist_daily + transit_daily) * calibration_factor
        total_daily_peak = total_daily * params["peak_uplift"]

        # Capacity constraint
        max_sessions = stalls * params["sessions_per_stall"]
        total_daily = min(total_daily, max_sessions)
        total_daily_peak = min(total_daily_peak, max_sessions)

        avg_kwh = params["avg_kwh_per_session"]
        daily_kwh = total_daily * avg_kwh
        daily_kwh_peak = total_daily_peak * avg_kwh
        utilization_pct = round(total_daily / max_sessions * 100, 1)

        result = {
            "year": year,
            "scenario": scenario,
            "stalls": stalls,
            "cm_ev_population": ev_pop,
            "daily_sessions": int(total_daily),
            "daily_sessions_peak": int(total_daily_peak),
            "daily_kwh": round(daily_kwh, 0),
            "daily_kwh_peak": round(daily_kwh_peak, 0),
            "max_sessions_per_day": int(max_sessions),
            "utilization_pct": utilization_pct,
            "components": {
                "resident": round(resident_daily),
                "ride_hail": round(ride_hail_daily),
                "tourist": round(tourist_daily),
                "transit": round(transit_daily),
            },
        }
        
        logger.debug(
            f"Station estimate: year={year}, scenario={scenario}, stalls={stalls} → "
            f"{int(total_daily)} sessions/day, {daily_kwh:.0f} kWh/day"
        )
        
        return result

    @staticmethod
    def _scenario_params(scenario: str) -> dict:
        """Get scenario-specific parameters.

        Args:
            scenario: One of "low", "base", "best"

        Returns:
            Dictionary of scenario parameters

        Raises:
            ValueError: If scenario is invalid
        """
        all_params = {
            "low": {
                "public_charge_frac": 0.30,
                "sessions_per_week": 1.0,
                "capture_resident": 0.08,
                "ride_hail_drivers": 3000,
                "ride_hail_ev_pct": 0.03,
                "ride_hail_sessions": 0.8,
                "capture_ride_hail": 0.15,
                "tourist_arrivals_daily": 33000,
                "rental_pct": 0.08,
                "avg_rental_days": 4,
                "rental_ev_pct": 0.03,
                "rental_sessions_per_day": 0.5,
                "rental_public_frac": 0.25,
                "capture_tourist": 0.15,
                "transit_ev_daily": 10,
                "capture_transit": 0.15,
                "peak_uplift": 1.4,
                "avg_kwh_per_session": 30.0,
                "sessions_per_stall": 20,
            },
            "base": {
                "public_charge_frac": 0.35,
                "sessions_per_week": 1.5,
                "capture_resident": 0.20,
                "ride_hail_drivers": 4000,
                "ride_hail_ev_pct": 0.05,
                "ride_hail_sessions": 1.0,
                "capture_ride_hail": 0.30,
                "tourist_arrivals_daily": 33000,
                "rental_pct": 0.10,
                "avg_rental_days": 4,
                "rental_ev_pct": 0.05,
                "rental_sessions_per_day": 0.5,
                "rental_public_frac": 0.30,
                "capture_tourist": 0.25,
                "transit_ev_daily": 20,
                "capture_transit": 0.25,
                "peak_uplift": 1.6,
                "avg_kwh_per_session": 32.0,
                "sessions_per_stall": 22,
            },
            "best": {
                "public_charge_frac": 0.40,
                "sessions_per_week": 2.0,
                "capture_resident": 0.30,
                "ride_hail_drivers": 5000,
                "ride_hail_ev_pct": 0.08,
                "ride_hail_sessions": 1.2,
                "capture_ride_hail": 0.40,
                "tourist_arrivals_daily": 35000,
                "rental_pct": 0.12,
                "avg_rental_days": 4,
                "rental_ev_pct": 0.08,
                "rental_sessions_per_day": 0.6,
                "rental_public_frac": 0.35,
                "capture_tourist": 0.35,
                "transit_ev_daily": 30,
                "capture_transit": 0.35,
                "peak_uplift": 1.8,
                "avg_kwh_per_session": 35.0,
                "sessions_per_stall": 24,
            },
        }
        
        if scenario not in all_params:
            raise ValueError(f"Unknown scenario: {scenario}")
        
        return all_params[scenario].copy()
