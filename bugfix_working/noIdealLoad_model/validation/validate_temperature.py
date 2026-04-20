"""
validate_temperature.py — noIdealLoad_model
=========================================
Standalone Temperature validation script.
Targets the specific NoIdealLoad experiment.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path

# --- LOCAL PATH DISCOVERY ---
_HERE = Path(__file__).parent
EXPERIMENT_ROOT = _HERE.parent
CONFIG_PATH = EXPERIMENT_ROOT / "experiment_config.json"
OUTPUT_DIR = EXPERIMENT_ROOT / "outputs" / "temperature"

# Ensure shared_validation is importable from this directory
sys.path.insert(0, str(_HERE))
from shared_validation import (
    SPACE_ZONE_MAP, load_keti_sensor, load_simulation_variable,
    align_series, compute_rmse, compute_mae, compute_cv_rmse,
    plot_comparison, save_metrics
)

# --- Configuration ---
VARIABLE      = "temperature"
SIM_VAR_NAME  = "Zone Air Temperature"
SENSOR_NAME   = "temperature"
UNIT          = "C"
YLABEL        = "Air Temperature"
CVRMSE_LIMIT  = 30.0 
MBE_LIMIT     = 10.0

def load_config():
    if not CONFIG_PATH.exists():
        print(f"[ERROR] experiment_config.json not found at {CONFIG_PATH}")
        return None
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def validate_zone(zone, offices):
    print(f"  [Zone {zone}] Offices: {offices}")
    
    # Load measured
    measured_series = []
    for office in offices:
        s = load_keti_sensor(office, SENSOR_NAME)
        if s is not None and not s.empty: measured_series.append(s)
    
    if not measured_series: return None
    measured = pd.concat(measured_series, axis=1).mean(axis=1).dropna()

    # Load simulated (Dynamic resolution via shared_validation)
    simulated = load_simulation_variable(SIM_VAR_NAME, zone)
    
    if simulated is None or simulated.empty: return None

    # Align
    meas_al, sim_al = align_series(measured, simulated)
    if len(meas_al) == 0: return None

    # Metrics
    rmse = compute_rmse(meas_al, sim_al)
    mae = compute_mae(meas_al, sim_al)
    cvrmse = compute_cv_rmse(meas_al, sim_al)
    mbe_pct = 100.0 * float(np.mean(sim_al - meas_al)) / float(np.mean(meas_al))
    
    ashrae_pass = (cvrmse < CVRMSE_LIMIT) and (abs(mbe_pct) < MBE_LIMIT)
    status = "PASS" if ashrae_pass else "FAIL"

    # Plot
    plot_path = OUTPUT_DIR / f"noIdealLoad_temperature_{zone}.png"
    plot_comparison(
        measured=meas_al, simulated=sim_al,
        title=f"NoIdealLoad Temp | {zone}", ylabel=YLABEL,
        output_path=str(plot_path), rmse=rmse, unit=UNIT
    )

    return {
        "Zone": zone, "RMSE": round(rmse, 3), "MAE": round(mae, 3),
        "CVRMSE": round(cvrmse, 2), "MBE_pct": round(mbe_pct, 2), "Status": status
    }

def main():
    config = load_config()
    if not config: return
    
    run_dir = config["latest_run_dir"]
    print(f"--- noIdealLoad_model: Temperature Validation ---")
    print(f"TARGET RUN: {run_dir}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    zone_offices = {}
    for office, zone in SPACE_ZONE_MAP.items():
        zone_offices.setdefault(zone, []).append(office)

    results = []
    for zone in sorted(zone_offices.keys()):
        m = validate_zone(zone, zone_offices[zone])
        if m: results.append(m)

    if results:
        df = pd.DataFrame(results)
        csv_path = OUTPUT_DIR / "noIdealLoad_temperature_metrics.csv"
        df.to_csv(csv_path, index=False)
        print(f"\nSummary metrics saved to {csv_path}")
        print(df.to_string(index=False))

if __name__ == "__main__":
    main()
