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
