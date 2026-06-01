"""
EV Adoption Model — S-curve forecast for Thailand
Calibrated to FTI/Autolife annual data: 2025 BEV share = 19.4% of new passenger cars.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from . import constants as C
from .exceptions import InvalidYearError, ProvinceNotFoundError

logger = logging.getLogger(__name__)

MIN_YEAR = 2018
MAX_YEAR = 2050


def _validate_year(year: int, min_year: int = MIN_YEAR, max_year: int = MAX_YEAR) -> None:
    """Validate year parameter is within acceptable range."""
    if not isinstance(year, int):
        raise TypeError(f"Year must be an integer, got {type(year).__name__}")
    if year < min_year or year > max_year:
        raise InvalidYearError(year, min_year, max_year)


def estimate_fleet_ev_population(year: int, province: str = "default") -> int:
    """Accumulate EV population from annual new-car BEV sales with scrappage.

    Model:
        annual_new_cars = province_new_car_rate (default 6,200 for CM)
        new_car_BEV_share(year) = S-curve × province_factor
        EV_pop += new_cars × BEV_share
        EV_pop -= scrapped_EVs (15-year linear retirement)

    Args:
        year: Target year (2018-2050)
        province: Province name (default uses national parameters)

    Returns:
        Estimated EV population in the province fleet

    Raises:
        InvalidYearError: If year is out of valid range [2018, 2050]
        TypeError: If year is not an integer
    """
    _validate_year(year)
    
    if not isinstance(province, str):
        raise TypeError(f"Province must be a string, got {type(province).__name__}")
    
    model = EVAdoptionModel(province=province, use_fleet_model=False)
    annual_new = C.PROVINCE_NEW_CAR_RATE.get(province, 6_200)
    
    if annual_new < 0:
        logger.warning(f"Negative new car rate for {province}: {annual_new}")
        annual_new = 0
    
    ev_pop = 0
    for y in range(MIN_YEAR, year + 1):
        share = model.get_ev_share(y)
        ev_pop += int(annual_new * share)
        scrap_year = y - 14
        if scrap_year >= MIN_YEAR:
            scrap_share = model.get_ev_share(scrap_year)
            ev_pop -= int(annual_new * scrap_share)
        ev_pop = max(ev_pop, 0)
    
    logger.debug(f"Estimated EV population for {province} in {year}: {ev_pop:,}")
    return ev_pop


def estimate_fleet_ev_share(year: int, province: str = "default") -> float:
    """Fraction of total passenger car fleet that is BEV.

    Args:
        year: Target year (2018-2050)
        province: Province name (default uses national parameters)

    Returns:
        Fraction of fleet that is BEV (0.0 to 1.0)

    Raises:
        InvalidYearError: If year is out of valid range [2018, 2050]
        TypeError: If year is not an integer or province is not a string
    """
    _validate_year(year)
    
    if not isinstance(province, str):
        raise TypeError(f"Province must be a string, got {type(province).__name__}")
    
    fleet = C.PROVINCE_FLEET_SIZE.get(province, 350_000)
    
    if fleet <= 0:
        logger.warning(f"Invalid fleet size for {province}: {fleet}, using default")
        fleet = 350_000
    
    ev_pop = estimate_fleet_ev_population(year, province)
    share = min(ev_pop / fleet, 1.0)
    
    logger.debug(f"Estimated EV share for {province} in {year}: {share:.4f}")
    return share


class EVAdoptionModel:
    """Forecast EV adoption for a Thai province using S-curve.

    get_ev_share(year) → new car BEV share (adjusted by province factor)
    get_ev_population(year) → accumulated EV count in fleet

    Attributes:
        province: Province name
        max_share: Maximum BEV share at saturation (carrying capacity)
        growth_rate: S-curve growth rate parameter
        midpoint: Year when adoption reaches 50% of max_share
        province_factor: Multiplier for province-level adjustment
        use_fleet_model: Whether to use fleet accumulation model

    Example:
        >>> model = EVAdoptionModel(province="เชียงใหม่")
        >>> model.get_ev_share(2030)
        0.3542
        >>> model.get_ev_population(2030)
        14587
    """

    def __init__(self, province: str = "default", use_fleet_model: bool = True):
        """Initialize EV adoption model for a province.

        Args:
            province: Province name (default uses national parameters)
            use_fleet_model: If True, use fleet accumulation model;
                           if False, use simple share × total_vehicles

        Raises:
            TypeError: If province is not a string or use_fleet_model is not bool
        """
        if not isinstance(province, str):
            raise TypeError(f"Province must be a string, got {type(province).__name__}")
        if not isinstance(use_fleet_model, bool):
            raise TypeError(f"use_fleet_model must be a boolean, got {type(use_fleet_model).__name__}")
        
        self.province = province
        self.max_share = C.S_CURVE["carrying_capacity"]
        self.growth_rate = C.S_CURVE["growth_rate"]
        self.midpoint = C.S_CURVE["midpoint_year"]
        self.province_factor = C.PROVINCE_EV_FACTOR.get(province, C.PROVINCE_EV_FACTOR["default"])
        self.use_fleet_model = use_fleet_model
        
        logger.debug(
            f"Initialized EVAdoptionModel for {province}: "
            f"max_share={self.max_share}, growth_rate={self.growth_rate}, "
            f"midpoint={self.midpoint}, province_factor={self.province_factor}"
        )

    def get_ev_share(self, year: int) -> float:
        """Return BEV share of NEW passenger car sales for that year.

        Uses logistic S-curve: share = max_share / (1 + exp(-growth_rate * (year - midpoint)))
        Adjusted by province_factor and capped at max_share.

        Args:
            year: Target year (2018-2050)

        Returns:
            BEV share of new car sales (0.0 to max_share)

        Raises:
            InvalidYearError: If year is out of valid range [2018, 2050]
            TypeError: If year is not an integer
        """
        _validate_year(year)
        
        raw = self.max_share / (1 + np.exp(-self.growth_rate * (year - self.midpoint)))
        adjusted = min(raw * self.province_factor, self.max_share)
        
        if adjusted < 0:
            logger.warning(f"Negative EV share calculated for {year}: {adjusted}, clamping to 0")
            adjusted = 0.0
        
        return round(adjusted, 4)

    def get_ev_population(self, year: int, total_vehicles: Optional[int] = None) -> int:
        """Return estimated number of EVs in the province fleet.

        Args:
            year: Target year (2018-2050)
            total_vehicles: Override total vehicle count (only used if use_fleet_model=False)

        Returns:
            Estimated number of EVs in the province

        Raises:
            InvalidYearError: If year is out of valid range [2018, 2050]
            TypeError: If year is not an integer or total_vehicles is not int/None
        """
        _validate_year(year)
        
        if total_vehicles is not None and not isinstance(total_vehicles, int):
            raise TypeError(f"total_vehicles must be an integer or None, got {type(total_vehicles).__name__}")
        
        if not self.use_fleet_model:
            if total_vehicles is None:
                total_vehicles = self._estimate_total_vehicles(year)
            
            if total_vehicles <= 0:
                logger.warning(f"Invalid total_vehicles: {total_vehicles}, using 1")
                total_vehicles = 1
            
            return int(total_vehicles * self.get_ev_share(year))
        
        return estimate_fleet_ev_population(year, self.province)

    def _estimate_total_vehicles(self, year: int) -> int:
        """Estimate total vehicle fleet size for a given year.

        Uses exponential growth from 2023 baseline with 1.5% annual growth.

        Args:
            year: Target year

        Returns:
            Estimated total vehicle count
        """
        base = C.PROVINCE_FLEET_SIZE.get(self.province, C.CHIANG_MAI_VEHICLES_2023)
        
        if base <= 0:
            logger.warning(f"Invalid base fleet size for {self.province}: {base}, using default")
            base = C.CHIANG_MAI_VEHICLES_2023
        
        annual_growth = 1.015
        return int(base * (annual_growth ** (year - 2023)))

    def summary(self, years: Optional[list[int]] = None) -> dict[int, dict[str, float | int]]:
        """Generate summary of EV adoption forecasts for multiple years.

        Args:
            years: List of years to forecast (default: [2025, 2027, 2030, 2032, 2035, 2040])

        Returns:
            Dictionary mapping year to {ev_share, ev_population}

        Raises:
            InvalidYearError: If any year is out of valid range
            TypeError: If years is not a list or contains non-integers
        """
        if years is None:
            years = [2025, 2027, 2030, 2032, 2035, 2040]
        
        if not isinstance(years, list):
            raise TypeError(f"years must be a list, got {type(years).__name__}")
        
        for year in years:
            if not isinstance(year, int):
                raise TypeError(f"All years must be integers, got {type(year).__name__}")
        
        return {
            year: {
                "ev_share": self.get_ev_share(year),
                "ev_population": self.get_ev_population(year),
            }
            for year in years
        }
