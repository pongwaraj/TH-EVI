from __future__ import annotations

import csv
import math
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(r"D:\Work\TH-EVI")
KMZ_PATH = Path(r"C:\Users\Lenovo\Downloads\DC EV Charging Station Thailand - Piyamate Wisanuvej.kmz")
OUT_ALL = ROOT / "artifacts" / "dc_ev_kmz_extracted.csv"
OUT_GAPS = ROOT / "artifacts" / "dc_ev_kmz_candidate_additions.csv"

TARGET_PROVINCES = {
    "เชียงใหม่": "chiang_mai",
    "เชียงราย": "chiang_rai",
    "ลำปาง": "lampang",
    "ลำพูน": "lamphun",
    "พิษณุโลก": "phitsanulok",
    "แพร่": "phrae",
    "น่าน": "nan",
    "พะเยา": "phayao",
    "แม่ฮ่องสอน": "mae_hong_son",
    "สมุทรปราการ": "samut_prakan",
    "ระยอง": "rayong",
    "นครนายก": "nakhon_nayok",
    "นครราชสีมา": "nakhon_ratchasima",
    "หนองคาย": "nong_khai",
    "อุดรธานี": "udon_thani",
    "ขอนแก่น": "khon_kaen",
    "อุบลราชธานี": "ubon_ratchathani",
}

NETWORK_BY_PROVIDER = {
    "PTT": "EV Station PluZ",
    "EA": "EA",
    "PEA": "PEA VOLTA",
    "EGAT": "EleXA",
    "MG": "MG Super Charge",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def parse_province_from_address(address: str) -> str:
    parts = address.split()
    if not parts:
        return ""
    if parts[-1].isdigit() and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def suggest_station_id(province_th: str, name_th: str, name_en: str) -> str:
    seed = name_en or name_th or "unknown"
    raw = f"{province_th}_{seed}".lower()
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return slug[:80] or "unknown_station"


def parse_kmz_rows() -> list[dict[str, object]]:
    with zipfile.ZipFile(KMZ_PATH) as archive:
        data = archive.read("doc.kml")
    root = ET.fromstring(data)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    rows: list[dict[str, object]] = []
    for placemark in root.findall(".//kml:Placemark", ns):
        description = placemark.findtext("kml:description", default="", namespaces=ns)
        meta: dict[str, str] = {}
        for part in re.split(r"<br>|\n", description):
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            meta[key.strip()] = value.strip()
        coords = placemark.findtext(".//kml:coordinates", default="", namespaces=ns).strip().split(",")
        if len(coords) < 2:
            continue
        lon = float(coords[0])
        lat = float(coords[1])
        address = meta.get("Address", "")
        province_th = parse_province_from_address(address)
        provider = meta.get("Provider", "").strip()
        rows.append(
            {
                "name_th": placemark.findtext("kml:name", default="", namespaces=ns),
                "name_en": meta.get("Name-EN", ""),
                "provider": provider,
                "network_suggested": NETWORK_BY_PROVIDER.get(provider, provider or "Unknown"),
                "connector_summary": meta.get("Description", ""),
                "address": address,
                "province_th": province_th,
                "lat": lat,
                "lon": lon,
                "style": placemark.findtext("kml:styleUrl", default="", namespaces=ns),
                "source_url": str(KMZ_PATH),
            }
        )
    return rows


def load_existing_competitors() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for province_th, slug in TARGET_PROVINCES.items():
        for path in ROOT.glob(f"data/competitors_{slug}*.csv"):
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    try:
                        lat = float(row.get("lat") or "")
                        lon = float(row.get("lon") or "")
                    except ValueError:
                        continue
                    rows.append(
                        {
                            "province_th": province_th,
                            "name": row.get("name", ""),
                            "network": row.get("network", ""),
                            "lat": lat,
                            "lon": lon,
                            "file": path.name,
                        }
                    )
    return rows


def find_gap_rows(
    kmz_rows: list[dict[str, object]], existing_rows: list[dict[str, object]], duplicate_radius_km: float = 0.35
) -> list[dict[str, object]]:
    gap_rows: list[dict[str, object]] = []
    for row in kmz_rows:
        province_th = str(row["province_th"])
        if province_th not in TARGET_PROVINCES:
            continue
        nearby = [
            item
            for item in existing_rows
            if item["province_th"] == province_th
            and haversine_km(float(row["lat"]), float(row["lon"]), float(item["lat"]), float(item["lon"])) <= duplicate_radius_km
        ]
        if nearby:
            continue
        gap_rows.append(
            {
                "province_th": province_th,
                "station_id_suggested": suggest_station_id(
                    province_th, str(row["name_th"]), str(row["name_en"])
                ),
                "name_th": row["name_th"],
                "name_en": row["name_en"],
                "provider": row["provider"],
                "network_suggested": row["network_suggested"],
                "lat": row["lat"],
                "lon": row["lon"],
                "connector_summary": row["connector_summary"],
                "address": row["address"],
                "suggested_verification_status": "public_listing_needs_operator_verification",
                "suggested_confidence": "medium",
                "source_url": row["source_url"],
            }
        )
    return gap_rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            handle.write("")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    kmz_rows = parse_kmz_rows()
    existing_rows = load_existing_competitors()
    gap_rows = find_gap_rows(kmz_rows, existing_rows)
    write_csv(OUT_ALL, kmz_rows)
    write_csv(OUT_GAPS, gap_rows)
    print(f"Extracted {len(kmz_rows)} placemarks to {OUT_ALL}")
    print(f"Found {len(gap_rows)} candidate additions to {OUT_GAPS}")


if __name__ == "__main__":
    main()
