import os
import sys
import pandas as pd
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(r"C:\Users\me.com\Documents\engery\OpenStudio_Project")
VALIDATION_DIR = PROJECT_ROOT / "aswani_model" / "validation"
SYS_PYTHON = r"C:\Users\me.com\anaconda3\envs\openstudio312\python.exe"

# The 6 Final Runs
MATRIX_RUNS = {
    "Aswani-VAV": {
        "Fused":  "B1b_eq20.0_oa0.01_inf0.5_20260418_161821",
        "ASHRAE": "B1b_eq20.0_oa0.01_inf0.5_20260418_161830"
    },
    "Ideal": {
        "Fused":  "run_20260418_161954",
        "ASHRAE": "run_20260418_162002"
    },
    "Not-Ideal": {
        "Fused":  "run_20260418_162010",
        "ASHRAE": "run_20260418_162017"
    }
}

SCRIPTS = ["validate_temperature.py", "validate_humidity.py", "validate_co2.py"]

def run_matrix():
    all_metrics = []
    
    for model_name, modes in MATRIX_RUNS.items():
        model_key = "aswani_model" if model_name == "Aswani-VAV" else ("idealLoad_model" if model_name == "Ideal" else "noIdealLoad_model")
        model_root = PROJECT_ROOT / model_key
        
        for mode_name, run_id in modes.items():
            print(f"\n>>> Validating {model_name} [{mode_name}]...")
            
            sql_path = model_root / "model" / "runs" / run_id / "run" / "eplusout.sql"
            out_dir = VALIDATION_DIR / "outputs" / f"{model_name}_{mode_name}"
            out_dir.mkdir(parents=True, exist_ok=True)
            
            env = os.environ.copy()
            env["VAL_RUN_DIR"] = run_id
            env["VAL_SQL_PATH"] = str(sql_path)
            env["VAL_OUT_DIR"] = str(out_dir)
            
            for s in SCRIPTS:
                script_path = VALIDATION_DIR / s
                print(f"  - Running {s}...")
                subprocess.run([SYS_PYTHON, str(script_path)], env=env, capture_output=True)
                
                # Collect Metrics
                var_name = s.replace("validate_", "").replace(".py", "")
                metrics_file = out_dir / var_name / f"{var_name}_metrics_summary.csv"
                if metrics_file.exists():
                    df = pd.read_csv(metrics_file)
                    df["Model"] = model_name
                    df["Mode"] = mode_name
                    df["Variable"] = var_name
                    all_metrics.append(df)
                else:
                    print(f"    [!] Metrics not found: {metrics_file}")
                    
    if all_metrics:
        master_df = pd.concat(all_metrics, ignore_index=True)
        master_df.to_csv(VALIDATION_DIR / "final_6run_matrix.csv", index=False)
        print("\nSuccess! Final matrix saved to aswani_model/validation/final_6run_matrix.csv")
        
        # Print a nice summary table for Temperature RMSE
        temp_df = master_df[master_df["Variable"] == "temperature"]
        pivot = temp_df.pivot_table(index="Model", columns="Mode", values="RMSE_C", aggfunc="mean")
        print("\n--- Temperature RMSE (Mean across zones) ---")
        print(pivot)
        
if __name__ == "__main__":
    import subprocess
    run_matrix()
