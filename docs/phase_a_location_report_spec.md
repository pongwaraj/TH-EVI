# Phase A: Location Analysis Report — Implementation Spec

## Objective

Build an **executive-ready Location Analysis Report** for EV charging sites in Thailand. The report is a self-contained HTML page that loads data from an existing analysis run and renders it in a professional, printable layout.

## Existing Data (from `/api/reports/{run_id}`)

The API already returns this JSON structure:

```
{
  "scenario": "base",
  "year": 2035,
  "site": {
    "name": "...",
    "lat": 18.xxx, "lon": 98.xxx,
    "province": "...", "district": "...", "zone": "..."
  },
  "location_estimate": {
    "location_type": "highway|city_center|destination|suburban",
    "aadt_used": 69988,
    "fleet_ev_share_pct": 14.2,
    "charge_probability_pct": 2.8,
    "charging_sessions_per_day": 28.5,
    "bev_penetration_pct": 8.1
  },
  "site_capture": {
    "captured_daily_sessions": 18.2,
    "daily_kwh": 582.4,
    "daily_revenue": 3785.6,
    "competitive_capture_share": 0.38,
    "readiness_multiplier": 0.72,
    "ramp_up_factor": 0.85,
    "competitor_count": 4,
    "effective_kw_at_expected_load": 120.0,
    "capture_reasoning": [...]
  },
  "charger_recommendation": {
    "recommended_ports": 6,
    "architecture": "distributed",
    "cabinet_count": 3,
    "cabinet_kw": 240,
    "dispenser_count": 6,
    "guns_per_dispenser": 2,
    "total_site_kw": 720,
    "max_kw_per_port": 120,
    "sessions_per_port_day": 3.0,
    "kwh_per_port_day": 97.1,
    "utilization_band": "low|medium|high",
    "reference_format": "community_mall"
  },
  "queue": {
    "peak_hour": 17,
    "peak_hour_arrivals": 2.7,
    "recommended_plugs": 6,
    "service_time_min": 16,
    "charger_kw": 120.0,
    "installed_at_peak": {...}
  },
  "summary": {
    "sessions_per_day": 18.2,
    "daily_kwh": 582.4,
    "daily_revenue": 3785.6,
    "capture_share": 0.38,
    "readiness_multiplier": 0.72,
    "recommended_plugs": 6,
    "installed_plugs": 4,
    "recommended_architecture": "distributed",
    "recommended_total_site_kw": 720,
    "recommended_cabinet_count": 3,
    "peak_hour": 17,
    "peak_hour_arrivals": 2.7,
    "installed_utilization_pct": 45.2,
    "kwh_per_port_day": 97.1,
    "sessions_per_port_day": 3.0
  },
  "scenario_band": {
    "conservative": { "sessions_per_day": ..., "daily_kwh": ..., ... },
    "base": { ... },
    "upside": { ... }
  }
}
```

## What to Build

### 1. NEW module: `th_evi/report.py`

A function `generate_location_report(run_id: int) -> str` that:
- Loads the report data via `_load_report()` (import from api.py, or better — load directly from DB using the existing db.py models)
- Renders a complete HTML page (inline CSS, no external deps)
- Returns the HTML string

### 2. OR better: Add rendering directly into the existing `api.py`

Modify the existing `/reports/{run_id}` endpoint (line 964) to use a new professional template instead of the current basic one.

**Recommendation:** Create a new endpoint `/reports/v2/{run_id}` so both old and new coexist, then we can switch after verification.

### 3. Report Sections (in order)

#### a) Header / Executive Summary
- Dark header bar with site name, run ID, date
- 4 big KPI cards: Sessions/day, Daily kWh, Daily Revenue (THB), Recommended Plugs
- Color-coded "score badge" (e.g., green/amber/red based on utilization band)

#### b) Location Overview
- Table with: Province, District, Zone, Coordinates, Location Type, Year, Scenario
- A small inline Leaflet map OR a static map image (if possible)
- Quick stats: AADT used, Fleet EV Share, BEV Penetration

#### c) Demand Breakdown
- Visual flow: AADT → Fleet EV Share → Charge Probability → Raw Sessions
- Percentage/progression bars for each step
- Show the math: e.g., "69,988 AADT × 14.2% EV share × 2.8% charge prob = 28.5 sessions/day"

#### d) Site Readiness Score
- Gauge/progress bar showing overall readiness multiplier (0-2 scale)
- Detail table of components: Visibility, Access, Signage, Tenant, Frontage, Parking
- Format interpretation (Community Mall, Highway Hub, etc.)
- Ramp-up factor explanation (new stations ramp up over time)

#### e) Competitor Landscape
- Table of competitors: Name, Distance, Guns, Power, Brand Score, Corridor
- Summary metric: "4 competitors within 5 km, competitive capture share: 38%"
- Visual indicator of competitive pressure (low/medium/high)

#### f) Charger Recommendation
- Equipment spec table: Architecture, Cabinet count, Dispensers, Total kW
- Utilization band badge (low/medium/high with color)
- Per-port metrics: sessions/port/day, kWh/port/day
- Recommended vs installed comparison

#### g) Queue & Operations
- Peak hour visualization (simple text-based or progress bar)
- Arrivals per hour at peak, service time, wait probability
- Utilization rate with color coding

#### h) 3-Scenario Band
- Table comparing Conservative / Base / Upside
- Columns: Sessions/day, kWh/day, THB/day, Recommended plugs
- Base scenario highlighted
- Revenue range: "1.1M - 1.8M THB/month"

#### i) Footer
- Generated timestamp
- Disclaimer text (TH-EVI model v0.2, assumptions apply)

### 4. Design Requirements

- **Dark professional theme** (navy/dark blue header, white cards)
- **Print-friendly** — use `@media print` CSS to hide non-essential elements
- **Responsive** — works on mobile and desktop
- **No external dependencies** — pure inline CSS (no Bootstrap, no CDN)
- **Thai language support** — content is in English for now, but font stack must support Thai (use system fonts: `Segoe UI`, `Tahoma`, `Sarabun`, sans-serif)
- **Color system:**
  - Primary: `#102a43` (dark navy)
  - Accent: `#3b82f6` (blue)
  - Success: `#10b981` (green for good metrics)
  - Warning: `#f59e0b` (amber for medium)
  - Danger: `#ef4444` (red for poor)
  - Background: `#f1f5f9`

## Implementation

### Approach: Create new `report.py` module, then add a new endpoint

```
C:\Project\TH-EVI\th_evi\
├── report.py          ← NEW: location report renderer
```

### `report.py` Structure

```python
"""Location Analysis Report — executive-ready HTML renderer."""

from __future__ import annotations
import html
import json
import logging
from datetime import datetime, timezone
from typing import Any

from .db import AnalysisRun, session_scope

logger = logging.getLogger(__name__)


def generate_location_report(run_id: int) -> str:
    """Generate a complete HTML report for an analysis run.
    
    Args:
        run_id: The analysis run ID from the database.
    
    Returns:
        Self-contained HTML string.
    """
    run, result = _load_report_data(run_id)
    site = result["site"]
    summary = result["summary"]
    loc = result["location_estimate"]
    cap = result["site_capture"]
    rec = result.get("charger_recommendation", {})
    queue = result["queue"]
    band = result.get("scenario_band", {})
    
    html_parts = []
    html_parts.append(_build_header(site, run, summary))
    html_parts.append(_build_executive_summary(summary, rec))
    html_parts.append(_build_location_overview(site, loc, run))
    html_parts.append(_build_demand_breakdown(loc))
    html_parts.append(_build_site_readiness(cap))
    html_parts.append(_build_competitor_landscape(cap, result.get("competitors", [])))
    html_parts.append(_build_charger_recommendation(rec, summary))
    html_parts.append(_build_queue_ops(queue, summary))
    html_parts.append(_build_scenario_band(band))
    html_parts.append(_build_footer(run))
    
    return _wrap_html("".join(html_parts))


def _wrap_html(body: str) -> str:
    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TH-EVI Location Report</title>
<style>
/* === CSS === */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Tahoma, 'Sarabun', Arial, sans-serif; color: #1e293b; background: #f1f5f9; }}
...
</style>
</head>
<body>
{body}
</body>
</html>"""


def _load_report_data(run_id: int) -> tuple[Any, dict]:
    """Load report from DB."""
    ...

# Each section builder returns an HTML string
def _build_header(...) -> str: ...
def _build_executive_summary(...) -> str: ...
def _build_location_overview(...) -> str: ...
def _build_demand_breakdown(...) -> str: ...
def _build_site_readiness(...) -> str: ...
def _build_competitor_landscape(...) -> str: ...
def _build_charger_recommendation(...) -> str: ...
def _build_queue_ops(...) -> str: ...
def _build_scenario_band(...) -> str: ...
def _build_footer(...) -> str: ...
```

### Then add this route to `th_evi/api.py`:

```python
from .report import generate_location_report

@app.get("/reports/v2/{run_id}", response_class=HTMLResponse)
def location_report_v2(run_id: int):
    """Executive-ready location analysis report."""
    return generate_location_report(run_id)
```

## Testing

1. Start the API: `python -m th_evi.api`
2. Create a site analysis via POST to `/api/site-analysis` (use existing test data or the web UI)
3. Open `http://localhost:8000/reports/v2/{run_id}` in browser
4. Verify all sections render with correct data
5. Test print/PDF (Ctrl+P → Save as PDF)
6. Test on mobile viewport

## Acceptance Criteria

- [ ] All sections render with real data from the API
- [ ] Executive summary shows 4 KPI cards
- [ ] Demand breakdown shows the math pipeline
- [ ] Readiness score has a visual gauge
- [ ] Competitor table renders
- [ ] Charger recommendation with utilization band
- [ ] 3-scenario band table works
- [ ] Print layout (CSS @media print)
- [ ] Responsive (mobile + desktop)
- [ ] No external CDN dependencies
- [ ] Thai font support
