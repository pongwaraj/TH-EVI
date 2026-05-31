"""
Location Demand Model — Given a lat/lon in Thailand, estimate daily EV visits.
"""

import math
from . import constants as C
from .adoption import EVAdoptionModel


# Approximate location type definitions for key Thai locations
# In future: load from GIS / AADT database
LANDMARK_DB = {
    # Chiang Mai landmarks (lat, lon, type, aadt_estimate)
    "cm_superhighway": {
        "name": "Superhighway เชียงใหม่-ลำปาง",
        "lat": 18.795, "lon": 99.010,
        "type": "highway", "aadt": 45000,
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
    "cm_maerim": {
        "name": "แม่ริม (เส้นทางท่องเที่ยว)",
        "lat": 18.907, "lon": 98.942,
        "type": "highway", "aadt": 15000,
    },
    "cm_hangdong": {
        "name": "หางดง (เส้นทางลงใต้)",
        "lat": 18.685, "lon": 98.919,
        "type": "highway", "aadt": 20000,
    },
}


class LocationDemandModel:
    """Estimate daily EV charging demand at a given location.

    Core formula:
        EVs/day = Traffic_Volume × EV_Share(year) × P(charge)

    For highway:  AADT × directional_factor × EV_share × p_charge
    For urban:    population_density × trip_rate × EV_share × p_charge
    """

    # Charging probability by location type
    CHARGE_PROB = {
        "highway": 0.06,       # 6% of EVs passing stop to charge
        "city_center": 0.12,   # 12% of EVs in city center charge
        "destination": 0.20,   # 20% at malls/hotels/airports
        "suburban": 0.08,
    }

    # Directional split for highways
    DIRECTIONAL_FACTOR = 0.50  # 50% of AADT goes each direction

    def __init__(self, province: str = "เชียงใหม่"):
        self.adoption = EVAdoptionModel(province=province)
        self.province = province

    def estimate(
        self, lat: float, lon: float, year: int, location_type: str = None, aadt: int = None
    ) -> dict:
        """Return daily EV visits and energy demand at this location."""

        # Determine location type
        if location_type is None:
            location_type = self._classify_location(lat, lon)

        # Determine traffic volume
        if aadt is None:
            aadt = self._estimate_aadt(lat, lon, location_type)

        # EV share in that year
        ev_share = self.adoption.get_ev_share(year)

        # Charging probability
        p_charge = self.CHARGE_PROB.get(location_type, 0.05)

        # Core calculation
        daily_ev_visits = int(aadt * ev_share * p_charge)

        # Energy estimate
        avg_kwh_per_session = self._avg_energy_per_session(location_type)
        daily_kwh = daily_ev_visits * avg_kwh_per_session

        return {
            "location_type": location_type,
            "aadt_used": aadt,
            "ev_share_pct": round(ev_share * 100, 1),
            "charge_probability_pct": round(p_charge * 100, 1),
            "daily_ev_visits": daily_ev_visits,
            "daily_kwh": round(daily_kwh, 1),
            "charging_sessions_per_day": max(1, daily_ev_visits),
        }

    def estimate_from_db(self, location_id: str, year: int) -> dict:
        """Use a predefined landmark from database."""
        if location_id not in LANDMARK_DB:
            raise KeyError(f"Unknown location: {location_id}")
        loc = LANDMARK_DB[location_id]
        return {
            "name": loc["name"],
            **self.estimate(loc["lat"], loc["lon"], year, loc["type"], loc["aadt"]),
        }

    def _classify_location(self, lat: float, lon: float) -> str:
        """Simple heuristic classification based on lat/lon.
        In future: use GIS overlay with road network & land use.
        """
        # Chiang Mai city center bounding box (approx)
        if 18.770 <= lat <= 18.810 and 98.960 <= lon <= 99.010:
            return "city_center"
        return "highway"

    def _estimate_aadt(self, lat: float, lon: float, loc_type: str) -> int:
        """Fallback AADT estimation when no database entry exists.
        Replace with real AADT lookups in production.
        """
        if loc_type == "city_center":
            return 10000
        elif loc_type == "destination":
            return 5000
        elif loc_type == "suburban":
            return 8000
        else:
            return 20000

    @staticmethod
    def _avg_energy_per_session(loc_type: str) -> float:
        """Average kWh delivered per charging session by location type."""
        if loc_type == "highway":
            return 30.0   # DCFC: quick top-up
        elif loc_type == "destination":
            return 15.0   # L2: while shopping/eating
        elif loc_type == "city_center":
            return 12.0
        elif loc_type == "suburban":
            return 10.0
        return 15.0
