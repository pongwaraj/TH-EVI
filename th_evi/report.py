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
    data = _load_report_data(run_id)
    site = data["site"]
    run = data["run"]
    result = data["result"]
    summary = data["summary"]
    loc = data["location_estimate"]
    cap = data["site_capture"]
    rec = data.get("charger_recommendation", {})
    queue = data["queue"]
    band = data.get("scenario_band", {})
    competitors = data.get("competitors", [])
    assumptions = data.get("assumptions", {})

    html_parts = []
    html_parts.append(_build_header(site, run, summary))
    html_parts.append(_build_executive_summary(summary, rec))
    html_parts.append(_build_location_overview(site, loc, run))
    html_parts.append(_build_demand_breakdown(loc, cap))
    html_parts.append(_build_site_readiness(cap, assumptions, run))
    html_parts.append(_build_competitor_landscape(cap, competitors))
    html_parts.append(_build_charger_recommendation(rec, summary))
    html_parts.append(_build_queue_ops(queue, summary))
    html_parts.append(_build_scenario_band(band))
    html_parts.append(_build_footer(run))

    return _wrap_html("".join(html_parts))


def _load_report_data(run_id: int) -> dict[str, Any]:
    """Load report data from DB using db.py models directly."""
    with session_scope() as session:
        run = session.get(AnalysisRun, run_id)
        if run is None or run.result is None:
            raise LookupError(f"Analysis run {run_id} not found or has no result")

        result = json.loads(run.result.result_json)
        inputs = json.loads(run.inputs_snapshot_json) if run.inputs_snapshot_json else {}

        site_data = {
            "name": run.site.name,
            "lat": run.site.lat,
            "lon": run.site.lon,
            "province": run.site.province,
            "district": run.site.district or "",
            "zone": run.site.zone or "",
        }

        assumption_data = {}
        if run.site.assumptions:
            a = run.site.assumptions[0]
            assumption_data = {
                "station_format": a.station_format,
                "visibility_from_road": a.visibility_from_road,
                "access_ease": a.access_ease,
                "signage_quality": a.signage_quality,
                "tenant_strength": a.tenant_strength,
                "parking_capacity": a.parking_capacity,
                "roadside_frontage": a.roadside_frontage,
                "inside_parking_structure": a.inside_parking_structure,
                "opening_age_days": a.opening_age_days,
            }

        competitor_rows = []
        for c in run.site.competitors:
            competitor_rows.append({
                "name": c.name,
                "distance_km": c.distance_km,
                "guns": c.guns,
                "max_kw": c.max_kw,
                "brand_score": c.brand_score,
            })

        # Extract run metadata before session closes
        run_data = {
            "id": run.id,
            "year": run.year,
            "scenario": run.scenario,
            "created_at": run.created_at.isoformat() if hasattr(run, "created_at") and run.created_at else "",
        }

        return {
            "run": run_data,
            "site": site_data,
            "result": result,
            "summary": result.get("summary", {}),
            "location_estimate": result.get("location_estimate", {}),
            "site_capture": result.get("site_capture", {}),
            "charger_recommendation": result.get("charger_recommendation", {}),
            "queue": result.get("queue", {}),
            "scenario_band": result.get("scenario_band", {}),
            "competitors": competitor_rows,
            "assumptions": assumption_data,
        }


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _fmt(val: Any, decimals: int = 0) -> str:
    if val is None:
        return "—"
    try:
        f = float(val)
        if f == int(f) and decimals == 0:
            return f"{int(f):,}"
        return f"{f:,.{decimals}f}"
    except (ValueError, TypeError):
        return _esc(val)


def _utilization_color(band: str) -> str:
    band_map = {"low": "#10b981", "medium": "#f59e0b", "high": "#ef4444"}
    return band_map.get(band, "#6b7280")


def _utilization_label(band: str) -> str:
    label_map = {"low": "Low", "medium": "Medium", "high": "High"}
    return label_map.get(band, band.capitalize())


def _readiness_bar(score: float, scale: float = 2.0) -> str:
    pct = min(100, max(0, (score / scale) * 100))
    color = "#10b981" if score >= 1.0 else "#f59e0b" if score >= 0.7 else "#ef4444"
    return f"""<div class="gauge-track"><div class="gauge-fill" style="width:{pct:.0f}%;background:{color}"></div></div>"""


def _build_header(site: dict, run: dict, summary: dict) -> str:
    return f"""<header class="report-header">
  <div class="header-content">
    <div class="header-left">
      <h1>{_esc(site.get('name', 'Unnamed Site'))}</h1>
      <div class="header-meta">
        <span class="meta-badge">Run #{_esc(run.get('id', '?'))}</span>
        <span class="meta-badge">Year {_esc(run.get('year', '?'))}</span>
        <span class="meta-badge">Scenario {_esc(run.get('scenario', '?'))}</span>
        <span class="meta-badge">{_esc(run.get('created_at', ''))}</span>
      </div>
    </div>
    <div class="header-right">
      <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24' fill='none' stroke='%23ffffff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M13 2L3 14h9l-1 8 10-12h-9l1-8z'/%3E%3C/svg%3E" alt="" class="header-icon">
      <div class="header-brand">TH-EVI</div>
      <div class="header-sub">Location Analysis Report</div>
    </div>
  </div>
</header>"""


def _build_executive_summary(summary: dict, rec: dict) -> str:
    sessions = _fmt(summary.get("sessions_per_day"), 1)
    kwh = _fmt(summary.get("daily_kwh"), 0)
    revenue = _fmt(summary.get("daily_revenue"), 0)
    plugs = _esc(summary.get("recommended_plugs", "—"))

    util_band = rec.get("utilization_band", "low") if rec else "low"
    badge_color = _utilization_color(util_band)
    badge_label = _utilization_label(util_band)

    return f"""<section class="section executive-summary">
  <h2>Executive Summary</h2>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Sessions / Day</div>
      <div class="kpi-value">{sessions}</div>
      <div class="kpi-sub">Captured daily sessions</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Daily Energy</div>
      <div class="kpi-value">{kwh}</div>
      <div class="kpi-sub">kWh / day</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Daily Revenue</div>
      <div class="kpi-value">{revenue}</div>
      <div class="kpi-sub">THB / day</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Recommended Plugs</div>
      <div class="kpi-value">{plugs}</div>
      <div class="kpi-sub">
        Utilisation: <span class="util-badge" style="background:{badge_color}">{badge_label}</span>
      </div>
    </div>
  </div>
</section>"""


def _build_location_overview(site: dict, loc: dict, run: Any) -> str:
    return f"""<section class="section">
  <h2>Location Overview</h2>
  <div class="card-grid-2col">
    <div class="info-table-wrapper">
      <table class="info-table">
        <tbody>
          <tr><td class="info-label">Province</td><td>{_esc(site.get('province', '—'))}</td></tr>
          <tr><td class="info-label">District</td><td>{_esc(site.get('district', '—'))}</td></tr>
          <tr><td class="info-label">Zone</td><td>{_esc(site.get('zone', '—'))}</td></tr>
          <tr><td class="info-label">Coordinates</td><td>{_esc(site.get('lat', '—'))}, {_esc(site.get('lon', '—'))}</td></tr>
          <tr><td class="info-label">Location Type</td><td>{_esc(loc.get('location_type', '—'))}</td></tr>
          <tr><td class="info-label">Year</td><td>{_esc(run.get('year', '?'))}</td></tr>
          <tr><td class="info-label">Scenario</td><td>{_esc(run.get('scenario', '?'))}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="stats-mini-grid">
      <div class="stat-mini">
        <div class="stat-mini-value">{_fmt(loc.get('aadt_used', 0), 0)}</div>
        <div class="stat-mini-label">AADT Used</div>
      </div>
      <div class="stat-mini">
        <div class="stat-mini-value">{_fmt(loc.get('fleet_ev_share_pct', 0), 1)}%</div>
        <div class="stat-mini-label">Fleet EV Share</div>
      </div>
      <div class="stat-mini">
        <div class="stat-mini-value">{_fmt(loc.get('bev_penetration_pct', 0), 1)}%</div>
        <div class="stat-mini-label">BEV Penetration</div>
      </div>
      <div class="stat-mini">
        <div class="stat-mini-value">{_fmt(loc.get('charging_sessions_per_day', 0), 1)}</div>
        <div class="stat-mini-label">Raw Sessions / Day</div>
      </div>
    </div>
  </div>
</section>"""


def _build_demand_breakdown(loc: dict, cap: dict) -> str:
    aadt = loc.get("aadt_used", 0) or 0
    ev_share = loc.get("fleet_ev_share_pct", 0) or 0
    charge_prob = loc.get("charge_probability_pct", 0) or 0
    raw_sessions = loc.get("charging_sessions_per_day", 0) or 0

    aadt_fmt = _fmt(aadt, 0)
    ev_fmt = _fmt(ev_share, 1)
    cp_fmt = _fmt(charge_prob, 1)
    raw_fmt = _fmt(raw_sessions, 1)

    captured = cap.get("captured_daily_sessions", 0) or 0
    ramp = cap.get("ramp_up_factor", 1.0) or 1.0
    readiness = cap.get("readiness_multiplier", 1.0) or 1.0
    capture_share = cap.get("competitive_capture_share", 0) or 0
    captured_fmt = _fmt(captured, 1)

    ev_share_bar = min(100, (ev_share / 30) * 100) if ev_share else 0
    cp_bar = min(100, (charge_prob / 10) * 100) if charge_prob else 0
    read_bar = min(100, (readiness / 1.5) * 100)

    return f"""<section class="section">
  <h2>Demand Breakdown</h2>
  <div class="demand-flow">
    <div class="demand-step">
      <div class="demand-label">AADT</div>
      <div class="demand-value">{aadt_fmt}</div>
      <div class="demand-bar"><div class="bar-fill bar-blue" style="width:100%"></div></div>
      <div class="demand-arrow">×</div>
    </div>
    <div class="demand-step">
      <div class="demand-label">Fleet EV Share</div>
      <div class="demand-value">{ev_fmt}%</div>
      <div class="demand-bar"><div class="bar-fill bar-green" style="width:{ev_share_bar:.0f}%"></div></div>
      <div class="demand-arrow">×</div>
    </div>
    <div class="demand-step">
      <div class="demand-label">Charge Probability</div>
      <div class="demand-value">{cp_fmt}%</div>
      <div class="demand-bar"><div class="bar-fill bar-amber" style="width:{cp_bar:.0f}%"></div></div>
      <div class="demand-arrow">=</div>
    </div>
    <div class="demand-step demand-step-result">
      <div class="demand-label">Raw Sessions / Day</div>
      <div class="demand-value">{raw_fmt}</div>
      <div class="demand-bar"><div class="bar-fill bar-purple" style="width:100%"></div></div>
    </div>
  </div>

  <div class="demand-math">
    <code>{aadt_fmt} AADT × {ev_fmt}% EV share × {cp_fmt}% charge prob = <strong>{raw_fmt} sessions/day</strong></code>
  </div>

  <div class="capture-pipeline">
    <h3>Site Capture Pipeline</h3>
    <div class="pipeline-step">
      <span class="pipe-label">Readiness Multiplier</span>
      <span class="pipe-bar">
        <div class="demand-bar"><div class="bar-fill bar-teal" style="width:{read_bar:.0f}%"></div></div>
      </span>
      <span class="pipe-value">× {readiness:.2f}</span>
    </div>
    <div class="pipeline-step">
      <span class="pipe-label">Competitive Capture Share</span>
      <span class="pipe-bar">
        <div class="demand-bar"><div class="bar-fill bar-blue" style="width:{capture_share * 100:.0f}%"></div></div>
      </span>
      <span class="pipe-value">× {capture_share:.0%}</span>
    </div>
    <div class="pipeline-step">
      <span class="pipe-label">Ramp-up Factor</span>
      <span class="pipe-bar">
        <div class="demand-bar"><div class="bar-fill bar-green" style="width:{ramp * 100:.0f}%"></div></div>
      </span>
      <span class="pipe-value">× {ramp:.0%}</span>
    </div>
    <div class="pipeline-step pipeline-step-result">
      <span class="pipe-label pipe-label-strong">Captured Sessions / Day</span>
      <span class="pipe-bar">
        <div class="demand-bar"><div class="bar-fill bar-purple" style="width:100%"></div></div>
      </span>
      <span class="pipe-value pipe-value-strong">{captured_fmt}</span>
    </div>
  </div>
</section>"""


def _build_site_readiness(cap: dict, assumptions: dict, run: Any) -> str:
    readiness = cap.get("readiness_multiplier", 0) or 0

    visibility = assumptions.get("visibility_from_road", 0.5)
    access = assumptions.get("access_ease", 0.5)
    signage = assumptions.get("signage_quality", 0.5)
    tenant = assumptions.get("tenant_strength", 0.5)
    parking = assumptions.get("parking_capacity", 0)
    frontage = assumptions.get("roadside_frontage", False)
    inside_parking = assumptions.get("inside_parking_structure", False)
    station_format = assumptions.get("station_format", "community_mall")

    def _score_color(s: float) -> str:
        return "#10b981" if s >= 0.7 else "#f59e0b" if s >= 0.4 else "#ef4444"

    def _score_bar(s: float) -> str:
        pct = min(100, s * 100)
        color = _score_color(s)
        return f"""<div class="mini-bar-track"><div class="mini-bar-fill" style="width:{pct:.0f}%;background:{color}"></div></div>"""

    format_labels = {
        "highway_hub": "Highway Hub",
        "roadside_destination": "Roadside Destination",
        "urban_hub": "Urban Hub",
        "mall_surface_lot": "Mall Surface Lot",
        "community_mall": "Community Mall",
        "inside_parking": "Inside Parking Structure",
        "test_launch": "Test Launch",
    }

    return f"""<section class="section">
  <h2>Site Readiness</h2>
  <div class="readiness-gauge-section">
    <div class="readiness-score-block">
      <div class="readiness-score-label">Overall Readiness Multiplier</div>
      <div class="readiness-score-value" style="color:{_score_color(readiness)}">{readiness:.2f}</div>
      <div class="readiness-score-scale">scale: 0.00 – 2.00</div>
      {_readiness_bar(readiness, 2.0)}
    </div>
    <div class="readiness-format-block">
      <div class="readiness-format-label">Station Format</div>
      <div class="readiness-format-value">{format_labels.get(station_format, station_format.replace('_', ' ').title())}</div>
    </div>
  </div>

  <table class="data-table">
    <thead>
      <tr>
        <th>Component</th>
        <th>Score</th>
        <th>Bar</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Visibility from Road</td>
        <td style="color:{_score_color(visibility)};font-weight:600">{_fmt(visibility, 2)}</td>
        <td>{_score_bar(visibility)}</td>
      </tr>
      <tr>
        <td>Access Ease</td>
        <td style="color:{_score_color(access)};font-weight:600">{_fmt(access, 2)}</td>
        <td>{_score_bar(access)}</td>
      </tr>
      <tr>
        <td>Signage Quality</td>
        <td style="color:{_score_color(signage)};font-weight:600">{_fmt(signage, 2)}</td>
        <td>{_score_bar(signage)}</td>
      </tr>
      <tr>
        <td>Tenant Strength</td>
        <td style="color:{_score_color(tenant)};font-weight:600">{_fmt(tenant, 2)}</td>
        <td>{_score_bar(tenant)}</td>
      </tr>
      <tr>
        <td>Parking Capacity</td>
        <td style="font-weight:600">{parking}</td>
        <td>{_score_bar(min(1.0, parking / 50))}</td>
      </tr>
      <tr>
        <td>Roadside Frontage</td>
        <td style="font-weight:600">{'✓ Yes' if frontage else '✗ No'}</td>
        <td>—</td>
      </tr>
      <tr>
        <td>Inside Parking Structure</td>
        <td style="font-weight:600">{'✓ Yes' if inside_parking else '✗ No'}</td>
        <td>—</td>
      </tr>
    </tbody>
  </table>

  <div class="readiness-note">
    <strong>Ramp-up Factor:</strong> {_fmt(cap.get('ramp_up_factor', 1.0), 2)} —
    New stations ramp up over time. At maturity this site reaches
    {_fmt(cap.get('ramp_up_factor', 1.0) * 100, 0)}% of its full potential.
  </div>
</section>"""


def _build_competitor_landscape(cap: dict, competitors: list) -> str:
    count = cap.get("competitor_count", len(competitors))
    capture_share = cap.get("competitive_capture_share", 0) or 0

    if capture_share >= 0.6:
        pressure = "Low"
        pressure_color = "#10b981"
    elif capture_share >= 0.35:
        pressure = "Medium"
        pressure_color = "#f59e0b"
    else:
        pressure = "High"
        pressure_color = "#ef4444"

    if not competitors:
        competitor_rows = '<tr><td colspan="6" class="empty-cell">No competitor data available</td></tr>'
    else:
        rows = []
        for c in competitors:
            rows.append(f"""<tr>
  <td>{_esc(c.get('name', '—'))}</td>
  <td>{_fmt(c.get('distance_km', 0), 1)} km</td>
  <td>{_esc(c.get('guns', '—'))}</td>
  <td>{_fmt(c.get('max_kw', 0), 0)} kW</td>
  <td>{_fmt(c.get('brand_score', 0), 2)}</td>
</tr>""")
        competitor_rows = "\n".join(rows)

    return f"""<section class="section">
  <h2>Competitor Landscape</h2>
  <div class="competitor-summary">
    <div class="comp-summary-item">
      <span class="comp-summary-label">Competitors within range</span>
      <span class="comp-summary-value">{count}</span>
    </div>
    <div class="comp-summary-item">
      <span class="comp-summary-label">Competitive capture share</span>
      <span class="comp-summary-value">{_fmt(capture_share * 100, 0)}%</span>
    </div>
    <div class="comp-summary-item">
      <span class="comp-summary-label">Competitive pressure</span>
      <span class="comp-summary-value"><span class="util-badge" style="background:{pressure_color}">{pressure}</span></span>
    </div>
  </div>

  <table class="data-table">
    <thead>
      <tr>
        <th>Name</th>
        <th>Distance</th>
        <th>Guns</th>
        <th>Power</th>
        <th>Brand Score</th>
      </tr>
    </thead>
    <tbody>
      {competitor_rows}
    </tbody>
  </table>
</section>"""


def _build_charger_recommendation(rec: dict, summary: dict) -> str:
    if not rec:
        return ""

    util_band = rec.get("utilization_band", "low")
    badge_color = _utilization_color(util_band)
    badge_label = _utilization_label(util_band)
    arch = rec.get("architecture", "—")
    arch_label = arch.replace("_", " ").title()

    return f"""<section class="section">
  <h2>Charger Recommendation</h2>
  <div class="card-grid-2col">
    <table class="data-table">
      <thead>
        <tr>
          <th>Parameter</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Architecture</td><td>{_esc(arch_label)}</td></tr>
        <tr><td>Recommended Ports</td><td>{_esc(rec.get('recommended_ports', '—'))}</td></tr>
        <tr><td>Cabinet Count</td><td>{_esc(rec.get('cabinet_count', '—'))}</td></tr>
        <tr><td>Cabinet Power</td><td>{_fmt(rec.get('cabinet_kw', 0), 0)} kW</td></tr>
        <tr><td>Dispenser Count</td><td>{_esc(rec.get('dispenser_count', '—'))}</td></tr>
        <tr><td>Total Site Power</td><td>{_fmt(rec.get('total_site_kw', 0), 0)} kW</td></tr>
        <tr><td>Max kW per Port</td><td>{_fmt(rec.get('max_kw_per_port', 0), 0)} kW</td></tr>
      </tbody>
    </table>
    <div class="util-section">
      <div class="util-band-box">
        <div class="util-band-label">Utilization Band</div>
        <div class="util-band-value" style="color:{badge_color};font-size:28px;font-weight:700">{badge_label}</div>
        <span class="util-badge" style="background:{badge_color};font-size:14px;padding:4px 14px">{badge_label} utilization</span>
      </div>
      <div class="util-metrics">
        <div class="util-metric">
          <div class="util-metric-value">{_fmt(rec.get('sessions_per_port_day', 0), 1)}</div>
          <div class="util-metric-label">Sessions / Port / Day</div>
        </div>
        <div class="util-metric">
          <div class="util-metric-value">{_fmt(rec.get('kwh_per_port_day', 0), 1)}</div>
          <div class="util-metric-label">kWh / Port / Day</div>
        </div>
      </div>
      <div class="install-compare">
        <div class="install-row">
          <span>Recommended Plugs</span>
          <span class="install-value">{_esc(summary.get('recommended_plugs', '—'))}</span>
        </div>
        <div class="install-row">
          <span>Installed Plugs</span>
          <span class="install-value">{_esc(summary.get('installed_plugs', '—'))}</span>
        </div>
      </div>
    </div>
  </div>
  {f'<div class="ref-format"><strong>Reference Format:</strong> {_esc(rec.get("reference_format", ""))}</div>' if rec.get("reference_format") else ''}
</section>"""


def _build_queue_ops(queue: dict, summary: dict) -> str:
    peak_hour = queue.get("peak_hour", 0) or 0
    arrivals = queue.get("peak_hour_arrivals", 0) or 0
    service_time = queue.get("service_time_min", 0) or 0
    charger_kw = queue.get("charger_kw", 0) or 0
    util_pct = summary.get("installed_utilization_pct", 0) or 0

    if util_pct >= 80:
        util_color = "#ef4444"
        util_text = "High"
    elif util_pct >= 50:
        util_color = "#f59e0b"
        util_text = "Medium"
    else:
        util_color = "#10b981"
        util_text = "Low"

    return f"""<section class="section">
  <h2>Queue &amp; Operations</h2>
  <div class="queue-grid">
    <div class="queue-card">
      <div class="queue-card-label">Peak Hour</div>
      <div class="queue-card-value">{peak_hour}:00</div>
    </div>
    <div class="queue-card">
      <div class="queue-card-label">Arrivals at Peak</div>
      <div class="queue-card-value">{_fmt(arrivals, 1)}</div>
      <div class="queue-card-sub">vehicles / hour</div>
    </div>
    <div class="queue-card">
      <div class="queue-card-label">Service Time</div>
      <div class="queue-card-value">{_fmt(service_time, 0)}</div>
      <div class="queue-card-sub">minutes / session</div>
    </div>
    <div class="queue-card">
      <div class="queue-card-label">Charger Power</div>
      <div class="queue-card-value">{_fmt(charger_kw, 0)}</div>
      <div class="queue-card-sub">kW</div>
    </div>
  </div>
  <div class="util-bar-section">
    <div class="util-bar-label">Installed Peak Utilization</div>
    <div class="util-bar-track">
      <div class="util-bar-fill" style="width:{min(100, util_pct):.0f}%;background:{util_color}"></div>
    </div>
    <div class="util-bar-value" style="color:{util_color};font-weight:700">{_fmt(util_pct, 1)}% — {util_text}</div>
  </div>
</section>"""


def _build_scenario_band(band: dict) -> str:
    if not band:
        return ""

    scenarios = ["conservative", "base", "upside"]
    labels = {"conservative": "Conservative", "base": "Base", "upside": "Upside"}

    rows = []
    for key in scenarios:
        s = band.get(key, {})
        is_base = key == "base"
        row_class = ' class="scenario-base-row"' if is_base else ""
        rows.append(f"""<tr{row_class}>
  <td><strong>{labels.get(key, key.title())}</strong>{' <span class="scenario-badge">Recommended</span>' if is_base else ''}</td>
  <td>{_fmt(s.get('sessions_per_day', 0), 1)}</td>
  <td>{_fmt(s.get('daily_kwh', 0), 0)}</td>
  <td>{_fmt(s.get('daily_revenue', 0), 0)}</td>
  <td>{_esc(s.get('recommended_plugs', '—'))}</td>
</tr>""")

    band_rows = "\n".join(rows)

    conservative = band.get("conservative", {})
    upside = band.get("upside", {})
    min_rev = conservative.get("daily_revenue", 0) or 0
    max_rev = upside.get("daily_revenue", 0) or 0

    return f"""<section class="section">
  <h2>Scenario Analysis</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>Scenario</th>
        <th>Sessions / Day</th>
        <th>kWh / Day</th>
        <th>THB / Day</th>
        <th>Recommended Plugs</th>
      </tr>
    </thead>
    <tbody>
      {band_rows}
    </tbody>
  </table>
  <div class="scenario-range">
    <strong>Revenue Range:</strong>
    {_fmt(min_rev, 0)} – {_fmt(max_rev, 0)} THB / day
    ({_fmt(min_rev * 30, 0)} – {_fmt(max_rev * 30, 0)} THB / month)
  </div>
</section>"""


def _build_footer(run: Any) -> str:
    now = datetime.now(timezone.utc)
    model_ver = getattr(run, "model_version", "0.2.0")
    return f"""<footer class="report-footer">
  <div class="footer-content">
    <div class="footer-left">
      Generated: {now.strftime('%d %B %Y, %H:%M UTC')}
    </div>
    <div class="footer-right">
      TH-EVI Model v{_esc(model_ver)} | Analysis Run #{_esc(run.get('id', '?'))}
    </div>
  </div>
  <div class="footer-disclaimer">
    <strong>Disclaimer:</strong> This report is generated by the TH-EVI forecasting model and is
    for planning purposes only. Actual results may vary based on market conditions, regulatory changes,
    and site-specific factors. Assumptions should be reviewed and validated before use in investment
    decisions.
  </div>
</footer>"""


def _wrap_html(body: str) -> str:
    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TH-EVI Location Analysis Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  font-family: 'Segoe UI', Tahoma, 'Sarabun', Arial, sans-serif;
  color: #1e293b;
  background: #f1f5f9;
  line-height: 1.6;
}}

.report-header {{
  background: #102a43;
  color: #ffffff;
  padding: 28px 36px;
  border-radius: 0;
}}

.header-content {{
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}}

.header-left h1 {{
  font-size: 26px;
  font-weight: 700;
  margin-bottom: 8px;
  letter-spacing: -0.3px;
}}

.header-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}

.meta-badge {{
  background: rgba(255,255,255,0.15);
  color: #e2e8f0;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
}}

.header-right {{
  text-align: right;
}}

.header-icon {{
  width: 32px;
  height: 32px;
  margin-bottom: 4px;
  opacity: 0.85;
}}

.header-brand {{
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 1px;
}}

.header-sub {{
  font-size: 12px;
  color: #94a3b8;
  letter-spacing: 0.5px;
}}

.section {{
  max-width: 1100px;
  margin: 24px auto;
  background: #ffffff;
  border-radius: 8px;
  padding: 28px 32px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}

.section h2 {{
  font-size: 18px;
  font-weight: 700;
  color: #102a43;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid #e2e8f0;
}}

.section h3 {{
  font-size: 15px;
  font-weight: 600;
  color: #334155;
  margin: 16px 0 10px;
}}

/* KPI Grid */
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}}

.kpi-card {{
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}}

.kpi-label {{
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}}

.kpi-value {{
  font-size: 32px;
  font-weight: 800;
  color: #102a43;
  line-height: 1.2;
}}

.kpi-sub {{
  font-size: 12px;
  color: #94a3b8;
  margin-top: 6px;
}}

/* Util Badge */
.util-badge {{
  display: inline-block;
  color: #ffffff;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}}

/* Card Grid */
.card-grid-2col {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}}

/* Tables */
.data-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}}

.data-table thead th {{
  background: #f1f5f9;
  color: #475569;
  font-weight: 600;
  text-align: left;
  padding: 10px 14px;
  border-bottom: 2px solid #e2e8f0;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}}

.data-table tbody td {{
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}}

.data-table tbody tr:last-child td {{
  border-bottom: none;
}}

.data-table tbody tr:hover {{
  background: #f8fafc;
}}

.empty-cell {{
  text-align: center;
  color: #94a3b8;
  font-style: italic;
  padding: 24px !important;
}}

/* Info Table */
.info-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}}

.info-table td {{
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
}}

.info-label {{
  font-weight: 600;
  color: #64748b;
  width: 40%;
}}

/* Stats Mini Grid */
.stats-mini-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}}

.stat-mini {{
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}}

.stat-mini-value {{
  font-size: 24px;
  font-weight: 700;
  color: #102a43;
}}

.stat-mini-label {{
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}}

/* Demand Flow */
.demand-flow {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}}

.demand-step {{
  flex: 1;
  min-width: 160px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  position: relative;
}}

.demand-step-result {{
  background: #eef2ff;
  border-color: #a5b4fc;
}}

.demand-label {{
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}}

.demand-value {{
  font-size: 22px;
  font-weight: 800;
  color: #102a43;
  margin-bottom: 10px;
}}

.demand-bar {{
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}}

.bar-fill {{
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}}

.bar-blue {{ background: #3b82f6; }}
.bar-green {{ background: #10b981; }}
.bar-amber {{ background: #f59e0b; }}
.bar-purple {{ background: #8b5cf6; }}
.bar-teal {{ background: #14b8a6; }}

.demand-arrow {{
  font-size: 20px;
  font-weight: 700;
  color: #94a3b8;
  text-align: center;
  padding: 20px 0;
  min-width: 24px;
}}

.demand-math {{
  background: #f1f5f9;
  border-radius: 8px;
  padding: 14px 18px;
  font-size: 14px;
  color: #475569;
  margin-bottom: 20px;
}}

.demand-math code {{
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
}}

.demand-math strong {{
  color: #102a43;
}}

/* Capture Pipeline */
.capture-pipeline {{
  margin-top: 12px;
}}

.pipeline-step {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}}

.pipeline-step-result {{
  border-bottom: none;
}}

.pipe-label {{
  flex: 0 0 220px;
  font-size: 13px;
  color: #475569;
}}

.pipe-label-strong {{
  font-weight: 700;
  color: #102a43;
}}

.pipe-bar {{
  flex: 1;
}}

.pipe-value {{
  flex: 0 0 80px;
  text-align: right;
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}}

.pipe-value-strong {{
  font-size: 18px;
  font-weight: 800;
  color: #102a43;
}}

/* Readiness */
.readiness-gauge-section {{
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}}

.readiness-score-block {{
  flex: 1;
  min-width: 280px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}}

.readiness-score-label {{
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 4px;
}}

.readiness-score-value {{
  font-size: 42px;
  font-weight: 800;
  line-height: 1.1;
}}

.readiness-score-scale {{
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 14px;
}}

.readiness-format-block {{
  flex: 0 0 240px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
}}

.readiness-format-label {{
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 6px;
}}

.readiness-format-value {{
  font-size: 18px;
  font-weight: 700;
  color: #102a43;
}}

.gauge-track {{
  height: 14px;
  background: #e2e8f0;
  border-radius: 7px;
  overflow: hidden;
}}

.gauge-fill {{
  height: 100%;
  border-radius: 7px;
  transition: width 0.5s;
}}

.mini-bar-track {{
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
  width: 120px;
}}

.mini-bar-fill {{
  height: 100%;
  border-radius: 3px;
}}

.readiness-note {{
  margin-top: 14px;
  padding: 12px 16px;
  background: #fefce8;
  border: 1px solid #fde68a;
  border-radius: 6px;
  font-size: 13px;
  color: #713f12;
}}

/* Competitor */
.competitor-summary {{
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}}

.comp-summary-item {{
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px 20px;
  flex: 1;
  min-width: 180px;
  text-align: center;
}}

.comp-summary-label {{
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}}

.comp-summary-value {{
  font-size: 24px;
  font-weight: 800;
  color: #102a43;
}}

/* Charger Recommendation */
.util-section {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}

.util-band-box {{
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}}

.util-band-label {{
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 8px;
}}

.util-metrics {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}}

.util-metric {{
  text-align: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
}}

.util-metric-value {{
  font-size: 22px;
  font-weight: 800;
  color: #102a43;
}}

.util-metric-label {{
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}}

.install-compare {{
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 18px;
}}

.install-row {{
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
  color: #475569;
}}

.install-value {{
  font-weight: 700;
  color: #102a43;
}}

.ref-format {{
  margin-top: 14px;
  padding: 12px 16px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  font-size: 13px;
  color: #1e40af;
}}

/* Queue */
.queue-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}}

.queue-card {{
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}}

.queue-card-label {{
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}}

.queue-card-value {{
  font-size: 28px;
  font-weight: 800;
  color: #102a43;
}}

.queue-card-sub {{
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}}

.util-bar-section {{
  margin-top: 8px;
}}

.util-bar-label {{
  font-size: 14px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}}

.util-bar-track {{
  height: 20px;
  background: #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}}

.util-bar-fill {{
  height: 100%;
  border-radius: 10px;
  transition: width 0.5s;
}}

.util-bar-value {{
  margin-top: 6px;
  font-size: 14px;
}}

/* Scenario */
.scenario-base-row {{
  background: #eff6ff;
}}

.scenario-base-row td {{
  border-bottom: 2px solid #bfdbfe;
}}

.scenario-badge {{
  display: inline-block;
  background: #3b82f6;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 6px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}}

.scenario-range {{
  margin-top: 14px;
  padding: 12px 16px;
  background: #fefce8;
  border: 1px solid #fde68a;
  border-radius: 6px;
  font-size: 14px;
  color: #713f12;
}}

/* Footer */
.report-footer {{
  max-width: 1100px;
  margin: 24px auto;
  padding: 0 32px 32px;
}}

.footer-content {{
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #64748b;
  padding: 16px 0;
  border-top: 1px solid #e2e8f0;
}}

.footer-disclaimer {{
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
  margin-top: 8px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 6px;
}}

/* Responsive */
@media (max-width: 900px) {{
  .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .card-grid-2col {{ grid-template-columns: 1fr; }}
  .queue-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .demand-flow {{ flex-direction: column; align-items: stretch; }}
  .demand-arrow {{ padding: 4px 0; transform: rotate(90deg); }}
  .pipeline-step {{ flex-wrap: wrap; gap: 6px; }}
  .pipe-label {{ flex-basis: 100%; }}
  .readiness-gauge-section {{ flex-direction: column; }}
  .demand-step {{ min-width: unset; }}
}}

@media (max-width: 540px) {{
  .kpi-grid {{ grid-template-columns: 1fr; }}
  .queue-grid {{ grid-template-columns: 1fr; }}
  .stats-mini-grid {{ grid-template-columns: 1fr; }}
  .section {{ padding: 18px 16px; }}
  .report-header {{ padding: 20px 16px; }}
  .header-content {{ flex-direction: column; text-align: center; }}
  .header-right {{ text-align: center; }}
  .competitor-summary {{ flex-direction: column; }}
  .util-metrics {{ grid-template-columns: 1fr; }}
}}

@media print {{
  body {{ background: #ffffff !important; }}
  .section {{ box-shadow: none !important; border: 1px solid #e2e8f0 !important; break-inside: avoid; }}
  .report-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .util-badge {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .bar-fill {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .gauge-fill {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .mini-bar-fill {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .util-bar-fill {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .scenario-base-row {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .scenario-badge {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
}}
</style>
</head>
<body>
{body}
</body>
</html>"""
