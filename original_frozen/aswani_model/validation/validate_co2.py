"""
validate_co2.py
=======================
CO2 validation – measured KETI vs simulated EnergyPlus.

Validates only spaces/zones that have fully fused schedules (SPACE_ZONE_MAP).
Aligns on overlapping hourly timestamps only (inner join).
Computes RMSE, MAE, CV(RMSE) per zone.
Saves plots and metrics to outputs/co2/.

Run independently:
    python validate_co2.py

Requires:
    - run/eplusout.sql  (must contain "Zone Air CO2 Concentration")
    - KETI/<office>/co2.csv
    - shared_validation.py (in same directory)
"""

import os
import sys
import pandas as pd
import numpy as np

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
VARIABLE      = "co2"
SIM_VAR_NAME  = "Zone Air CO2 Concentration"   # EnergyPlus output variable name
SENSOR_NAME   = "co2"                    # KETI sensor subfolder file
UNIT          = "ppm"
YLABEL        = "CO2 Concentration"

# Reference bounds for validation (can be adjusted for CO2 specifics)
CVRMSE_LIMIT  = 30.0   # %
MBE_LIMIT     = 10.0   # %


def validate_zone_co2(zone: str, offices: list[str], out_dir: str) -> dict | None:
    """
    Validate CO2 for one EnergyPlus zone against its measured offices.

    Measured data: average of all offices belonging to the zone.
    Simulated data: Zone Air CO2 Concentration for the zone.

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

    # Average across offices
    if len(measured_series) > 1:
        measured_df = pd.concat(measured_series, axis=1).dropna(how="all")
        measured = measured_df.mean(axis=1).dropna()
    elif len(measured_series) == 1:
        measured = measured_series[0]
    else:
        measured = pd.Series()

    if measured.empty:
        print(f"    [SKIP] Empty measured data after processing for zone {zone}")
        return None
    
    print(f"    Measured (Aggregated): {len(measured)} 10-min intervals "
          f"({measured.index[0]} to {measured.index[-1]})")

    # ── Load simulated data ───────────────────────────────────────────────────
    simulated = load_simulation_variable(SIM_VAR_NAME, zone)
    if simulated is None or simulated.empty:
        print(f"    [SKIP] No simulated data for zone {zone} - you may need to update EnergyPlus IDF to output CO2.")
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
    plot_path = os.path.join(out_dir, f"aswani_co2_{zone}_{offices_str}.png")
    
    # AXIS DATA EXPLANATION:
    # X-Axis: Represents "Date / Time" containing concurrent hourly-stepped timestamps 
    #         for the August 23-31, 2013 validation period.
    # Y-Axis: Represents CO2 Concentration measured in units of 'ppm'
    plot_comparison(
        measured  = meas_al,
        simulated = sim_al,
        title     = f"Aswani CO2 Validation | Zone {zone} | Offices: {offices_str}",
        ylabel    = YLABEL,
        output_path = plot_path,
        rmse      = rmse,
        unit      = UNIT,
    )

    return {
        "Zone":         zone,
        "Offices":      offices_str,
        "N_Overlap_h":  n_overlap,
        "RMSE_CO2":     round(rmse, 4),
        "MAE_CO2":      round(mae, 4),
        "CVRMSE_pct":   round(cvrmse, 2),
        "MBE_CO2":      round(mbe, 4),
        "MBE_pct":      round(mbe_pct, 2),
        "ASHRAE14":     status,
    }


def main():
    print("=" * 65)
    print("STEP 4 — Aswani CO2 Validation")
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
        metrics = validate_zone_co2(zone, offices, out_dir)
        if metrics:
            all_metrics.append(metrics)

    if not all_metrics:
        print("\n[ERROR] No metrics computed — check data paths.")
        return

    # ── Save summary metrics CSV ──────────────────────────────────────────────
    summary_df = pd.DataFrame(all_metrics)
    metrics_path = os.path.join(out_dir, "co2_metrics_summary.csv")
    summary_df.to_csv(metrics_path, index=False)
    print(f"\n  [METRICS] Summary saved -> {metrics_path}")

    # ── Print summary table ───────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("CO2 VALIDATION SUMMARY")
    print("=" * 65)
    cols = ["Zone", "Offices", "N_Overlap_h", "RMSE_CO2", "CVRMSE_pct", "MBE_pct", "ASHRAE14"]
    print(summary_df[cols].to_string(index=False))

    n_pass = (summary_df["ASHRAE14"] == "PASS").sum()
    print(f"\n  {n_pass}/{len(summary_df)} zones pass equivalent ASHRAE Guideline 14 thresholds.")
    print("\n[DONE] CO2 validation complete.\n")


if __name__ == "__main__":
    main()
