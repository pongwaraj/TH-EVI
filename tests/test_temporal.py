"""Tests for the temporal + queueing layer."""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from th_evi.temporal import (
    erlang_c, size_plugs, HOURLY_PROFILES, HourlyLoadModel, service_time_hours,
)


def test_profiles_normalized():
    for name, p in HOURLY_PROFILES.items():
        assert len(p) == 24
        assert abs(sum(p) - 1.0) < 1e-9, f"{name} not normalized"


def test_erlang_c_textbook():
    # Erlang-C closed form, verified by hand:
    #   a=2, c=3 -> P(wait) = 4/9 = 0.4444
    m = erlang_c(arrival_rate_per_h=2.0, service_time_h=1.0, c=3)
    assert abs(m["p_wait"] - 0.4444) < 0.001, m["p_wait"]
    assert abs(m["utilization"] - round(2/3, 3)) < 1e-6
    # second check: a=1, c=2 -> P(wait) = 1/3
    m2 = erlang_c(1.0, 1.0, 2)
    assert abs(m2["p_wait"] - 0.3333) < 0.001, m2["p_wait"]


def test_more_plugs_lower_wait():
    p_prev = 1.1
    for c in range(3, 12):
        m = erlang_c(20.0, 0.35, c)
        if m["stable"]:
            assert m["p_wait"] <= p_prev + 1e-9, "P(wait) must be non-increasing in c"
            p_prev = m["p_wait"]


def test_unstable_when_overloaded():
    m = erlang_c(arrival_rate_per_h=10.0, service_time_h=1.0, c=5)  # a=10 > c=5
    assert m["stable"] is False
    assert m["p_wait"] == 1.0


def test_size_plugs_meets_target():
    c, m = size_plugs(18.0, 0.35, target_p_wait=0.10, max_wait_min=10.0)
    assert m["stable"] and m["p_wait"] <= 0.10 and m["wq_min"] <= 10.0
    # one fewer plug must violate at least one target
    c2 = erlang_c(18.0, 0.35, c - 1)
    assert (not c2["stable"]) or c2["p_wait"] > 0.10 or c2["wq_min"] > 10.0


def test_service_time():
    # 32 kWh @ 120 kW = 16 min charge + 5 min overhead = 21 min
    assert abs(service_time_hours(32, 120, 5) * 60 - 21.0) < 0.1


def test_peak_hour():
    h, lam = HourlyLoadModel("destination").peak_hour(300)
    assert 16 <= h <= 19, "destination peak should be evening"


if __name__ == "__main__":
    test_profiles_normalized()
    test_erlang_c_textbook()
    test_more_plugs_lower_wait()
    test_unstable_when_overloaded()
    test_size_plugs_meets_target()
    test_service_time()
    test_peak_hour()
    print("OK: All temporal tests passed")
