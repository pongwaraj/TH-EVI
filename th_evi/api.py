"""TH-EVI FastAPI server — EV charging demand forecast for Thailand."""

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn, os, json
from pathlib import Path

from .location import LocationDemandModel, LANDMARK_DB, StationDemandModel
from .data import (
    load_osm_charging_stations,
    get_chiang_mai_district_population,
    get_cm_highway_aadt,
    load_doh_aadt,
)

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


# ── API Endpoints ──────────────────────────────────────────────


@app.get("/api/landmarks")
def list_landmarks():
    """Return all predefined landmarks."""
    return [
        {"id": lid, **meta}
        for lid, meta in LANDMARK_DB.items()
    ]


@app.get("/api/landmarks/{location_id}")
def estimate_landmark(location_id: str, year: int = Query(2035, ge=2025, le=2050)):
    """Estimate EV demand at a predefined landmark."""
    result = model.estimate_from_db(location_id, year)
    return result


@app.post("/api/estimate")
def estimate_location(req: EstimateRequest):
    """Estimate EV demand at an arbitrary lat/lon."""
    result = model.estimate(req.lat, req.lon, req.year, req.location_type, req.aadt)
    return result


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


@app.get("/api/scenario")
def scenario(year: int = Query(2035, ge=2025, le=2050)):
    """Return comprehensive scenario: all landmarks + summary."""
    results = []
    total_daily_kwh = 0
    total_ev_visits = 0
    for lid in LANDMARK_DB:
        r = model.estimate_from_db(lid, year)
        results.append(r)
        total_daily_kwh += r.get("daily_kwh", 0)
        total_ev_visits += r.get("daily_ev_visits", 0)
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


@app.get("/api/station")
def station_forecast(
    year: int = Query(2030, ge=2025, le=2040),
    scenario: str = Query("base", pattern="^(low|base|best)$"),
    stalls: int = Query(12, ge=1, le=50),
):
    """Forecast daily demand at a charging station using fleet-based model."""
    sm = StationDemandModel(province="เชียงใหม่")
    result = sm.estimate(year=year, scenario=scenario, stalls=stalls)
    return result


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the main Leaflet map page."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>TH-EVI</h1><p>Frontend not built yet. Run: python -m th_evi.api</p>")
    return FileResponse(str(index_path))


def main():
    uvicorn.run("th_evi.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
