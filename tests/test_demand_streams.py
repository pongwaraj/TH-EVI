import pytest

from th_evi.demand_streams import (
    combine_streams,
    community_sessions,
    corridor_conversion_guard,
    corridor_sessions,
    ev_penetration,
    fleet_sessions,
)


def test_demand_stream_math():
    assert ev_penetration(426, 51702) == pytest.approx(0.0082395, rel=1e-5)
    assert community_sessions(500, 0.40, 0.25) == pytest.approx(10.0)
    assert corridor_sessions(12000, 0.008, 0.30, 0.45, 0.20) == pytest.approx(2.592)
    assert fleet_sessions(100, 0.20, 0.80, 0.50) == pytest.approx(8.0)
    assert combine_streams(10, 2.592, 8, overlap_discount=0.10) == pytest.approx(18.5328)


def test_corridor_conversion_guard_accepts_normal_range():
    assert corridor_conversion_guard(0.015, scenario="realistic") is True


def test_corridor_conversion_guard_warns_outside_range():
    with pytest.warns(UserWarning, match="Corridor conversion"):
        assert corridor_conversion_guard(0.050, scenario="optimistic") is False
