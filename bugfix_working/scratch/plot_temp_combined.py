"""
Generate a combined multi-panel temperature alignment figure for all
fused-schedule zones (Aug 23-31, 2013).
"""
import os, sys

# Always resolve paths relative to project root (parent of scratch/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)   # ensure relative paths inside shared_validation work

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from shared_validation import (
    SPACE_ZONE_MAP, get_output_dir,
    load_keti_sensor, load_simulation_variable,
    align_series, compute_rmse, compute_cv_rmse,
)

ZONE_OFFICES = {}
for office, zone in sorted(SPACE_ZONE_MAP.items()):
    ZONE_OFFICES.setdefault(zone, []).append(office)

zones = sorted(ZONE_OFFICES.keys())
n = len(zones)

fig, axes = plt.subplots(n, 1, figsize=(16, 4 * n), dpi=130, sharex=False)
fig.suptitle(
    "Temperature Validation  |  Measured (KETI) vs Simulated (EnergyPlus)\n"
    "Fused-Schedule Zones  |  Aug 23-31, 2013  |  Sutardja Dai Hall Level 4",
    fontsize=14, fontweight="bold", y=1.01
)

COLORS = {"measured": "#1565C0", "simulated": "#C62828"}
PASS_COLOR = "#2E7D32"
FAIL_COLOR = "#B71C1C"

out_dir = get_output_dir("temperature")

for ax, zone in zip(axes, zones):
    offices = sorted(ZONE_OFFICES[zone])

    # Load + average measured
    series_list = [s for o in offices
                   for s in [load_keti_sensor(o, "temperature")]
                   if s is not None and not s.empty]
    if not series_list:
        ax.set_title(f"{zone} — no measured data", color="gray")
        continue

    measured = pd.concat(series_list, axis=1).mean(axis=1).dropna()
    simulated = load_simulation_variable("Zone Air Temperature", zone)
    if simulated is None:
        ax.set_title(f"{zone} — no simulated data", color="gray")
        continue

    meas_al, sim_al = align_series(measured, simulated)
    if len(meas_al) == 0:
        ax.set_title(f"{zone} — no overlap", color="gray")
        continue

    rmse   = compute_rmse(meas_al, sim_al)
    cvrmse = compute_cv_rmse(meas_al, sim_al)
    mbe_pct = 100.0 * float(np.mean(sim_al.values - meas_al.values)) / float(np.mean(meas_al.values))
    passed = (cvrmse < 30.0) and (abs(mbe_pct) < 10.0)
    status = "PASS" if passed else "FAIL"
    status_color = PASS_COLOR if passed else FAIL_COLOR

    # Plot
    ax.fill_between(meas_al.index, meas_al.values, sim_al.values,
                    alpha=0.08, color="#1976D2")
    ax.plot(meas_al.index, meas_al.values,
            color=COLORS["measured"], linewidth=1.6,
            label=f"Measured KETI avg ({len(offices)} office{'s' if len(offices)>1 else ''})")
    ax.plot(sim_al.index, sim_al.values,
            color=COLORS["simulated"], linewidth=1.4, linestyle="--",
            label="EnergyPlus simulated")

    # Annotation box
    info = (f"Offices: {', '.join(offices)}\n"
            f"n = {len(meas_al)} h  |  RMSE = {rmse:.3f}°C  |  "
            f"CV(RMSE) = {cvrmse:.1f}%  |  MBE = {mbe_pct:+.1f}%")
    ax.text(0.01, 0.97, info, transform=ax.transAxes,
            fontsize=8.5, va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    # ASHRAE badge
    ax.text(0.99, 0.97, f"ASHRAE-14: {status}",
            transform=ax.transAxes, fontsize=9, fontweight="bold",
            va="top", ha="right", color=status_color,
            bbox=dict(boxstyle="round,pad=0.3",
                      facecolor="#E8F5E9" if passed else "#FFEBEE", alpha=0.9))

    ax.set_title(f"Zone  {zone}", fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("Temperature (°C)", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha="center")
    ax.grid(True, linestyle=":", alpha=0.45)
    ax.legend(fontsize=8.5, loc="upper right", framealpha=0.85)
    ax.set_xlim(meas_al.index[0], meas_al.index[-1])

fig.tight_layout()
combined_path = os.path.join(out_dir, "temperature_all_zones_combined.png")
fig.savefig(combined_path, bbox_inches="tight", dpi=130)
plt.close(fig)
print(f"Saved: {combined_path}")
