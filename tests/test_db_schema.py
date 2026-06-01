"""Tests for database schema creation."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from th_evi.db import (
    EVBooking,
    EVFleetMix,
    EVModel,
    EVRegistration,
    create_session_factory,
)


def test_ev_model_schema_supports_registration_booking_and_fleet_mix():
    Session = create_session_factory("sqlite:///:memory:")
    with Session() as session:
        model = EVModel(
            brand="BYD",
            model="Atto 3",
            segment="crossover",
            battery_kwh=60.5,
            usable_battery_kwh=58.0,
            max_dc_kw=88.0,
            typical_dc_kw=70.0,
            efficiency_kwh_per_km=0.155,
            source="schema_test",
            confidence="test",
        )
        session.add(model)
        session.flush()

        session.add(
            EVRegistration(
                ev_model_id=model.id,
                province="เชียงใหม่",
                year=2026,
                month=5,
                brand="BYD",
                model="Atto 3",
                registrations=120,
                source="schema_test",
            )
        )
        session.add(
            EVBooking(
                ev_model_id=model.id,
                event_name="Motor Show",
                year=2026,
                month=4,
                brand="BYD",
                model="Atto 3",
                bookings=300,
                estimated_delivery_lag_months=2,
                source="schema_test",
            )
        )
        session.add(
            EVFleetMix(
                ev_model_id=model.id,
                province="เชียงใหม่",
                year=2026,
                month=5,
                brand="BYD",
                model="Atto 3",
                estimated_active_units=1400,
                share_pct=18.5,
                weighted_battery_kwh=10.73,
                weighted_session_kwh_city=4.07,
                weighted_session_kwh_highway=7.4,
                weighted_dc_kw=12.95,
                source="schema_test",
            )
        )
        session.commit()

    with Session() as session:
        saved = session.query(EVModel).one()
        assert saved.brand == "BYD"
        assert saved.registrations[0].registrations == 120
        assert saved.bookings[0].bookings == 300
        assert saved.fleet_mix_rows[0].estimated_active_units == 1400
