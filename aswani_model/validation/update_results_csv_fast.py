import os
import pandas as pd
import json
import subprocess
import sys
from pathlib import Path

# --- Config ---
VALIDATION_DIR = Path(r"c:\Users\me.com\Documents\engery\OpenStudio_Project\aswani_model\validation")
AGGREGATOR_SCRIPT = VALIDATION_DIR / "aggregate_performance_matrix.py"
RESULTS_FILE = VALIDATION_DIR / "outputs" / "track_b_results_granular.csv"
PYTHON_EXE = sys.executable

def get_metrics(run_id):
    print(f"Processing: {run_id}")
    env = os.environ.copy()
    cmd = [PYTHON_EXE, str(AGGREGATOR_SCRIPT), "--run_id", run_id]
    res = subprocess.run(cmd, env=env, capture_output=False, text=True)
    if res.returncode != 0:
        return None
    try:
        output = res.stdout
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        return json.loads(output[json_start:json_end])
    except Exception:
        return None

def main():
    if not RESULTS_FILE.exists(): return

    # Define the "Best" runs for each stage to focus on
    target_runs = {
        "B0": "B0_eq20.0_oa0.01_inf0.5_20260420_022219",
        "B1a": "B1a_eq20.0_oa0.01_inf0.5_20260418_184017",
        "B1b": "B1b_eq20.0_oa0.01_inf0.5_20260418_184053",
        "B2a": "B2a_eq25.0_oa0.01_inf0.5_20260418_184300",
        "B3":  "B3_eq25.0_oa0.015_inf0.5_20260418_184749",
        "B5a": "B5a_eq25.0_oa0.015_inf0.25_20260418_184918",
        "B5b": "B5b_eq25.0_oa0.015_inf0.5_20260418_185001",
        "B4":  "B4_eq25.0_oa0.015_inf0.5_20260418_185116"
    }

    df = pd.read_csv(RESULTS_FILE)
    
    # We will build a new dataframe with just these target runs + updated metrics
    all_updated_data = []
    
    # Also include the original B0 run data if it was missing from the file
    if target_runs["B0"] not in df['run_id'].values:
        b0_row = {
            "eq_density": 20.0, "eq_sch_type": "Scaled", "oa_rate": 0.01, 
            "infiltration": 0.5, "use_baseline": False, "stage": "B0", 
            "run_id": target_runs["B0"], "sensible_fraction": 0.577
        }
        df = pd.concat([pd.DataFrame([b0_row]), df], ignore_index=True)

    for stage, rid in target_runs.items():
        # Get existing params from any row with this run_id
        matching = df[df['run_id'] == rid]
        if matching.empty: continue
        
        row = matching.iloc[0].to_dict()
        metrics = get_metrics(rid)
        if metrics:
            row.update(metrics)
            all_updated_data.append(row)

    updated_df = pd.DataFrame(all_updated_data)
    updated_df.to_csv(RESULTS_FILE, index=False)
    print(f"Fast Update complete. Saved to {RESULTS_FILE}")

if __name__ == "__main__":
    main()
