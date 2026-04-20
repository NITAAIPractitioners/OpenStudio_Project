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
    print(f"Fetching: {run_id}")
    env = os.environ.copy()
    cmd = [PYTHON_EXE, str(AGGREGATOR_SCRIPT), "--run_id", run_id]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0: return None
    try:
        output = res.stdout
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        return json.loads(output[json_start:json_end])
    except Exception: return None

def main():
    target_runs = [
        # (Stage, Run_ID)
        ("B0",  "B0_eq20.0_oa0.01_inf0.5_20260420_022219"),
        ("B1b", "B1b_eq20.0_oa0.01_inf0.5_20260418_184053"),
        ("B2a", "B2a_eq25.0_oa0.01_inf0.5_20260418_184300"),
        ("B3",  "B3_eq25.0_oa0.015_inf0.5_20260418_184749"),
        ("B5a", "B5a_eq25.0_oa0.015_inf0.25_20260418_184918"),
        ("B5b", "B5b_eq25.0_oa0.015_inf0.5_20260418_185001"),
        ("B4",  "B4_eq25.0_oa0.015_inf0.5_20260418_185116")
    ]

    all_data = []
    for stage, rid in target_runs:
        metrics = get_metrics(rid)
        if metrics:
            row = {"stage": stage, "run_id": rid}
            row.update(metrics)
            all_data.append(row)

    df = pd.DataFrame(all_data)
    df.to_csv(RESULTS_FILE, index=False)
    print(f"CSV REBUILT: {RESULTS_FILE}")

if __name__ == "__main__":
    main()
