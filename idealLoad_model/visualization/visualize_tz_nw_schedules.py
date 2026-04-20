"""
visualize_tz_nw_schedules.py — idealLoad_model
=========================================
Standalone script to visualize sensor fusion vs EP outputs for TZ_NW.
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
OUTPUT_DIR = EXPERIMENT_ROOT / "outputs" / "tz_nw"
FUSED_DIR = PROJECT_ROOT / "fused_results"

# --- Constants ---
SIM_YEAR = 2013
TZ_ZONE = "TZ_NW"
OFFICES = ["413", "415", "417", "419", "421", "423"]

# Colors for fused params
FUSED_COLS = {
    "co2_score":   ("CO2 Score",   "#4A90D9"),
    "light_score": ("Light Score", "#F5A623"),
    "pir_score":   ("PIR Score",   "#7ED321"),
    "fused_score": ("Fused Score", "#9B59B6"),
    "occupied":    ("Occupied",    "#E74C3C"),
}

def load_config():
    if not CONFIG_PATH.exists(): return None
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def load_ep_var(conn, variable_name, zone_name):
    idx = pd.read_sql_query("SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE KeyValue=? AND Name=? LIMIT 1", conn, params=(zone_name.upper(), variable_name))
    if idx.empty: return None
    rdd = int(idx.iloc[0, 0])
    df = pd.read_sql_query("SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value FROM ReportData rd JOIN Time t ON rd.TimeIndex=t.TimeIndex WHERE rd.ReportDataDictionaryIndex=? ORDER BY t.TimeIndex", conn, params=(rdd,))
    if df.empty: return None
    df["dt"] = pd.to_datetime({"year": SIM_YEAR, "month": df["Month"], "day": df["Day"], "hour": (df["Hour"]-1).clip(lower=0), "minute": df["Minute"].clip(upper=59)})
    return df.set_index("dt").sort_index()["Value"]

def main():
    config = load_config()
    if not config: return
    
    run_dir = config["latest_run_dir"]
    sql_path = EXPERIMENT_ROOT / "model" / "runs" / run_dir / "run" / "eplusout.sql"
    
    print(f"--- idealLoad_model: TZ_NW Schedule Visualization ---")
    print(f"TARGET RUN: {run_dir}")
    if not sql_path.exists():
        print(f"[ERROR] SQL not found at {sql_path}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sql_path)
    
    ep_occ = load_ep_var(conn, "Zone People Occupant Count", TZ_ZONE)
    ep_ltg = load_ep_var(conn, "Zone Lights Electricity Rate", TZ_ZONE)
    conn.close()

    # Normalisation for overlay
    ep_occ_norm = (ep_occ / ep_occ.max()) if ep_occ is not None else None
    ep_ltg_norm = (ep_ltg / ep_ltg.max()) if ep_ltg is not None else None

    for office in OFFICES:
        fpath = FUSED_DIR / f"{office}_fused_data.csv"
        if not fpath.exists(): continue
        df = pd.read_csv(fpath, parse_dates=["dt"]).set_index("dt").sort_index()

        n_plots = len(FUSED_COLS) + 1
        fig, axes = plt.subplots(n_plots, 1, figsize=(22, 2.8 * n_plots), sharex=True)
        fig.suptitle(f"Office {office} vs {TZ_ZONE} | {run_dir}", fontsize=13, fontweight="bold")

        # Fused rows
        for ax, (col, (label, color)) in zip(axes[:-1], FUSED_COLS.items()):
            if col in df.columns:
                s = df[col].dropna()
                ax.fill_between(s.index, s.values, alpha=0.5, color=color)
                ax.set_ylabel(label, fontsize=8)
                ax.set_ylim(-0.05, 1.15)
                ax.set_yticks([0, 1])
                ax.grid(alpha=0.3)

        # EP row
        ax_ep = axes[-1]
        if ep_occ_norm is not None:
            ax_ep.plot(ep_occ_norm.index, ep_occ_norm.values, color="#1ABC9C", lw=1.5, label="EP Occ (norm)")
        if ep_ltg_norm is not None:
            ax_ep.plot(ep_ltg_norm.index, ep_ltg_norm.values, color="#E67E22", lw=1.5, ls="--", label="EP Lights (norm)")
        
        ax_ep.legend(loc="upper right", fontsize=8)
        ax_ep.set_ylabel("EP (norm)", fontsize=8)
        ax_ep.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        
        plt.tight_layout()
        out_path = OUTPUT_DIR / f"idealLoad_tz_nw_{office}_schedule.png"
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        print(f"Saved: {out_path.name}")

if __name__ == "__main__":
    main()
