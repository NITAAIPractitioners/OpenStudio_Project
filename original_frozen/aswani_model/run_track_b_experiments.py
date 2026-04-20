import subprocess
import json
import pandas as pd
from pathlib import Path
import sys
import time

SCRIPT_DIR = Path(__file__).parent
MODEL_SCRIPT = SCRIPT_DIR / "model" / "test_unified_Aswani.py"
AGGREGATOR_SCRIPT = SCRIPT_DIR / "validation" / "aggregate_performance_matrix.py"
RESULTS_FILE = SCRIPT_DIR / "validation" / "outputs" / "track_b_results.csv"

def run_simulation(params):
    cmd = [sys.executable, str(MODEL_SCRIPT)]
    for k, v in params.items():
        if isinstance(v, bool):
            if v: cmd.append(f"--{k}")
        elif v == "": # Handle the way I declared it in main
             cmd.append(f"--{k}")
        else:
            cmd.extend([f"--{k}", str(v)])
    
    print(f"\n>>> Running Simulation: {params['stage']} with {params}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"ERROR: Simulation failed\n{res.stderr}")
        return None
    
    # Extract Run ID from experiment_config.json
    config_path = SCRIPT_DIR / "experiment_config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config["latest_run_dir"]

def get_metrics(run_id):
    cmd = [sys.executable, str(AGGREGATOR_SCRIPT), "--run_id", run_id]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"ERROR: Aggregation failed\n{res.stderr}")
        return None
    
    # Aggregator prints JSON block at the end
    try:
        output = res.stdout
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        return json.loads(output[json_start:json_end])
    except Exception as e:
        print(f"ERROR parsing metrics: {e}")
        return None

def main():
    experiments = []
    
    # ---------------------------------------------------------
    # STAGE B1: Reference Baselines
    # ---------------------------------------------------------
    # B1a: Original Baseline (Force --use_baseline)
    params_a = {
        "stage": "B1a",
        "eq_density": 20.0,
        "eq_sch_type": "Scaled",
        "oa_rate": 0.010,
        "infiltration": 0.5,
        "use_baseline": "" # CLI flag
    }
    run_id_a = run_simulation(params_a)
    if run_id_a:
        metrics = get_metrics(run_id_a)
        if metrics:
            experiments.append({**params_a, **metrics, "run_id": run_id_a})

    # B1b: Occupancy-Calibrated Baseline (Reference)
    params_b = {
        "stage": "B1b",
        "eq_density": 20.0,
        "eq_sch_type": "Scaled",
        "oa_rate": 0.010,
        "infiltration": 0.5
    }
    run_id_b = run_simulation(params_b)
    if run_id_b:
        metrics = get_metrics(run_id_b)
        if metrics:
            experiments.append({**params_b, **metrics, "run_id": run_id_b})

    # ---------------------------------------------------------
    # STAGE B3 (Skipping - Already Run)
    # ---------------------------------------------------------
    """
    for oa in [0.005, 0.0075, 0.0125, 0.015]:
        ...
    """

    # ---------------------------------------------------------
    # STAGE B5a: Infiltration Sensitivity
    # ---------------------------------------------------------
    for inf in [0.1, 0.25]: # 0.5 already run in B3 winner
        params = {
            "stage": "B5a",
            "eq_density": 25.0,
            "eq_sch_type": "Scaled",
            "oa_rate": 0.015, # B3 winner
            "infiltration": inf
        }
        run_id = run_simulation(params)
        if run_id:
            metrics = get_metrics(run_id)
            if metrics:
                row = {**params, **metrics, "run_id": run_id}
                experiments.append(row)

    # Save all results (Append mode or reload/save)
    if RESULTS_FILE.exists():
        old_df = pd.read_csv(RESULTS_FILE)
        df = pd.concat([old_df, pd.DataFrame(experiments)])
    else:
        df = pd.DataFrame(experiments)
    
    df.to_csv(RESULTS_FILE, index=False)
    print(f"\n\n=== TRACK B EXPERIMENTS COMPLETE ===")
    print(f"Results saved to: {RESULTS_FILE}")
    print(df.to_string())

if __name__ == "__main__":
    main()
