from __future__ import annotations

import csv
import io
import math
from pathlib import Path

import openpyxl


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORKBOOK = ROOT / "outputs/dlt_ev_by_province_20260930/fuel30Sep26_W.xlsx"
DLT_URL = "https://web.dlt.go.th/statistics/load_file_select_new_car.php?t=3&data_file=1302"
DLT_PAGE = "https://web.dlt.go.th/statistics/m1_collect_new_car.php"
AS_OF = "2569-09"
AS_OF_DATE = "2569-09-30"
SITE = (18.789713, 99.068629)

SHEET_ALIASES = {
    "สุราษฯ": "สุราษฎร์ธานี",
    "นครศรีฯ": "นครศรีธรรมราช",
}
SEGMENTS = {
    "all_vehicle_law": 6,
    "ror1_passenger_car": 8,
}
COMPETITOR_FILES = (
    "competitors_chiang_mai_google_verified.csv",
    "competitors_chiang_mai_seed.csv",
    "competitors_chiang_mai_detailed.csv",
)
TARGET_COMPETITORS = {
    "ea_anywhere_caltex_sankamphaeng",
    "elex_pt_san_kamphaeng_6",
    "ptt_ev_station_payap",
    "ptt_san_kamphaeng_kmz",
    "tce_ev_meta_mall",
    "ptt_ev_station_don_jan",
    "ea_anywhere_chanasin",
    "pea_volta_bangchak_superhighway",
    "ea_anywhere_cbp",
    "ea_anywhere_my_hip_condo",
    "tesla_supercharger_big_c_extra",
    "bcp_pornphawit_oil_san_sai",
    "fair_super_charge_greenbus",
    "ev_station_pluz_green_park",
    "greenbus_fair_super_charge",
    "elexa_route_118_sansai",
    "ptt_ev_station_saraphi_2",
    "ptt_san_kamphaeng_3_kml",
    "ptt_ev_station_ruamchock",
    "pea_volta_hub_chiangmai_gmaps",
    "evolt_parking_area_sansai",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def value(ws, row: int, col: int) -> int:
    return int(ws.cell(row, col).value or 0)


def dlt_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    workbook = openpyxl.load_workbook(WORKBOOK, data_only=True, read_only=True)
    normalized: list[dict[str, object]] = []
    province_summary: list[dict[str, object]] = []

    for sheet in workbook.sheetnames:
        if sheet.strip() in {"ทั่วประเทศ", "ส่วนกลาง", "ภูมิภาค"}:
            continue
        ws = workbook[sheet]
        province = SHEET_ALIASES.get(sheet, sheet)
        for segment, source_row in SEGMENTS.items():
            total = value(ws, source_row, 2)
            bev = value(ws, source_row, 14)
            phev_gas = value(ws, source_row, 19) + value(ws, source_row, 21)
            phev_diesel = value(ws, source_row, 20) + value(ws, source_row, 22)
            normalized.append(
                {
                    "source_project": "TH-EVI",
                    "source_file": WORKBOOK.name,
                    "source_month": AS_OF,
                    "source_year_be": 2569,
                    "province": province,
                    "vehicle_segment": segment,
                    "total_vehicles": total,
                    "gasoline": value(ws, source_row, 3),
                    "diesel": value(ws, source_row, 4),
                    "bev": bev,
                    "hev_gasoline": value(ws, source_row, 15),
                    "hev_diesel": value(ws, source_row, 16),
                    "phev_gasoline": phev_gas,
                    "phev_diesel": phev_diesel,
                    "bev_share": round(bev / total, 10) if total else 0,
                }
            )

        total_vehicles = sum(value(ws, row, 2) for row in (8, 9, 10))
        bev = sum(value(ws, row, 14) for row in (8, 9, 10))
        phev = sum(
            value(ws, row, col)
            for row in (8, 9, 10)
            for col in (19, 20, 21, 22)
        )
        province_summary.append(
            {
                "province": province,
                "as_of_be": AS_OF_DATE,
                "registered_private_cars_vans_pickups_ror1_3": total_vehicles,
                "bev": bev,
                "phev": phev,
                "plugin_total": bev + phev,
                "plugin_share_pct": round((bev + phev) / total_vehicles * 100, 8)
                if total_vehicles
                else 0,
                "source_url": DLT_URL,
                "source_scope": "DLT cumulative private vehicles under Motor Vehicle Act, Ror.1-Ror.3; BEV plus plug-in hybrid categories only; excludes HEV, motorcycles, and transport-law vehicles",
                "notes": "Province tab in official DLT fuel30Sep26_W.xlsx; totals rows Ror.1-Ror.3. This is a provincial fleet baseline, not site catchment or charging demand.",
            }
        )
    workbook.close()
    return normalized, province_summary


def update_dlt_files() -> dict[str, int]:
    normalized, summary = dlt_rows()
    write_csv(
        DATA / "evhub_dlt_fleet_2569_09.csv",
        [
            "source_project",
            "source_file",
            "source_month",
            "source_year_be",
            "province",
            "vehicle_segment",
            "total_vehicles",
            "gasoline",
            "diesel",
            "bev",
            "hev_gasoline",
            "hev_diesel",
            "phev_gasoline",
            "phev_diesel",
            "bev_share",
        ],
        normalized,
    )
    write_csv(
        DATA / "dlt_ev_province_20260930.csv",
        [
            "province",
            "as_of_be",
            "registered_private_cars_vans_pickups_ror1_3",
            "bev",
            "phev",
            "plugin_total",
            "plugin_share_pct",
            "source_url",
            "source_scope",
            "notes",
        ],
        summary,
    )
    return {r["province"]: int(r["bev"]) for r in summary}


def update_poi_coordinates() -> None:
    for filename in ("poi_mahachok_park_seed.csv", "poi_chiang_mai_seed.csv"):
        path = DATA / filename
        lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        for index, line in enumerate(lines):
            if not line.startswith("mahachok_park,"):
                continue
            row = next(csv.reader([line.rstrip("\r\n")]))
            row[3], row[4] = map(str, SITE)
            addition = (
                "User analysis pin: 18.789713, 99.068629; verified 2026-10-16. "
                "For Eyes Optic announced its Mahachok Park branch on 2026-09-13; "
                "record as an on-site tenant, not a separate demand anchor."
            )
            if addition not in row[7]:
                row[7] = f"{row[7].rstrip('. ')}. {addition}"
            buffer = io.StringIO(newline="")
            csv.writer(buffer, lineterminator="\r\n" if line.endswith("\r\n") else "\n").writerow(row)
            lines[index] = buffer.getvalue()
            break
        path.write_text("".join(lines), encoding="utf-8", newline="")


def haversine_km(lat: float, lon: float) -> float:
    dlat = math.radians(lat - SITE[0])
    dlon = math.radians(lon - SITE[1])
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(SITE[0])) * math.cos(
        math.radians(lat)
    ) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def update_competitors() -> list[dict[str, object]]:
    by_id: dict[str, dict[str, str]] = {}
    for filename in COMPETITOR_FILES:
        _, rows = read_csv(DATA / filename)
        for row in rows:
            station_id = row.get("station_id") or ""
            if station_id in TARGET_COMPETITORS and station_id not in by_id:
                by_id[station_id] = row

    columns = [
        "station_id",
        "name",
        "operator",
        "network",
        "lat",
        "lon",
        "distance_straight_km",
        "area",
        "connector_summary",
        "power_summary",
        "source",
        "source_url",
        "verification_status",
        "competition_relevance",
        "notes",
    ]
    out: list[dict[str, object]] = []
    for station_id, row in by_id.items():
        try:
            lat = float(row.get("lat") or "")
            lon = float(row.get("lon") or "")
        except ValueError:
            continue
        distance = haversine_km(lat, lon)
        if distance > 8.0:
            continue
        notes = row.get("notes", "")
        if station_id == "ea_anywhere_caltex_sankamphaeng":
            notes = (
                "Public directory places the charger at Caltex M-Energy on Route 121. "
                "It reports CCS outputs at 150 kW and 75 kW; simultaneous capacity and "
                "live availability remain unverified. Straight-line distance is measured "
                "from the Mahachok Park analysis pin."
            )
        out.append(
            {
                "station_id": station_id,
                "name": row.get("name", ""),
                "operator": row.get("operator", ""),
                "network": row.get("network", ""),
                "lat": lat,
                "lon": lon,
                "distance_straight_km": round(distance, 2),
                "area": row.get("area") or row.get("district") or row.get("corridor", ""),
                "connector_summary": row.get("connector_summary", ""),
                "power_summary": row.get("power_summary", ""),
                "source": row.get("source") or row.get("source_type", ""),
                "source_url": row.get("source_url", ""),
                "verification_status": row.get("verification_status") or row.get("confidence", ""),
                "competition_relevance": "Direct/nearby public charger; review actual route, access, and live operating status before investment model.",
                "notes": notes,
            }
        )
    out.sort(key=lambda row: float(row["distance_straight_km"]))
    write_csv(DATA / "site_mahachok_park_competitors.csv", columns, out)
    return out


def update_market_profile() -> None:
    path = DATA / "chiang_mai_mahachok_park_market_profile.csv"
    fields = [
        "metric_id",
        "domain",
        "metric_name",
        "value",
        "unit",
        "reference_area",
        "source_file",
        "source_url",
        "reference_date_be",
        "verification_status",
        "notes",
    ]
    rows: list[dict[str, str]] = []
    values = {
        "cm_dlt_all_vehicle_fleet_2569_09": {
            "domain": "DLT",
            "metric_name": "รถจดทะเบียนสะสมทุกประเภทรถตามกฎหมายว่าด้วยรถยนต์",
            "value": "1704812",
            "unit": "คัน",
            "reference_area": "จังหวัดเชียงใหม่",
            "source_file": "data/evhub_dlt_fleet_2569_09.csv",
            "source_url": DLT_PAGE,
            "reference_date_be": AS_OF_DATE,
            "verification_status": "official_DLT_download",
            "notes": "รถรวมตามกฎหมายว่าด้วยรถยนต์; ใช้เป็นบริบทตลาดรวม ไม่ใช้แทนฐานรถยนต์ รย.1 ในสูตรหลัก.",
        },
        "cm_dlt_ror1_fleet_2569_09": {
            "domain": "DLT",
            "metric_name": "รถยนต์นั่งส่วนบุคคลไม่เกิน 7 คน (รย.1)",
            "value": "460081",
            "unit": "คัน",
            "reference_area": "จังหวัดเชียงใหม่",
            "source_file": "data/evhub_dlt_fleet_2569_09.csv",
            "source_url": DLT_PAGE,
            "reference_date_be": AS_OF_DATE,
            "verification_status": "official_DLT_download",
            "notes": "ฐานทะเบียนรถยนต์ รย.1 ณ 30 ก.ย. 2569.",
        },
        "cm_dlt_ror1_bev_2569_09": {
            "domain": "DLT",
            "metric_name": "BEV ในกลุ่ม รย.1",
            "value": "17002",
            "unit": "คัน",
            "reference_area": "จังหวัดเชียงใหม่",
            "source_file": "data/evhub_dlt_fleet_2569_09.csv",
            "source_url": DLT_PAGE,
            "reference_date_be": AS_OF_DATE,
            "verification_status": "official_DLT_download",
            "notes": "BEV คิดเป็น 3.6950% ของรถ รย.1; เป็นยอดทะเบียนจังหวัด ไม่ใช่จำนวนผู้ใช้สถานี.",
        },
        "cm_dlt_ror1_phev_2569_09": {
            "domain": "DLT",
            "metric_name": "PHEV ในกลุ่ม รย.1",
            "value": "2443",
            "unit": "คัน",
            "reference_area": "จังหวัดเชียงใหม่",
            "source_file": "data/evhub_dlt_fleet_2569_09.csv",
            "source_url": DLT_PAGE,
            "reference_date_be": AS_OF_DATE,
            "verification_status": "official_DLT_download",
            "notes": "รวมเบนซิน-ไฟฟ้าแบบเสียบปลั๊กและดีเซล-ไฟฟ้าแบบเสียบปลั๊ก; ไม่รวม HEV.",
        },
        "cm_dlt_ror1_3_fleet_2569_09": {
            "domain": "DLT",
            "metric_name": "รถส่วนบุคคล รย.1-รย.3",
            "value": "748561",
            "unit": "คัน",
            "reference_area": "จังหวัดเชียงใหม่",
            "source_file": "data/dlt_ev_province_20260930.csv",
            "source_url": DLT_PAGE,
            "reference_date_be": AS_OF_DATE,
            "verification_status": "official_DLT_download",
            "notes": "ผลรวม รย.1 รถยนต์นั่งไม่เกิน 7 คน, รย.2 รถยนต์นั่งเกิน 7 คน และ รย.3 รถบรรทุกส่วนบุคคล.",
        },
        "cm_dlt_ror1_3_plugin_total_2569_09": {
            "domain": "DLT",
            "metric_name": "BEV และ PHEV ในรถส่วนบุคคล รย.1-รย.3",
            "value": "19468",
            "unit": "คัน",
            "reference_area": "จังหวัดเชียงใหม่",
            "source_file": "data/dlt_ev_province_20260930.csv",
            "source_url": DLT_PAGE,
            "reference_date_be": AS_OF_DATE,
            "verification_status": "official_DLT_download",
            "notes": "BEV 17,025 + PHEV 2,443; ไม่รวม HEV. Provincial fleet reference, not site demand.",
        },
        "cm_dopa_doi_saket_population_2568": {
            "domain": "DOPA",
            "metric_name": "ประชากรตามทะเบียนราษฎร",
            "value": "48911",
            "unit": "คน",
            "reference_area": "อำเภอดอยสะเก็ด",
            "source_file": "data/evhub_dopa_population_2568.csv",
            "source_url": "https://stat.bora.dopa.go.th/stat/statnew/statyear/",
            "reference_date_be": "2568",
            "verification_status": "official_imported_latest_available",
            "notes": "จำนวนประชากรตามทะเบียนระดับอำเภอ; ไม่ใช่ประชากรแฝงหรือผู้เดินทางผ่านจุด.",
        },
        "cm_dopa_chiang_mai_population_2568": {
            "domain": "DOPA",
            "metric_name": "ประชากรตามทะเบียนราษฎร",
            "value": "1798588",
            "unit": "คน",
            "reference_area": "จังหวัดเชียงใหม่",
            "source_file": "data/evhub_dopa_population_2568.csv",
            "source_url": "https://stat.bora.dopa.go.th/stat/statnew/statyear/",
            "reference_date_be": "2568",
            "verification_status": "official_imported_latest_available",
            "notes": "ใช้เป็นบริบทจังหวัด ไม่ใช้แทนจำนวนผู้เดินทางหรือผู้ใช้บริการในจุดวิเคราะห์.",
        },
        "cm_dopa_san_pu_loei_population_2568": {
            "domain": "DOPA",
            "metric_name": "ประชากรตามทะเบียนราษฎรในเขตเทศบาลตำบล",
            "value": "19230",
            "unit": "คน",
            "reference_area": "เทศบาลตำบลสันปูเลย",
            "source_file": "data/evhub_dopa_population_2568.csv",
            "source_url": "https://stat.bora.dopa.go.th/stat/statnew/statyear/",
            "reference_date_be": "2568",
            "verification_status": "official_imported_latest_available",
            "notes": "เขตเทศบาลเป็นขอบเขตปกครองท้องถิ่น ไม่ใช่รัศมีลูกค้าหรือพื้นที่เดินทางถึงสถานี.",
        },
        "cm_drr_aadt_route3029_2567": {
            "domain": "AADT",
            "metric_name": "ปริมาณจราจรเฉลี่ยรายวัน ถนนสมโภชเชียงใหม่ 700 ปี (ทางหลวงชนบท ชม.3029)",
            "value": "25442",
            "unit": "คันต่อวัน",
            "reference_area": "แนวถนนสมโภชเชียงใหม่ 700 ปี",
            "source_file": "outputs/drr_aadt_2567/pcu-update-67.csv",
            "source_url": "https://data.go.th/en/dataset/aadt1",
            "reference_date_be": "2567",
            "verification_status": "official_DRR_latest_available",
            "notes": "ข้อมูลล่าสุดที่ดาวน์โหลดได้จากชุดสถิติปริมาณจราจร DRR; ใช้เป็นบริบทระดับแนวถนนเท่านั้น ไม่ใช่ AADT หน้าพื้นที่มหาโชคปาร์ค และไม่นับเป็น EV charging demand.",
        },
    }
    for metric_id, new in values.items():
        rows.append({"metric_id": metric_id, **new})
    write_csv(path, fields, rows)


def main() -> None:
    bev_by_province = update_dlt_files()
    update_poi_coordinates()
    competitors = update_competitors()
    update_market_profile()
    print(
        {
            "province_tabs": len(bev_by_province),
            "chiang_mai_bev_ror1_3": bev_by_province.get("เชียงใหม่"),
            "competitors_within_8km": len(competitors),
            "nearest_competitors": [
                (r["name"], r["distance_straight_km"]) for r in competitors[:5]
            ],
        }
    )


if __name__ == "__main__":
    main()
