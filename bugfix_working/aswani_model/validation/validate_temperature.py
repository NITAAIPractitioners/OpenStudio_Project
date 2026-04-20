"""
validate_temperature.py
=======================
Step 2: Temperature validation – measured KETI vs simulated EnergyPlus.

Validates only spaces/zones that have fully fused schedules (SPACE_ZONE_MAP).
Aligns on overlapping hourly timestamps only (inner join).
Computes RMSE, MAE, CV(RMSE) per zone.
Saves plots and metrics to outputs/temperature/.

Run independently:
    python validate_temperature.py

Requires:
    - run/eplusout.sql  (must contain Zone Air Temperature)
    - KETI/<office>/temperature.csv
    - shared_validation.py (in same directory)
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Ensure the shared module is importable when run from any working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared_validation import (
    SPACE_ZONE_MAP,
    FUSED_ZONES,
    get_output_dir,
    load_keti_sensor,
    load_simulation_variable,
    align_series,
    compute_rmse,
    compute_mae,
    compute_cv_rmse,
    plot_comparison,
    save_metrics,
)

# ─── Config ───────────────────────────────────────────────────────────────────
VARIABLE      = "temperature"
SIM_VAR_NAME  = "Zone Air Temperature"   # EnergyPlus output variable name
SENSOR_NAME   = "temperature"            # KETI sensor subfolder file
UNIT          = "C"
YLABEL        = "Air Temperature"

# ASHRAE Guideline 14 calibration acceptance thresholds
CVRMSE_LIMIT  = 30.0   # % – hourly CV(RMSE) must be < 30 %
MBE_LIMIT     = 10.0   # % – hourly MBE must be < 10 %


def validate_zone_temperature(zone: str, offices: list[str], out_dir: str) -> dict | None:
    """
    Validate temperature for one EnergyPlus zone against its measured offices.

    Measured data: average of all offices belonging to the zone.
    Simulated data: Zone Air Temperature for the zone.

    Returns a metrics dict or None on failure.
    """
    print(f"\n  [Zone {zone}] Offices: {offices}")

    # ── Load and average measured data across offices in this zone ────────────
    measured_series = []
    for office in offices:
        s = load_keti_sensor(office, SENSOR_NAME)
        if s is not None and not s.empty:
            measured_series.append(s)
        else:
            print(f"    [WARN] No sensor data for office {office}")

    # Average across offices (ensure they are on the same time grid before mean)
    # We use a 10-min inner join to ensure we only average points where sensors overlapped,
    # or handle NaNs gracefully to allow one sensor to cover for another.
    if len(measured_series) > 1:
        measured_df = pd.concat(measured_series, axis=1).dropna(how="all")
        measured = measured_df.mean(axis=1).dropna()
    elif len(measured_series) == 1:
        measured = measured_series[0]
    else:
        measured = pd.Series()  # BUG8-FIX: graceful empty instead of IndexError

    if measured.empty:
        print(f"    [SKIP] Empty measured data after processing for zone {zone}")
        return None
    
    print(f"    Measured (Aggregated): {len(measured)} 10-min intervals "
          f"({measured.index[0]} to {measured.index[-1]})")

    # ── Load simulated data ───────────────────────────────────────────────────
    simulated = load_simulation_variable(SIM_VAR_NAME, zone)
    if simulated is None or simulated.empty:
        print(f"    [SKIP] No simulated data for zone {zone}")
        return None
    print(f"    Simulated: {len(simulated)} timesteps "
          f"({simulated.index[0]} to {simulated.index[-1]})")

    # ── Align on overlapping hourly timestamps ────────────────────────────────
    meas_al, sim_al = align_series(measured, simulated)
    n_overlap = len(meas_al)
    if n_overlap == 0:
        print(f"    [SKIP] No overlapping timestamps for zone {zone}")
        return None
    print(f"    Overlap: {n_overlap} hourly timestamps")

    # ── Metrics ───────────────────────────────────────────────────────────────
    # Calculate Root Mean Squared Error (RMSE) to quantify absolute magnitude of errors
    # Equation: RMSE = sqrt( mean( (simulated - measured)^2 ) )
    rmse   = compute_rmse(meas_al, sim_al)
    
    # Calculate Mean Absolute Error (MAE)
    # Equation: MAE = mean( |simulated - measured| )
    mae    = compute_mae(meas_al, sim_al)
    
    # Calculate Coefficient of Variation of RMSE (CV(RMSE))
    # Equation: CV(RMSE) % = 100 * ( RMSE / mean(measured) )
    cvrmse = compute_cv_rmse(meas_al, sim_al)
    
    # Calculate Mean Bias Error (MBE) to quantify systemic over/under-prediction
    # Equation: MBE = mean(simulated - measured) 
    mbe    = float(np.mean(sim_al.values - meas_al.values))          
    
    # Calculate % MBE normalized against the measured mean
    # Equation: % MBE = 100 * ( MBE / mean(measured) )
    mbe_pct = 100.0 * mbe / float(np.mean(meas_al.values))           

    # ASHRAE 14 compliance check
    ashrae_pass = (cvrmse < CVRMSE_LIMIT) and (abs(mbe_pct) < MBE_LIMIT)
    status = "PASS" if ashrae_pass else "FAIL"

    print(f"    RMSE     = {rmse:.4f} {UNIT}")
    print(f"    MAE      = {mae:.4f} {UNIT}")
    print(f"    CV(RMSE) = {cvrmse:.2f}%  (limit {CVRMSE_LIMIT}%)")
    print(f"    MBE      = {mbe:.4f} {UNIT}  ({mbe_pct:.2f}%)  (limit +/-{MBE_LIMIT}%)")
    print(f"    ASHRAE-14: {status}")

    # ── Plot ──────────────────────────────────────────────────────────────────
    offices_str = "+".join(offices)
    # BUG15-FIX: Infer model label from VAL_OUT_DIR (set by aggregate_performance_matrix.py
    # when calling this script for multiple models). Falls back to 'Temperature' if unset.
    out_dir_path = Path(out_dir)
    # The aggregator sets VAL_OUT_DIR = .../outputs/{ModelName}, so last part = model name
    model_label = out_dir_path.parent.name if out_dir_path.name.lower() == "temperature" else out_dir_path.name
    plot_fname = f"{model_label.lower().replace('-', '_').replace(' ', '_')}_temp_{zone}_{offices_str}.png"
    plot_path = os.path.join(out_dir, plot_fname)
    
    # AXIS DATA EXPLANATION:
    # X-Axis: Represents "Date / Time" containing concurrent hourly-stepped timestamps 
    #         for the August 23-31, 2013 validation period.
    # Y-Axis: Represents Air Temperature measured in units of '°C'
    plot_comparison(
        measured  = meas_al,
        simulated = sim_al,
        title     = f"{model_label} Temperature Validation | Zone {zone} | Offices: {offices_str}",
        ylabel    = YLABEL,
        output_path = plot_path,
        rmse      = rmse,
        unit      = UNIT,
    )

    return {
        "Zone":         zone,
        "Offices":      offices_str,
        "N_Overlap_h":  n_overlap,
        "RMSE_C":       round(rmse, 4),
        "MAE_C":        round(mae, 4),
        "CVRMSE_pct":   round(cvrmse, 2),
        "MBE_C":        round(mbe, 4),
        "MBE_pct":      round(mbe_pct, 2),
        "ASHRAE14":     status,
    }


def main():
    print("=" * 65)
    print("STEP 2 — Aswani Temperature Validation")
    print("=" * 65)

    out_dir = get_output_dir(VARIABLE)
    print(f"Output directory: {out_dir}")

    # Group offices by zone
    zone_offices: dict[str, list[str]] = {}
    for office, zone in SPACE_ZONE_MAP.items():
        zone_offices.setdefault(zone, []).append(office)

    all_metrics = []

    for zone in sorted(zone_offices.keys()):
        offices = sorted(zone_offices[zone])
        metrics = validate_zone_temperature(zone, offices, out_dir)
        if metrics:
            all_metrics.append(metrics)

    if not all_metrics:
        print("\n[ERROR] No metrics computed — check data paths.")
        return

    # ── Save summary metrics CSV ──────────────────────────────────────────────
    summary_df = pd.DataFrame(all_metrics)
    metrics_path = os.path.join(out_dir, "temperature_metrics_summary.csv")
    summary_df.to_csv(metrics_path, index=False)
    print(f"\n  [METRICS] Summary saved -> {metrics_path}")

    # ── Print summary table ───────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("TEMPERATURE VALIDATION SUMMARY")
    print("=" * 65)
    cols = ["Zone", "Offices", "N_Overlap_h", "RMSE_C", "CVRMSE_pct", "MBE_pct", "ASHRAE14"]
    print(summary_df[cols].to_string(index=False))

    n_pass = (summary_df["ASHRAE14"] == "PASS").sum()
    print(f"\n  {n_pass}/{len(summary_df)} zones pass ASHRAE Guideline 14 thresholds.")
    print("\n[DONE] Temperature validation complete.\n")


if __name__ == "__main__":
    main()
