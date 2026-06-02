import warnings


CORRIDOR_CONVERSION_MIN = 0.005
CORRIDOR_CONVERSION_MAX = 0.030


def ev_penetration(ev_count, total_vehicle_count):
    """Return EV share as a fraction."""
    if total_vehicle_count <= 0:
        return 0.0
    return max(ev_count, 0) / total_vehicle_count


def community_sessions(ev_fleet, public_charge_share, capture_rate, sessions_per_ev_day=0.20):
    """Estimate daily charging sessions from local community demand."""
    return max(ev_fleet, 0) * max(public_charge_share, 0) * max(capture_rate, 0) * sessions_per_ev_day


def corridor_sessions(aadt, ev_share, long_trip_share, public_charge_need, site_capture_rate):
    """Estimate daily charging sessions from corridor through-traffic."""
    return (
        max(aadt, 0)
        * max(ev_share, 0)
        * max(long_trip_share, 0)
        * max(public_charge_need, 0)
        * max(site_capture_rate, 0)
    )


def fleet_sessions(fleet_size, ev_share, operating_days_share, charge_sessions_per_active_ev):
    """Estimate daily charging sessions from fleet or operational vehicles."""
    return (
        max(fleet_size, 0)
        * max(ev_share, 0)
        * max(operating_days_share, 0)
        * max(charge_sessions_per_active_ev, 0)
    )


def combine_streams(*streams, overlap_discount=0.10):
    """Combine demand streams with a modest overlap discount."""
    total = sum(max(stream, 0) for stream in streams)
    return total * (1 - max(min(overlap_discount, 1), 0))


def corridor_conversion_guard(combined_conversion, scenario=""):
    """Warn when a corridor conversion assumption is outside the EV Hub guard rail."""
    if combined_conversion < CORRIDOR_CONVERSION_MIN or combined_conversion > CORRIDOR_CONVERSION_MAX:
        label = f" for {scenario}" if scenario else ""
        warnings.warn(
            "Corridor conversion"
            f"{label} should normally stay between {CORRIDOR_CONVERSION_MIN:.3f}"
            f" and {CORRIDOR_CONVERSION_MAX:.3f}.",
            UserWarning,
            stacklevel=2,
        )
        return False
    return True
