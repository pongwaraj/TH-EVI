"""Transparent DC screening pressure, not observed competitor sales or capacity."""

from __future__ import annotations

from math import asin, cos, exp, isfinite, radians, sin, sqrt
import re


def positive_number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) and result > 0 else None


def distance_km(lat, lon, other_lat, other_lon):
    a, b = radians(lat), radians(other_lat)
    h = sin((b - a) / 2) ** 2 + cos(a) * cos(b) * sin(radians(other_lon - lon) / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(min(1, h)))


def competitor_evidence(row: dict) -> dict:
    power_text = str(row.get("power_summary") or "")
    text = " ".join(str(row.get(k) or "") for k in
                    ("connector_summary", "power_summary", "charger_type", "charging_type"))
    assumed = bool(re.search(r"model[l]?ed|modeling assumption|interim|assumed|conservatively as", power_text, re.I))
    kw = next((v for k in ("max_kw", "power_kw", "kw")
               if (v := positive_number(row.get(k))) is not None), None)
    # Never interpret a bare number, year, or site-total rating as per-gun power.
    if kw is None and not re.search(r"\btotal\b|site power", power_text, re.I):
        values = re.findall(r"(\d+(?:\.\d+)?)\s*kW\b", power_text, re.I)
        kw = max((float(v) for v in values), default=None)
    if assumed:
        kw = None
    guns = next((v for k in ("guns", "connector_count")
                 if (v := positive_number(row.get(k))) is not None), None)
    if guns is None:
        match = re.search(r"(\d+)\s*(?:guns|heads|CCS2|DC connectors)", text, re.I)
        guns = float(match.group(1)) if match else None
    if assumed:
        guns = None
    if guns is not None and guns != int(guns):
        guns = None
    has_dc = bool(re.search(r"\bDC\b|CCS|CHAdeMO|supercharg", text, re.I))
    has_ac = bool(re.search(r"\bAC\b|type\s*2", text, re.I))
    kind = "dc" if has_dc else "ac" if has_ac else "unknown"
    public = str(row.get("public_access", "")).lower() not in {"false", "no", "private", "0"}
    status = str(row.get("verification_status") or "").lower()
    active = status not in {"closed", "removed", "offline", "inactive"}
    return {
        "station_id": row.get("station_id") or row.get("name"),
        "name": row.get("name") or row.get("station_id") or "Competitor",
        "network": row.get("network") or row.get("operator") or "unknown",
        "charging_type": kind, "max_kw": kw, "guns": guns,
        "power_evidence": "assumed_not_verified" if assumed else "specified" if kw else "unknown",
        "source_url": row.get("source_url"), "verification_status": status or "unknown",
        "direct_dc_eligible": public and active and kind == "dc" and kw is not None,
        "public_active": public and active,
    }


def dc_competition_pressure(lat: float, lon: float, rows: list[dict], radius_km: float = 3.0) -> dict:
    """Uncalibrated relative pressure; 25 kW has no artificial power floor.

    Unknowns are reported, not silently filled. The optional upper bound is a
    missing-data envelope, not a statistical prediction interval. Road detours,
    prices, queues and uptime remain unmodelled.
    """
    pressure = 0.0
    contributions, uncertain = [], []
    skipped = 0
    for row in rows:
        try:
            a, b = float(row["lat"]), float(row["lon"])
            if not (isfinite(a) and isfinite(b) and -90 <= a <= 90 and -180 <= b <= 180):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        distance = distance_km(lat, lon, a, b)
        if distance > radius_km * 3:
            continue
        item = competitor_evidence(row)
        item["distance_km"] = distance
        item["pressure"] = 0.0
        if item["direct_dc_eligible"]:
            count_factor = sqrt(item["guns"]) if item["guns"] else 1.0
            item["pressure"] = item["max_kw"] / 120.0 * count_factor * exp(-(distance / radius_km) ** 2)
            pressure += item["pressure"]
        if item["public_active"] and item["charging_type"] != "ac" and (
            not item["direct_dc_eligible"] or item["guns"] is None
        ):
            uncertain.append(item["station_id"])
        contributions.append(item)
    share = pressure / (1.0 + pressure)
    contributions.sort(key=lambda item: item["pressure"], reverse=True)
    return {
        "method": "dc_relative_pressure_v1_not_sales",
        "pressure": pressure, "competition_share": share,
        "competition_share_missing_data_bounds": [share, 1.0 if uncertain else share],
        "unknown_station_ids": uncertain, "skipped_without_coordinates": skipped,
        "contributions": contributions,
    }
