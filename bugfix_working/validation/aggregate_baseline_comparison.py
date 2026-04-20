import os
import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path

# BUG3-FIX: Use absolute path anchored to this file, not relative to cwd
_HERE = Path(__file__).resolve().parent

def extract_nw_metrics(run_dir):
    """Extracted core validation logic to avoid dependencies."""
    sql_path = Path(run_dir) / "run" / "eplusout.sql"
    if not sql_path.exists():
        return None
    
    conn = sqlite3.connect(sql_path)
    
    def get_var(var_name, key_value):
        query = f"""
        SELECT Value, TimeIndex 
        FROM ReportData 
        INNER JOIN ReportDataDictionary ON ReportData.ReportDataDictionaryIndex = ReportDataDictionary.ReportDataDictionaryIndex
        WHERE Name = '{var_name}' AND KeyValue = '{key_value}'
        """
        return pd.read_sql_query(query, conn)

    # Note: Extracting just NW Zone for this comparison
    metrics = {}
    for var, key in [
        ("Zone Air Temperature", "TZ_NW"),
        ("Zone Air Relative Humidity", "TZ_NW"),
        ("Zone Air CO2 Concentration", "TZ_NW"),
        ("Zone People Occupant Count", "TZ_NW")
    ]:
        df = get_var(var, key)
        if df.empty:
            print(f"  MISSING: {var} for {key}")
            conn.close()
            return None
        metrics[var] = round(df['Value'].mean(), 2)
    
    conn.close()
    return {
        "Sim_Temp_Avg": metrics["Zone Air Temperature"],
        "Sim_Hum_Avg": metrics["Zone Air Relative Humidity"],
        "Sim_CO2_Avg": metrics["Zone Air CO2 Concentration"],
        "Sim_Occ_Avg": metrics["Zone People Occupant Count"]
    }

def generate_table(results):
    df = pd.DataFrame(results)
    # BUG3-FIX: absolute path so script works from any working directory
    output_dir = _HERE / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / "baseline_schedule_comparison.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nFinal Comparison Table Saved to: {csv_path}")
    return df

# BUG3-FIX: added main() entry point — script previously had no callable entry
def main():
    """
    Aggregate baseline comparison metrics from a list of run directories.
    Run directories must contain run/eplusout.sql from a completed EnergyPlus sim.
    Edit the 'runs' list below to point to the actual run vault directories.
    """
    PROJECT_ROOT = _HERE.parent.parent
    
    # Define the runs to compare — update these paths after each new simulation
    runs = [
        # Example: PROJECT_ROOT / "aswani_model" / "model" / "runs" / "ashrae_eq20.0_oa0.01_inf0.5_20260417_151213",
        # Example: PROJECT_ROOT / "aswani_model" / "model" / "runs" / "fused_eq20.0_oa0.01_inf0.5_20260417_181516",
    ]
    
    if not runs:
        print("[INFO] No run directories configured in main(). Edit 'runs' list to add paths.")
        return
    
    results = []
    for run_dir in runs:
        print(f"Processing: {run_dir}")
        metrics = extract_nw_metrics(run_dir)
        if metrics:
            metrics["run_dir"] = str(run_dir)
            results.append(metrics)
        else:
            print(f"  [SKIP] Could not extract metrics from {run_dir}")
    
    if results:
        generate_table(results)
    else:
        print("[ERROR] No valid results collected.")

if __name__ == "__main__":
    main()

