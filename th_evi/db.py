"""SQLite storage for candidate sites and analysis reports."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "th_evi.sqlite3"
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


class Base(DeclarativeBase):
    pass


class CandidateSite(Base):
    __tablename__ = "candidate_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    province: Mapped[str] = mapped_column(String(120), default="เชียงใหม่", nullable=False)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    assumptions: Mapped[list["SiteAssumption"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )
    competitors: Mapped[list["CompetitorRecord"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )
    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )


class SiteAssumption(Base):
    __tablename__ = "site_assumptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("candidate_sites.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    location_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    aadt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    station_format: Mapped[str] = mapped_column(String(60), default="community_mall", nullable=False)
    guns: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    total_site_kw: Mapped[float] = mapped_column(Float, default=360.0, nullable=False)
    max_kw_per_gun: Mapped[float] = mapped_column(Float, default=120.0, nullable=False)
    parking_capacity: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    visibility_from_road: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    access_ease: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    roadside_frontage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signage_quality: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    tenant_strength: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    inside_parking_structure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opening_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_kwh_per_session: Mapped[float] = mapped_column(Float, default=32.0, nullable=False)
    price_per_kwh: Mapped[float] = mapped_column(Float, default=6.5, nullable=False)

    site: Mapped[CandidateSite] = relationship(back_populates="assumptions")


class CompetitorRecord(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("candidate_sites.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    guns: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_kw: Mapped[float] = mapped_column(Float, default=120.0, nullable=False)
    brand_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    price_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    access_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    visibility_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    same_corridor: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    site: Mapped[CandidateSite] = relationship(back_populates="competitors")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("candidate_sites.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario: Mapped[str] = mapped_column(String(40), default="base", nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), default="0.2.0-db1", nullable=False)
    inputs_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    site: Mapped[CandidateSite] = relationship(back_populates="runs")
    result: Mapped["AnalysisResult"] = relationship(
        back_populates="run", cascade="all, delete-orphan", uselist=False
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False, unique=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    sessions_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    daily_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    daily_revenue: Mapped[float] = mapped_column(Float, nullable=False)
    capture_share: Mapped[float] = mapped_column(Float, nullable=False)
    readiness_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_plugs: Mapped[int] = mapped_column(Integer, nullable=False)
    peak_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    utilization_pct: Mapped[float] = mapped_column(Float, nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="result")


class EVModel(Base):
    __tablename__ = "ev_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    variant: Mapped[str | None] = mapped_column(String(120), nullable=True)
    segment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    battery_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    usable_battery_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_dc_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    typical_dc_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    efficiency_kwh_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(160), nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    registrations: Mapped[list["EVRegistration"]] = relationship(
        back_populates="ev_model", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["EVBooking"]] = relationship(
        back_populates="ev_model", cascade="all, delete-orphan"
    )
    fleet_mix_rows: Mapped[list["EVFleetMix"]] = relationship(
        back_populates="ev_model", cascade="all, delete-orphan"
    )


class EVRegistration(Base):
    __tablename__ = "ev_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ev_model_id: Mapped[int | None] = mapped_column(ForeignKey("ev_models.id"), nullable=True)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registrations: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(80), default="passenger_bev", nullable=False)
    source: Mapped[str | None] = mapped_column(String(160), nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="high", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    ev_model: Mapped[EVModel | None] = relationship(back_populates="registrations")


class EVBooking(Base):
    __tablename__ = "ev_bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ev_model_id: Mapped[int | None] = mapped_column(ForeignKey("ev_models.id"), nullable=True)
    event_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    booking_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bookings: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_delivery_lag_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(160), nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    ev_model: Mapped[EVModel | None] = relationship(back_populates="bookings")


class EVFleetMix(Base):
    __tablename__ = "ev_fleet_mix"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ev_model_id: Mapped[int | None] = mapped_column(ForeignKey("ev_models.id"), nullable=True)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estimated_active_units: Mapped[int] = mapped_column(Integer, nullable=False)
    share_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_battery_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_session_kwh_city: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_session_kwh_highway: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_dc_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(160), nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    ev_model: Mapped[EVModel | None] = relationship(back_populates="fleet_mix_rows")


class ReferenceSource(Base):
    __tablename__ = "reference_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(40), default="official", nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    license_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ProvinceIngestionRun(Base):
    __tablename__ = "province_ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    province_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="planned", nullable=False)
    git_commit: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DistrictPopulation(Base):
    __tablename__ = "district_population"
    __table_args__ = (
        UniqueConstraint("province", "district_name_en", "year_be", name="uq_district_population"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    district_name_th: Mapped[str | None] = mapped_column(String(120), nullable=True)
    district_name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    district_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    year_be: Mapped[int] = mapped_column(Integer, nullable=False)
    population: Mapped[int] = mapped_column(Integer, nullable=False)
    male_population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    female_population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    households: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("reference_sources.id"), nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="high", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AADTSegment(Base):
    __tablename__ = "aadt_segments"
    __table_args__ = (
        UniqueConstraint("province", "route_number", "segment_name", "km_start", "year_be", name="uq_aadt_segment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    route_number: Mapped[str] = mapped_column(String(20), nullable=False)
    segment_name: Mapped[str] = mapped_column(String(200), nullable=False)
    km_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    km_end: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    aadt: Mapped[int] = mapped_column(Integer, nullable=False)
    heavy_vehicle_share_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_be: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("reference_sources.id"), nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class POIReference(Base):
    __tablename__ = "poi_reference"
    __table_args__ = (
        UniqueConstraint("province", "poi_id", name="uq_poi_reference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poi_id: Mapped[str] = mapped_column(String(80), nullable=False)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    demand_role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    radius_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("reference_sources.id"), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(40), default="seed_needs_verification", nullable=False)
    confidence: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ChargerCompetitor(Base):
    __tablename__ = "charger_competitors"
    __table_args__ = (
        UniqueConstraint("province", "station_id", name="uq_charger_competitor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[str] = mapped_column(String(80), nullable=False)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    network: Mapped[str | None] = mapped_column(String(80), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    plug_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gun_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_site_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    dc_fast: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    price_per_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_hours: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("reference_sources.id"), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(40), default="seed_needs_verification", nullable=False)
    confidence: Mapped[str] = mapped_column(String(40), default="low", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


def get_database_url() -> str:
    url = (
        os.environ.get("TH_EVI_DB_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or DEFAULT_DB_URL
    )
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_session_factory(db_url: str | None = None) -> sessionmaker[Session]:
    url = db_url or get_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        DATA_DIR.mkdir(exist_ok=True)
        connect_args = {"check_same_thread": False}
    engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


SessionLocal: sessionmaker[Session] | None = None


def get_session_factory() -> sessionmaker[Session]:
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = create_session_factory()
    return SessionLocal


@contextmanager
def session_scope():
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
