"""
EV Adoption Model — S-curve forecast for Thailand
Calibrated to 30@30 policy targets with provincial factors.
"""

import numpy as np
from . import constants as C


class EVAdoptionModel:
    """Forecast EV population for any Thai province using S-curve.

    Usage:
        model = EVAdoptionModel(province="เชียงใหม่")
        ev_share_2035 = model.get_ev_share(2035)
        ev_count_2035 = model.get_ev_population(2035)
    """

    def __init__(self, province: str = "default"):
        self.province = province
        self.max_share = C.S_CURVE["carrying_capacity"]
        self.growth_rate = C.S_CURVE["growth_rate"]
        self.midpoint = C.S_CURVE["midpoint_year"]
        self.province_factor = C.PROVINCE_EV_FACTOR.get(province, C.PROVINCE_EV_FACTOR["default"])

    def get_ev_share(self, year: int) -> float:
        """Return EV share of total vehicles in that province for given year."""
        raw = self.max_share / (1 + np.exp(-self.growth_rate * (year - self.midpoint)))
        adjusted = min(raw * self.province_factor, self.max_share)
        return round(adjusted, 4)

    def get_ev_population(self, year: int, total_vehicles: int = None) -> int:
        """Return estimated number of EVs in the province."""
        if total_vehicles is None:
            total_vehicles = self._estimate_total_vehicles(year)
        return int(total_vehicles * self.get_ev_share(year))

    def _estimate_total_vehicles(self, year: int) -> int:
        """Simple linear growth projection of total vehicles."""
        base_year = 2023
        base = C.CHIANG_MAI_VEHICLES_2023
        if self.province != "เชียงใหม่":
            base = int(C.THAILAND_TOTAL_VEHICLES_2023 * 0.04)
        annual_growth = 1.015  # 1.5% vehicle growth per year
        return int(base * (annual_growth ** (year - base_year)))

    def summary(self, years: list = None) -> dict:
        """Return EV share and population for multiple years."""
        if years is None:
            years = [2025, 2027, 2030, 2032, 2035, 2040]
        return {
            year: {
                "ev_share": self.get_ev_share(year),
                "ev_population": self.get_ev_population(year),
            }
            for year in years
        }
