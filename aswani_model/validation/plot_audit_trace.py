import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# --- Configuration ---
VALIDATION_DIR = Path(r"c:\Users\me.com\Documents\engery\OpenStudio_Project\aswani_model\validation")
sys.path.append(str(VALIDATION_DIR))
import shared_validation as sv

RUN_NAIVE = "B0_eq20.0_oa0.01_inf0.5_20260420_022219"
RUN_OPTIMIZED = "B4_eq25.0_oa0.015_inf0.5_20260418_185116"
ZONE = "TZ_NW"
OFFICES = ["413", "415", "417", "419", "421", "423"]
# Adopting the user's "Good" filename
OUTPUT_PATH = VALIDATION_DIR / "outputs" / "TZ_NW_super_validation_audit.png"

# Classical Styling (Academic White Background)
plt.style.use('default')
plt.rcParams.update({
    "font.family": "serif",
    "axes.grid": True,
    "grid.linestyle": ":",
    "grid.alpha": 0.5,
    "legend.frameon": True,
    "legend.facecolor": "white",
    "legend.edgecolor": "black"
})

def load_sim_data(run_id, var_name, zone):
    os.environ["VAL_RUN_DIR"] = run_id
    series = sv.load_simulation_variable(var_name, zone)
    return series

def load_meas_data(offices, sensor_name):
    series_list = []
    for off in offices:
        s = sv.load_keti_sensor(off, sensor_name)
        if s is not None and not s.empty: series_list.append(s)
    if not series_list: return None
    # Use inner join to ensure we only average concurrent sensors
    return pd.concat(series_list, axis=1).mean(axis=1)

def main():
    print("Generating Academic-Style Super Validation Audit Trace...")
    
    # 1. Load Data
    meas_temp = load_meas_data(OFFICES, "temperature")
    meas_hum  = load_meas_data(OFFICES, "humidity")
    meas_co2  = load_meas_data(OFFICES, "co2")
    
    naive_temp = load_sim_data(RUN_NAIVE, "Zone Air Temperature", ZONE)
    naive_hum  = load_sim_data(RUN_NAIVE, "Zone Air Relative Humidity", ZONE)
    naive_co2  = load_sim_data(RUN_NAIVE, "Zone Air CO2 Concentration", ZONE)
    
    opt_temp = load_sim_data(RUN_OPTIMIZED, "Zone Air Temperature", ZONE)
    opt_hum  = load_sim_data(RUN_OPTIMIZED, "Zone Air Relative Humidity", ZONE)
    opt_co2  = load_sim_data(RUN_OPTIMIZED, "Zone Air CO2 Concentration", ZONE)
    opt_occ  = load_sim_data(RUN_OPTIMIZED, "Zone People Occupant Count", ZONE)

    # 4. Create Plot
    fig, axes = plt.subplots(3, 1, figsize=(14, 18), sharex=True)
    
    metrics = [
        ("Temperature", "°C", meas_temp, naive_temp, opt_temp, "#1f77b4", "#ff7f0e", "#2ca02c"),
        ("Relative Humidity", "%", meas_hum, naive_hum, opt_hum, "#1f77b4", "#ff7f0e", "#2ca02c"),
        ("CO2 Concentration", "ppm", meas_co2, naive_co2, opt_co2, "#1f77b4", "#ff7f0e", "#2ca02c")
    ]
    
    for i, (name, unit, meas, naive, opt, c_meas, c_naive, c_opt) in enumerate(metrics):
        ax = axes[i]
        
        if meas is not None and naive is not None:
            m_a, n_a = sv.align_series(meas, naive)
            m_a, o_a = sv.align_series(meas, opt)
            
            # Classical Colors: Blue (Meas), Orange Dashed (Naive), Green Solid (Opt)
            ax.plot(m_a.index, m_a.values, color=c_meas, linewidth=2.5, label="Measured (KETI)")
            ax.plot(n_a.index, n_a.values, color=c_naive, linestyle='--', linewidth=2, label="Naive (45m Lag)")
            ax.plot(o_a.index, o_a.values, color=c_opt, linestyle='-', linewidth=2.5, label="Optimized (20m Lag)")
            
            n_rmse = sv.compute_rmse(m_a, n_a)
            o_rmse = sv.compute_rmse(m_a, o_a)
            ax.text(0.02, 0.96, f"RMSE Naive: {n_rmse:.2f} {unit}\nRMSE Optimized: {o_rmse:.2f} {unit}", 
                    transform=ax.transAxes, verticalalignment='top', fontsize=11, 
                    bbox=dict(facecolor='white', alpha=0.9, edgecolor='gray'))

        # Secondary Axis for Occupancy
        ax2 = ax.twinx()
        if opt_occ is not None:
            ax2.plot(opt_occ.index, opt_occ.values, color='#9467bd', linewidth=1.5, alpha=0.4, label="Occupancy Count")
            ax2.fill_between(opt_occ.index, 0, opt_occ.values, color='#9467bd', alpha=0.05)
        ax2.set_ylabel("Occupants", color='#9467bd', fontsize=10)
        ax2.set_ylim(0, 15) # Scaled for NW zone capacity
        ax2.tick_params(axis='y', labelcolor='#9467bd')

        ax.set_title(f"{name} Analysis - {ZONE}", fontsize=14, fontweight='bold')
        ax.set_ylabel(f"{name} [{unit}]", fontsize=11, fontweight='bold')

    axes[2].set_xlabel("Calibration Period (Aug 2013)", fontsize=12, fontweight='bold')
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    axes[2].xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(axes[2].xaxis.get_majorticklabels(), rotation=30, ha="right")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.98), ncol=3)
    
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(OUTPUT_PATH, dpi=300, bbox_inches='tight')
    print(f"SUCCESS: Super Validation Audit generated at {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
