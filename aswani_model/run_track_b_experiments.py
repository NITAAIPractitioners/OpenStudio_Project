import os
import subprocess
import json
import pandas as pd
from pathlib import Path

# --- Environment Configuration ---
PYTHON_EXE = r"C:\Users\me.com\anaconda3\envs\openstudio312\python.exe"
OS_PYTHON_PATH = r"C:\openstudioapplication-1.10.0\Python"

SCRIPT_DIR = Path(__file__).parent
MODEL_SCRIPT = SCRIPT_DIR / "model" / "test_unified_Aswani.py"
AGGREGATOR_SCRIPT = SCRIPT_DIR / "validation" / "aggregate_performance_matrix.py"
RESULTS_FILE = SCRIPT_DIR / "validation" / "outputs" / "track_b_results_granular.csv"

def run_simulation(params):
    env = os.environ.copy()
    env["PYTHONPATH"] = OS_PYTHON_PATH
    
    cmd = [PYTHON_EXE, str(MODEL_SCRIPT)]
    for k, v in params.items():
        if k == "stage":
            cmd.extend([f"--{k}", str(v)])
            continue
            
        if isinstance(v, bool):
            if v: cmd.append(f"--{k}") # Robust flag handling
        else:
            cmd.extend([f"--{k}", str(v)])
    
    print(f"\n>>> Running Simulation: {params['stage']} with {params}")
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"ERROR: Simulation failed\n{res.stderr}")
        return None
    
    config_path = SCRIPT_DIR / "experiment_config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config["latest_run_dir"]

def get_metrics(run_id):
    env = os.environ.copy()
    env["PYTHONPATH"] = OS_PYTHON_PATH
    cmd = [PYTHON_EXE, str(AGGREGATOR_SCRIPT), "--run_id", run_id]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"ERROR: Aggregation failed\n{res.stderr}")
        return None
    
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
    
    def add_exp(stage_id, p):
        run_id = run_simulation({**p, "stage": stage_id})
        if run_id:
            m = get_metrics(run_id)
            if m:
                row = {**p, "stage": stage_id, **m, "run_id": run_id}
                experiments.append(row)
                return row
        return None

    # STAGE B1: Reference Baselines
    add_exp("B1a", {"eq_density": 20.0, "eq_sch_type": "Scaled", "oa_rate": 0.01, "infiltration": 0.5, "use_baseline": True})
    add_exp("B1b", {"eq_density": 20.0, "eq_sch_type": "Scaled", "oa_rate": 0.01, "infiltration": 0.5, "use_baseline": False})

    # STAGE B2: Equipment Density Sweep
    for d in [10.0, 15.0, 25.0]:
        add_exp("B2a", {"eq_density": d, "eq_sch_type": "Scaled", "oa_rate": 0.01, "infiltration": 0.5, "use_baseline": False})

    # STAGE B2b: Equipment Schedule Sensitivity
    for sch in ["Constant", "Softer"]:
        add_exp("B2b", {"eq_density": 20.0, "eq_sch_type": sch, "oa_rate": 0.01, "infiltration": 0.5, "use_baseline": False})

    # STAGE B3: Ventilation Sweep
    for oa in [0.005, 0.0075, 0.0125, 0.015]:
        add_exp("B3", {"eq_density": 25.0, "eq_sch_type": "Scaled", "oa_rate": oa, "infiltration": 0.5, "use_baseline": False})

    # STAGE B5a: Infiltration Sensitivity
    for inf in [0.1, 0.25]:
        add_exp("B5a", {"eq_density": 25.0, "eq_sch_type": "Scaled", "oa_rate": 0.015, "infiltration": inf, "use_baseline": False})

    # STAGE B5b: NEW EXPERIMENT - Sensible Fraction Refinement
    for f in [0.55, 0.65]: 
        add_exp("B5b", {"eq_density": 25.0, "eq_sch_type": "Scaled", "oa_rate": 0.015, "infiltration": 0.5, "sensible_fraction": f, "use_baseline": False})

    # STAGE B4: THE GOLDEN MODEL (Option A)
    add_exp("B4", {"eq_density": 25.0, "eq_sch_type": "Scaled", "oa_rate": 0.015, "infiltration": 0.5, "use_baseline": False})

    # Save Granular Zone-Level Data
    df = pd.DataFrame(experiments)
    df.to_csv(RESULTS_FILE, index=False)
    print(f"\n\n=== TRACK B EXPERIMENTS COMPLETE (GRANULAR) ===")
    print(f"Results saved to: {RESULTS_FILE}")
    
    print("\n>>> PRIMARY ANALYTICAL REFERENCE (TZ_NW):")
    cols = [c for c in df.columns if 'TZ_NW' in c or c in ['stage', 'eq_density', 'oa_rate', 'infiltration']]
    print(df[cols].to_string(index=False))

if __name__ == "__main__":
    main()
