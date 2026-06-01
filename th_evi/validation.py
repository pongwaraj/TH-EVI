"""
TH-EVI Validation Harness
=========================

Validates the two model layers against observed ground truth and reports
out-of-sample error via leave-one-out (LOO) cross-validation.

Two validation targets
-----------------------
1. Adoption layer  -> national new-car BEV share vs FTI annual actuals.
2. Station layer   -> StationDemandModel daily sessions vs observed station-days.

Design notes
------------
- The station model has one explicit free parameter for calibration:
  `calibration_factor` (a single scalar multiplier on total demand). All other
  scenario parameters keep their physical meaning. We fit ONLY this scalar to the
  training ground-truth, so the model is not silently over-tuned.
- With a single ground-truth station-day the calibration is *just-identified*
  (n == #params), so LOO cannot estimate generalization error. The harness makes
  this explicit and lists the additional stations required to actually validate.

Run:  python -m th_evi.validation
"""

from __future__ import annotations

import logging
from statistics import mean
from typing import Optional

from .adoption import EVAdoptionModel
from .location import StationDemandModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

# FTI / Autolife annual BEV share of NEW passenger cars (ror.1 basis).
ADOPTION_GROUND_TRUTH = {
    2023: 0.150,   # ~76,500 BEV
    2024: 0.140,   # 70,137 BEV  (subsidy-transition dip)
    2025: 0.194,   # 120,301 BEV (FTI full-year actual)
}

# Observed charging-station demand (station-days). CONFIRMED points only.
# Each: id, year, stalls, obs_daily (typical), obs_peak, source.
STATION_GROUND_TRUTH = [
    {
        "id": "cm_cultural_center_hub",
        "year": 2026,
        "stalls": 12,
        "obs_daily": 130,
        "obs_peak": 300,
        "source": "Operator report, typical vs peak-season day, 2026",
    },
]

# Stations to instrument next so LOO becomes meaningful (target n >= 5).
# Pulled from the CM competitor set in notebooks/03_location_analysis.py.
STATION_TO_COLLECT = [
    "BYD CM (4 bays)", "PTT Central Airport", "EGAT EleXA",
    "PEA Volta", "Centara Hotel", "MG Airport",
]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _mae(pred: list[float], obs: list[float]) -> float:
    """Mean Absolute Error."""
    return mean(abs(p - o) for p, o in zip(pred, obs))


def _mape(pred: list[float], obs: list[float]) -> float:
    """Mean Absolute Percentage Error."""
    return mean(abs(p - o) / o for p, o in zip(pred, obs)) * 100


def _rmse(pred: list[float], obs: list[float]) -> float:
    """Root Mean Square Error."""
    return (mean((p - o) ** 2 for p, o in zip(pred, obs))) ** 0.5


# ---------------------------------------------------------------------------
# Adoption layer
# ---------------------------------------------------------------------------

def validate_adoption(province: str = "default") -> dict:
    """Compare S-curve new-car BEV share to FTI annual actuals.

    Args:
        province: Province name (default uses national curve)

    Returns:
        Dictionary with keys:
            - rows: list of {year, pred_pct, obs_pct, abs_err_pp}
            - MAPE_pct: Mean Absolute Percentage Error
            - RMSE_pp: Root Mean Square Error in percentage points
    """
    m = EVAdoptionModel(province=province)
    years = sorted(ADOPTION_GROUND_TRUTH)
    pred = [m.get_ev_share(y) for y in years]
    obs = [ADOPTION_GROUND_TRUTH[y] for y in years]
    rows = [
        {"year": y, "pred_pct": round(p * 100, 1), "obs_pct": round(o * 100, 1),
         "abs_err_pp": round((p - o) * 100, 1)}
        for y, p, o in zip(years, pred, obs)
    ]
    
    result = {
        "rows": rows,
        "MAPE_pct": round(_mape(pred, obs), 1),
        "RMSE_pp": round(_rmse(pred, obs) * 100, 2),
    }
    
    logger.info(f"Adoption validation: MAPE={result['MAPE_pct']}%, RMSE={result['RMSE_pp']} pp")
    return result


# ---------------------------------------------------------------------------
# Station layer
# ---------------------------------------------------------------------------

def _predict_base_daily(point, calibration_factor=1.0):
    sm = StationDemandModel(province="เชียงใหม่")
    r = sm.estimate(
        year=point["year"], scenario="base", stalls=point["stalls"],
        calibration_factor=calibration_factor,
    )
    return r["daily_sessions"], r["daily_sessions_peak"]


def fit_station_calibration(train):
    """Fit the single scalar calibration_factor = mean(obs / raw_pred)."""
    ratios = []
    for pt in train:
        raw_daily, _ = _predict_base_daily(pt, calibration_factor=1.0)
        if raw_daily > 0:
            ratios.append(pt["obs_daily"] / raw_daily)
    return mean(ratios) if ratios else 1.0


def loo_validate_station():
    """Leave-one-out CV of the station model's single calibration scalar."""
    pts = STATION_GROUND_TRUTH
    n = len(pts)
    n_params = 1  # calibration_factor

    # In-sample fit (always available)
    factor = fit_station_calibration(pts)
    in_sample = []
    for pt in pts:
        pred_daily, pred_peak = _predict_base_daily(pt, calibration_factor=factor)
        in_sample.append({
            "id": pt["id"], "obs": pt["obs_daily"], "pred": pred_daily,
            "abs_err_pct": round(abs(pred_daily - pt["obs_daily"]) / pt["obs_daily"] * 100, 1),
        })

    result = {
        "n_points": n,
        "n_free_params": n_params,
        "fitted_calibration_factor": round(factor, 3),
        "in_sample": in_sample,
        "to_collect": STATION_TO_COLLECT,
    }

    if n <= n_params:
        result["loo"] = None
        result["status"] = (
            "JUST-IDENTIFIED (n=%d, params=%d): the calibration is exactly "
            "determined, so out-of-sample error CANNOT be estimated. Collect at "
            "least %d more station-days (see 'to_collect') for real validation."
            % (n, n_params, max(0, 5 - n))
        )
        return result

    # Genuine LOO once n > params
    test_pred, test_obs = [], []
    for i in range(n):
        train = pts[:i] + pts[i + 1:]
        f = fit_station_calibration(train)
        pred_daily, _ = _predict_base_daily(pts[i], calibration_factor=f)
        test_pred.append(pred_daily)
        test_obs.append(pts[i]["obs_daily"])
    result["loo"] = {
        "MAE": round(_mae(test_pred, test_obs), 1),
        "MAPE_pct": round(_mape(test_pred, test_obs), 1),
    }
    result["status"] = "OK"
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def main():
    print("=" * 64)
    print("TH-EVI VALIDATION REPORT")
    print("=" * 64)

    a = validate_adoption()
    print("\n[1] ADOPTION  (new-car BEV share vs FTI annual actual)")
    print("    year   pred%   obs%   err(pp)")
    for r in a["rows"]:
        print("    %d   %5.1f  %5.1f   %+5.1f" %
              (r["year"], r["pred_pct"], r["obs_pct"], r["abs_err_pp"]))
    print("    --> MAPE = %.1f%%   RMSE = %.2f pp" % (a["MAPE_pct"], a["RMSE_pp"]))

    s = loo_validate_station()
    print("\n[2] STATION  (daily sessions vs observed)")
    print("    fitted calibration_factor = %.3f" % s["fitted_calibration_factor"])
    print("    in-sample:")
    for r in s["in_sample"]:
        print("      %-24s obs=%d  pred=%d  err=%.1f%%" %
              (r["id"], r["obs"], r["pred"], r["abs_err_pct"]))
    if s["loo"] is None:
        print("    LOO: not available")
        print("    " + s["status"])
        print("    next to instrument: " + ", ".join(s["to_collect"]))
    else:
        print("    LOO  MAE=%.1f  MAPE=%.1f%%" % (s["loo"]["MAE"], s["loo"]["MAPE_pct"]))
    print("=" * 64)


if __name__ == "__main__":
    main()
