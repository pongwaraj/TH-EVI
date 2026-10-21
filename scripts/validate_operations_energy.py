"""Temporal holdout for conditional kWh per meaningful order at one station."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def validate_mean_order_energy(train: dict, holdout: dict) -> dict:
    periods = (train["range"], holdout["range"])
    if periods[0]["to"] >= periods[1]["from"]:
        raise ValueError("Training and holdout periods must be distinct and ordered")
    values = []
    for payload in (train, holdout):
        months = payload["averages"]
        if months["excludedMonths"] or not months["fullMonths"]:
            raise ValueError("Only complete calendar months may be evaluated")
        n = payload["kpis"]["reportSessions"]
        energy = payload["kpis"]["reportKwh"]
        if n <= 0 or energy <= 0:
            raise ValueError("Positive meaningful-order count and energy are required")
        values.append((n, energy))
    (train_n, train_kwh), (test_n, test_kwh) = values
    train_mean, test_mean = train_kwh / train_n, test_kwh / test_n
    predicted_test_kwh = train_mean * test_n
    baseline_kwh = 35 * test_n
    return {
        "schema_version": 1, "province": "Chiang Mai", "station_scope": "Meta Mall only",
        "target": "connector_kwh_per_meaningful_order_conditional_on_an_order",
        "stations_in_evaluation": 1, "station_demand_holdout_ready": False,
        "train": {"range": periods[0], "full_months": train["averages"]["fullMonths"],
                  "meaningful_orders": train_n, "connector_kwh": train_kwh,
                  "mean_connector_kwh_per_order": train_mean},
        "holdout": {"range": periods[1], "full_months": holdout["averages"]["fullMonths"],
                    "meaningful_orders": test_n, "connector_kwh": test_kwh,
                    "mean_connector_kwh_per_order": test_mean},
        "prediction_using_train_mean": {
            "connector_kwh": predicted_test_kwh,
            "signed_error_kwh": predicted_test_kwh - test_kwh,
            "absolute_percentage_error": abs(predicted_test_kwh - test_kwh) / test_kwh,
        },
        "illustrative_35_kwh_per_order_comparator": {
            "connector_kwh": baseline_kwh,
            "signed_error_kwh": baseline_kwh - test_kwh,
            "absolute_percentage_error": abs(baseline_kwh - test_kwh) / test_kwh,
        },
        "forecast_enabled": False,
        "limitations": [
            "One station, one holdout month, and meaningful orders conditional on observed visits only.",
            "This does not validate visit frequency, station choice, province-wide session size or any new site.",
            "The 35 kWh comparator assumes 35 kWh per order; proposal values stated per vehicle are not directly equivalent.",
            "No station uptime or import-completeness proof is available from this aggregate endpoint.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    train = json.loads(args.train.read_text(encoding="utf-8-sig"))
    holdout = json.loads(args.holdout.read_text(encoding="utf-8-sig"))
    result = validate_mean_order_energy(train, holdout)
    result["validated_at"] = datetime.now(timezone.utc).isoformat()
    result["source_application"] = "EV Station Operation Team"
    result["source_endpoints"] = ["/api/dashboard/customer-value"]
    result["source_sha256"] = {"train": hashlib.sha256(args.train.read_bytes()).hexdigest(),
                               "holdout": hashlib.sha256(args.holdout.read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"train_mean": result["train"]["mean_connector_kwh_per_order"],
                      "holdout_mean": result["holdout"]["mean_connector_kwh_per_order"],
                      "holdout_absolute_percentage_error": result["prediction_using_train_mean"]["absolute_percentage_error"]}))


if __name__ == "__main__":
    main()
