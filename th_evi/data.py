import pandas as pd
import numpy as np
import json
from pathlib import Path
import warnings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PROVINCE_MAP = {
    "ทั่วประเทศ": 0,
    "กทม": 1,
    "ส่วนภูมิภาค": 2,
    "ชัยนาท": 3,
    "สิงห์บุรี": 4,
    "ลพบุรี": 5,
    "อ่างทอง": 6,
    "สระบุรี": 7,
    "อยุธยา": 8,
    "ปทุมธานี": 9,
    "นนทบุรี": 10,
    "สมุทรปราการ": 11,
    "ปราจีนบุรี": 12,
    "ฉะเชิงเทรา": 13,
    "ชลบุรี": 14,
    "ระยอง": 15,
    "จันทบุรี": 16,
    "ตราด": 17,
    "สระแก้ว": 18,
    "ชัยภูมิ": 19,
    "ยโสธร": 20,
    "อุบลราชธานี": 21,
    "ศรีสะเกษ": 22,
    "บุรีรัมย์": 23,
    "นครราชสีมา": 24,
    "สุรินทร์": 25,
    "อำนาจเจริญ": 26,
    "หนองบัวลำภู": 27,
    "บึงกาฬ": 28,
    "หนองคาย": 29,
    "เลย": 30,
    "อุดรธานี": 31,
    "นครพนม": 32,
    "สกลนคร": 33,
    "ขอนแก่น": 34,
    "กาฬสินธุ์": 35,
    "มหาสารคาม": 36,
    "ร้อยเอ็ด": 37,
    "มุกดาหาร": 38,
    "แม่ฮ่องสอน": 39,
    "เชียงใหม่": 40,
    "พะเยา": 41,
    "น่าน": 42,
    "ลำพูน": 43,
    "ลำปาง": 44,
    "แพร่": 45,
    "อุตรดิตถ์": 46,
    "สุโขทัย": 47,
    "ตาก": 48,
    "พิษณุโลก": 49,
    "กำแพงเพชร": 50,
    "พิจิตร": 51,
    "เพชรบูรณ์": 52,
    "นครสวรรค์": 53,
    "อุทัยธานี": 54,
    "กาญจนบุรี": 55,
    "นครปฐม": 56,
    "ราชบุรี": 57,
    "สมุทรสาคร": 58,
    "สมุทรสงคราม": 59,
    "เพชรบุรี": 60,
    "ประจวบคีรีขันธ์": 61,
    "ชุมพร": 62,
    "ระนอง": 63,
    "สุราษฎร์ธานี": 64,
    "พังงา": 65,
    "นครศรีธรรมราช": 66,
    "กระบี่": 67,
    "ภูเก็ต": 68,
    "พัทลุง": 69,
    "ตรัง": 70,
    "สตูล": 71,
    "ปัตตานี": 72,
    "ยะลา": 73,
    "นราธิวาส": 74,
}

SHEET_TO_PROVINCE = {v: k for k, v in PROVINCE_MAP.items()}


def load_dlt_fuel_newcar(path=None):
    """Load DLT new car registration by fuel type (Excel .xls format).

    File structure (BIFF8 .xls, 79 sheets):
        Col 0 = row label, Col 1 = total, Col 2 = gasoline, Col 3 = diesel
        Row 6 (0-indexed) = Grand total
        Row 8 = ร.1 passenger cars
        Row ~37 = รถยนต์ไฟฟ้า (EV section) — Col 1 = total EV count

    Returns a DataFrame with columns:
        province, total, gasoline, diesel, bev
    """
    if path is None:
        files = sorted(DATA_DIR.glob("Fuel_NewCar_*.xls"))
        if not files:
            files = sorted(Path.cwd().glob("Fuel_NewCar_*.xls"))
        if not files:
            raise FileNotFoundError("No Fuel_NewCar_*.xls found in data/ or cwd")
        path = str(files[0])

    xl = pd.ExcelFile(path)
    records = []
    for idx in range(min(len(xl.sheet_names), 79)):
        df = pd.read_excel(path, sheet_name=idx, header=None)
        if df.shape[0] < 8 or df.shape[1] < 4:
            continue
        prov = SHEET_TO_PROVINCE.get(idx)
        if prov is None:
            continue

        # Grand total row (Row 6, 0-indexed): Col 0 = label, Col 1 = total, Col 2 = gasoline, Col 3 = diesel
        gt = df.iloc[6]

        # Find BEV row by searching for "รถยนต์ไฟฟ้า" (EV) in column 0
        bev_total = 0
        for r in range(df.shape[0]):
            val = str(df.iloc[r, 0]).strip() if pd.notna(df.iloc[r, 0]) else ""
            if "รถยนต์ไฟฟ" in val:
                bev_total = int(df.iloc[r, 1]) if pd.notna(df.iloc[r, 1]) else 0
                break

        records.append({
            "province": prov,
            "total": int(gt[1]),
            "gasoline": int(gt[2]),
            "diesel": int(gt[3]),
            "bev": bev_total,
        })

    result = pd.DataFrame(records)
    result = result[result["province"].notna()]
    for col in ["total", "gasoline", "diesel", "bev"]:
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0).astype(int)
    return result.reset_index(drop=True)


def load_dlt_fuel_newcar_monthly(files=None):
    """Load and combine multiple monthly DLT files.

    Expects filenames like 'Fuel_NewCar_Apr69.xls' (month + year in BE).
    Returns DataFrame with columns: province, year, month, total, bev, ...
    """
    if files is None:
        files = sorted(DATA_DIR.glob("Fuel_NewCar_*.xls"))
        if not files:
            files = sorted(Path.cwd().glob("Fuel_NewCar_*.xls"))

    if not files:
        raise FileNotFoundError("No Fuel_NewCar_*.xls files found")

    all_records = []
    for f in files:
        name = Path(f).stem
        parts = name.split("_")
        if len(parts) >= 3:
            month_year = parts[-1]
        else:
            continue

        month_str = "".join(c for c in month_year if c.isalpha())[:3]
        year_be = int("".join(c for c in month_year if c.isdigit()))
        year_ce = year_be - 543

        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month = month_map.get(month_str.lower(), 0)

        df = load_dlt_fuel_newcar(str(f))
        df["year"] = year_ce
        df["month"] = month
        all_records.append(df)

    if not all_records:
        return pd.DataFrame()
    return pd.concat(all_records, ignore_index=True)


def get_ev_adoption_history(province="เชียงใหม่"):
    """Get historical EV adoption data for a province.

    Returns DataFrame with columns: year, month, total, bev, ev_share
    """
    monthly = load_dlt_fuel_newcar_monthly()
    if monthly.empty:
        return monthly
    prov_data = monthly[monthly["province"] == province].copy()
    if prov_data.empty:
        return prov_data
    prov_data["ev_share"] = prov_data["bev"] / prov_data["total"].replace(0, np.nan)
    prov_data = prov_data.sort_values(["year", "month"])
    return prov_data.reset_index(drop=True)


def get_ev_share(province="เชียงใหม่"):
    """Get current EV market share (BEV / total new cars) for a province."""
    monthly = load_dlt_fuel_newcar_monthly()
    if monthly.empty:
        single = load_dlt_fuel_newcar()
        if single.empty:
            return None
        row = single[single["province"] == province]
        if row.empty:
            return None
        return row["bev"].values[0] / max(row["total"].values[0], 1)

    prov = monthly[monthly["province"] == province]
    if prov.empty:
        return None
    latest = prov.sort_values(["year", "month"]).iloc[-1]
    return latest["bev"] / max(latest["total"], 1)


def load_population(level="province", province=None):
    """Load population data from HDX (Humanitarian Data Exchange) Thailand dataset.

    Parameters
    ----------
    level : str
        "province" (ADM1) or "district" (ADM2)
    province : str or None
        English name to filter (e.g. "Chiang Mai"), or None for all

    Returns DataFrame with columns like ADM1_EN, T_TL (total pop), etc.
    """
    fname = "tha_pop_adm1_2023.csv" if level == "province" else "tha_pop_adm2_2023.csv"
    path = DATA_DIR / fname
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if province:
        df = df[df["ADM1_EN"] == province].copy()
    return df


def load_evhub_dopa_population(province=None, area_type=None):
    """Load normalized DOPA 2568 population imported from the old EV Hub project."""
    path = DATA_DIR / "evhub_dopa_population_2568.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if province:
        df = df[df["province"] == province].copy()
    if area_type:
        df = df[df["area_type"] == area_type].copy()
    return df.reset_index(drop=True)


def get_evhub_population(province, area_name=None, area_type=None):
    """Return the best DOPA 2568 population row for a province or named area."""
    df = load_evhub_dopa_population(province=province, area_type=area_type)
    if df.empty:
        return None

    if area_name:
        match = df[df["area_name"].astype(str).str.contains(area_name, regex=False, na=False)]
        if match.empty:
            return None
        return match.sort_values("population", ascending=False).iloc[0].to_dict()

    province_rows = df[df["area_type"] == "province"]
    if not province_rows.empty:
        return province_rows.iloc[0].to_dict()
    return df.sort_values("population", ascending=False).iloc[0].to_dict()


def load_evhub_dlt_fleet(province=None, vehicle_segment=None):
    """Load normalized DLT April 2026 fleet by fuel type from the old EV Hub project."""
    path = DATA_DIR / "evhub_dlt_fleet_2569_04.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if province:
        df = df[df["province"] == province].copy()
    if vehicle_segment:
        df = df[df["vehicle_segment"] == vehicle_segment].copy()
    return df.reset_index(drop=True)


def get_evhub_dlt_fleet(province, vehicle_segment="ror1_passenger_car"):
    """Return the current DLT fleet row for a province and vehicle segment."""
    df = load_evhub_dlt_fleet(province=province, vehicle_segment=vehicle_segment)
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def load_evhub_sinexcel_prices(package_code=None):
    """Load SINEXEL charger package prices imported from the old EV Hub project."""
    path = DATA_DIR / "evhub_sinexcel_price_list.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if package_code:
        df = df[df["package_code"] == package_code].copy()
    return df.reset_index(drop=True)


def get_sinexcel_package(package_code):
    """Return one SINEXEL package price row by package code."""
    df = load_evhub_sinexcel_prices(package_code=package_code)
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_chiang_mai_district_population():
    """Get population for all 25 Chiang Mai districts.

    Returns DataFrame with columns: district (English), population (int)
    """
    df = load_population(level="district", province="Chiang Mai")
    if df.empty:
        return pd.DataFrame()
    result = df[["ADM2_EN", "T_TL"]].rename(
        columns={"ADM2_EN": "district", "T_TL": "population"}
    ).sort_values("district").reset_index(drop=True)
    result["population"] = result["population"].astype(str).str.replace(",", "", regex=False)
    result["population"] = pd.to_numeric(result["population"], errors="coerce").fillna(0).astype(int)
    return result


def load_osm_charging_stations():
    """Load OSM charging station data for Chiang Mai.

    Returns DataFrame with columns: lat, lon, operator, brand, capacity, connectors
    """
    path = DATA_DIR / "osm_chargers_cm_full.json"
    if not path.exists():
        return pd.DataFrame()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for e in data.get("elements", []):
        tags = e.get("tags", {})
        lat = e.get("lat") or (e.get("center", {}).get("lat") if "center" in e else None)
        lon = e.get("lon") or (e.get("center", {}).get("lon") if "center" in e else None)
        if lat is None or lon is None:
            continue
        sockets = {}
        for k, v in tags.items():
            if k.startswith("socket:") and "output" not in k and "current" not in k and "voltage" not in k:
                sock_type = k.replace("socket:", "")
                sockets[sock_type] = v
        records.append({
            "lat": float(lat),
            "lon": float(lon),
            "operator": tags.get("operator", tags.get("brand", "")),
            "network": tags.get("network", ""),
            "capacity": int(tags["capacity"]) if "capacity" in tags and tags["capacity"].isdigit() else 0,
            "connectors": list(sockets.keys()),
        })
    return pd.DataFrame(records)


def load_doh_aadt(year_be=None, province="เชียงใหม่"):
    """Load DOH (Department of Highways) AADT data for a province.

    Files follow pattern: aadt_<BE_year>.csv from data/ directory.
    Returns DataFrame with highway segments and AADT values.
    """
    available = {60: 2560, 63: 2563, 64: 2564, 66: 2566}
    if year_be is not None and year_be not in available.values():
        raise ValueError(f"Year must be one of {list(available.values())}")

    files_to_try = [year_be] if year_be else sorted(available.values(), reverse=True)

    for yr in files_to_try:
        fname = f"aadt_{yr}.csv"
        path = DATA_DIR / fname
        if not path.exists():
            continue
        df = pd.read_csv(path, encoding="utf-8")
        prov_col = df.columns[-1]
        prov_data = df[df[prov_col].str.strip() == province].copy()
        if not prov_data.empty:
            return prov_data

    return pd.DataFrame()


def get_cm_highway_aadt(year_be=2566):
    """Get AADT lookup for Chiang Mai highways keyed by route number.

    Returns dict: {route_number: {"name": str, "aadt": int, "km": str}}
    """
    df = load_doh_aadt(year_be=year_be, province="เชียงใหม่")
    if df.empty:
        return {}

    total_col = df.columns[14]
    route_col = df.columns[0]
    name_col = df.columns[2]
    km_col = df.columns[3]

    result = {}
    for _, row in df.iterrows():
        route = int(row[route_col])
        aadt = int(row[total_col])
        if route not in result or aadt > result[route]["aadt"]:
            result[route] = {
                "name": row[name_col],
                "aadt": aadt,
                "km": row[km_col],
            }
    return result
