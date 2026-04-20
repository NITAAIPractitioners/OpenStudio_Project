"""
visualize_load_injection.py — idealLoad_model
=========================================
Standalone script to visualize load injection (fs -> W/m2).
Targets the specific IdealLoad experiment.
"""

import os
import sys
import json
import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# --- LOCAL PATH DISCOVERY ---
_HERE = Path(__file__).parent
EXPERIMENT_ROOT = _HERE.parent
PROJECT_ROOT = EXPERIMENT_ROOT.parent
CONFIG_PATH = EXPERIMENT_ROOT / "experiment_config.json"
OUTPUT_DIR = EXPERIMENT_ROOT / "outputs" / "loads"
FUSED_DIR = PROJECT_ROOT / "fused_results"

# --- Constants ---
LPD = 11.0; EPD = 20.0; PD = 0.05; Q_SENS = 75.0; Q_ACH = 0.5
ZONE = "TZ_NW"; OFFICE = "413"; SIM_YEAR = 2013

def load_config():
    if not CONFIG_PATH.exists(): return None
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def load_ep_var(conn, variable_name, zone_name):
    idx = pd.read_sql_query("SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE KeyValue=? AND Name=? LIMIT 1", conn, params=(zone_name.upper(), variable_name))
    if idx.empty: return None
    rdd = int(idx.iloc[0, 0])
    df2 = pd.read_sql_query("SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value FROM ReportData rd JOIN Time t ON rd.TimeIndex=t.TimeIndex WHERE rd.ReportDataDictionaryIndex=? ORDER BY t.TimeIndex", conn, params=(rdd,))
    if df2.empty: return None
    df2["dt"] = pd.to_datetime({"year": SIM_YEAR, "month": df2["Month"], "day": df2["Day"], "hour": (df2["Hour"]-1).clip(lower=0), "minute": df2["Minute"].clip(upper=59)})
    return df2.set_index("dt").sort_index()["Value"]

def main():
    config = load_config()
    if not config: return
    
    run_dir = config["latest_run_dir"]
    sql_path = EXPERIMENT_ROOT / "model" / "runs" / run_dir / "run" / "eplusout.sql"
    
    print(f"--- idealLoad_model: Load Injection Visualization ---")
    print(f"TARGET RUN: {run_dir}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load fused data
    fpath = FUSED_DIR / f"{OFFICE}_fused_data.csv"
    if not fpath.exists():
        print(f"[ERROR] Fused data missing: {fpath}")
        return
    df = pd.read_csv(fpath, parse_dates=["dt"]).set_index("dt").sort_index()
    fs = df["fused_score"].fillna(0).clip(0, 1)
    occ = df["occupied"].fillna(0)

    # Compute loads
    lt_load = fs * LPD; eq_load = fs * EPD; ppl_load = occ * PD * Q_SENS
    total = lt_load + eq_load + ppl_load

    # Load EP actuals
    ep_ltg = ep_occ = ep_cool = ep_heat = None
    if sql_path.exists():
        conn = sqlite3.connect(sql_path)
        ep_ltg = load_ep_var(conn, "Zone Lights Electricity Rate", ZONE)
        ep_occ = load_ep_var(conn, "Zone People Occupant Count", ZONE)
        ep_cool = load_ep_var(conn, "Zone Ideal Loads Supply Air Total Cooling Energy", ZONE)
        ep_heat = load_ep_var(conn, "Zone Ideal Loads Supply Air Total Heating Energy", ZONE)
        conn.close()

    # Plot
    fig, axes = plt.subplots(7, 1, figsize=(20, 18), sharex=True)
    x = fs.index
    
    # 0 - Fused Score
    axes[0].fill_between(x, fs.values, color="#9B59B6", alpha=0.5, label="Fused Score")
    axes[0].plot(x, occ.values, color="red", lw=0.5, ls="--", label="Occupied")
    
    # 1 - Lights
    axes[1].fill_between(x, lt_load.values, color="#F39C12", alpha=0.5, label=f"Comp ({LPD}W/m2)")
    if ep_ltg is not None:
        ep_ltg_max = ep_ltg.max()
        if ep_ltg_max > 0:  # BUG14-FIX: guard against all-zero lighting series (would produce NaN/ZeroDivisionError)
            norm = ep_ltg.groupby(level=0).mean().reindex(x, method="nearest") / ep_ltg_max * LPD
            axes[1].plot(x, norm.values, color="orange", lw=1, ls="--", label="EP Norm")
        else:
            print("[WARN] ep_ltg is all zeros for this window — skipping EP lighting overlay on axes[1]")

    # 2 - Equipment
    axes[2].fill_between(x, eq_load.values, color="#3498DB", alpha=0.5, label=f"Comp ({EPD}W/m2)")

    # 3 - People
    axes[3].fill_between(x, ppl_load.values, color="#27AE60", alpha=0.5, label=f"Comp ({PD*Q_SENS:.1f} W/m2)")
    if ep_occ is not None:
        norm = ep_occ.groupby(level=0).mean().reindex(x, method="nearest") / ep_occ.max() * ppl_load.max() if ppl_load.max() > 0 else ep_occ
        axes[3].plot(x, norm.values, color="green", lw=1, ls="--", label="EP Norm")

    # 4 - Infiltration
    axes[4].axhline(Q_ACH, color="grey", lw=2, label=f"Const {Q_ACH} ACH")
    axes[4].set_ylim(0, 1)

    # 5 - Total
    axes[5].fill_between(x, total.values, color="#E74C3C", alpha=0.5, label="Total Internal")

    # 6 - HVAC Response
    if ep_cool is not None:
        cl = ep_cool.groupby(level=0).mean().reindex(x, method="nearest") / 1e6
        axes[6].fill_between(x, -cl.values, color="#2980B9", alpha=0.5, label="Cooling (MJ)")
    if ep_heat is not None:
        ht = ep_heat.groupby(level=0).mean().reindex(x, method="nearest") / 1e6
        axes[6].fill_between(x, ht.values, color="#E67E22", alpha=0.5, label="Heating (MJ)")

    for ax in axes: ax.legend(loc="upper right", fontsize=8); ax.grid(alpha=0.3)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.tight_layout()
    
    plot_path = OUTPUT_DIR / f"idealLoad_load_injection_{OFFICE}.png"
    fig.savefig(plot_path, dpi=300)
    print(f"Plot saved to {plot_path}")

if __name__ == "__main__":
    main()
