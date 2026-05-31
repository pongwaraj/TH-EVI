# TH-EVI Constants — Thailand-specific default parameters

# --- 30@30 Policy Targets ---
# Target: 30% EV production by 2030 (30@30 policy)
# Implication for EV stock: ~15-20% of total vehicles by 2030

# Thailand vehicle population (approx, 2023 baseline)
THAILAND_TOTAL_VEHICLES_2023 = 44_000_000  # รวมทุกประเภท
CHIANG_MAI_VEHICLES_2023 = 1_800_000       # ประมาณการ

# --- S-Curve Adoption Parameters ---
# Calibrated loosely to 30@30 policy + historical EV registration growth
S_CURVE = {
    "carrying_capacity": 0.50,    # max EV share of fleet (long-term ceiling)
    "growth_rate": 0.30,          # steepness of adoption
    "midpoint_year": 2032,        # inflection point (50% of ceiling)
}

# --- EV Efficiency (Thailand context) ---
# Higher temps = less AC load vs US, but different driving cycles
EV_EFFICIENCY_KWH_PER_KM = 0.20  # avg for Thailand (BEV)

# --- Charging Behavior ---
# Thailand-specific defaults (adjusted for condo-dwelling, motorcycle culture)
HOME_CHARGING_ACCESS = 0.45       # % with home charging (lower than US ~80%)
WORK_CHARGING_ACCESS = 0.15
PUBLIC_CHARGING_PREFERENCE = 0.40 # conditional on no home access

# --- DCFC Thresholds ---
DCFC_MIN_KWH = 20                # min energy for DCFC visit to make sense
DCFC_MAX_RANGE_KM = 300          # max acceptable range before needing charge

# --- Provincial Adjustment Factors ---
# Scale national EV share to province level (1.0 = national average)
# Chiang Mai = 1.20 (higher income, tourism, early adopter)
PROVINCE_EV_FACTOR = {
    "เชียงใหม่": 1.20,
    "กรุงเทพ": 1.50,
    "ชลบุรี": 1.30,
    "ภูเก็ต": 1.25,
    "default": 0.60,
}
