"""
EV Adoption Model — S-curve forecast for Thailand
Calibrated to FTI/Autolife data: 2025 BEV share = 23.9% of new passenger cars.
"""

import numpy as np
from . import constants as C


def estimate_fleet_ev_population(year: int, province: str = "default") -> int:
    """Accumulate EV population from annual new-car BEV sales with scrappage.

    Model:
        annual_new_cars = province_new_car_rate (default 6,200 for CM)
        new_car_BEV_share(year) = S-curve × province_factor
        EV_pop += new_cars × BEV_share
        EV_pop -= scrapped_EVs (15-year linear retirement)
    """
    model = EVAdoptionModel(province=province, use_fleet_model=False)
    annual_new = C.PROVINCE_NEW_CAR_RATE.get(province, 6_200)
    ev_pop = 0
    for y in range(2018, year + 1):
        share = model.get_ev_share(y)
        ev_pop += int(annual_new * share)
        if y <= year - 15:
            scrap_share = model.get_ev_share(y - 14)
            ev_pop -= int(annual_new * scrap_share)
        ev_pop = max(ev_pop, 0)
    return ev_pop


def estimate_fleet_ev_share(year: int, province: str = "default") -> float:
    """Fraction of total passenger car fleet that is BEV."""
    fleet = C.PROVINCE_FLEET_SIZE.get(province, 350_000)
    ev_pop = estimate_fleet_ev_population(year, province)
    return min(ev_pop / fleet, 1.0)


class EVAdoptionModel:
    """Forecast EV adoption for a Thai province using S-curve.

    get_ev_share(year) → new car BEV share (adjusted by province factor)
    get_ev_population(year) → accumulated EV count in fleet
    """

    def __init__(self, province: str = "default", use_fleet_model: bool = True):
        self.province = province
        self.max_share = C.S_CURVE["carrying_capacity"]
        self.growth_rate = C.S_CURVE["growth_rate"]
        self.midpoint = C.S_CURVE["midpoint_year"]
        self.province_factor = C.PROVINCE_EV_FACTOR.get(province, C.PROVINCE_EV_FACTOR["default"])
        self.use_fleet_model = use_fleet_model

    def get_ev_share(self, year: int) -> float:
        """Return BEV share of NEW passenger car sales for that year."""
        raw = self.max_share / (1 + np.exp(-self.growth_rate * (year - self.midpoint)))
        adjusted = min(raw * self.province_factor, self.max_share)
        return round(adjusted, 4)

    def get_ev_population(self, year: int, total_vehicles: int = None) -> int:
        """Return estimated number of EVs in the province fleet."""
        if not self.use_fleet_model:
            if total_vehicles is None:
                total_vehicles = self._estimate_total_vehicles(year)
            return int(total_vehicles * self.get_ev_share(year))
        return estimate_fleet_ev_population(year, self.province)

    def _estimate_total_vehicles(self, year: int) -> int:
        base = C.PROVINCE_FLEET_SIZE.get(self.province, C.CHIANG_MAI_VEHICLES_2023)
        annual_growth = 1.015
        return int(base * (annual_growth ** (year - 2023)))

    def summary(self, years: list = None) -> dict:
        if years is None:
            years = [2025, 2027, 2030, 2032, 2035, 2040]
        return {
            year: {
                "ev_share": self.get_ev_share(year),
                "ev_population": self.get_ev_population(year),
            }
            for year in years
        }
