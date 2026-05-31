"""Tests for EV adoption model."""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from th_evi.adoption import EVAdoptionModel


def test_ev_share_increases():
    model = EVAdoptionModel(province='เชียงใหม่')
    assert model.get_ev_share(2025) < model.get_ev_share(2040), "Share must increase over time"

def test_ev_share_between_0_and_1():
    model = EVAdoptionModel(province='เชียงใหม่')
    for y in range(2025, 2041):
        s = model.get_ev_share(y)
        assert 0 <= s <= 1, f"Share {s} out of range at year {y}"

def test_ev_population_reasonable():
    model = EVAdoptionModel(province='เชียงใหม่')
    pop = model.get_ev_population(2030)
    assert 1000 < pop < 2000000, f"Population {pop} unreasonable"

def test_province_factor_differs():
    cm = EVAdoptionModel(province='เชียงใหม่')
    default = EVAdoptionModel(province='unknown')
    assert cm.get_ev_share(2030) != default.get_ev_share(2030), "Province factors should differ"

if __name__ == '__main__':
    test_ev_share_increases()
    test_ev_share_between_0_and_1()
    test_ev_population_reasonable()
    test_province_factor_differs()
    print("OK: All adoption tests passed")
