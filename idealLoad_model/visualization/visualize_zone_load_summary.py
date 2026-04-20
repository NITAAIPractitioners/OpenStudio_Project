"""
visualize_zone_load_summary.py — idealLoad_model
=========================================
Standalone script to aggregate per-office loads to Zone TZ_NW level.
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
OUTPUT_DIR = EXPERIMENT_ROOT / "outputs" / "summary"
FUSED_DIR = PROJECT_ROOT / "fused_results"

# --- Constants ---
SIM_YEAR = 2013
ZONE = "TZ_NW"
OFFICES = ["413", "415", "417", "419", "421", "423"]
LPD = 11.0; EPD = 20.0; PD = 0.05; Q_SENS = 75.0
ZONE_AREA = len(OFFICES) * 14.0 # 3.5m x 4m each

def load_config():
    if not CONFIG_PATH.exists(): return None
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def load_ep(conn, variable, zone):
    idx = pd.read_sql_query("SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE KeyValue=? AND Name=? LIMIT 1", conn, params=(zone.upper(), variable))
    if idx.empty: return None
    rdd = int(idx.iloc[0, 0])
    df2 = pd.read_sql_query("SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value FROM ReportData rd JOIN Time t ON rd.TimeIndex=t.TimeIndex WHERE rd.ReportDataDictionaryIndex=? ORDER BY t.TimeIndex", conn, params=(rdd,))
    if df2.empty: return None
    df2["dt"] = pd.to_datetime({"year": SIM_YEAR, "month": df2["Month"], "day": df2["Day"], "hour": (df2["Hour"]-1).clip(lower=0), "minute": df2["Minute"].clip(upper=59)})
    return df2.set_index("dt").sort_index()["Value"].groupby(level=0).mean()

def main():
    config = load_config()
    if not config: return
    
    run_dir = config["latest_run_dir"]
    sql_path = EXPERIMENT_ROOT / "model" / "runs" / run_dir / "run" / "eplusout.sql"
    
    print(f"--- idealLoad_model: Zone TZ_NW Load Summary ---")
    print(f"TARGET RUN: {run_dir}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load fused data for all offices
    office_loads = []
    for office in OFFICES:
        fpath = FUSED_DIR / f"{office}_fused_data.csv"
        if fpath.exists():
            df = pd.read_csv(fpath, parse_dates=["dt"]).set_index("dt").sort_index()
            df = df[~df.index.duplicated(keep="first")]
            fs = df["fused_score"].fillna(0).clip(0, 1)
            occ = df["occupied"].fillna(0)
            office_loads.append({
                "ltg": (fs * LPD), "eq": (fs * EPD), "ppl": (occ * PD * Q_SENS)
            })
    
    if not office_loads:
        print("[ERROR] No fused data found.")
        return

    # 2. Aggregate
    idx = office_loads[0]["ltg"].index
    zone_ltg = pd.concat([d["ltg"] for d in office_loads], axis=1).mean(axis=1)
    zone_eq = pd.concat([d["eq"] for d in office_loads], axis=1).mean(axis=1)
    zone_ppl = pd.concat([d["ppl"] for d in office_loads], axis=1).mean(axis=1)
    zone_total = zone_ltg + zone_eq + zone_ppl

    # 3. Load EP comparisons
    ep_ltg = ep_occ = ep_cool = ep_heat = None
    if sql_path.exists():
        conn = sqlite3.connect(sql_path)
        ep_ltg = load_ep(conn, "Zone Lights Electricity Rate", ZONE)
        ep_occ = load_ep(conn, "Zone People Occupant Count", ZONE)
        ep_cool = load_ep(conn, "Zone Ideal Loads Supply Air Total Cooling Energy", ZONE)
        ep_heat = load_ep(conn, "Zone Ideal Loads Supply Air Total Heating Energy", ZONE)
        conn.close()

    # 4. Plot
    fig = plt.figure(figsize=(22, 24))
    fig.suptitle(f"Zone TZ_NW Aggregate Summary | {run_dir}", fontsize=14, fontweight="bold")
    gs = fig.add_gridspec(6, 1, hspace=0.4)
    grid = zone_ltg.index

    # Lights Comparison
    ax0 = fig.add_subplot(gs[0])
    ax0.fill_between(grid, zone_ltg.values, color="#F39C12", alpha=0.5, label="Comp zone mean")
    if ep_ltg is not None:
        norm = ep_ltg.reindex(grid, method="nearest") / ep_ltg.max() * LPD
        ax0.plot(grid, norm.values, color="orange", lw=1.2, ls="--", label="EP Norm")
    ax0.set_ylabel("Lights [W/m2]")
    ax0.legend(loc="upper right")

    # Total Internal
    ax1 = fig.add_subplot(gs[1])
    ax1.fill_between(grid, zone_total.values, color="#E74C3C", alpha=0.5, label="Total Internal (W/m2)")
    ax1.set_ylabel("Total [W/m2]")

    # HVAC Response
    ax2 = fig.add_subplot(gs[2])
    if ep_cool is not None:
        ax2.fill_between(grid, -ep_cool.reindex(grid, method="nearest").values/1e3, color="#2980B9", alpha=0.5, label="Cooling (kW)")
    if ep_heat is not None:
        ax2.fill_between(grid, ep_heat.reindex(grid, method="nearest").values/1e3, color="#E67E22", alpha=0.5, label="Heating (kW)")
    ax2.set_ylabel("HVAC [kW]")
    ax2.legend(loc="upper right")

    # Energy Balance (Total Internal vs Cooling Removal)
    ax3 = fig.add_subplot(gs[3])
    ax3.fill_between(grid, zone_total.values, color="#E74C3C", alpha=0.3, label="Internal Gain (W/m2)")
    if ep_cool is not None:
        cl_wm2 = ep_cool.reindex(grid, method="nearest") / 1e3 / ZONE_AREA * 1000
        ax3.plot(grid, cl_wm2.values, color="#2980B9", lw=1.2, label="Cooling Output (W/m2)")
    ax3.set_ylabel("W/m2")
    ax3.legend(loc="upper right")

    # Heatmap of office scores
    ax4 = fig.add_subplot(gs[4])
    f_mat = pd.DataFrame({f"O{i+413}": office_loads[i//2]["ltg"]/LPD if i%2==0 else office_loads[i//2]["ltg"]/LPD for i in range(len(OFFICES))}).T
    im = ax4.imshow(f_mat.values, aspect="auto", cmap="YlOrRd")
    ax4.set_title("Office Occupancy Heatmap")
    plt.colorbar(im, ax=ax4, label="Score")

    # Summary Stats Bar
    ax5 = fig.add_subplot(gs[5])
    means = {"Lights": zone_ltg.mean(), "Equip": zone_eq.mean(), "People": zone_ppl.mean(), "Total": zone_total.mean()}
    ax5.bar(means.keys(), means.values(), color=["#F39C12", "#3498DB", "#27AE60", "#E74C3C"], alpha=0.7)
    for i, (k, v) in enumerate(means.items()): ax5.text(i, v+0.1, f"{v:.2f}", ha="center", fontweight="bold")
    ax5.set_ylabel("Mean W/m2")

    for ax in [ax0, ax1, ax2, ax3]: ax.grid(alpha=0.3); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    
    plt.tight_layout()
    plot_path = OUTPUT_DIR / "idealLoad_zone_load_summary.png"
    fig.savefig(plot_path, dpi=300)
    print(f"Summary plot saved to {plot_path}")

if __name__ == "__main__":
    main()
