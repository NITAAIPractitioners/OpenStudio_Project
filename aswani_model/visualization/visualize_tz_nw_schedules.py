"""
visualize_tz_nw_schedules.py
============================
For each of the 6 offices in TZ_NW (413,415,417,419,421,423), plot the
fused sensor-derived schedule columns (co2_score, light_score, pir_score,
fused_score, occupied) alongside the EnergyPlus-simulated Zone output
(Occupant Count and Lights Rate) aggregated to the TZ_NW zone level.

Usage:
    python visualize_tz_nw_schedules.py
    python visualize_tz_nw_schedules.py --sql run/eplusout.sql --out outputs_schedules
"""

import os, sys, sqlite3, argparse
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ── Config ────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--sql", default=os.path.join(_HERE, "run", "eplusout.sql"))
parser.add_argument("--fused", default=os.path.join(_HERE, "fused_results"))
parser.add_argument("--out",  default=os.path.join(_HERE, "outputs_schedules", "tz_nw"))
args = parser.parse_args()

SQL_PATH  = args.sql
FUSED_DIR = args.fused
OUT_DIR   = args.out
SIM_YEAR  = 2013
TZ_ZONE   = "TZ_NW"
OFFICES   = ["413", "415", "417", "419", "421", "423"]

os.makedirs(OUT_DIR, exist_ok=True)

# Fused columns to plot and their display labels
FUSED_COLS = {
    "co2_score":   ("CO2 Score",   "#4A90D9"),
    "light_score": ("Light Score", "#F5A623"),
    "pir_score":   ("PIR Score",   "#7ED321"),
    "fused_score": ("Fused Score", "#9B59B6"),
    "occupied":    ("Occupied",    "#E74C3C"),
}

# ── Helper: load EnergyPlus zone variable ─────────────────────────────────────
def load_ep_var(conn, variable_name, zone_name):
    idx = pd.read_sql_query(
        "SELECT ReportDataDictionaryIndex FROM ReportDataDictionary "
        "WHERE KeyValue=? AND Name=? LIMIT 1",
        conn, params=(zone_name.upper(), variable_name)
    )
    if idx.empty:
        return None
    rdd = int(idx.iloc[0, 0])
    df = pd.read_sql_query(
        "SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value "
        "FROM ReportData rd JOIN Time t ON rd.TimeIndex=t.TimeIndex "
        "WHERE rd.ReportDataDictionaryIndex=? ORDER BY t.TimeIndex",
        conn, params=(rdd,)
    )
    if df.empty:
        return None
    df["dt"] = pd.to_datetime({
        "year": SIM_YEAR, "month": df["Month"], "day": df["Day"],
        "hour": (df["Hour"] - 1).clip(lower=0),
        "minute": df["Minute"].clip(upper=59)
    })
    return df.set_index("dt").sort_index()["Value"]


# ── Load EnergyPlus TZ_NW outputs ─────────────────────────────────────────────
if not os.path.exists(SQL_PATH):
    print(f"[ERROR] SQL not found: {SQL_PATH}")
    sys.exit(1)

conn = sqlite3.connect(SQL_PATH)
ep_occ  = load_ep_var(conn, "Zone People Occupant Count",  TZ_ZONE)
ep_ltg  = load_ep_var(conn, "Zone Lights Electricity Rate", TZ_ZONE)
conn.close()

# ── Normalization Equations ───────────────────────────────────────────────────
# EnergyPlus outputs raw scalar values (e.g. 5 persons, 550 Watts).
# The Fused data operates strictly on probabilities [0-1]. 
# To visually overlay the two on the same axis, we must Max-Normalize the EnergyPlus outputs.
# Equation: Normalized_Value = Actual_Value_t / Max_Value_in_Array

if ep_occ is not None:
    ep_occ_norm = (ep_occ / ep_occ.max()).rename("EP Occupants (norm)")
else:
    ep_occ_norm = None

if ep_ltg is not None:
    ep_ltg_norm = (ep_ltg / ep_ltg.max()).rename("EP Lights (norm)")
else:
    ep_ltg_norm = None

print(f"[OK] EnergyPlus data loaded for zone {TZ_ZONE}")


# ── Per-office plots ──────────────────────────────────────────────────────────
for office in OFFICES:
    fpath = os.path.join(FUSED_DIR, f"{office}_fused_data.csv")
    if not os.path.exists(fpath):
        print(f"[SKIP] {fpath} not found")
        continue

    df = pd.read_csv(fpath, parse_dates=["dt"]).set_index("dt").sort_index()

    n_cols = len(FUSED_COLS) + 1   # one sub-plot per fused param + 1 for EP overlay
    fig, axes = plt.subplots(
        nrows=n_cols, ncols=1,
        figsize=(22, 2.8 * n_cols),
        sharex=True
    )
    fig.suptitle(
        f"Office {office}  —  Fused Schedule vs EnergyPlus Zone {TZ_ZONE}  (Aug 23-31, 2013)",
        fontsize=13, fontweight="bold", y=1.002
    )

    # ── Fused parameter rows ──────────────────────────────────────────────────
    for ax, (col, (label, color)) in zip(axes[:-1], FUSED_COLS.items()):
        if col not in df.columns:
            ax.text(0.5, 0.5, f"'{col}' not in data", ha="center",
                    va="center", transform=ax.transAxes, color="grey")
        else:
            series = df[col].dropna()
            ax.fill_between(series.index, series.values,
                            alpha=0.55, color=color, linewidth=0)
            ax.plot(series.index, series.values,
                    color=color, linewidth=0.6)
        ax.set_ylabel(label, fontsize=8)
        ax.set_ylim(-0.05, 1.15)
        ax.set_yticks([0, 0.5, 1])
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.spines[["top", "right"]].set_visible(False)

    # ── EnergyPlus overlay row (occupants + lights, normalised) ──────────────
    ax_ep = axes[-1]
    added = False
    if ep_occ_norm is not None:
        ax_ep.plot(ep_occ_norm.index, ep_occ_norm.values,
                   color="#1ABC9C", linewidth=1.2, label="EP Occupants (norm)")
        added = True
    if ep_ltg_norm is not None:
        ax_ep.plot(ep_ltg_norm.index, ep_ltg_norm.values,
                   color="#E67E22", linewidth=1.2, linestyle="--",
                   label="EP Lights (norm)")
        added = True
    if added:
        ax_ep.legend(fontsize=7, loc="upper right")
    ax_ep.set_ylabel("EnergyPlus\n(normalised)", fontsize=8)
    ax_ep.set_ylim(-0.05, 1.15)
    ax_ep.set_yticks([0, 0.5, 1])
    ax_ep.tick_params(axis="y", labelsize=7)
    ax_ep.grid(True, linestyle="--", alpha=0.35)
    ax_ep.spines[["top", "right"]].set_visible(False)

    # ── X-axis formatting ─────────────────────────────────────────────────────
    # AXIS DATA EXPLANATION:
    # X-Axis explicitly mapped across all subplots, representing 'Simulation Date and Time'
    # operating on matching 10-minute intervals aligned between KETI sensors and EnergyPlus.
    ax_ep.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax_ep.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax_ep.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
    ax_ep.tick_params(axis="x", labelsize=8, rotation=30)
    ax_ep.set_xlabel("Simulation Dates (August 2013)", fontsize=9, fontweight="bold")

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, f"tz_nw_office_{office}_schedule.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[SAVED] {out_path}")

print("\n[DONE] All TZ_NW office schedule plots saved to:", OUT_DIR)
