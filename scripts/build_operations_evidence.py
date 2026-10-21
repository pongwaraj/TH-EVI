"""Build aggregate-only pilot evidence from authorized read-only dashboard exports.

No database credentials, customer IDs or raw sessions are needed. The source
application retains responsibility for its Normal/meaningful-order filters.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def build_evidence(overview, meaningful):
    if overview["range"] != meaningful["range"]:
        raise ValueError("Operational exports must cover the same time range")
    total, usable = overview["kpis"], meaningful["kpis"]
    n, kwh = usable["reportSessions"], usable["reportKwh"]
    if n <= 0 or n > total["sessions"] or kwh <= 0 or kwh > total["energyKwh"] + 0.02:
        raise ValueError("Inconsistent order counts or energy totals")
    hours = overview["peakHours"]
    if sum(row["sessions"] for row in hours) != total["sessions"]:
        raise ValueError("Hourly order counts do not reconcile")
    return {
        "schema_version": 1, "province": "Chiang Mai", "station_scope": "Meta Mall only",
        "source_application": "https://ev-station-operation-team.vercel.app",
        "source_endpoints": ["/api/dashboard/overview", "/api/dashboard/customer-value"],
        "range": overview["range"], "source_coverage": overview["coverage"],
        "privacy": "aggregate_only_no_customer_order_vin_or_device_identifiers",
        "normal_orders": {"count": total["sessions"], "connector_kwh": total["energyKwh"],
                          "mean_connector_kwh": total["energyKwh"] / total["sessions"],
                          "mean_duration_minutes": total["avgDurationMinutes"],
                          "short_orders": total["shortSessions"],
                          "short_definition": "Normal; duration < 60 seconds OR energy < 1 kWh"},
        "meaningful_orders": {"count": n, "connector_kwh": kwh, "mean_connector_kwh": kwh / n,
                              "excluded_count": total["sessions"] - n,
                              "definition": "Normal; duration >= 300 seconds AND connector energy >= 1 kWh"},
        "hourly_normal_order_share": [{"bangkok_hour": row["hour"], "orders": row["sessions"],
                                        "share": row["sessions"] / total["sessions"]} for row in hours],
        "soc_distribution": None, "forecast_enabled": False,
        "limitations": ["Observed customers of one station, not all provincial EV owners.",
                        "Orders and retries are not necessarily unique visits or vehicles.",
                        "No SOC distribution is exposed by the current aggregate endpoints.",
                        "The mean duration includes Normal orders and is not mean duration of meaningful orders.",
                        "Dates with orders do not prove complete imports or station uptime.",
                        "No home access, travel distance, charger acceptance curve or new-site capture is inferred."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overview", required=True, type=Path)
    parser.add_argument("--meaningful", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_evidence(*(json.loads(p.read_text(encoding="utf-8-sig")) for p in (args.overview, args.meaningful)))
    result["extracted_at"] = datetime.now(timezone.utc).isoformat()
    result["source_sha256"] = {name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for name, p in (("overview", args.overview), ("meaningful", args.meaningful))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "mean_connector_kwh": result["meaningful_orders"]["mean_connector_kwh"]}))


if __name__ == "__main__":
    main()
