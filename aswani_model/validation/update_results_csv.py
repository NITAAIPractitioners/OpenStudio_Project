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
    env = os.environ.copy()
    # Ensure correct ENV for aggregator
    cmd = [PYTHON_EXE, str(AGGREGATOR_SCRIPT), "--run_id", run_id]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error fetching metrics for {run_id}: {res.stderr}")
        return None
    try:
        output = res.stdout
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        return json.loads(output[json_start:json_end])
    except Exception as e:
        print(f"Error parsing metrics for {run_id}: {e}")
        return None

def main():
    if not RESULTS_FILE.exists():
        print("Results file not found.")
        return

    df = pd.read_csv(RESULTS_FILE)
    print(f"Current rows: {len(df)}")

    # Add B0 (Naive Fused) if missing
    # Run ID for B0 was found in logs: B0_eq20.0_oa0.01_inf0.5_20260420_022219
    b0_run_id = "B0_eq20.0_oa0.01_inf0.5_20260420_022219"
    if b0_run_id not in df['run_id'].values:
        print(f"Adding B0 run: {b0_run_id}")
        # Note: B0 uses same params as B1b but with 45m lag
        b0_row = {
            "eq_density": 20.0, "eq_sch_type": "Scaled", "oa_rate": 0.01, 
            "infiltration": 0.5, "use_baseline": False, "stage": "B0", 
            "run_id": b0_run_id, "sensible_fraction": 0.577
        }
        df = pd.concat([pd.DataFrame([b0_row]), df], ignore_index=True)

    # Re-fetch metrics for ALL runs to include MAE
    all_updated_data = []
    for _, row in df.iterrows():
        run_id = row['run_id']
        print(f"Updating: {run_id}")
        metrics = get_metrics(run_id)
        if metrics:
            # Merge existing params with new metrics
            # Keep original params from the row, overwrite metrics
            updated_row = row.to_dict()
            updated_row.update(metrics)
            all_updated_data.append(updated_row)
        else:
            print(f"Skipping {run_id} due to error.")

    updated_df = pd.DataFrame(all_updated_data)
    updated_df.to_csv(RESULTS_FILE, index=False)
    print(f"Updated results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    main()
