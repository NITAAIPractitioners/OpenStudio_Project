"""
TZ_NW Temperature Diagnostic
Investigates the raw sensor temperature distribution for offices 413-423
vs the simulated zone temperature to understand the RMSE=7.18C cold bias.
"""
import os, sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared_validation import (
    load_keti_sensor, load_simulation_variable,
    align_series, get_output_dir,
)

offices = ["413", "415", "417", "419", "421", "423"]
zone    = "TZ_NW"
out_dir = get_output_dir("temperature")

print("=" * 60)
print("TZ_NW SENSOR TEMPERATURE DIAGNOSTIC")
print("=" * 60)

# ── Load all 6 office sensors ─────────────────────────────────────
all_series = {}
for o in offices:
    s = load_keti_sensor(o, "temperature")
    if s is not None and not s.empty:
        all_series[o] = s
        mn = s.mean(); mx = s.max(); mi = s.min(); sd = s.std()
        print(f"  Office {o}: mean={mn:.1f}C  min={mi:.1f}C  "
              f"max={mx:.1f}C  std={sd:.2f}C  n={len(s)}")

measured_df = pd.concat(all_series.values(), axis=1).dropna(how="all")
measured_avg = measured_df.mean(axis=1).dropna()
print(f"\n  Zone average (6 offices):"
      f"  mean={measured_avg.mean():.1f}C"
      f"  min={measured_avg.min():.1f}C"
      f"  max={measured_avg.max():.1f}C")

# ── Load simulation ───────────────────────────────────────────────
simulated = load_simulation_variable("Zone Air Temperature", zone)
print(f"\n  Simulated TZ_NW:"
      f"  mean={simulated.mean():.1f}C"
      f"  min={simulated.min():.1f}C"
      f"  max={simulated.max():.1f}C")

# ── Align ─────────────────────────────────────────────────────────
meas_al, sim_al = align_series(measured_avg, simulated)
diff = meas_al.values - sim_al.values
print(f"\n  Aligned ({len(meas_al)} h overlap):")
print(f"  Mean diff (meas-sim) = {diff.mean():+.2f}C")
print(f"  Hours meas > 26C     = {(meas_al > 26).sum()}")
print(f"  Hours meas > 28C     = {(meas_al > 28).sum()}")
print(f"  Hours meas > 30C     = {(meas_al > 30).sum()}")
print(f"  Hours sim  == 24C    = {(sim_al == 24.0).sum()} "
      f"({100*(sim_al==24.0).sum()/len(sim_al):.0f}% stuck at setpoint)")

# ── Plot ──────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), dpi=120)

# Panel 1: All 6 office traces + zone avg + simulated
colors = ["#1565C0","#1976D2","#42A5F5","#90CAF9","#0D47A1","#1E88E5"]
for i, (office, s) in enumerate(all_series.items()):
    s_hr = s.resample("1h").mean()
    ax1.plot(s_hr.index, s_hr.values,
             color=colors[i], linewidth=0.8, alpha=0.55, label=f"Office {office}")

ax1.plot(meas_al.index, meas_al.values,
         color="navy", linewidth=2.2, label="Zone average (measured)", zorder=5)
ax1.plot(sim_al.index, sim_al.values,
         color="#C62828", linewidth=2.0, linestyle="--",
         label="EnergyPlus TZ_NW (simulated)", zorder=5)
ax1.axhline(24.0, color="orange", linewidth=1.2, linestyle=":",
            label="Cooling setpoint (24°C)")

ax1.set_title("TZ_NW Temperature: All Office Sensors vs EnergyPlus  |  Aug 23-31, 2013",
              fontsize=12, fontweight="bold")
ax1.set_ylabel("Temperature (°C)")
ax1.legend(fontsize=8, ncol=4, loc="upper right")
ax1.grid(True, linestyle=":", alpha=0.4)
ax1.set_ylim(18, 35)

# Panel 2: Bias (measured - simulated)
ax2.bar(meas_al.index, diff, width=0.04, color=[
    "#C62828" if d > 0 else "#1565C0" for d in diff],
    alpha=0.75, label="Measured − Simulated (°C)")
ax2.axhline(0, color="black", linewidth=0.8)
ax2.axhline(diff.mean(), color="darkorange", linewidth=1.5, linestyle="--",
            label=f"Mean bias = {diff.mean():+.2f}°C")
ax2.set_title("Temperature Bias  (Measured − Simulated)  |  Red = model too cold",
              fontsize=11)
ax2.set_ylabel("Bias (°C)")
ax2.legend(fontsize=9)
ax2.grid(True, linestyle=":", alpha=0.4)

import matplotlib.dates as mdates
for ax in [ax1, ax2]:
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha="center")

fig.tight_layout()
path = os.path.join(out_dir, "TZ_NW_diagnostic.png")
fig.savefig(path, bbox_inches="tight")
plt.close(fig)
print(f"\n  Diagnostic plot saved -> {path}")
print("\n[DONE]")
