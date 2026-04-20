import subprocess
import sys
import os
import pandas as pd
from pathlib import Path
import json
from validation.aggregate_baseline_comparison import extract_nw_metrics, generate_table

# --- CONFIGURATION ---
MODELS = {
    "Aswani": "aswani_model/model/test_comparison_ASHRAE_Aswani.py",
    "IdealLoad": "idealLoad_model/model/test_comparison_ASHRAE_IdealLoad.py",
    "NoIdealLoad": "noIdealLoad_model/model/test_comparison_ASHRAE_NoIdealLoad.py"
}

BASE_PARAMS = {
    "eq_density": 20.0,
    "oa_rate": 0.01,
    "infiltration": 0.5
}

def run_model(model_name, script_path, mode):
    print(f"\n>>> EXECUTION: {model_name} | Mode: {mode}")
    cmd = [
        sys.executable, 
        script_path,
        "--schedule_mode", mode,
        "--eq_density", str(BASE_PARAMS["eq_density"]),
        "--oa_rate", str(BASE_PARAMS["oa_rate"]),
        "--infiltration", str(BASE_PARAMS["infiltration"]),
        "--stage", f"Comp_{model_name}_{mode}"
    ]
    
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"FAILED: {model_name} - {mode}")
        print(proc.stderr)
        return None
    
    # Extract run directory from output
    # My scripts print: DONE: <run_name>
    for line in proc.stdout.splitlines():
        if line.startswith("DONE: "):
            run_name = line.replace("DONE: ", "").strip()
            return Path(script_path).parent / "runs" / run_name
    return None

def main():
    results = []
    
    for model_name, script in MODELS.items():
        for mode in ['ashrae', 'fused']:
            run_dir = run_model(model_name, script, mode)
            if run_dir:
                metrics = extract_nw_metrics(run_dir)
                if metrics:
                    res = {
                        "model": model_name,
                        "schedule_type": mode.upper(),
                        **BASE_PARAMS,
                        **metrics
                    }
                    results.append(res)
                else:
                    print(f"WARNING: Could not extract metrics for {model_name} {mode}")
            else:
                print(f"ERROR: No run directory found for {model_name} {mode}")

    if results:
        df = generate_table(results)
        
        # --- Improvement Calculation ---
        print("\n" + "="*50)
        print("BASELINE IMPROVEMENT ANALYSIS (ASHRAE -> FUSED)")
        print("="*50)
        for model_name in MODELS.keys():
            m_df = df[df['model'] == model_name]
            if len(m_df) == 2:
                ash = m_df[m_df['schedule_type'] == 'ASHRAE'].iloc[0]
                fus = m_df[m_df['schedule_type'] == 'FUSED'].iloc[0]
                
                # Temperature Improvement
                t_diff = ash['Sim_Temp_Avg'] - fus['Sim_Temp_Avg']
                # CO2 Improvement
                c_imp = ((ash['Sim_CO2_Avg'] - fus['Sim_CO2_Avg']) / ash['Sim_CO2_Avg']) * 100
                
                print(f"[{model_name}]")
                print(f"  - Delta T: {t_diff:+.2f} C")
                print(f"  - CO2 Reduction: {c_imp:+.1f}%")
        print("="*50)

if __name__ == "__main__":
    main()
