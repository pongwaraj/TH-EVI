"""
Location Demand Model — Given a lat/lon in Thailand, estimate daily EV visits.
"""

import numpy as np
from . import constants as C
from .adoption import EVAdoptionModel, estimate_fleet_ev_share, estimate_fleet_ev_population
from .data import get_cm_highway_aadt


CHIANG_MAI_HIGHWAY_AADT = None

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
}


class LocationDemandModel:
    """Estimate daily EV charging demand for general locations using a traffic-based model.

    Formula: EVs/day = Traffic_Volume × Fleet_EV_Share(year) × P(charge)
    """

    CHARGE_PROB = {
        "highway": 0.06,
        "city_center": 0.12,
        "destination": 0.20,
        "suburban": 0.08,
    }

    DIRECTIONAL_FACTOR = 0.50

    def __init__(self, province: str = "เชียงใหม่"):
        self.adoption = EVAdoptionModel(province=province)
        self.province = province

    def estimate(
        self, lat: float, lon: float, year: int, location_type: str = None, aadt: int = None
    ) -> dict:
        if location_type is None:
            location_type = self._classify_location(lat, lon)

        if aadt is None:
            aadt = self._estimate_aadt(lat, lon, location_type)

        fleet_ev_share = estimate_fleet_ev_share(year, self.province)
        p_charge = self.CHARGE_PROB.get(location_type, 0.05)

        daily_ev_visits = int(aadt * fleet_ev_share * p_charge)
        avg_kwh = self._avg_energy_per_session(location_type)
        daily_kwh = daily_ev_visits * avg_kwh

        return {
            "location_type": location_type,
            "aadt_used": aadt,
            "fleet_ev_share_pct": round(fleet_ev_share * 100, 3),
            "charge_probability_pct": round(p_charge * 100, 1),
            "daily_ev_visits": daily_ev_visits,
            "daily_kwh": round(daily_kwh, 1),
            "charging_sessions_per_day": max(1, daily_ev_visits),
        }

    def estimate_from_db(self, location_id: str, year: int) -> dict:
        if location_id not in LANDMARK_DB:
            raise KeyError(f"Unknown location: {location_id}")
        loc = LANDMARK_DB[location_id]
        return {
            "name": loc["name"],
            **self.estimate(loc["lat"], loc["lon"], year, loc["type"], loc["aadt"]),
        }

    def _classify_location(self, lat: float, lon: float) -> str:
        if 18.770 <= lat <= 18.810 and 98.960 <= lon <= 99.010:
            return "city_center"
        return "highway"

    def _estimate_aadt(self, lat: float, lon: float, loc_type: str) -> int:
        global CHIANG_MAI_HIGHWAY_AADT
        if CHIANG_MAI_HIGHWAY_AADT is None:
            CHIANG_MAI_HIGHWAY_AADT = get_cm_highway_aadt()

        if loc_type == "highway" and CHIANG_MAI_HIGHWAY_AADT:
            nearest = self._find_nearest_highway(lat, lon)
            if nearest:
                return nearest

        if loc_type == "city_center":
            return 10000
        elif loc_type == "destination":
            return 5000
        elif loc_type == "suburban":
            return 8000
        else:
            return 20000

    @staticmethod
    def _find_nearest_highway(lat: float, lon: float) -> int | None:
        if CHIANG_MAI_HIGHWAY_AADT is None:
            return None
        route_bboxes = [
            (1141, (18.76, 18.80, 98.94, 98.98)),
            (121,  (18.75, 18.90, 98.90, 99.10)),
            (1001, (18.80, 19.00, 98.85, 99.00)),
            (107,  (18.80, 19.50, 98.80, 99.10)),
            (108,  (18.20, 18.80, 98.60, 99.00)),
            (118,  (18.70, 19.30, 98.95, 99.50)),
            (11,   (18.60, 18.85, 98.85, 99.20)),
        ]
        for route, (lat_min, lat_max, lon_min, lon_max) in route_bboxes:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                entry = CHIANG_MAI_HIGHWAY_AADT.get(route)
                if entry:
                    return entry["aadt"]
        return None

    @staticmethod
    def _avg_energy_per_session(loc_type: str) -> float:
        if loc_type == "highway":
            return 30.0
        elif loc_type == "destination":
            return 15.0
        elif loc_type == "city_center":
            return 12.0
        elif loc_type == "suburban":
            return 10.0
        return 15.0


class StationDemandModel:
    """Fleet-based demand model for dedicated EV charging stations.

    Three demand components:
    1. Resident EV charging: CM_EV_pop × public_need × sessions/week × capture
    2. Ride-hailing fleet:     drivers × EV% × daily_sessions × capture
    3. Tourist EV rentals:     arrivals × rental% × EV% × avg_days × sessions/day × public_frac × capture

    This model is calibrated for the CM Cultural Center Super Hub location.
    For other locations, override params accordingly.
    """

    def __init__(self, province: str = "\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e43\u0e2b\u0e21\u0e48"):
        self.province = province

    def estimate_cm_ev_population(self, year: int) -> int:
        return estimate_fleet_ev_population(year, self.province)

    def estimate(
        self,
        year: int,
        scenario: str = "base",
        stalls: int = 12,
        station_capture_rate: float = None,
        sessions_per_stall_per_day_peak: float = None,
        calibration_factor: float = 1.0,
    ) -> dict:
        """Estimate daily sessions and energy for a charging station.

        Parameters
        ----------
        year : int
            Forecast year (2026-2036)
        scenario : str
            "low", "base", or "best"
        stalls : int
            Number of charging stalls at the station
        station_capture_rate : float or None
            Override capture rate for residents (0-1)
        sessions_per_stall_per_day_peak : float or None
            Override max sessions per stall per day
        """
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

        return {
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

    @staticmethod
    def _scenario_params(scenario: str) -> dict:
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
        return all_params[scenario].copy()
