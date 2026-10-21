"""Road-distance examples, not observed OD frequencies or provincial daily km."""

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DESTINATIONS = ("thapae_gate", "cmu_main_campus", "maya_lifestyle_mall",
                "central_festival_chiangmai", "maharaj_medical_cluster")


def route_rows(origins, destinations, matrix):
    points = origins + destinations
    if matrix.get("code") != "Ok" or matrix.get("fallback_speed_cells"):
        raise ValueError("A real road-routing distance matrix is required; no speed or straight-line fallback")
    n = len(points)
    for key in ("distances", "durations"):
        if len(matrix[key]) != n or any(len(row) != n for row in matrix[key]):
            raise ValueError("Routing matrix dimensions do not match the input points")
    rows = []
    # Both suburban-to-city and city-to-major-destination examples; no frequency weights.
    pairs = [(i, j) for i in range(len(origins)) for j in range(len(origins), n)]
    pairs.extend((len(origins), j) for j in range(len(origins)+1, n))
    for i, j in pairs:
        outward, back = matrix["distances"][i][j], matrix["distances"][j][i]
        snap = max(matrix["sources"][i]["distance"], matrix["sources"][j]["distance"])
        supported = outward is not None and back is not None and snap <= 250
        rows.append({"origin_id": points[i]["id"], "destination_id": points[j]["id"],
                     "outbound_road_km": outward / 1000 if supported else None,
                     "return_road_km": back / 1000 if supported else None,
                     "round_trip_road_km": (outward + back) / 1000 if supported else None,
                     "outbound_free_flow_minutes": matrix["durations"][i][j] / 60 if supported else None,
                     "max_road_snap_metres": snap,
                     "status": "road_distance_proxy" if supported else "route_or_entrance_review_required",
                     "trip_frequency_per_vehicle_day": None})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, help="Use a saved OSRM response for reproducible/offline checks")
    parser.add_argument("--output", type=Path, default=ROOT / "data/chiang_mai_travel_routes.json")
    args = parser.parse_args()
    with (ROOT / "data/chiang_mai_travel_origins.csv").open(encoding="utf-8-sig", newline="") as source:
        origins = [{"id": r["origin_id"], "name": r["name"], "housing_type": r["housing_type"],
                    "lat": float(r["lat"]), "lon": float(r["lon"]), "source_url": r["source_url"],
                    "coordinate_basis": r["coordinate_basis"]} for r in csv.DictReader(source)]
    with (ROOT / "data/poi_chiang_mai_seed.csv").open(encoding="utf-8-sig", newline="") as source:
        pois = {r["poi_id"]: r for r in csv.DictReader(source)}
    destinations = [{"id": key, "name": pois[key]["name"], "lat": float(pois[key]["lat"]),
                     "lon": float(pois[key]["lon"]), "coordinate_basis": "existing_seed_poi_not_verified_gate"}
                    for key in DESTINATIONS]
    coordinates = ";".join(f"{p['lon']},{p['lat']}" for p in origins + destinations)
    url = f"https://router.project-osrm.org/table/v1/driving/{coordinates}?annotations=distance,duration"
    if args.matrix:
        matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    else:
        with urlopen(Request(url, headers={"User-Agent": "TH-EVI-research/1.0"}), timeout=30) as response:
            matrix = json.load(response)
        cache = ROOT / "tmp/chiang_mai_route_matrix.json"
        cache.write_text(json.dumps(matrix), encoding="utf-8")
    result = {"schema_version": 1, "province": "Chiang Mai", "source": "OSRM driving on OpenStreetMap",
              "source_url": url, "attribution": "OpenStreetMap contributors (ODbL); OSRM",
              "computed_at": datetime.now(timezone.utc).isoformat(), "origins": origins, "destinations": destinations,
              "routes": route_rows(origins, destinations, matrix), "forecast_enabled": False,
              "limitations": ["Purposive examples from a few developers, not a representative commuter sample.",
                              "Project map points and POI seed points are not independently verified entrances.",
                              "Driving distances use road routing, not straight-line distance; free-flow duration is not traffic time.",
                              "A round trip is a possible itinerary, not observed daily km or a required trip every day.",
                              "Trip frequency, destination choice, extra stops, occupancy and EV ownership weights are missing."]}
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    valid = [r["round_trip_road_km"] for r in result["routes"] if r["round_trip_road_km"] is not None]
    print(json.dumps({"routes": len(result["routes"]), "supported_routes": len(valid),
                      "round_trip_km_range": [min(valid), max(valid)] if valid else None}))


if __name__ == "__main__":
    main()
