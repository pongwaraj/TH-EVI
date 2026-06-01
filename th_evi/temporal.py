"""
Temporal & Queueing Layer  (TH-EVI)
===================================

Adds the dimension the model was missing vs NREL EVI-Pro: it turns a *daily*
session count into an *hour-by-hour* arrival profile, then sizes charging plugs
with an Erlang-C (M/M/c) queue so the station meets an explicit service level
(e.g. "P(a driver has to wait) < 10% in the peak hour").

Pipeline
--------
    daily_sessions ---> hourly arrivals (lambda_h)  [HourlyLoadModel]
                   ---> service time from kWh & charger power
                   ---> Erlang-C per hour: rho, P(wait), Wq  [QueueModel]
                   ---> min plugs to meet service level       [size_plugs]

All queueing math is closed-form (no scipy needed).

Run:  python -m th_evi.temporal
"""

from __future__ import annotations

import logging
from math import factorial
from typing import Optional

from .exceptions import InvalidQueueParametersError, InvalidStationTypeError

logger = logging.getLogger(__name__)

VALID_STATION_TYPES = {"highway", "destination", "urban_hub", "city_center"}


# ---------------------------------------------------------------------------
# 1. Hourly arrival profiles  (24 normalized weights, sum = 1.0)
# ---------------------------------------------------------------------------
# Shapes are archetypes; tune against real session timestamps when available.

_RAW_PROFILES = {
    # Highway / corridor: commute bimodal + a travel midday bump.
    "highway": [
        1, 1, 1, 1, 2, 4, 7, 9, 8, 6, 5, 5,
        6, 6, 6, 6, 7, 9, 8, 6, 4, 3, 2, 1,
    ],
    # Destination (mall / attraction): builds through afternoon, evening peak.
    "destination": [
        0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7,
        8, 8, 8, 8, 9, 10, 10, 9, 7, 4, 2, 1,
    ],
    # Urban hub / super-hub: broad daytime plateau (residents + ride-hail + tourist).
    "urban_hub": [
        2, 1, 1, 1, 2, 3, 5, 7, 8, 8, 8, 8,
        8, 8, 8, 8, 8, 8, 8, 7, 6, 5, 4, 3,
    ],
    # City center: midday + evening social.
    "city_center": [
        1, 1, 1, 1, 1, 2, 3, 5, 6, 7, 7, 8,
        8, 7, 7, 7, 8, 9, 9, 8, 6, 4, 3, 2,
    ],
}


def _normalize(weights):
    total = float(sum(weights))
    return [w / total for w in weights]


HOURLY_PROFILES = {k: _normalize(v) for k, v in _RAW_PROFILES.items()}


class HourlyLoadModel:
    """Distribute a daily session count across 24 hours of arrivals.

    Attributes:
        station_type: Type of station (highway, destination, urban_hub, city_center)
        profile: Normalized hourly weights (24 values, sum to 1.0)

    Example:
        >>> model = HourlyLoadModel(station_type="urban_hub")
        >>> arrivals = model.hourly_arrivals(daily_sessions=100)
        >>> peak_hour, peak_arrivals = model.peak_hour(daily_sessions=100)
    """

    def __init__(self, station_type: str = "urban_hub"):
        """Initialize hourly load model.

        Args:
            station_type: One of "highway", "destination", "urban_hub", "city_center"

        Raises:
            InvalidStationTypeError: If station_type is invalid
            TypeError: If station_type is not a string
        """
        if not isinstance(station_type, str):
            raise TypeError(f"station_type must be a string, got {type(station_type).__name__}")
        
        if station_type not in VALID_STATION_TYPES:
            raise InvalidStationTypeError(station_type, list(VALID_STATION_TYPES))
        
        self.station_type = station_type
        self.profile = HOURLY_PROFILES[station_type]
        logger.debug(f"Initialized HourlyLoadModel for {station_type}")

    def hourly_arrivals(self, daily_sessions: float) -> list[float]:
        """Return list of 24 arrival counts (lambda per hour).

        Args:
            daily_sessions: Total daily sessions

        Returns:
            List of 24 hourly arrival counts

        Raises:
            TypeError: If daily_sessions is not a number
            ValueError: If daily_sessions is negative
        """
        if not isinstance(daily_sessions, (int, float)):
            raise TypeError(f"daily_sessions must be a number, got {type(daily_sessions).__name__}")
        if daily_sessions < 0:
            raise ValueError(f"daily_sessions must be non-negative, got {daily_sessions}")
        
        return [daily_sessions * w for w in self.profile]

    def peak_hour(self, daily_sessions: float) -> tuple[int, float]:
        """Return (hour_index, arrivals_in_that_hour).

        Args:
            daily_sessions: Total daily sessions

        Returns:
            Tuple of (hour_index, peak_arrivals)

        Raises:
            TypeError: If daily_sessions is not a number
            ValueError: If daily_sessions is negative
        """
        if not isinstance(daily_sessions, (int, float)):
            raise TypeError(f"daily_sessions must be a number, got {type(daily_sessions).__name__}")
        if daily_sessions < 0:
            raise ValueError(f"daily_sessions must be non-negative, got {daily_sessions}")
        
        arr = self.hourly_arrivals(daily_sessions)
        h = max(range(24), key=lambda i: arr[i])
        return h, arr[h]


# ---------------------------------------------------------------------------
# 2. Service time
# ---------------------------------------------------------------------------

def service_time_hours(avg_kwh: float, charger_kw: float, plugin_overhead_min: float = 5.0) -> float:
    """Mean time a plug is occupied per session (hours).

    = energy / power  +  fixed plug-in/handshake/payment overhead.

    Args:
        avg_kwh: Average energy per session in kWh
        charger_kw: Charger power in kW
        plugin_overhead_min: Fixed overhead in minutes (default 5.0)

    Returns:
        Service time in hours

    Raises:
        TypeError: If parameters are not numbers
        ValueError: If parameters are not positive
    """
    if not isinstance(avg_kwh, (int, float)):
        raise TypeError(f"avg_kwh must be a number, got {type(avg_kwh).__name__}")
    if not isinstance(charger_kw, (int, float)):
        raise TypeError(f"charger_kw must be a number, got {type(charger_kw).__name__}")
    if not isinstance(plugin_overhead_min, (int, float)):
        raise TypeError(f"plugin_overhead_min must be a number, got {type(plugin_overhead_min).__name__}")
    
    if avg_kwh <= 0:
        raise ValueError(f"avg_kwh must be positive, got {avg_kwh}")
    if charger_kw <= 0:
        raise ValueError(f"charger_kw must be positive, got {charger_kw}")
    if plugin_overhead_min < 0:
        raise ValueError(f"plugin_overhead_min must be non-negative, got {plugin_overhead_min}")
    
    charge_h = avg_kwh / charger_kw
    return charge_h + plugin_overhead_min / 60.0


# ---------------------------------------------------------------------------
# 3. Erlang-C (M/M/c) queue
# ---------------------------------------------------------------------------

def erlang_c(arrival_rate_per_h: float, service_time_h: float, c: int) -> dict:
    """Erlang-C metrics for c parallel plugs.

    Args:
        arrival_rate_per_h: lambda (arrivals/hour in the hour analyzed)
        service_time_h: mean service time (hours) = 1/mu
        c: number of plugs (servers)

    Returns:
        Dictionary with keys:
            - offered_load_erlangs: float
            - utilization: float
            - p_wait: float (probability of waiting)
            - wq_min: float (average wait time in minutes)
            - lq: float (average number waiting)
            - stable: bool

    Raises:
        TypeError: If parameters have wrong types
        ValueError: If parameters are invalid
    """
    if not isinstance(arrival_rate_per_h, (int, float)):
        raise TypeError(f"arrival_rate_per_h must be a number, got {type(arrival_rate_per_h).__name__}")
    if not isinstance(service_time_h, (int, float)):
        raise TypeError(f"service_time_h must be a number, got {type(service_time_h).__name__}")
    if not isinstance(c, int):
        raise TypeError(f"c must be an integer, got {type(c).__name__}")
    
    if arrival_rate_per_h < 0:
        raise ValueError(f"arrival_rate_per_h must be non-negative, got {arrival_rate_per_h}")
    if service_time_h <= 0:
        raise ValueError(f"service_time_h must be positive, got {service_time_h}")
    
    a = arrival_rate_per_h * service_time_h
    
    if c <= 0:
        return {
            "offered_load_erlangs": round(a, 2),
            "utilization": float("inf"),
            "p_wait": 1.0,
            "wq_min": float("inf"),
            "lq": float("inf"),
            "stable": False,
        }
    
    rho = a / c
    if rho >= 1.0:
        return {
            "offered_load_erlangs": round(a, 2),
            "utilization": round(rho, 3),
            "p_wait": 1.0,
            "wq_min": float("inf"),
            "lq": float("inf"),
            "stable": False,
        }

    sum_terms = sum(a ** k / factorial(k) for k in range(c))
    top = a ** c / (factorial(c) * (1 - rho))
    p_wait = top / (sum_terms + top)

    wq_h = p_wait * service_time_h / (c * (1 - rho))
    lq = p_wait * rho / (1 - rho)
    
    return {
        "offered_load_erlangs": round(a, 2),
        "utilization": round(rho, 3),
        "p_wait": round(p_wait, 3),
        "wq_min": round(wq_h * 60, 1),
        "lq": round(lq, 2),
        "stable": True,
    }


def size_plugs(
    arrival_rate_per_h: float,
    service_time_h: float,
    target_p_wait: float = 0.10,
    max_wait_min: float = 10.0,
    max_plugs: int = 60,
) -> tuple[int, dict]:
    """Smallest plug count meeting BOTH a P(wait) and a max-avg-wait target.

    Args:
        arrival_rate_per_h: Arrival rate in arrivals/hour
        service_time_h: Mean service time in hours
        target_p_wait: Target probability of waiting (default 0.10)
        max_wait_min: Maximum average wait time in minutes (default 10.0)
        max_plugs: Maximum number of plugs to consider (default 60)

    Returns:
        Tuple of (recommended_plugs, queue_metrics)

    Raises:
        TypeError: If parameters have wrong types
        ValueError: If parameters are invalid
    """
    if not isinstance(arrival_rate_per_h, (int, float)):
        raise TypeError(f"arrival_rate_per_h must be a number, got {type(arrival_rate_per_h).__name__}")
    if not isinstance(service_time_h, (int, float)):
        raise TypeError(f"service_time_h must be a number, got {type(service_time_h).__name__}")
    if not isinstance(target_p_wait, (int, float)):
        raise TypeError(f"target_p_wait must be a number, got {type(target_p_wait).__name__}")
    if not isinstance(max_wait_min, (int, float)):
        raise TypeError(f"max_wait_min must be a number, got {type(max_wait_min).__name__}")
    if not isinstance(max_plugs, int):
        raise TypeError(f"max_plugs must be an integer, got {type(max_plugs).__name__}")
    
    if arrival_rate_per_h < 0:
        raise ValueError(f"arrival_rate_per_h must be non-negative, got {arrival_rate_per_h}")
    if service_time_h <= 0:
        raise ValueError(f"service_time_h must be positive, got {service_time_h}")
    if target_p_wait <= 0 or target_p_wait >= 1:
        raise ValueError(f"target_p_wait must be in (0, 1), got {target_p_wait}")
    if max_wait_min <= 0:
        raise ValueError(f"max_wait_min must be positive, got {max_wait_min}")
    if max_plugs <= 0:
        raise ValueError(f"max_plugs must be positive, got {max_plugs}")
    
    a = arrival_rate_per_h * service_time_h
    c_min = max(1, int(a) + 1)
    
    for c in range(c_min, max_plugs + 1):
        m = erlang_c(arrival_rate_per_h, service_time_h, c)
        if m["stable"] and m["p_wait"] <= target_p_wait and m["wq_min"] <= max_wait_min:
            logger.debug(
                f"size_plugs: {arrival_rate_per_h}/h, {service_time_h}h → {c} plugs "
                f"(P_wait={m['p_wait']:.3f}, wait={m['wq_min']:.1f} min)"
            )
            return c, m
    
    m = erlang_c(arrival_rate_per_h, service_time_h, max_plugs)
    logger.warning(
        f"size_plugs: could not meet targets with {max_plugs} plugs, "
        f"returning max_plugs={max_plugs}"
    )
    return max_plugs, m


# ---------------------------------------------------------------------------
# 4. End-to-end station analysis
# ---------------------------------------------------------------------------

def analyze_station(
    daily_sessions: float,
    station_type: str = "urban_hub",
    avg_kwh: float = 32.0,
    charger_kw: float = 120.0,
    target_p_wait: float = 0.10,
    max_wait_min: float = 10.0,
    installed_plugs: Optional[int] = None,
) -> dict:
    """Full temporal + queueing analysis for one station-day.

    Returns hourly table, peak-hour queue metrics at the recommended plug count,
    and (if installed_plugs given) the service level of the current build.

    Args:
        daily_sessions: Total daily sessions
        station_type: Station type for hourly profile
        avg_kwh: Average energy per session in kWh
        charger_kw: Charger power in kW
        target_p_wait: Target probability of waiting
        max_wait_min: Maximum average wait time in minutes
        installed_plugs: Number of installed plugs (optional)

    Returns:
        Dictionary with keys:
            - station_type: str
            - daily_sessions: float
            - service_time_min: float
            - charger_kw: float
            - peak_hour: int
            - peak_hour_arrivals: float
            - recommended_plugs: int
            - recommended_at_peak: dict
            - hourly: list[dict]
            - installed_plugs: int (if provided)
            - installed_at_peak: dict (if installed_plugs provided)

    Raises:
        TypeError: If parameters have wrong types
        ValueError: If parameters are invalid
        InvalidStationTypeError: If station_type is invalid
    """
    if not isinstance(daily_sessions, (int, float)):
        raise TypeError(f"daily_sessions must be a number, got {type(daily_sessions).__name__}")
    if daily_sessions < 0:
        raise ValueError(f"daily_sessions must be non-negative, got {daily_sessions}")
    
    if installed_plugs is not None:
        if not isinstance(installed_plugs, int):
            raise TypeError(f"installed_plugs must be an integer, got {type(installed_plugs).__name__}")
        if installed_plugs <= 0:
            raise ValueError(f"installed_plugs must be positive, got {installed_plugs}")
    
    load = HourlyLoadModel(station_type)
    arrivals = load.hourly_arrivals(daily_sessions)
    peak_h, peak_lambda = load.peak_hour(daily_sessions)
    st = service_time_hours(avg_kwh, charger_kw)

    rec_plugs, rec_metrics = size_plugs(peak_lambda, st, target_p_wait, max_wait_min)

    hourly = []
    for h in range(24):
        m = erlang_c(arrivals[h], st, rec_plugs)
        hourly.append({
            "hour": h,
            "arrivals": round(arrivals[h], 1),
            "utilization": m["utilization"],
            "p_wait": m["p_wait"],
            "wq_min": m["wq_min"],
        })

    out = {
        "station_type": station_type,
        "daily_sessions": daily_sessions,
        "service_time_min": round(st * 60, 1),
        "charger_kw": charger_kw,
        "peak_hour": peak_h,
        "peak_hour_arrivals": round(peak_lambda, 1),
        "recommended_plugs": rec_plugs,
        "recommended_at_peak": rec_metrics,
        "hourly": hourly,
    }
    
    if installed_plugs is not None:
        out["installed_plugs"] = installed_plugs
        out["installed_at_peak"] = erlang_c(peak_lambda, st, installed_plugs)
    
    logger.debug(
        f"analyze_station: {daily_sessions} sessions/day, {station_type} → "
        f"recommended {rec_plugs} plugs, peak hour {peak_h}:00 with {peak_lambda:.1f} arrivals/h"
    )
    
    return out


def main():
    # Demo: CM Cultural Center super-hub, calibrated 2026 base (~130/day, peak ~300).
    print("=" * 64)
    print("TH-EVI TEMPORAL + QUEUEING  (CM Cultural Center super-hub)")
    print("=" * 64)
    for label, daily in [("typical day (130)", 130), ("peak season (300)", 300)]:
        r = analyze_station(daily, station_type="urban_hub",
                            avg_kwh=32.0, charger_kw=120.0,
                            target_p_wait=0.10, max_wait_min=10.0,
                            installed_plugs=12)
        print("\n--- %s ---" % label)
        print("  service time / session : %.1f min  (32 kWh @ 120 kW)" % r["service_time_min"])
        print("  peak hour              : %02d:00, %.0f arrivals/h" %
              (r["peak_hour"], r["peak_hour_arrivals"]))
        print("  recommended plugs      : %d  (P_wait=%.0f%%, wait=%.1f min, util=%.0f%%)" %
              (r["recommended_plugs"], r["recommended_at_peak"]["p_wait"] * 100,
               r["recommended_at_peak"]["wq_min"], r["recommended_at_peak"]["utilization"] * 100))
        i = r["installed_at_peak"]
        verdict = "OK" if i["stable"] and i["p_wait"] <= 0.10 else "UNDER-BUILT"
        print("  installed 12 plugs     : util=%s  P_wait=%s  wait=%s min  -> %s" %
              ("%.0f%%" % (i["utilization"] * 100) if i["utilization"] != float("inf") else "inf",
               "%.0f%%" % (i["p_wait"] * 100), i["wq_min"], verdict))
    print("=" * 64)


if __name__ == "__main__":
    main()
