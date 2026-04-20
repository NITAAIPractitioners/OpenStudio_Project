"""
visualize_schedules.py — idealLoad_model
=========================================
Standalone script to visualize EnergyPlus schedules from SQL.
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
CONFIG_PATH = EXPERIMENT_ROOT / "experiment_config.json"
OUTPUT_DIR = EXPERIMENT_ROOT / "outputs" / "schedules"

# --- Constants ---
SIM_YEAR = 2013
ZONES = ["TZ_NW", "TZ_C", "TZ_S", "TZ_W", "TZ_E", "TZ_NE"]

def load_config():
    if not CONFIG_PATH.exists(): return None
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def load_sql_variable(conn, variable_name: str, zone_name: str) -> pd.Series | None:
    query_idx = "SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE KeyValue=? AND Name=? LIMIT 1"
    idx_df = pd.read_sql_query(query_idx, conn, params=(zone_name.upper(), variable_name))
    if idx_df.empty: return None
    rdd_idx = int(idx_df.iloc[0, 0])
    query_data = "SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value FROM ReportData rd JOIN Time t ON rd.TimeIndex=t.TimeIndex WHERE rd.ReportDataDictionaryIndex=? ORDER BY t.TimeIndex"
    df = pd.read_sql_query(query_data, conn, params=(rdd_idx,))
    if df.empty: return None
    df["dt"] = pd.to_datetime({"year": SIM_YEAR, "month": df["Month"], "day": df["Day"], "hour": (df["Hour"]-1), "minute": df["Minute"].clip(upper=59)})
    return df.set_index("dt").sort_index()["Value"]

def main():
    config = load_config()
    if not config: return
    
    run_dir = config["latest_run_dir"]
    sql_path = EXPERIMENT_ROOT / "model" / "runs" / run_dir / "run" / "eplusout.sql"
    
    print(f"--- idealLoad_model: Schedule Visualization (SQL) ---")
    print(f"TARGET RUN: {run_dir}")
    if not sql_path.exists():
        print(f"[ERROR] SQL not found at {sql_path}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sql_path)

    # 1. Grid Plot
    fig, axes = plt.subplots(len(ZONES), 2, figsize=(20, 3.2 * len(ZONES)), sharex=True)
    fig.suptitle(f"IdealLoad Schedules | {run_dir}", fontsize=14, fontweight="bold")

    for row_i, zone in enumerate(ZONES):
        occ = load_sql_variable(conn, "Zone People Occupant Count", zone)
        ltg = load_sql_variable(conn, "Zone Lights Electricity Rate", zone)
        
        ax_o, ax_l = axes[row_i, 0], axes[row_i, 1]
        if occ is not None:
            ax_o.fill_between(occ.index, occ.values, color="#2196F3", alpha=0.7, label="Occ")
            ax_o.set_ylabel(f"{zone}\nPersons", fontsize=8)
        if ltg is not None:
            ax_l.fill_between(ltg.index, ltg.values / 1000.0, color="#FF9800", alpha=0.7, label="kW")
            ax_l.set_ylabel("kW", fontsize=8)
        
        for ax in (ax_o, ax_l):
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
            ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    grid_path = OUTPUT_DIR / "idealLoad_schedules_grid.png"
    fig.savefig(grid_path, dpi=300)
    plt.close(fig)

    # 2. Heatmap
    occ_series = {z: load_sql_variable(conn, "Zone People Occupant Count", z) for z in ZONES}
    occ_series = {k: v for k, v in occ_series.items() if v is not None}
    
    if occ_series:
        fig2, axes2 = plt.subplots(1, len(occ_series), figsize=(4 * len(occ_series), 8), sharey=True)
        if len(occ_series) == 1: axes2 = [axes2]
        for ax, (zone, series) in zip(axes2, occ_series.items()):
            pivot = series.resample("30min").mean().to_frame("occ")
            pivot["date"] = pivot.index.date; pivot["time"] = pivot.index.time
            mat = pivot.pivot_table(index="time", columns="date", values="occ")
            im = ax.imshow(mat.values, aspect="auto", cmap="YlOrRd")
            ax.set_title(zone, fontsize=9)
            fig2.colorbar(im, ax=ax, shrink=0.8)
        
        plt.tight_layout()
        heat_path = OUTPUT_DIR / "idealLoad_occupancy_heatmap.png"
        fig2.savefig(heat_path, dpi=300)
        plt.close(fig2)

    conn.close()
    print(f"Plots saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
