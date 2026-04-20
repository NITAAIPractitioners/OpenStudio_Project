import pandas as pd
from pathlib import Path
from validation.aggregate_baseline_comparison import extract_nw_metrics, generate_table

# --- MANUAL PICK LIST OF SUCCESSFUL RUNS ---
RUNS = [
    {"model": "Aswani", "schedule_type": "ASHRAE", "path": "aswani_model/model/runs/ashrae_eq20.0_oa0.01_inf0.5_20260417_213040"},
    {"model": "Aswani", "schedule_type": "FUSED", "path": "aswani_model/model/runs/fused_eq20.0_oa0.01_inf0.5_20260417_213108"},
    {"model": "IdealLoad", "schedule_type": "ASHRAE", "path": "idealLoad_model/model/runs/ashrae_eq20.0_oa0.01_inf0.5_20260417_213127"},
    {"model": "IdealLoad", "schedule_type": "FUSED", "path": "idealLoad_model/model/runs/fused_eq20.0_oa0.01_inf0.5_20260417_213144"},
    {"model": "NoIdealLoad", "schedule_type": "ASHRAE", "path": "noIdealLoad_model/model/runs/ashrae_eq20.0_oa0.01_inf0.5_20260417_213154"},
    {"model": "NoIdealLoad", "schedule_type": "FUSED", "path": "noIdealLoad_model/model/runs/fused_eq20.0_oa0.01_inf0.5_20260417_213228"}
]

def main():
    results = []
    for run in RUNS:
        print(f"Aggregating: {run['model']} {run['schedule_type']}...")
        metrics = extract_nw_metrics(run['path'])
        if metrics:
            results.append({
                "model": run['model'],
                "schedule_type": run['schedule_type'],
                "eq_density": 20.0,
                "oa_rate": 0.01,
                "infiltration": 0.5,
                **metrics
            })
        else:
            print(f"  ERROR: Could not extract from {run['path']}")
    
    if results:
        df = generate_table(results)
        print("\nSUCCESS: Final comparison table generated.")
        
        # Display Improvement
        print("\n" + "="*50)
        print("FINAL BASELINE IMPROVEMENT CROSS-MODEL")
        print("="*50)
        for m in ["Aswani", "IdealLoad", "NoIdealLoad"]:
            m_df = df[df['model'] == m]
            if len(m_df) == 2:
                ash = m_df[m_df['schedule_type'] == 'ASHRAE'].iloc[0]
                fus = m_df[m_df['schedule_type'] == 'FUSED'].iloc[0]
                t_diff = ash['Sim_Temp_Avg'] - fus['Sim_Temp_Avg']
                c_imp = ((ash['Sim_CO2_Avg'] - fus['Sim_CO2_Avg']) / ash['Sim_CO2_Avg']) * 100
                print(f"[{m}]")
                print(f"  - Delta T: {t_diff:+.2f} C")
                print(f"  - CO2 Reduction: {c_imp:+.1f}%")
        print("="*50)

if __name__ == "__main__":
    main()
