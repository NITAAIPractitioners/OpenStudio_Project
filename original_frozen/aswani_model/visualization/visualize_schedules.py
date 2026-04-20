"""
visualize_schedules.py
======================
Reads Zone People Occupant Count and Zone Lights Electricity Rate
directly from the EnergyPlus SQL output (run/eplusout.sql) and
plots the full August 2013 schedule for all thermal zones.

Usage:
    python visualize_schedules.py
    python visualize_schedules.py --sql run_no_idealload/run/eplusout.sql --out outputs_schedules
"""

import os
import sqlite3
import argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ── Configuration ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--sql", default=os.path.join(_HERE, "run", "eplusout.sql"),
                    help="Path to EnergyPlus eplusout.sql")
parser.add_argument("--out", default=os.path.join(_HERE, "outputs_schedules"),
                    help="Output directory for plots")
args = parser.parse_args()

SQL_PATH = args.sql
OUT_DIR  = args.out
SIM_YEAR = 2013

# Zones to plot — must match EnergyPlus zone names exactly
ZONES = ["TZ_NW", "TZ_C", "TZ_S", "TZ_W", "TZ_E", "TZ_NE"]

os.makedirs(OUT_DIR, exist_ok=True)

# ── Helper: load one variable for one zone ─────────────────────────────────────
def load_sql_variable(conn, variable_name: str, zone_name: str) -> pd.Series | None:
    query_idx = """
        SELECT ReportDataDictionaryIndex
        FROM ReportDataDictionary
        WHERE KeyValue = ?
          AND Name     = ?
        LIMIT 1
    """
    idx_df = pd.read_sql_query(query_idx, conn, params=(zone_name.upper(), variable_name))
    if idx_df.empty:
        print(f"  [WARN] '{variable_name}' not found for zone '{zone_name}'")
        return None

    rdd_idx = int(idx_df.iloc[0, 0])

    query_data = """
        SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value
        FROM ReportData rd
        JOIN Time t ON rd.TimeIndex = t.TimeIndex
        WHERE rd.ReportDataDictionaryIndex = ?
        ORDER BY t.TimeIndex
    """
    df = pd.read_sql_query(query_data, conn, params=(rdd_idx,))
    if df.empty:
        return None

    # Build datetime index (EnergyPlus Hour is 1-based; Minute may be 0 or 60-step)
    df["dt"] = pd.to_datetime({
        "year":   SIM_YEAR,
        "month":  df["Month"],
        "day":    df["Day"],
        "hour":   (df["Hour"] - 1),          # convert to 0-based
        "minute": df["Minute"].clip(upper=59)
    })
    df = df.set_index("dt").sort_index()
    return df["Value"]


# ── Main ───────────────────────────────────────────────────────────────────────
if not os.path.exists(SQL_PATH):
    raise FileNotFoundError(f"SQL file not found: {SQL_PATH}")

conn = sqlite3.connect(SQL_PATH)

# ── Plot 1: Per-zone grid (Occupants + Lights) ────────────────────────────────
fig, axes = plt.subplots(
    nrows=len(ZONES), ncols=2,
    figsize=(20, 3.2 * len(ZONES)),
    sharex=True
)
fig.suptitle("EnergyPlus Schedules — SDH Level 4 — August 2013",
             fontsize=15, fontweight="bold", y=1.002)

for row_i, zone in enumerate(ZONES):
    occ  = load_sql_variable(conn, "Zone People Occupant Count",   zone)
    ltg  = load_sql_variable(conn, "Zone Lights Electricity Rate", zone)

    ax_occ = axes[row_i, 0]
    ax_ltg = axes[row_i, 1]

    if occ is not None:
        ax_occ.fill_between(occ.index, occ.values, alpha=0.7,
                            color="#2196F3", linewidth=0.4, label="Occupants")
        ax_occ.set_ylabel(f"{zone}\nPersons", fontsize=8)
    else:
        ax_occ.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax_occ.transAxes, color="grey")

    if ltg is not None:
        ax_ltg.fill_between(ltg.index, ltg.values / 1000.0, alpha=0.7,
                            color="#FF9800", linewidth=0.4, label="Lights")
        ax_ltg.set_ylabel("kW", fontsize=8)
    else:
        ax_ltg.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax_ltg.transAxes, color="grey")

    for ax in (ax_occ, ax_ltg):
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_minor_locator(mdates.DayLocator(interval=1))
        ax.tick_params(axis="x", labelsize=7, rotation=30)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(True, which="major", linestyle="--", alpha=0.4)
        ax.spines[["top", "right"]].set_visible(False)

    # Column headers (top row only)
    if row_i == 0:
        ax_occ.set_title("Occupant Count  (persons)", fontsize=10, pad=6)
        ax_ltg.set_title("Lighting Power  (kW)", fontsize=10, pad=6)
        
    if row_i == len(ZONES) - 1:
        # AXIS DATA EXPLANATION:
        # This explicit X-axis label applies universally to the bottom row, propagating
        # up through the sharex=True configuration of the subplots.
        ax_occ.set_xlabel("Simulation Dates (August 2013)", fontsize=9, fontweight="bold")
        ax_ltg.set_xlabel("Simulation Dates (August 2013)", fontsize=9, fontweight="bold")

plt.tight_layout()
out_grid = os.path.join(OUT_DIR, "schedules_all_zones_August.png")
fig.savefig(out_grid, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"[SAVED] {out_grid}")


# ── Plot 2: Combined occupancy heatmap (all zones, full August) ───────────────
occ_series = {}
for zone in ZONES:
    s = load_sql_variable(conn, "Zone People Occupant Count", zone)
    if s is not None:
        occ_series[zone] = s

if occ_series:
    occ_df = pd.DataFrame(occ_series).resample("30min").mean()

    # Pivot to day x time-of-day matrix for each zone
    fig2, axes2 = plt.subplots(1, len(occ_series), figsize=(4 * len(occ_series), 8), sharey=True)
    fig2.suptitle("Occupant Heatmap — SDH Level 4 — Full August 2013",
                  fontsize=13, fontweight="bold")

    if len(occ_series) == 1:
        axes2 = [axes2]

    for ax, (zone, series) in zip(axes2, occ_series.items()):
        # ── Matrix Generation for Heatmap ───────────────────────────────────────
        # Equation/Logic: To create a heatmap, continuous 1D temporal data must be reshaped.
        # We extract `.date` for the columns and `.time` for the index (rows). 
        # By calling .pivot_table(), pandas maps (Date_i, Time_j) -> (Occupants_i,j).
        pivot = series.resample("30min").mean().to_frame("occ")
        pivot["date"] = pivot.index.date
        pivot["time"] = pivot.index.time
        mat = pivot.pivot_table(index="time", columns="date", values="occ")

        im = ax.imshow(mat.values, aspect="auto", cmap="YlOrRd",
                       origin="upper", interpolation="nearest")

        # Y-axis: time labels every 4 hours
        # AXIS DATA EXPLANATION: Y-axis represents the Time of Day (00:00 to 23:30)
        n_bins = mat.shape[0]
        step   = max(1, n_bins // 6)
        ytick_idx = list(range(0, n_bins, step))
        ax.set_yticks(ytick_idx)
        ax.set_yticklabels(
            [str(mat.index[i])[:5] for i in ytick_idx], fontsize=7
        )

        # X-axis: dates
        # AXIS DATA EXPLANATION: X-axis represents the individual dates spanning August 2013 
        n_days = mat.shape[1]
        ax.set_xticks(range(n_days))
        ax.set_xticklabels(
            [str(d)[5:] for d in mat.columns], rotation=45, ha="right", fontsize=7
        )
        ax.set_xlabel("Day in August 2013", fontsize=8)
        
        # Explicitly label Y axis on the leftmost plot
        if ax == axes2[0]:
            ax.set_ylabel("Time of Day (HH:MM)", fontsize=8)
            
        ax.set_title(zone, fontsize=9, fontweight="bold")
        fig2.colorbar(im, ax=ax, shrink=0.8, label="Persons")

    plt.tight_layout()
    out_heat = os.path.join(OUT_DIR, "schedules_occupancy_heatmap.png")
    fig2.savefig(out_heat, dpi=300, bbox_inches="tight")
    plt.close(fig2)
    print(f"[SAVED] {out_heat}")

conn.close()
print("\n[DONE] Schedule visualization complete.")
print(f"  -> Plots saved to: {OUT_DIR}/")
