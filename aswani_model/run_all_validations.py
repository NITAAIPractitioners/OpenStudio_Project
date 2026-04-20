import os
import subprocess
import pandas as pd
import sys
from pathlib import Path

# --- Configuration ---
_HERE          = Path(__file__).parent          # aswani_model/
VALIDATION_DIR = _HERE / "validation"
PROJECT_ROOT   = _HERE.parent
def find_latest_run(model_root: Path) -> str:
    """Return the name of the most-recently-modified run directory, or '' if none."""
    runs_dir = model_root / "model" / "runs"
    if not runs_dir.exists():
        return ""
    candidates = [d for d in runs_dir.iterdir() if d.is_dir()]
    if not candidates:
        return ""
    latest = max(candidates, key=lambda d: d.stat().st_mtime)
    return latest.name
MODELS = {
    "Aswani-VAV": PROJECT_ROOT / "aswani_model",
    "Ideal":      PROJECT_ROOT / "idealLoad_model",
    "Not-Ideal":  PROJECT_ROOT / "noIdealLoad_model",   # was missing entirely
}

VARIABLES = ["temperature", "humidity", "co2"]

def run_validations():
    summary_results = []

    for model_name, model_root in MODELS.items():
        run_dir = find_latest_run(model_root)

        if not run_dir:
            print(f"\n[SKIP] {model_name}: no run directories found under {model_root / 'model' / 'runs'}")
            continue

        sql_path = model_root / "model" / "runs" / run_dir / "run" / "eplusout.sql"
        if not sql_path.exists():
            print(f"\n[SKIP] {model_name}: SQL not found for latest run '{run_dir}'")
            continue

        print(f"\n{'='*60}")
        print(f"RUNNING VALIDATION FOR: {model_name}")
        print(f"  Run : {run_dir}")
        print(f"  SQL : {sql_path}")
        print("="*60)

        # Set environment variables for shared_validation.py
        env = os.environ.copy()
        env["VAL_RUN_DIR"]  = run_dir
        env["VAL_SQL_PATH"] = str(sql_path)
        env["VAL_OUT_DIR"]  = str(VALIDATION_DIR / "outputs" / model_name)

        os.makedirs(env["VAL_OUT_DIR"], exist_ok=True)

        for var in VARIABLES:
            script = VALIDATION_DIR / f"validate_{var}.py"
            if script.exists():
                print(f"  --> Executing {script.name}...")
                res = subprocess.run(
                    [sys.executable, str(script)],
                    env=env, capture_output=True, text=True
                )
                if res.returncode != 0:
                    print(f"    [ERROR] {script.name} failed:\n{res.stderr[:400]}")

                # Try to load metrics for summary
                metrics_path = Path(env["VAL_OUT_DIR"]) / var / f"{var}_metrics_summary.csv"
                if metrics_path.exists():
                    df = pd.read_csv(metrics_path)
                    df["Model"] = model_name
                    summary_results.append(df)
            else:
                print(f"  [SKIP] Script not found: {script}")

    # --- Generate Comparative Summary ---
    if summary_results:
        master_df = pd.concat(summary_results, ignore_index=True)

        print("\n\n" + "="*80)
        print("COMPARATIVE METRICS SUMMARY")
        print("="*80)

        if "RMSE_C" in master_df.columns:
            cols = [c for c in ["Model", "Zone", "Offices", "RMSE_C", "MAE_C", "MBE_pct", "ASHRAE14"] if c in master_df.columns]
            temp_df = master_df.dropna(subset=["RMSE_C"])
            print("\nAIR TEMPERATURE COMPARISON:")
            print(temp_df.sort_values(["Zone", "Model"])[cols].to_string(index=False))

        print("\n" + "="*80)
        print("Audit Complete. Plots saved to aswani_model/validation/outputs/")
    else:
        print("\n[WARNING] No summary metrics were collected. Check that SQL files exist.")

if __name__ == "__main__":
    run_validations()

