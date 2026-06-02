# TH-EVI Constants — Thailand-specific default parameters

# --- BEV Market Share (New Passenger Cars, ร.1) ---
# Source: Federation of Thai Industries (FTI), Autolife Thailand
# 2023: ~15.0%  (76,500 BEV / ~510,000 passenger cars)
# 2024: ~14.0%  (70,137 BEV / ~500,000 — subsidy transition dip)
# 2025: 19.4%   (120,301 BEV / ~620,000 passenger cars) — FTI FULL-YEAR actual
#   NOTE: prior calibration used 23.9% (a peak-month figure); corrected to the
#   full-year annual share, which is the right basis for a yearly S-curve.
# DLT Fuel_NewCar data: see data.py for parser (currently not used for calibration)

# --- 30@30 Policy Targets ---
# Target: 30% EV production by 2030 (30@30 policy)

# Thailand vehicle population (approx, 2023 baseline)
THAILAND_TOTAL_VEHICLES_2023 = 44_000_000
CHIANG_MAI_VEHICLES_2023 = 1_800_000

# --- S-Curve Adoption Parameters ---
# RE-CALIBRATED (May 2026) via scipy logistic least-squares to FTI ANNUAL points:
#   2023=15.0%, 2024=14.0% (subsidy dip), 2025=19.4%  | ceiling fixed at 85%
# Fitted result: growth_rate=0.179, midpoint_year=2032
#   -> logistic(2025)=19.1%, logistic(2030)=35.4% (consistent with 30@30 policy),
#      logistic(2035)=54%. Previous (0.30 / 2028) overshot: it implied 2030=55%.
S_CURVE = {
    "carrying_capacity": 0.85,   # 85% BEV share at saturation
    "growth_rate": 0.179,        # Re-fitted to FTI annual data
    "midpoint_year": 2032,       # 50% adoption year (was 2028 — too aggressive)
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
# RESOLVED (May 2026): The 0.40 factor mixed denominators — it divided province
# all-type BEV share (incl. motorcycles) by national all-type share, which is NOT
# comparable to the ร.1 (passenger-car) national S-curve. For ร.1 analysis the
# national new-car BEV share applies directly, so the factor is set to 1.0.
# This also reconciles the two demand pathways: LocationDemandModel (fleet_ev_share)
# and StationDemandModel (absolute EV population) now both derive from the SAME
# national new-car share accumulated into the provincial fleet.
PROVINCE_EV_FACTOR = {
    "เชียงใหม่": 1.00,   # ร.1 basis — use national S-curve directly (was 0.40, mixed-denominator)
    "ลำปาง": 0.85,       # Pilot assumption until DLT province calibration is added
    "อุดรธานี": 0.90,     # Pilot assumption: regional hub, below Chiang Mai until DLT calibration
    "ขอนแก่น": 1.00,      # Pilot assumption: major Northeast hub; keep at national curve until DLT calibration
    "พะเยา": 0.72,        # Pilot assumption: smaller northern province with Route 1 travel demand
    "หนองคาย": 0.78,      # Pilot assumption: smaller province, lifted by Route 2 border gateway demand
    "แพร่": 0.76,         # Pilot assumption: smaller northern province, lifted by Den Chai Route 11/101 gateway demand
    "อุบลราชธานี": 0.92,  # Pilot assumption: large regional hub with Route 24/231 and Chong Mek demand
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
    "ลำปาง": 2_000,
    "อุดรธานี": 3_200,
    "ขอนแก่น": 5_000,
    "พะเยา": 900,
    "หนองคาย": 1_100,
    "แพร่": 1_000,
    "อุบลราชธานี": 3_800,
}
# Total passenger car fleet by province (approx)
PROVINCE_FLEET_SIZE = {
    "เชียงใหม่": 350_000,
    "ลำปาง": 115_000,
    "อุดรธานี": 180_000,
    "ขอนแก่น": 300_000,
    "พะเยา": 65_000,
    "หนองคาย": 75_000,
    "แพร่": 70_000,
    "อุบลราชธานี": 220_000,
}

# --- National Average Daily Trips per Vehicle ---
# Thailand average (based on OTP survey data)
TRIPS_PER_DAY_PER_VEHICLE = 2.5
AVG_TRIP_KM = 12.0
