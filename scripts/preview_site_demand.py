"""Run the same explicit site-transfer request used by the API, without a server."""

import argparse
import json
from pathlib import Path

from th_evi.api import SiteDemandPreviewRequest, charging_site_preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = SiteDemandPreviewRequest(**json.loads(args.request.read_text(encoding="utf-8")))
    result = charging_site_preview(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "scenarios": [
        {"name": row["name"], "event_equivalents_per_day": round(row["charging_event_equivalents_per_day"], 2),
         "connector_kwh_per_day": round(row["site_served_connector_kwh_per_day"], 2)}
        for row in result["scenarios"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
