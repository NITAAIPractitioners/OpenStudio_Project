"""
visualize_zone_load_summary.py
==============================
Aggregates the per-office fused-score-based computed loads for all 6
offices in TZ_NW and overlays the EnergyPlus zone-level actual outputs
to show how the simulation matches the expected internal heat gains.

Usage:
    python visualize_zone_load_summary.py
    python visualize_zone_load_summary.py --sql run/eplusout.sql
"""

import os, sys, sqlite3, argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ── Config ────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--sql",   default=os.path.join(_HERE, "run", "eplusout.sql"))
parser.add_argument("--fused", default=os.path.join(_HERE, "fused_results"))
parser.add_argument("--out",   default=os.path.join(_HERE, "outputs_schedules"))
args = parser.parse_args()

SQL_PATH  = args.sql
FUSED_DIR = args.fused
OUT_DIR   = args.out
SIM_YEAR  = 2013
ZONE      = "TZ_NW"
OFFICES   = ["413", "415", "417", "419", "421", "423"]
OFFICE_AREA = 3.5 * 4.0     # m2 per office (from space_map)
ZONE_AREA   = OFFICE_AREA * len(OFFICES)   # total TZ_NW area

# Physical constants (test.py)
LPD    = 11.0   # W/m2
EPD    = 20.0   # W/m2
PD     = 0.05   # p/m2
Q_SENS = 75.0   # W/p

os.makedirs(OUT_DIR, exist_ok=True)

# ── Load all fused CSVs and compute per-office loads ─────────────────────────
print("Loading fused data for all offices...")
common_index = None
office_data  = {}

for office in OFFICES:
    fpath = os.path.join(FUSED_DIR, f"{office}_fused_data.csv")
    if not os.path.exists(fpath):
        print(f"  [SKIP] {fpath}")
        continue
    df = pd.read_csv(fpath, parse_dates=["dt"]).set_index("dt").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    fs  = df["fused_score"].fillna(0).clip(0, 1)
    occ = df["occupied"].fillna(0)

    office_data[office] = {
        "lights": (fs  * LPD).rename(f"ltg_{office}"),
        "equip":  (fs  * EPD).rename(f"eq_{office}"),
        "people": (occ * PD * Q_SENS).rename(f"ppl_{office}"),
    }
    if common_index is None:
        common_index = fs.index
    print(f"  Office {office}: {len(fs)} timesteps")

# Align everything to common 10-min grid
grid = pd.date_range(common_index.min(), common_index.max(), freq="10min")

def align(series):
    return series.resample("10min").mean().reindex(grid).interpolate(limit=3).fillna(0)

ltg_all   = pd.DataFrame({o: align(d["lights"]) for o, d in office_data.items()})
eq_all    = pd.DataFrame({o: align(d["equip"])  for o, d in office_data.items()})
ppl_all   = pd.DataFrame({o: align(d["people"]) for o, d in office_data.items()})

# ── Aggregate to Zone-Level (Mean) ──────────────────────────────────────────
# Equation: Zone Average W/m2 = Sum of individual office loads / Number of offices
# Assuming all offices present an equal area footprint (3.5m x 4.0m = 14.0 m2). 
# Summing their W/m2 and dividing by N is mathematically equivalent to computing 
# the total watts over the total zone area.
zone_lights = ltg_all.mean(axis=1)
zone_equip  = eq_all.mean(axis=1)
zone_people = ppl_all.mean(axis=1)
zone_total  = zone_lights + zone_equip + zone_people

print(f"\nZone TZ_NW computed loads (mean over 6 offices):")
print(f"  Lights:  {zone_lights.mean():.2f} W/m2")
print(f"  Equip:   {zone_equip.mean():.2f}  W/m2")
print(f"  People:  {zone_people.mean():.2f} W/m2")
print(f"  Total:   {zone_total.mean():.2f}  W/m2")

# ── Load EnergyPlus zone-level data ─────────────────────────────────────────
def load_ep(conn, variable, zone):
    idx = pd.read_sql_query(
        "SELECT ReportDataDictionaryIndex FROM ReportDataDictionary "
        "WHERE KeyValue=? AND Name=? LIMIT 1",
        conn, params=(zone.upper(), variable)
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
    s = df2.set_index("dt").sort_index()["Value"]
    return s.groupby(level=0).mean()

ep_ltg = ep_occ = ep_cool = ep_heat = None
if os.path.exists(SQL_PATH):
    conn = sqlite3.connect(SQL_PATH)
    ep_ltg  = load_ep(conn, "Zone Lights Electricity Rate",                    ZONE)
    ep_occ  = load_ep(conn, "Zone People Occupant Count",                      ZONE)
    ep_cool = load_ep(conn, "Zone Ideal Loads Supply Air Total Cooling Energy", ZONE)
    ep_heat = load_ep(conn, "Zone Ideal Loads Supply Air Total Heating Energy", ZONE)
    conn.close()
    print(f"\n[OK] EnergyPlus data loaded for {ZONE}")
else:
    print(f"[WARN] SQL not found — EP overlay disabled")

def ep_align(series):
    if series is None:
        return None
    return series.resample("10min").mean().reindex(grid, method="nearest",
           tolerance=pd.Timedelta("15min")).ffill().fillna(0)

ep_ltg_a  = ep_align(ep_ltg)
ep_occ_a  = ep_align(ep_occ)
ep_cool_a = ep_align(ep_cool)
ep_heat_a = ep_align(ep_heat)

# ── PLOT ──────────────────────────────────────────────────────────────────────
COLORS = {
    413: "#E74C3C", 415: "#3498DB", 417: "#2ECC71",
    419: "#F39C12", 421: "#9B59B6", 423: "#1ABC9C"
}

fig = plt.figure(figsize=(24, 28))
fig.suptitle(
    f"Zone TZ_NW — Sensor-Fused Load Injection vs EnergyPlus Output\n"
    f"6 offices (413–423) × Aug 23–31, 2013  |  test.py (Ideal Loads ON)",
    fontsize=14, fontweight="bold", y=1.002
)

gs = fig.add_gridspec(8, 2, hspace=0.45, wspace=0.25)

# Helper
def fmt_ax(ax, ylabel, ylim=None, title=None):
    # AXIS DATA EXPLANATION:
    # All plots generated by this formatter share the same global datetime X-Axis.
    # The X-Axis uniformly ranges over August 23-31, 2013 on 10-minute intervals.
    ax.set_ylabel(ylabel, fontsize=8)
    if ylim:   ax.set_ylim(ylim)
    if title:  ax.set_title(title, fontsize=9, loc="left", pad=3)
    ax.tick_params(axis="both", labelsize=7)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.tick_params(axis="x", rotation=25, labelsize=7)
    ax.set_xlabel("Simulation Dates (August 2013)", fontsize=9, fontweight="bold")

# ── LEFT column: stacked individual office contributions ──────────────────────

# Row 0L: Lighting per office (stacked area)
ax0l = fig.add_subplot(gs[0, 0])
bottom = np.zeros(len(grid))
for o in OFFICES:
    vals = ltg_all[o].values
    ax0l.fill_between(grid, bottom, bottom + vals,
                      alpha=0.75, color=COLORS[int(o)], label=f"Office {o}")
    bottom += vals
ax0l.legend(fontsize=6.5, ncol=3, loc="upper right")
fmt_ax(ax0l, "Lights [W/m²]", title="Per-office Lighting  (stacked)")

# Row 1L: Equipment per office (stacked area)
ax1l = fig.add_subplot(gs[1, 0])
bottom = np.zeros(len(grid))
for o in OFFICES:
    vals = eq_all[o].values
    ax1l.fill_between(grid, bottom, bottom + vals,
                      alpha=0.75, color=COLORS[int(o)], label=f"Office {o}")
    bottom += vals
fmt_ax(ax1l, "Equip [W/m²]", title="Per-office Equipment  (stacked)")

# Row 2L: People per office (stacked)
ax2l = fig.add_subplot(gs[2, 0])
bottom = np.zeros(len(grid))
for o in OFFICES:
    vals = ppl_all[o].values
    ax2l.fill_between(grid, bottom, bottom + vals, step="post",
                      alpha=0.75, color=COLORS[int(o)], label=f"Office {o}")
    bottom += vals
fmt_ax(ax2l, "People [W/m²]", title="Per-office Occupant Heat  (stacked)")

# Row 3L: Total internal gain per office (line)
ax3l = fig.add_subplot(gs[3, 0])
for o in OFFICES:
    total_o = ltg_all[o] + eq_all[o] + ppl_all[o]
    ax3l.plot(grid, total_o.values, color=COLORS[int(o)],
              linewidth=1.0, label=f"Office {o}")
ax3l.legend(fontsize=6.5, ncol=3, loc="upper right")
fmt_ax(ax3l, "Total Gain\n[W/m²]", title="Per-office Total Internal Gain")

# ── RIGHT column: Zone aggregated vs EnergyPlus ───────────────────────────────

# Row 0R: Zone lighting computed vs EP
ax0r = fig.add_subplot(gs[0, 1])
ax0r.fill_between(grid, zone_lights.values, alpha=0.5, color="#F39C12",
                  label=f"Computed zone mean: fused × {LPD}")
if ep_ltg_a is not None:
    ep_ltg_norm = ep_ltg_a / ep_ltg_a.max() * LPD
    ax0r.plot(grid, ep_ltg_norm.values, color="#D35400", linewidth=1.2,
              linestyle="--", label="EnergyPlus (normalised to LPD)")
ax0r.legend(fontsize=7, loc="upper right")
fmt_ax(ax0r, "Lights [W/m²]", ylim=(0, LPD*1.15),
       title="Zone TZ_NW  Lighting  (computed vs EP)")

# Row 1R: Zone equipment computed
ax1r = fig.add_subplot(gs[1, 1])
ax1r.fill_between(grid, zone_equip.values, alpha=0.5, color="#3498DB",
                  label=f"Computed zone mean: fused × {EPD}")
ax1r.legend(fontsize=7, loc="upper right")
fmt_ax(ax1r, "Equip [W/m²]", ylim=(0, EPD*1.15),
       title="Zone TZ_NW  Equipment")

# Row 2R: Zone occupants computed vs EP
ax2r = fig.add_subplot(gs[2, 1])
ax2r.fill_between(grid, zone_people.values, step="post", alpha=0.5,
                  color="#27AE60", label=f"Computed zone: occ × {PD} × {Q_SENS}W")
if ep_occ_a is not None:
    ep_occ_scale = ep_occ_a / ep_occ_a.max() * zone_people.max() if zone_people.max() > 0 else ep_occ_a
    ax2r.plot(grid, ep_occ_scale.values, color="#1E8449", linewidth=1.2,
              linestyle="--", label="EnergyPlus occupants (normalised)")
ax2r.legend(fontsize=7, loc="upper right")
fmt_ax(ax2r, "People Heat\n[W/m²]", title="Zone TZ_NW  People Heat Gain")

# Row 3R: Total zone computed vs EP lighting proxy
ax3r = fig.add_subplot(gs[3, 1])
ax3r.fill_between(grid, zone_total.values, alpha=0.5, color="#E74C3C",
                  label="Total computed (Lights + Equip + People)")
ax3r.axhline(zone_total.mean(), color="#C0392B", linewidth=0.8, linestyle=":",
             label=f"Mean = {zone_total.mean():.1f} W/m²")
ax3r.legend(fontsize=7, loc="upper right")
fmt_ax(ax3r, "Total Internal\nGain [W/m²]", title="Zone TZ_NW  Total Heat Gain")

# Row 4: HVAC response (full width)
ax4 = fig.add_subplot(gs[4, :])
plotted = False
if ep_cool_a is not None:
    cool_kw = ep_cool_a / 1e3    # W -> kW
    ax4.fill_between(grid, -cool_kw.values, 0, alpha=0.6, color="#2980B9",
                     label="Cooling Energy (kW) [negative = removing heat]")
    plotted = True
if ep_heat_a is not None:
    heat_kw = ep_heat_a / 1e3
    ax4.fill_between(grid, 0, heat_kw.values, alpha=0.6, color="#E67E22",
                     label="Heating Energy (kW)")
    plotted = True
if plotted:
    ax4.axhline(0, color="black", linewidth=0.8)
    ax4.legend(fontsize=8, loc="upper right")
else:
    ax4.text(0.5, 0.5, "HVAC data not in SQL", ha="center", va="center",
             transform=ax4.transAxes, color="grey", fontsize=10)
fmt_ax(ax4, "HVAC Energy [kW]",
       title="EnergyPlus HVAC Response for Zone TZ_NW  (Ideal Air Loads: 20-24°C band)")

# Row 5: Energy balance — show total gain vs total HVAC
ax5 = fig.add_subplot(gs[5, :])
ax5.fill_between(grid, zone_total.values, alpha=0.45, color="#E74C3C",
                 label="Internal Heat Gain (W/m²) — from fused schedules")
if ep_cool_a is not None:
    # Normalise cooling to same scale as W/m2
    cool_norm = ep_cool_a / 1e3 / ZONE_AREA * 1000   # kW / m2 -> W/m2
    ax5.plot(grid, cool_norm.values, color="#2980B9", linewidth=1.2,
             label=f"Cooling Output (W/m², zone={ZONE_AREA:.0f}m²)")
ax5.legend(fontsize=8, loc="upper right")
ax5.axhline(zone_total.mean(), color="#C0392B", linewidth=0.6, linestyle=":",)
fmt_ax(ax5, "W/m²",
       title="Energy Balance: Internal Gains vs HVAC Cooling Removal")

# Row 6: Per-office fused_score heatmap
ax6 = fig.add_subplot(gs[6, :])
fused_matrix = pd.DataFrame({o: ltg_all[o] / LPD for o in OFFICES}).T
im = ax6.imshow(fused_matrix.values, aspect="auto", cmap="YlOrRd",
                origin="upper", vmin=0, vmax=1,
                extent=[0, len(grid), len(OFFICES) - 0.5, -0.5])
ax6.set_yticks(range(len(OFFICES)))
ax6.set_yticklabels([f"Office {o}" for o in OFFICES], fontsize=8)
n = len(grid)
xtick_idx = list(range(0, n, n // 9))
ax6.set_xticks(xtick_idx)
ax6.set_xticklabels([str(grid[i])[:10] for i in xtick_idx], rotation=25, fontsize=7)
plt.colorbar(im, ax=ax6, orientation="vertical", shrink=0.9, label="Fused Score")
ax6.set_title("Fused Score Heatmap: All 6 Offices × Time  (colour = occupancy intensity)",
              fontsize=9, loc="left")

# Row 7: Summary stats bar
ax7 = fig.add_subplot(gs[7, :])
means = {
    "Lights\n(W/m²)":     zone_lights.mean(),
    "Equipment\n(W/m²)":  zone_equip.mean(),
    "People Heat\n(W/m²)": zone_people.mean(),
    "Total\n(W/m²)":      zone_total.mean(),
}
bars = ax7.bar(means.keys(), means.values(),
               color=["#F39C12", "#3498DB", "#27AE60", "#E74C3C"],
               alpha=0.82, edgecolor="white")
for bar, val in zip(bars, means.values()):
    ax7.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
             f"{val:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
ax7.set_title("Zone TZ_NW — Mean Internal Load Summary (Aug 23–31, 2013)", fontsize=9, loc="left")
ax7.set_ylabel("Mean W/m²", fontsize=8)
ax7.tick_params(axis="both", labelsize=8)
ax7.spines[["top", "right"]].set_visible(False)
ax7.set_ylim(0, zone_total.mean() * 1.3)

plt.tight_layout()
out_path = os.path.join(OUT_DIR, "zone_tz_nw_load_summary.png")
fig.savefig(out_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"\n[SAVED] {out_path}")
print("[DONE]")
