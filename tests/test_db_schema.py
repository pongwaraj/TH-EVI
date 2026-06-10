"""Tests for database schema creation."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from th_evi.db import (
    BusinessAreaReference,
    DistrictNodeReference,
    EVBooking,
    EVFleetMix,
    EVModel,
    EVRegistration,
    HeatmapExclusionReference,
    HotZoneReference,
    create_session_factory,
    get_database_url,
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


def test_reference_schema_supports_business_areas_and_heatmap_exclusions():
    Session = create_session_factory("sqlite:///:memory:")
    with Session() as session:
        session.add(
            BusinessAreaReference(
                business_area_id="cm_airport_frontage",
                province="Chiang Mai",
                name="Airport frontage",
                area_type="urban_fringe",
                center_lat=18.77,
                center_lon=98.97,
                radius_km=3.2,
                demand_pool_base=175.0,
                confidence="high",
            )
        )
        session.add(
            HeatmapExclusionReference(
                exclusion_id="py_kwan_water_core",
                province="Phayao",
                name="Kwan Phayao water core",
                center_lat=19.17,
                center_lon=99.92,
                radius_km=3.4,
                exclusion_type="water",
                confidence="high",
            )
        )
        session.commit()

    with Session() as session:
        area = session.query(BusinessAreaReference).one()
        exclusion = session.query(HeatmapExclusionReference).one()
        assert area.business_area_id == "cm_airport_frontage"
        assert area.active is True
        assert area.updated_at is not None
        assert exclusion.exclusion_id == "py_kwan_water_core"
        assert exclusion.active is True


def test_reference_schema_supports_hot_zones_and_district_nodes():
    Session = create_session_factory("sqlite:///:memory:")
    with Session() as session:
        session.add(
            HotZoneReference(
                zone_id="cm_airport_core",
                province="Chiang Mai",
                name="Airport core",
                center_lat=18.767,
                center_lon=98.976,
                radius_km=2.5,
                heat_rank=1,
                demand_pool_base=320.0,
                confidence="high",
            )
        )
        session.add(
            DistrictNodeReference(
                node_id="cm_mueang",
                province="Chiang Mai",
                district_name="Mueang Chiang Mai",
                name="Chiang Mai city and inner ring",
                node_type="district_center",
                lat=18.7904,
                lon=98.9847,
                radius_km=4.8,
                confidence_multiplier=1.0,
                confidence="high",
            )
        )
        session.commit()

    with Session() as session:
        zone = session.query(HotZoneReference).one()
        node = session.query(DistrictNodeReference).one()
        assert zone.zone_id == "cm_airport_core"
        assert zone.active is True
        assert zone.updated_at is not None
        assert node.node_id == "cm_mueang"
        assert node.active is True


def test_get_database_url_falls_back_to_local_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("TH_EVI_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.setattr("th_evi.db.PROJECT_ROOT", tmp_path)
    (tmp_path / ".env.local").write_text(
        'DATABASE_URL="postgresql://example_user:secret@example-host/neondb?sslmode=require"\n',
        encoding="utf-8",
    )

    url = get_database_url()

    assert url.startswith("postgresql+psycopg://example_user:secret@example-host/neondb")
