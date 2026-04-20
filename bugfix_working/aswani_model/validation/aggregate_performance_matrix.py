import os
import sys
import subprocess
import pandas as pd
import numpy as np
import json
from pathlib import Path

# Add shared logic path
sys.path.append(str(Path(__file__).parent))
import shared_validation as sv

# --- Configuration ---
VALIDATION_DIR = Path(__file__).parent
PROJECT_ROOT = VALIDATION_DIR.parent.parent

# BUG12-FIX: dynamic latest-run discovery — always uses the most-recently-modified
# run directory under each model's vault instead of a hardcoded timestamp string.
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
    "Aswani-VAV": {"root": PROJECT_ROOT / "aswani_model"},
    "Ideal":      {"root": PROJECT_ROOT / "idealLoad_model"},
    "Not-Ideal":  {"root": PROJECT_ROOT / "noIdealLoad_model"},
}
# Resolve latest run for each model at startup and report it
for _m, _cfg in MODELS.items():
    _cfg["run"] = find_latest_run(_cfg["root"])
    print(f"[BUG12-FIX] {_m} -> latest run: {_cfg['run'] or '(none found)'}")

VARIABLES = ["temperature", "humidity", "co2"]
ZONES = ["TZ_C", "TZ_E", "TZ_NW", "TZ_S", "TZ_W"]

def run_all_validations():
    """Runs sub-validation scripts for all models to ensure CSVs exist."""
    for model_name, cfg in MODELS.items():
        print(f"\nProcessing {model_name}...")
        env = os.environ.copy()
        env["VAL_RUN_DIR"] = cfg["run"]
        # Force the experiment root for shared_validation.py to find the right vault
        # Actually, shared_validation uses Path(__file__).parent.parent
        # So we must call the scripts FROM their respective directories or set an ENV
        
        # We'll set VAL_SQL_PATH directly to be safe
        sql_path = cfg["root"] / "model" / "runs" / cfg["run"] / "run" / "eplusout.sql"
        env["VAL_SQL_PATH"] = str(sql_path)
        env["VAL_OUT_DIR"] = str(VALIDATION_DIR / "outputs" / model_name)
        
        os.makedirs(env["VAL_OUT_DIR"], exist_ok=True)
        
        for var in VARIABLES:
            script = VALIDATION_DIR / f"validate_{var}.py"
            print(f"  -> {var}")
            subprocess.run([sys.executable, str(script)], env=env, capture_output=True)

def aggregate_fused_data():
    """Aggregates Average Fused Score and Occupancy Fraction per zone."""
    stats = []
    for zone in ZONES:
        offices = []
        # Find offices for this zone from shared_validation
        for off, zname in sv.SPACE_ZONE_MAP.items():
            if zname == zone:
                offices.append(off)
        
        fused_scores = []
        occ_fracs = []
        
        for off in offices:
            f_path = Path(sv.FUSED_DIR) / f"{off}_fused_data.csv"
            if f_path.exists():
                df = pd.read_csv(f_path)
                # Aug 23-31 window
                fused_scores.append(df['fused_score'].mean())
                occ_fracs.append(df['occupied'].mean())
        
        stats.append({
            "Zone": zone,
            "Avg_Fused_Score": np.mean(fused_scores) if fused_scores else 0,
            "Avg_Fused_Occ": np.mean(occ_fracs) if occ_fracs else 0
        })
    return pd.DataFrame(stats)

def extract_sim_occupancy():
    """Extracts simulated occupant count for each zone and model."""
    results = []
    for model_name, cfg in MODELS.items():
        # Temporarily set ENV for get_sql_path
        os.environ["VAL_SQL_PATH"] = str(cfg["root"] / "model" / "runs" / cfg["run"] / "run" / "eplusout.sql")
        
        for zone in ZONES:
            series = sv.load_simulation_variable("Zone People Occupant Count", zone)
            avg_occ = series.mean() if series is not None else 0
            results.append({
                "Model": model_name,
                "Zone": zone,
                "Avg_Sim_Occ": avg_occ
            })
    return pd.DataFrame(results)

# BUG1-FIX: This block was originally named "def main()" but was silently overwritten
# by the second "def main()" below (Python keeps only the last definition).
# Renamed to _legacy_main_stub to prevent the overwrite; the authoritative main()
# is the block below which includes --run_id support and markdown output.
def _legacy_main_stub():
    print("=== STARTING ULTIMATE PERFORMANCE AGGREGATION ===")
    
    # 1. Ensure latest metrics exist
    run_all_validations()
    
    # 2. Get Fused Context (Window-based)
    fused_df = aggregate_fused_data()
    
    # 3. Get Sim Occupancy
    sim_occ_df = extract_sim_occupancy()
    
    # 4. Load RMSE metrics
    all_metrics = []
    for model_name in MODELS.keys():
        for var in VARIABLES:
            csv_path = VALIDATION_DIR / "outputs" / model_name / var / f"{var}_metrics_summary.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                df['Model'] = model_name
                df['Var'] = var
                
                # Unify RMSE column names
                # Temperature: RMSE_C, Humidity: RMSE_RH, CO2: RMSE_CO2
                for col in df.columns:
                    if "RMSE" in col:
                        df["RMSE_unified"] = df[col]
                        break
                
                all_metrics.append(df[['Model', 'Zone', 'Var', 'RMSE_unified']])
    
    metrics_df = pd.concat(all_metrics)
    
    # 5. Pivot for a pretty table
    pivot_df = metrics_df.pivot_table(
        index=['Model', 'Zone'], 
        columns='Var', 
        values='RMSE_unified'
    ).reset_index()
    
    # Note: Pivot might put RMSE in columns named 'temperature', 'humidity', 'co2'
    # Actually, humidity/co2 might have different unit suffixes in RMSE column name
    # Let's manually merge for safety
    
    # Merge Fused Context
    final_df = pivot_df.merge(fused_df, on='Zone', how='left')
    
    # Merge Sim Occupancy
    final_df = final_df.merge(sim_occ_df, on=['Model', 'Zone'], how='left')
    
    # Final Presentation
    print("\n" + "#"*80)
    print("ULTIMATE Aswani CALIBRATION PERFORMANCE MATRIX")
    print("#"*80)
    
    # Rename for clarity
    final_df = final_df.rename(columns={
        "temperature": "Temp_RMSE",
        "humidity": "Hum_RMSE",
        "co2": "CO2_RMSE"
    })
    
    print(final_df.sort_values(['Zone', 'Model']).to_string(index=False))
    
def get_metrics_for_run(model_name, run_id):
    """Orchestrates validation and returns a flattened metrics dictionary."""
    model_root = MODELS[model_name]["root"]
    env = os.environ.copy()
    env["VAL_RUN_DIR"] = run_id
    sql_path = model_root / "model" / "runs" / run_id / "run" / "eplusout.sql"
    env["VAL_SQL_PATH"] = str(sql_path)
    env["VAL_OUT_DIR"] = str(VALIDATION_DIR / "outputs" / model_name)
    
    os.makedirs(env["VAL_OUT_DIR"], exist_ok=True)
    
    # 1. Run validation scripts
    for var in VARIABLES:
        script = VALIDATION_DIR / f"validate_{var}.py"
        subprocess.run([sys.executable, str(script)], env=env, capture_output=True)
    
    # 2. Extract RMSE and Occupancy
    # Occupancy
    os.environ["VAL_SQL_PATH"] = str(sql_path)
    series = sv.load_simulation_variable("Zone People Occupant Count", "TZ_NW")
    avg_sim_occ = series.mean() if series is not None else 0
    
    # RMSE (NW focused for B2/B3)
    results = {"Avg_Sim_Occ_NW": avg_sim_occ}
    for var in VARIABLES:
        csv_path = VALIDATION_DIR / "outputs" / model_name / var / f"{var}_metrics_summary.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            nw_rmse = df[df['Zone'] == 'TZ_NW']['RMSE_C' if var=='temperature' else 'RMSE_RH' if var=='humidity' else 'RMSE_CO2'].values
            results[f"{var}_RMSE_NW"] = nw_rmse[0] if len(nw_rmse) > 0 else 0
            
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", type=str, help="Specific run ID to evaluate for Aswani-VAV")
    args = parser.parse_args()

    if args.run_id:
        print(f"--- TRACK B AUDIT MODE: {args.run_id} ---")
        metrics = get_metrics_for_run("Aswani-VAV", args.run_id)
        print(json.dumps(metrics, indent=2))
        return

    print("=== STARTING ULTIMATE PERFORMANCE AGGREGATION ===")
    
    # 1. Ensure latest metrics exist
    run_all_validations()
    
    # 2. Get Fused Context (Window-based)
    fused_df = aggregate_fused_data()
    
    # 3. Get Sim Occupancy
    sim_occ_df = extract_sim_occupancy()
    
    # 4. Load RMSE metrics
    all_metrics = []
    for model_name in MODELS.keys():
        for var in VARIABLES:
            csv_path = VALIDATION_DIR / "outputs" / model_name / var / f"{var}_metrics_summary.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                df['Model'] = model_name
                df['Var'] = var
                
                # Unify RMSE column names
                for col in df.columns:
                    if "RMSE" in col:
                        df["RMSE_unified"] = df[col]
                        break
                
                all_metrics.append(df[['Model', 'Zone', 'Var', 'RMSE_unified']])
    
    metrics_df = pd.concat(all_metrics)
    
    # 5. Pivot for a pretty table
    pivot_df = metrics_df.pivot_table(
        index=['Model', 'Zone'], 
        columns='Var', 
        values='RMSE_unified'
    ).reset_index()
    
    # Merge Fused Context
    final_df = pivot_df.merge(fused_df, on='Zone', how='left')
    
    # Merge Sim Occupancy
    final_df = final_df.merge(sim_occ_df, on=['Model', 'Zone'], how='left')
    
    # Final Presentation
    print("\n" + "#"*80)
    print("ULTIMATE Aswani CALIBRATION PERFORMANCE MATRIX")
    print("#"*80)
    
    # Rename for clarity
    final_df = final_df.rename(columns={
        "temperature": "Temp_RMSE",
        "humidity": "Hum_RMSE",
        "co2": "CO2_RMSE"
    })
    
    print(final_df.sort_values(['Zone', 'Model']).to_string(index=False))
    
    # Save to Markdown
    md_path = VALIDATION_DIR / "outputs" / "complete_performance_matrix.md"
    os.makedirs(md_path.parent, exist_ok=True)
    with open(md_path, 'w') as f:
        f.write("# Aswani Calibration: Ultimate Performance Matrix\n\n")
        f.write("Generated from simulation window: Aug 23 - 31, 2013.\n\n")
        df_sorted = final_df.sort_values(['Zone', 'Model'])
        header = "| " + " | ".join(df_sorted.columns) + " |"
        sep = "| " + " | ".join(["---"] * len(df_sorted.columns)) + " |"
        f.write(header + "\n" + sep + "\n")
        for _, row in df_sorted.iterrows():
            line = "| " + " | ".join([str(x) for x in row.values]) + " |"
            f.write(line + "\n")
        f.write("\n\n*Note: Temp_RMSE is in C, Hum_RMSE in %, CO2_RMSE in ppm.*")
    
    print(f"\nResults saved to: {md_path}")

if __name__ == "__main__":
    main()
