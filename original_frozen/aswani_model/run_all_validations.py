import os
import subprocess
import pandas as pd
import sys
from pathlib import Path

# --- Configuration ---
VALIDATION_DIR = Path(__file__).parent / "validation"
RUNS_BASE      = Path(__file__).parent / "model" / "runs"

MODELS = {
    "Ideal_Loads": "run_20260416_162119",
    "VAV_Reheat":  "run_20260417_151213"
}

VARIABLES = ["temperature", "humidity", "co2"]

def run_validations():
    summary_results = []
    
    for model_name, run_dir in MODELS.items():
        print(f"\n" + "="*60)
        print(f"RUNNING VALIDATION FOR: {model_name} ({run_dir})")
        print("="*60)
        
        # Set environment variables for shared_validation.py
        env = os.environ.copy()
        env["VAL_RUN_DIR"] = run_dir
        env["VAL_OUT_DIR"] = str(VALIDATION_DIR / "outputs" / model_name)
        
        # Ensure output directory exists
        os.makedirs(env["VAL_OUT_DIR"], exist_ok=True)
        
        for var in VARIABLES:
            script = VALIDATION_DIR / f"validate_{var}.py"
            if script.exists():
                print(f"  --> Executing {script.name}...")
                res = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
                if res.returncode != 0:
                    print(f"    [ERROR] {script.name} failed:\n{res.stderr}")
                
                # Try to load metrics for summary
                metrics_path = Path(env["VAL_OUT_DIR"]) / var / f"{var}_metrics_summary.csv"
                if metrics_path.exists():
                    df = pd.read_csv(metrics_path)
                    df['Model'] = model_name
                    summary_results.append(df)
            else:
                print(f"  [SKIP] Script not found: {script}")

    # --- Generate Comparative Summary ---
    if summary_results:
        master_df = pd.concat(summary_results, ignore_index=True)
        
        print("\n\n" + "="*80)
        print("COMPARATIVE METRICS SUMMARY")
        print("="*80)
        
        # Filter for Temperature first (primary success metric)
        if "temperature" in master_df.columns or any("RMSE" in c for c in master_df.columns):
            # The CSV names might vary slightly between scripts, let's be flexible
            # Expected columns: Zone, Offices, RMSE_C, MAE_C, MBE_pct, Model
            cols = ["Model", "Zone", "RMSE_C", "MAE_C", "MBE_pct", "ASHRAE14"]
            temp_df = master_df[master_df['RMSE_C'].notnull()] if 'RMSE_C' in master_df.columns else master_df
            print("\nAIR TEMPERATURE COMPARISON:")
            print(temp_df.sort_values(['Zone', 'Model'])[cols].to_string(index=False))
            
        print("\n" + "="*80)
        print("Audit Complete. Plots saved to aswani_model/validation/outputs/")

if __name__ == "__main__":
    run_validations()
