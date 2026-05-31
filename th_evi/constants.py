# TH-EVI Constants — Thailand-specific default parameters

# --- BEV Market Share (New Passenger Cars, ร.1) ---
# Source: Federation of Thai Industries (FTI), Autolife Thailand
# 2023: ~15%   (76,500 BEV / ~510,000 passenger cars)
# 2024: ~14%   (70,137 BEV / ~500,000 — subsidy transition dip)
# 2025: 23.9%  (122,128 BEV / 510,062 passenger cars)
# DLT Fuel_NewCar data: see data.py for parser (currently not used for calibration)

# --- 30@30 Policy Targets ---
# Target: 30% EV production by 2030 (30@30 policy)

# Thailand vehicle population (approx, 2023 baseline)
THAILAND_TOTAL_VEHICLES_2023 = 44_000_000
CHIANG_MAI_VEHICLES_2023 = 1_800_000

# --- S-Curve Adoption Parameters ---
# Calibrated to FTI/Autolife data points:
#   2023=15%, 2025=24%, long-term ceiling=85%
# Fitted: logistic(2025) ≈ 24%, midpoint=2028, rate=0.30
S_CURVE = {
    "carrying_capacity": 0.85,   # 85% BEV share at saturation
    "growth_rate": 0.30,         # Moderate steepness
    "midpoint_year": 2028,       # 50% adoption year
}

# --- EV Efficiency (Thailand context) ---
EV_EFFICIENCY_KWH_PER_KM = 0.20

# --- Charging Behavior ---
HOME_CHARGING_ACCESS = 0.45
WORK_CHARGING_ACCESS = 0.15
PUBLIC_CHARGING_PREFERENCE = 0.40

# --- DCFC Thresholds ---
DCFC_MIN_KWH = 20
DCFC_MAX_RANGE_KM = 300

# --- Provincial Adjustment Factors ---
# Multiplier applied to national S-curve BEV share to estimate province-level adoption.
# Computed from DLT April 2026: Province_BEV_share(all types) / National_BEV_share(all types)
# Bayesian-smoothed with prior_weight=500, default=0.60.
#
# NOTE: These factors use ALL-vehicle-type BEV share (including motorcycles in denominator).
# For passenger-car-only (ร.1) analysis, the national S-curve should be used directly
# (set province factor to 1.0). These factors are best-effort estimates pending ร.1-specific data.
PROVINCE_EV_FACTOR = {
    "เชียงใหม่": 0.40,
    "default": 1.00,
}

# --- Province-to-sheet-index mapping (for DLT .xls files) ---
PROVINCE_SHEET_INDEX = {
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

# --- Fleet Model Parameters ---
# Annual new passenger car registrations by province (ร.1 per year)
# Source: DLT April 2026 monthly rate × 12 (estimated)
PROVINCE_NEW_CAR_RATE = {
    "เชียงใหม่": 6_200,
}
# Total passenger car fleet by province (approx)
PROVINCE_FLEET_SIZE = {
    "เชียงใหม่": 350_000,
}

# --- National Average Daily Trips per Vehicle ---
# Thailand average (based on OTP survey data)
TRIPS_PER_DAY_PER_VEHICLE = 2.5
AVG_TRIP_KM = 12.0
