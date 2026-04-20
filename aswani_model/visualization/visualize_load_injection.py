"""
visualize_load_injection.py
===========================
Shows how the fused_score translates into computed thermal loads
(Lights, Equipment, Occupant Heat Gain, Infiltration) and compares
the computed loads against what EnergyPlus actually simulated.

Usage:
    python visualize_load_injection.py
    python visualize_load_injection.py --office 413 --sql run/eplusout.sql
"""

import os, sys, sqlite3, argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates

# ── Config ────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--office", default="413", help="Office ID to visualize")
parser.add_argument("--sql",    default=os.path.join(_HERE, "run", "eplusout.sql"))
parser.add_argument("--fused",  default=os.path.join(_HERE, "fused_results"))
parser.add_argument("--out",    default=os.path.join(_HERE, "outputs_schedules"))
args = parser.parse_args()

OFFICE    = args.office
SQL_PATH  = args.sql
FUSED_DIR = args.fused
OUT_DIR   = args.out
SIM_YEAR  = 2013

# ── Physical constants (from test.py / model_parameters_table.tex) ────────────
LPD       = 11.0    # W/m2  Lighting Power Density
EPD       = 20.0    # W/m2  Equipment Power Density
PD        = 0.05    # p/m2  People Density
Q_SENS    = 75.0    # W/p   Sensible heat per person (0.577 * 130W)
Q_ACH     = 0.5     # ACH   Infiltration rate (constant in test.py)
ZONE      = "TZ_NW"

os.makedirs(OUT_DIR, exist_ok=True)

# ── Load fused data ───────────────────────────────────────────────────────────
fpath = os.path.join(FUSED_DIR, f"{OFFICE}_fused_data.csv")
if not os.path.exists(fpath):
    print(f"[ERROR] Fused data not found: {fpath}")
    sys.exit(1)

df = pd.read_csv(fpath, parse_dates=["dt"]).set_index("dt").sort_index()
fs  = df["fused_score"].fillna(0).clip(0, 1)
occ = df["occupied"].fillna(0)

# ── Compute derived loads ─────────────────────────────────────────────────────
# Equation: Lights (W/m²) = Probability of occupancy (fs) [0-1] × Peak Lighting Power Density (LPD)
lights_load  = fs   * LPD                      # W/m2  — varies with fused_score

# Equation: Equipment (W/m²) = Probability of occupancy (fs) [0-1] × Peak Equipment Power Density (EPD)
equip_load   = fs   * EPD                      # W/m2  — varies with fused_score

# Equation: People (W/m²) = Binary Occupancy [0 or 1] × People Density (PD) × Sensible Heat Ratio (Q_SENS)
people_load  = occ  * PD * Q_SENS              # W/m2  — binary (occupied flag)

# Equation: Infiltration (ACH) = Constant base infiltration rate specified in test.py
infil_ach    = Q_ACH  * np.ones(len(fs))       # ACH   — constant in test.py

# Equation: Total Internal Heat Gain (W/m²) = Lights + Equipment + People Sensible Heat
total_gain   = lights_load + equip_load + people_load  # W/m2 total internal

print(f"[OK] Computed loads for office {OFFICE}")
print(f"     Lights:  {lights_load.mean():.2f} W/m2 mean")
print(f"     Equip:   {equip_load.mean():.2f} W/m2 mean")
print(f"     People:  {people_load.mean():.2f} W/m2 mean")
print(f"     Total:   {total_gain.mean():.2f} W/m2 mean")

# ── Load EnergyPlus actuals from SQL ─────────────────────────────────────────
def load_ep_var(conn, variable_name, zone_name):
    idx = pd.read_sql_query(
        "SELECT ReportDataDictionaryIndex FROM ReportDataDictionary "
        "WHERE KeyValue=? AND Name=? LIMIT 1",
        conn, params=(zone_name.upper(), variable_name)
    )
    if idx.empty:
        return None
    rdd = int(idx.iloc[0, 0])
    df2 = pd.read_sql_query(
        "SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value "
        "FROM ReportData rd JOIN Time t ON rd.TimeIndex=t.TimeIndex "
        "WHERE rd.ReportDataDictionaryIndex=? ORDER BY t.TimeIndex",
        conn, params=(rdd,)
    )
    if df2.empty:
        return None
    df2["dt"] = pd.to_datetime({
        "year": SIM_YEAR, "month": df2["Month"], "day": df2["Day"],
        "hour": (df2["Hour"] - 1).clip(lower=0),
        "minute": df2["Minute"].clip(upper=59)
    })
    return df2.set_index("dt").sort_index()["Value"]

ep_ltg = ep_occ = ep_cool = ep_heat = None
if os.path.exists(SQL_PATH):
    conn = sqlite3.connect(SQL_PATH)
    ep_ltg  = load_ep_var(conn, "Zone Lights Electricity Rate",                  ZONE)
    ep_occ  = load_ep_var(conn, "Zone People Occupant Count",                    ZONE)
    ep_cool = load_ep_var(conn, "Zone Ideal Loads Supply Air Total Cooling Energy", ZONE)
    ep_heat = load_ep_var(conn, "Zone Ideal Loads Supply Air Total Heating Energy", ZONE)
    conn.close()
    print(f"[OK] EnergyPlus data loaded for {ZONE}")
else:
    print(f"[WARN] SQL not found — EnergyPlus overlay disabled")

# ── Plot ──────────────────────────────────────────────────────────────────────
# Layout: 7 rows
#  0 - fused_score (input driver)
#  1 - Lighting computed vs EP
#  2 - Equipment computed
#  3 - People heat gain computed vs EP occupant count
#  4 - Infiltration (constant bar)
#  5 - Total internal heat gain
#  6 - HVAC response (heating + cooling) — from EP

rows = 7
fig, axes = plt.subplots(rows, 1, figsize=(22, 3.0 * rows), sharex=True)
fig.suptitle(
    f"Fused Score  ->  Thermal Load Injection  |  Office {OFFICE} / Zone {ZONE}\n"
    f"Aug 23-31, 2013  (test.py: Ideal Air Loads ON)",
    fontsize=13, fontweight="bold", y=1.002
)

xdata = fs.index

def style_ax(ax, ylabel, ylim=None):
    ax.set_ylabel(ylabel, fontsize=8)
    if ylim:
        ax.set_ylim(ylim)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.spines[["top", "right"]].set_visible(False)

# Row 0 — Fused Score (driver)
axes[0].fill_between(xdata, fs.values, alpha=0.6, color="#9B59B6")
axes[0].plot(xdata, occ.values, color="#E74C3C", linewidth=0.7,
             linestyle="--", label="Occupied (binary)")
axes[0].set_ylim(-0.05, 1.15)
axes[0].set_yticks([0, 0.5, 1])
axes[0].legend(fontsize=7, loc="upper right")
style_ax(axes[0], "Fused Score\n[0-1]")
axes[0].set_title("INPUT: Fused Occupancy Score (drives all loads below)", fontsize=9, loc="left")

# Row 1 — Lighting
axes[1].fill_between(xdata, lights_load.values, alpha=0.55, color="#F39C12",
                     label=f"Computed: fused × {LPD} W/m²")
if ep_ltg is not None:
    # Normalize EP lighting to same scale (it's per zone, not m2)
    ep_ltg_dedup = ep_ltg.groupby(level=0).mean()
    ep_ltg_r = ep_ltg_dedup.reindex(xdata, method="nearest", tolerance=pd.Timedelta("10min"))
    ep_ltg_r_norm = ep_ltg_r / ep_ltg_r.max() * LPD
    axes[1].plot(ep_ltg_r_norm.index, ep_ltg_r_norm.values,
                 color="#D35400", linewidth=1.0, linestyle="--",
                 label="EnergyPlus (normalised)")
axes[1].legend(fontsize=7, loc="upper right")
style_ax(axes[1], f"Lights\n[W/m²]", (0, LPD * 1.15))
axes[1].axhline(LPD, color="#F39C12", linewidth=0.5, linestyle=":")
axes[1].text(xdata[-1], LPD + 0.3, f"Max={LPD} W/m²", fontsize=6, ha="right", color="#F39C12")

# Row 2 — Equipment
axes[2].fill_between(xdata, equip_load.values, alpha=0.55, color="#3498DB",
                     label=f"Computed: fused × {EPD} W/m²")
axes[2].legend(fontsize=7, loc="upper right")
style_ax(axes[2], f"Equipment\n[W/m²]", (0, EPD * 1.15))
axes[2].axhline(EPD, color="#3498DB", linewidth=0.5, linestyle=":")
axes[2].text(xdata[-1], EPD + 0.5, f"Max={EPD} W/m²", fontsize=6, ha="right", color="#3498DB")

# Row 3 — People
axes[3].fill_between(xdata, people_load.values, step="post", alpha=0.55,
                     color="#27AE60", label=f"Computed: occupied × {PD}p/m² × {Q_SENS}W")
if ep_occ is not None:
    ep_occ_dedup = ep_occ.groupby(level=0).mean()
    ep_occ_r = ep_occ_dedup.reindex(xdata, method="nearest", tolerance=pd.Timedelta("10min"))
    ep_occ_norm = ep_occ_r / ep_occ_r.max() * people_load.max() if people_load.max() > 0 else ep_occ_r
    axes[3].plot(ep_occ_norm.index, ep_occ_norm.values,
                 color="#1E8449", linewidth=1.0, linestyle="--",
                 label="EnergyPlus (normalised)")
axes[3].legend(fontsize=7, loc="upper right")
style_ax(axes[3], f"People Heat\n[W/m²]")

# Row 4 — Infiltration
infil_series = pd.Series(infil_ach, index=xdata)
axes[4].fill_between(xdata, infil_series.values, alpha=0.35, color="#95A5A6",
                     label=f"Constant: {Q_ACH} ACH (test.py)")
axes[4].legend(fontsize=7, loc="upper right")
axes[4].set_ylim(0, 1.0)
axes[4].axhline(Q_ACH, color="#7F8C8D", linewidth=1.0, linestyle="-")
style_ax(axes[4], "Infiltration\n[ACH]")
axes[4].text(xdata[-1], Q_ACH + 0.03, "Constant 0.5 ACH", fontsize=6.5,
             ha="right", color="#7F8C8D")

# Row 5 — Total Internal Gain
axes[5].fill_between(xdata, total_gain.values, alpha=0.55, color="#E74C3C",
                     label="Total = Lights + Equip + People")
axes[5].legend(fontsize=7, loc="upper right")
style_ax(axes[5], f"Total Internal\nGain [W/m²]")
axes[5].axhline(LPD + EPD + PD * Q_SENS, color="#C0392B", linewidth=0.5, linestyle=":",)
axes[5].text(xdata[-1], LPD + EPD + PD * Q_SENS + 0.3,
             f"Peak={LPD + EPD + PD * Q_SENS:.1f} W/m²", fontsize=6, ha="right", color="#C0392B")

# Row 6 — HVAC Response
plotted = False
if ep_cool is not None:
    ep_cool_r = ep_cool.groupby(level=0).mean().reindex(xdata, method="nearest", tolerance=pd.Timedelta("10min")) / 1e6
    axes[6].fill_between(ep_cool_r.index, -ep_cool_r.values, alpha=0.55,
                         color="#2980B9", label="Cooling Energy (MJ) — negative")
    plotted = True
if ep_heat is not None:
    ep_heat_r = ep_heat.groupby(level=0).mean().reindex(xdata, method="nearest", tolerance=pd.Timedelta("10min")) / 1e6
    axes[6].fill_between(ep_heat_r.index, ep_heat_r.values, alpha=0.55,
                         color="#E67E22", label="Heating Energy (MJ)")
    plotted = True
if plotted:
    axes[6].legend(fontsize=7, loc="upper right")
    axes[6].axhline(0, color="black", linewidth=0.5)
else:
    axes[6].text(0.5, 0.5, "HVAC data not available", ha="center", va="center",
                 transform=axes[6].transAxes, color="grey")
style_ax(axes[6], "HVAC Response\n[MJ]")
axes[6].set_title("OUTPUT: EnergyPlus HVAC energy to maintain 20-24°C setpoints", fontsize=9, loc="left")

# ── X-axis ──────────────────────────────────────────────────────────────────
# AXIS DATA EXPLANATION:
# The shared X-Axis across all 7 subplots maps directly to the Pandas DatetimeIndex (xdata)
# representing the simulation window for August 2013. Ticks are placed daily.
axes[-1].xaxis.set_major_locator(mdates.DayLocator(interval=1))
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
axes[-1].xaxis.set_minor_locator(mdates.HourLocator(interval=6))
axes[-1].tick_params(axis="x", labelsize=8, rotation=30)
axes[-1].set_xlabel("Date and Time (August 2013)", fontsize=10, fontweight="bold")

# ── Annotation arrows showing the flow ───────────────────────────────────────
for i, label in enumerate(["Lights W/m²", "Equip W/m²", "People W/m²",
                             "Infiltration", "Total Gain", "HVAC Response"]):
    axes[i].annotate("", xy=(0.005, -0.18), xycoords="axes fraction",
                     xytext=(0.005,  1.05),
                     arrowprops=dict(arrowstyle="-|>", color="#BDC3C7", lw=0.8))

plt.tight_layout()
out_path = os.path.join(OUT_DIR, f"load_injection_office_{OFFICE}.png")
fig.savefig(out_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"\n[SAVED] {out_path}")
print("[DONE]")
