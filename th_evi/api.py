"""TH-EVI FastAPI server - EV charging demand forecast for Thailand."""

from __future__ import annotations

import html
import json
import math
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
import uvicorn

from .data import (
    get_chiang_mai_district_population,
    get_cm_highway_aadt,
    load_doh_aadt,
    load_osm_charging_stations,
)
from .db import (
    AnalysisResult,
    AnalysisRun,
    CandidateSite,
    CompetitorRecord,
    SiteAssumption,
    get_database_url,
    session_scope,
)
from .heatmap import generate_chiang_mai_heatmap
from .location import LANDMARK_DB, LocationDemandModel, StationDemandModel
from .site import (
    CompetitiveCaptureModel,
    Competitor,
    SiteDemandCase,
    SiteReadiness,
    StationSpec,
    recommend_station_spec,
)
from .spatial import analyze_click_location
from .temporal import analyze_station


HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="TH-EVI", version="0.2.0")

model = LocationDemandModel(province="เชียงใหม่")


class EstimateRequest(BaseModel):
    lat: float
    lon: float
    year: int = 2035
    location_type: str | None = None
    aadt: int | None = None


class CandidateSiteInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    lat: float
    lon: float
    province: str = "เชียงใหม่"
    district: str | None = None
    zone: str | None = None
    notes: str | None = None


class SiteAssumptionInput(BaseModel):
    location_type: str | None = None
    aadt: int | None = None
    station_format: str = "community_mall"
    guns: int = Field(4, ge=1, le=100)
    total_site_kw: float = Field(360.0, gt=0)
    max_kw_per_gun: float = Field(120.0, gt=0)
    parking_capacity: int = Field(12, ge=0)
    visibility_from_road: float = Field(0.6, ge=0, le=1)
    access_ease: float = Field(0.6, ge=0, le=1)
    roadside_frontage: bool = False
    signage_quality: float = Field(0.6, ge=0, le=1)
    tenant_strength: float = Field(0.6, ge=0, le=1)
    inside_parking_structure: bool = False
    opening_age_days: int | None = Field(None, ge=0)
    avg_kwh_per_session: float = Field(32.0, gt=0)
    price_per_kwh: float = Field(6.5, gt=0)


class CompetitorInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    lat: float | None = None
    lon: float | None = None
    distance_km: float = Field(..., ge=0)
    guns: int = Field(2, ge=1)
    max_kw: float = Field(120.0, gt=0)
    brand_score: float = Field(1.0, ge=0.2, le=2.0)
    price_score: float = Field(1.0, ge=0.4, le=1.6)
    access_score: float = Field(1.0, ge=0.2, le=1.8)
    visibility_score: float = Field(1.0, ge=0.2, le=1.8)
    same_corridor: bool = True


class SiteAnalysisRequest(BaseModel):
    site: CandidateSiteInput
    assumptions: SiteAssumptionInput = Field(default_factory=SiteAssumptionInput)
    competitors: list[CompetitorInput] = Field(default_factory=list)
    year: int = Field(2030, ge=2025, le=2050)
    scenario: str = Field("base", pattern="^(conservative|base|upside)$")


class ClickAnalysisRequest(BaseModel):
    lat: float
    lon: float
    province: str = "เชียงใหม่"
    year: int = Field(2030, ge=2025, le=2050)
    scenario: str = Field("base", pattern="^(conservative|base|upside)$")
    avg_kwh_per_session: float = Field(32.0, gt=0)
    price_per_kwh: float = Field(6.8, gt=0)


def _dump_model(model_obj: BaseModel) -> dict[str, Any]:
    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()
    return model_obj.dict()


def _json_safe(value: Any) -> Any:
    """Convert model output into strict JSON-safe values."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _station_type_for_queue(location_type: str | None, station_format: str) -> str:
    if location_type in {"highway", "destination", "city_center"}:
        return location_type
    if station_format in {"highway_hub", "roadside_destination"}:
        return "highway"
    if station_format in {"mall_surface_lot", "community_mall"}:
        return "destination"
    return "urban_hub"


def _compute_site_analysis(
    request: SiteAnalysisRequest,
    raw_factor: float = 1.0,
    scenario_label: str | None = None,
) -> dict[str, Any]:
    site_in = request.site
    assumption = request.assumptions

    location_model = LocationDemandModel(province=site_in.province)
    location_result = location_model.estimate(
        site_in.lat,
        site_in.lon,
        request.year,
        location_type=assumption.location_type,
        aadt=assumption.aadt,
    )
    raw_sessions = max(0.0, location_result["charging_sessions_per_day"] * raw_factor)

    station = StationSpec(
        guns=assumption.guns,
        total_site_kw=assumption.total_site_kw,
        max_kw_per_gun=assumption.max_kw_per_gun,
    )
    readiness = SiteReadiness(
        station_format=assumption.station_format,
        visibility_from_road=assumption.visibility_from_road,
        access_ease=assumption.access_ease,
        parking_capacity=assumption.parking_capacity,
        roadside_frontage=assumption.roadside_frontage,
        signage_quality=assumption.signage_quality,
        tenant_strength=assumption.tenant_strength,
        inside_parking_structure=assumption.inside_parking_structure,
    )
    competitors = [
        Competitor(
            name=c.name,
            distance_km=c.distance_km,
            guns=c.guns,
            max_kw=c.max_kw,
            brand_score=c.brand_score,
            price_score=c.price_score,
            access_score=c.access_score,
            visibility_score=c.visibility_score,
            same_corridor=c.same_corridor,
        )
        for c in request.competitors
    ]
    case = SiteDemandCase(
        name=site_in.name,
        raw_daily_sessions=raw_sessions,
        station=station,
        readiness=readiness,
        competitors=competitors,
        opening_age_days=assumption.opening_age_days,
        avg_kwh_per_session=assumption.avg_kwh_per_session,
        price_per_kwh=assumption.price_per_kwh,
    )
    capture_result = CompetitiveCaptureModel().estimate(case)
    queue_station_type = _station_type_for_queue(
        location_result["location_type"], assumption.station_format
    )
    charger_kw = max(1.0, capture_result["effective_kw_at_expected_load"])
    queue_result = analyze_station(
        daily_sessions=capture_result["captured_daily_sessions"],
        station_type=queue_station_type,
        avg_kwh=assumption.avg_kwh_per_session,
        charger_kw=charger_kw,
        installed_plugs=assumption.guns,
    )
    installed = queue_result.get("installed_at_peak", {})
    installed_util = installed.get("utilization", 0)
    utilization_pct = 999.0 if installed_util == float("inf") else round(installed_util * 100, 1)
    charger_recommendation = recommend_station_spec(
        capture_result["captured_daily_sessions"],
        avg_kwh_per_session=assumption.avg_kwh_per_session,
        preferred_ports=assumption.guns,
    )

    return {
        "scenario": scenario_label or request.scenario,
        "year": request.year,
        "site": _dump_model(site_in),
        "location_estimate": location_result,
        "site_capture": capture_result,
        "charger_recommendation": charger_recommendation,
        "queue": queue_result,
        "summary": {
            "sessions_per_day": capture_result["captured_daily_sessions"],
            "daily_kwh": capture_result["daily_kwh"],
            "daily_revenue": capture_result["daily_revenue"],
            "capture_share": capture_result["competitive_capture_share"],
            "readiness_multiplier": capture_result["readiness_multiplier"],
            "recommended_plugs": queue_result["recommended_plugs"],
            "installed_plugs": assumption.guns,
            "recommended_architecture": charger_recommendation["architecture"],
            "recommended_total_site_kw": charger_recommendation["total_site_kw"],
            "recommended_cabinet_count": charger_recommendation["cabinet_count"],
            "recommended_cabinet_kw": charger_recommendation["cabinet_kw"],
            "kwh_per_port_day": charger_recommendation["kwh_per_port_day"],
            "sessions_per_port_day": charger_recommendation["sessions_per_port_day"],
            "peak_hour": queue_result["peak_hour"],
            "peak_hour_arrivals": queue_result["peak_hour_arrivals"],
            "installed_utilization_pct": utilization_pct,
        },
    }


def _scenario_band(request: SiteAnalysisRequest) -> dict[str, dict[str, Any]]:
    factors = {"conservative": 0.75, "base": 1.0, "upside": 1.25}
    band = {}
    for label, factor in factors.items():
        computed = _compute_site_analysis(request, raw_factor=factor, scenario_label=label)
        band[label] = computed["summary"]
    return band


def _store_analysis(request: SiteAnalysisRequest, result: dict[str, Any]) -> int:
    result = _json_safe(result)
    site_data = _dump_model(request.site)
    assumption_data = _dump_model(request.assumptions)
    input_snapshot = {
        "site": site_data,
        "assumptions": assumption_data,
        "competitors": [_dump_model(c) for c in request.competitors],
        "year": request.year,
        "scenario": request.scenario,
    }

    with session_scope() as session:
        site = CandidateSite(**site_data)
        session.add(site)
        session.flush()

        session.add(SiteAssumption(site_id=site.id, **assumption_data))
        for competitor in request.competitors:
            session.add(CompetitorRecord(site_id=site.id, **_dump_model(competitor)))

        run = AnalysisRun(
            site_id=site.id,
            year=request.year,
            scenario=request.scenario,
            inputs_snapshot_json=json.dumps(input_snapshot, ensure_ascii=False, allow_nan=False),
        )
        session.add(run)
        session.flush()

        summary = result["summary"]
        session.add(
            AnalysisResult(
                run_id=run.id,
                result_json=json.dumps(result, ensure_ascii=False, allow_nan=False),
                sessions_per_day=summary["sessions_per_day"],
                daily_kwh=summary["daily_kwh"],
                daily_revenue=summary["daily_revenue"],
                capture_share=summary["capture_share"],
                readiness_multiplier=summary["readiness_multiplier"],
                recommended_plugs=summary["recommended_plugs"],
                peak_hour=summary["peak_hour"],
                utilization_pct=summary["installed_utilization_pct"],
            )
        )
        return run.id


def _load_report(run_id: int) -> tuple[AnalysisRun, dict[str, Any]]:
    with session_scope() as session:
        run = session.get(AnalysisRun, run_id)
        if run is None or run.result is None:
            raise HTTPException(status_code=404, detail="Analysis report not found")
        result = json.loads(run.result.result_json)
        session.expunge(run)
        return run, result


@app.get("/api/landmarks")
def list_landmarks():
    """Return all predefined landmarks."""
    return [{"id": lid, **meta} for lid, meta in LANDMARK_DB.items()]


@app.get("/api/landmarks/{location_id}")
def estimate_landmark(location_id: str, year: int = Query(2035, ge=2025, le=2050)):
    """Estimate EV demand at a predefined landmark."""
    return model.estimate_from_db(location_id, year)


@app.post("/api/estimate")
def estimate_location(req: EstimateRequest):
    """Estimate EV demand at an arbitrary lat/lon."""
    return model.estimate(req.lat, req.lon, req.year, req.location_type, req.aadt)


@app.post("/api/click-analysis")
def click_analysis(req: ClickAnalysisRequest):
    """Estimate a clicked map point using POI attraction and competitor penalty fields."""
    return analyze_click_location(
        lat=req.lat,
        lon=req.lon,
        province=req.province,
        year=req.year,
        scenario=req.scenario,
        avg_kwh_per_session=req.avg_kwh_per_session,
        price_per_kwh=req.price_per_kwh,
    )


@app.get("/api/highways")
def list_highways():
    """Return Chiang Mai highway segments with AADT."""
    aadt = get_cm_highway_aadt()
    df = load_doh_aadt(province="เชียงใหม่")
    segments = []
    for _, row in df.iterrows():
        segments.append({
            "route": int(row.iloc[0]),
            "section": int(row.iloc[1]),
            "name": row.iloc[2],
            "km": row.iloc[3],
            "aadt": int(row.iloc[14]),
        })
    return {"segments": segments, "routes": aadt}


@app.get("/api/chargers")
def list_chargers():
    """Return existing EV charging stations from OSM."""
    df = load_osm_charging_stations()
    return {"stations": df.to_dict(orient="records")}


@app.get("/api/population")
def population():
    """Return Chiang Mai district population data."""
    df = get_chiang_mai_district_population()
    return {"districts": df.to_dict(orient="records")}


@app.get("/api/health/db")
def database_health():
    """Return database connectivity status without exposing credentials."""
    configured_env = next(
        (
            name
            for name in ("TH_EVI_DB_URL", "DATABASE_URL", "POSTGRES_URL")
            if os.environ.get(name)
        ),
        None,
    )
    db_url = get_database_url()
    backend = "postgres" if db_url.startswith("postgresql+psycopg://") else "sqlite"
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
        return {
            "ok": True,
            "backend": backend,
            "configured_env": configured_env,
            "persistent": backend == "postgres",
        }
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "backend": backend,
                "configured_env": configured_env,
                "persistent": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "hint": "Set TH_EVI_DB_URL, DATABASE_URL, or POSTGRES_URL to a managed Postgres connection string for production.",
            },
        )


@app.get("/api/scenario")
def scenario(year: int = Query(2035, ge=2025, le=2050)):
    """Return comprehensive scenario: all landmarks + summary."""
    results = []
    total_daily_kwh = 0
    total_ev_visits = 0
    for lid in LANDMARK_DB:
        result = model.estimate_from_db(lid, year)
        results.append(result)
        total_daily_kwh += result.get("daily_kwh", 0)
        total_ev_visits += result.get("daily_ev_visits", 0)
    return {
        "year": year,
        "province": "เชียงใหม่",
        "landmarks": results,
        "summary": {
            "total_daily_kwh": round(total_daily_kwh, 1),
            "total_ev_visits": total_ev_visits,
            "landmark_count": len(results),
        },
    }


@app.get("/api/heatmap/chiang-mai")
def chiang_mai_heatmap(
    year: int = Query(2030, ge=2025, le=2050),
    scenario: str = Query("base", pattern="^(conservative|base|upside)$"),
    resolution_km: float = Query(1.0, gt=0, le=5),
):
    """Return Chiang Mai area-demand heat-map points."""
    return generate_chiang_mai_heatmap(
        year=year,
        scenario=scenario,
        resolution_km=resolution_km,
    )


@app.get("/api/station")
def station_forecast(
    year: int = Query(2030, ge=2025, le=2040),
    scenario: str = Query("base", pattern="^(low|base|best)$"),
    stalls: int = Query(12, ge=1, le=50),
):
    """Forecast daily demand at a charging station using fleet-based model."""
    sm = StationDemandModel(province="เชียงใหม่")
    return sm.estimate(year=year, scenario=scenario, stalls=stalls)


@app.post("/api/site-analysis")
def create_site_analysis(req: SiteAnalysisRequest):
    """Create a candidate site analysis, persist it, and return the report payload."""
    factors = {"conservative": 0.75, "base": 1.0, "upside": 1.25}
    result = _compute_site_analysis(req, raw_factor=factors[req.scenario])
    result["scenario_band"] = _scenario_band(req)
    run_id = _store_analysis(req, result)
    result["run_id"] = run_id
    result["report_url"] = f"/reports/{run_id}"
    return _json_safe(result)


@app.get("/api/sites")
def list_candidate_sites():
    """Return saved candidate sites with their latest analysis summary."""
    with session_scope() as session:
        sites = session.query(CandidateSite).order_by(CandidateSite.created_at.desc()).all()
        rows = []
        for site in sites:
            latest_run = max(site.runs, key=lambda r: r.created_at, default=None)
            latest = None
            if latest_run and latest_run.result:
                latest = {
                    "run_id": latest_run.id,
                    "year": latest_run.year,
                    "scenario": latest_run.scenario,
                    "sessions_per_day": latest_run.result.sessions_per_day,
                    "daily_kwh": latest_run.result.daily_kwh,
                    "daily_revenue": latest_run.result.daily_revenue,
                    "recommended_plugs": latest_run.result.recommended_plugs,
                    "created_at": latest_run.created_at.isoformat(),
                }
            rows.append({
                "id": site.id,
                "name": site.name,
                "lat": site.lat,
                "lon": site.lon,
                "province": site.province,
                "district": site.district,
                "zone": site.zone,
                "created_at": site.created_at.isoformat(),
                "latest": latest,
            })
        return {"sites": rows}


@app.get("/api/reports/{run_id}")
def get_report_json(run_id: int):
    """Return one saved analysis report as JSON."""
    _, result = _load_report(run_id)
    return _json_safe(result)


@app.get("/reports/{run_id}", response_class=HTMLResponse)
def report_page(run_id: int):
    """Human-readable report for one saved analysis run."""
    run, result = _load_report(run_id)
    site = result["site"]
    summary = result["summary"]
    loc = result["location_estimate"]
    cap = result["site_capture"]
    queue = result["queue"]
    band = result.get("scenario_band", {})

    def esc(value: Any) -> str:
        return html.escape(str(value))

    band_rows = "".join(
        "<tr>"
        f"<td>{esc(label.title())}</td>"
        f"<td>{esc(s['sessions_per_day'])}</td>"
        f"<td>{esc(s['daily_kwh'])}</td>"
        f"<td>{esc(s['daily_revenue'])}</td>"
        f"<td>{esc(s['recommended_plugs'])}</td>"
        "</tr>"
        for label, s in band.items()
    )

    return HTMLResponse(f"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TH-EVI Report - {esc(site['name'])}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; color: #17202a; background: #f6f7f9; }}
main {{ max-width: 1040px; margin: 0 auto; padding: 28px; }}
header {{ background: #102a43; color: white; padding: 28px; border-radius: 8px; }}
h1 {{ margin: 0 0 6px; font-size: 28px; }}
h2 {{ margin: 28px 0 10px; font-size: 18px; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }}
.metric, section {{ background: white; border: 1px solid #dde3ea; border-radius: 8px; padding: 16px; }}
.metric b {{ display: block; font-size: 24px; margin-top: 6px; }}
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }}
th, td {{ text-align: left; border-bottom: 1px solid #e6ebf0; padding: 10px; }}
th {{ background: #edf2f7; }}
.muted {{ color: #d7e2ee; }}
@media (max-width: 780px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} main {{ padding: 14px; }} }}
</style>
</head>
<body>
<main>
<header>
  <h1>{esc(site['name'])}</h1>
  <div class="muted">Run #{run.id} | Year {run.year} | Scenario {esc(run.scenario)} | {esc(run.created_at.isoformat())}</div>
  <div>Lat/Lon: {esc(site['lat'])}, {esc(site['lon'])}</div>
</header>

<div class="grid">
  <div class="metric">Sessions/day<b>{esc(summary['sessions_per_day'])}</b></div>
  <div class="metric">Energy/day<b>{esc(summary['daily_kwh'])} kWh</b></div>
  <div class="metric">Revenue/day<b>{esc(summary['daily_revenue'])} THB</b></div>
  <div class="metric">Recommended plugs<b>{esc(summary['recommended_plugs'])}</b></div>
</div>

<h2>Scenario Band</h2>
<table>
  <thead><tr><th>Scenario</th><th>Sessions/day</th><th>kWh/day</th><th>THB/day</th><th>Recommended plugs</th></tr></thead>
  <tbody>{band_rows}</tbody>
</table>

<h2>Demand & Site Capture</h2>
<section>
  <p>Area demand uses <b>{esc(loc['location_type'])}</b> with AADT <b>{esc(loc['aadt_used'])}</b>, fleet EV share <b>{esc(loc['fleet_ev_share_pct'])}%</b>, and charge probability <b>{esc(loc['charge_probability_pct'])}%</b>.</p>
  <p>Site readiness multiplier: <b>{esc(cap['readiness_multiplier'])}</b>. Competitive capture share: <b>{esc(cap['competitive_capture_share'])}</b>. Ramp-up factor: <b>{esc(cap['ramp_up_factor'])}</b>. Competitors counted: <b>{esc(cap['competitor_count'])}</b>.</p>
</section>

<h2>Queue & Operations</h2>
<section>
  <p>Peak hour: <b>{esc(queue['peak_hour'])}:00</b> with <b>{esc(queue['peak_hour_arrivals'])}</b> arrivals/hour. Service time is <b>{esc(queue['service_time_min'])}</b> minutes/session at effective charger power <b>{esc(queue['charger_kw'])}</b> kW.</p>
  <p>Installed plugs: <b>{esc(summary['installed_plugs'])}</b>. Installed peak utilization: <b>{esc(summary['installed_utilization_pct'])}%</b>.</p>
</section>
</main>
</body>
</html>
""")


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the main Leaflet map page."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>TH-EVI</h1><p>Frontend not built yet.</p>")
    return FileResponse(str(index_path))


def main():
    uvicorn.run("th_evi.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
