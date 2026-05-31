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

from math import factorial


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
    """Distribute a daily session count across 24 hours of arrivals."""

    def __init__(self, station_type="urban_hub"):
        if station_type not in HOURLY_PROFILES:
            station_type = "urban_hub"
        self.station_type = station_type
        self.profile = HOURLY_PROFILES[station_type]

    def hourly_arrivals(self, daily_sessions):
        """Return list of 24 arrival counts (lambda per hour)."""
        return [daily_sessions * w for w in self.profile]

    def peak_hour(self, daily_sessions):
        """Return (hour_index, arrivals_in_that_hour)."""
        arr = self.hourly_arrivals(daily_sessions)
        h = max(range(24), key=lambda i: arr[i])
        return h, arr[h]


# ---------------------------------------------------------------------------
# 2. Service time
# ---------------------------------------------------------------------------

def service_time_hours(avg_kwh, charger_kw, plugin_overhead_min=5.0):
    """Mean time a plug is occupied per session (hours).

    = energy / power  +  fixed plug-in/handshake/payment overhead.
    """
    charge_h = avg_kwh / charger_kw
    return charge_h + plugin_overhead_min / 60.0


# ---------------------------------------------------------------------------
# 3. Erlang-C (M/M/c) queue
# ---------------------------------------------------------------------------

def erlang_c(arrival_rate_per_h, service_time_h, c):
    """Erlang-C metrics for c parallel plugs.

    Parameters
    ----------
    arrival_rate_per_h : float   lambda (arrivals/hour in the hour analyzed)
    service_time_h     : float   mean service time (hours) = 1/mu
    c                  : int      number of plugs (servers)

    Returns dict: offered_load_erlangs, utilization, p_wait, wq_min, lq, stable
    """
    a = arrival_rate_per_h * service_time_h          # offered load (Erlangs)
    if c <= 0:
        return {"offered_load_erlangs": round(a, 2), "utilization": float("inf"),
                "p_wait": 1.0, "wq_min": float("inf"), "lq": float("inf"), "stable": False}
    rho = a / c
    if rho >= 1.0:                                    # unstable: queue grows forever
        return {"offered_load_erlangs": round(a, 2), "utilization": round(rho, 3),
                "p_wait": 1.0, "wq_min": float("inf"), "lq": float("inf"), "stable": False}

    # Erlang-C probability of waiting
    sum_terms = sum(a ** k / factorial(k) for k in range(c))
    top = a ** c / (factorial(c) * (1 - rho))
    p_wait = top / (sum_terms + top)

    wq_h = p_wait * service_time_h / (c * (1 - rho))  # avg wait (hours)
    lq = p_wait * rho / (1 - rho)                     # avg number waiting
    return {
        "offered_load_erlangs": round(a, 2),
        "utilization": round(rho, 3),
        "p_wait": round(p_wait, 3),
        "wq_min": round(wq_h * 60, 1),
        "lq": round(lq, 2),
        "stable": True,
    }


def size_plugs(arrival_rate_per_h, service_time_h,
               target_p_wait=0.10, max_wait_min=10.0, max_plugs=60):
    """Smallest plug count meeting BOTH a P(wait) and a max-avg-wait target."""
    a = arrival_rate_per_h * service_time_h
    c_min = max(1, int(a) + 1)                        # must exceed offered load
    for c in range(c_min, max_plugs + 1):
        m = erlang_c(arrival_rate_per_h, service_time_h, c)
        if m["stable"] and m["p_wait"] <= target_p_wait and m["wq_min"] <= max_wait_min:
            return c, m
    m = erlang_c(arrival_rate_per_h, service_time_h, max_plugs)
    return max_plugs, m


# ---------------------------------------------------------------------------
# 4. End-to-end station analysis
# ---------------------------------------------------------------------------

def analyze_station(daily_sessions, station_type="urban_hub",
                    avg_kwh=32.0, charger_kw=120.0,
                    target_p_wait=0.10, max_wait_min=10.0, installed_plugs=None):
    """Full temporal + queueing analysis for one station-day.

    Returns hourly table, peak-hour queue metrics at the recommended plug count,
    and (if installed_plugs given) the service level of the current build.
    """
    load = HourlyLoadModel(station_type)
    arrivals = load.hourly_arrivals(daily_sessions)
    peak_h, peak_lambda = load.peak_hour(daily_sessions)
    st = service_time_hours(avg_kwh, charger_kw)

    rec_plugs, rec_metrics = size_plugs(peak_lambda, st, target_p_wait, max_wait_min)

    hourly = []
    for h in range(24):
        m = erlang_c(arrivals[h], st, rec_plugs)
        hourly.append({"hour": h, "arrivals": round(arrivals[h], 1),
                       "utilization": m["utilization"], "p_wait": m["p_wait"],
                       "wq_min": m["wq_min"]})

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
