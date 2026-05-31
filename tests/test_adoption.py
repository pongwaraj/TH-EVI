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

def test_cm_uses_ror1_national_curve():
    # Reconciliation (May 2026): for the ror.1 passenger-car basis, the Chiang Mai
    # factor is intentionally 1.0, so CM tracks the national new-car BEV curve.
    cm = EVAdoptionModel(province='เชียงใหม่')
    default = EVAdoptionModel(province='unknown')
    assert cm.get_ev_share(2030) == default.get_ev_share(2030), \
        "CM should equal national curve on the ror.1 basis (factor=1.0)"

def test_calibrated_to_fti_2025():
    # National new-car BEV share should sit near the FTI full-year actual (19.4%).
    m = EVAdoptionModel(province='unknown')
    assert abs(m.get_ev_share(2025) - 0.194) < 0.02, \
        "2025 share should be within 2pp of FTI actual 19.4%"

if __name__ == '__main__':
    test_ev_share_increases()
    test_ev_share_between_0_and_1()
    test_ev_population_reasonable()
    test_cm_uses_ror1_national_curve()
    test_calibrated_to_fti_2025()
    print("OK: All adoption tests passed")
