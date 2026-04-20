"""
analyze_sensors.py
==================
Visualizes raw CO2, PIR, and Light sensor readings across all KETI offices.

Section 1 (this file): CO2 for all offices — full time-series plots.
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — no GUI needed
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib

# ── Config ────────────────────────────────────────────────────────────────────
BASE_PATH   = "KETI"
DATE_RANGE  = ("2013-08-23", "2013-08-31 23:59:59")   # study period
OUTPUT_DIR  =  "office_plots2"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Helper ────────────────────────────────────────────────────────────────────
def load_sensor(office_path, file_name):
    """Load a KETI sensor CSV (Unix-timestamp, value) → datetime-indexed Series."""
    path = os.path.join(office_path, file_name)
    if not os.path.isfile(path):
        return None
    try:
        df = pd.read_csv(
            path,
            header=None,
            names=["timestamp", "value"],
            skipinitialspace=True
        )
    except Exception as e:
        print(f"  [ERROR] {path} – {e}")
        return None
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.set_index("datetime").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df["value"]


# No resampling — raw timestamps are used directly


# ── Discover available offices ────────────────────────────────────────────────
offices = sorted([
    d for d in os.listdir(BASE_PATH)
    if os.path.isdir(os.path.join(BASE_PATH, d))
])
print(f"Found {len(offices)} office folders: {offices}\n")

# ── 1. Load CO2 for every office ──────────────────────────────────────────────
co2_data = {}
for office in offices:
    office_path = os.path.join(BASE_PATH, office)
    raw = load_sensor(office_path, "co2.csv")
    if raw is None or raw.empty:
        print(f"  [SKIP] {office} — no co2.csv")
        continue
    # filter to study period
    raw = raw.loc[DATE_RANGE[0]:DATE_RANGE[1]]
    if raw.empty:
        print(f"  [SKIP] {office} — no data in study period")
        continue
    co2_data[office] = raw   # raw data, no resampling
    print(f"  [OK]   {office}  |  {len(raw):>6} raw rows  |  range {raw.min():.0f}–{raw.max():.0f} ppm")

print(f"\nLoaded CO2 for {len(co2_data)} offices.\n")

# ── 2. Per-Office, Per-Day Charts ───────────────────────────────────────────────
print("\nPlotting: Daily charts for each office …")

for office, series in co2_data.items():
    # Create office directory
    office_dir = os.path.join(OUTPUT_DIR, office)
    os.makedirs(office_dir, exist_ok=True)
    
    # Group data by day
    # series.index is datetime
    # We can handle each day individually
    days = series.resample("D")
    
    for day_start, day_data in days:
        if day_data.empty:
            continue
            
        date_str = day_start.strftime("%Y-%m-%d")
        
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor("#0f0f1a")
        ax.set_facecolor("#13132b")
        
        # Plot raw data, marker='.' shows the exact raw reading points
        ax.plot(day_data.index, day_data.values,
                color="#00ffcc", linewidth=1.0, alpha=0.9, marker='.', markersize=4)
                
        # Shaded day/night bands (8:00 - 18:00 business hours)
        ax.axvspan(day_start + pd.Timedelta(hours=8),
                   day_start + pd.Timedelta(hours=18),
                   color="#1e3a5f", alpha=0.3, zorder=0)

        dt_format = mdates.DateFormatter("%H:%M")
        ax.xaxis.set_major_formatter(dt_format)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        
        ax.set_title(f"Office {office} - CO₂ on {date_str} (Raw Readings)", color="white", fontsize=12, pad=12)
        ax.set_xlabel("Time of Day", color="white", fontsize=10)
        ax.set_ylabel("CO₂ (ppm)", color="white", fontsize=10)
        
        ax.tick_params(colors="#aaa", labelsize=9)
        ax.grid(True, color="#2a2a3a", linewidth=0.5)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333")
            
        plt.tight_layout()
        out_file = os.path.join(office_dir, f"co2_{date_str}.png")
        plt.savefig(out_file, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        
    print(f"  [DONE] {office} daily plots saved.")

print(f"\n✅ Done. All daily office plots saved to: {OUTPUT_DIR}")

# ── 3. Per-Day, All-Offices Charts ──────────────────────────────────────────────
print("\nPlotting: Daily charts showing all offices …")
daily_dir = os.path.join(OUTPUT_DIR, "all_offices_by_day")
os.makedirs(daily_dir, exist_ok=True)

# Find all unique dates across all offices
all_days = set()
for office, series in co2_data.items():
    if not series.empty:
        all_days.update(series.index.normalize().unique())

for day_start in sorted(all_days):
    date_str = day_start.strftime("%Y-%m-%d")
    
    fig, ax = plt.subplots(figsize=(15, 8))
    fig.patch.set_facecolor("#0f0f1a")
    ax.set_facecolor("#13132b")
    
    cmap = matplotlib.colormaps["tab20"].resampled(len(co2_data))
    
    # Shaded day/night bands (8:00 - 18:00 business hours)
    ax.axvspan(day_start + pd.Timedelta(hours=8),
               day_start + pd.Timedelta(hours=18),
               color="#1e3a5f", alpha=0.3, zorder=0)

    for i, (office, series) in enumerate(co2_data.items()):
        if series.empty: continue
        
        # Extract just this day's data
        day_end = day_start + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        day_data = series.loc[day_start:day_end]
        
        if not day_data.empty:
            ax.plot(day_data.index, day_data.values,
                    color=cmap(i), linewidth=1.0, alpha=0.8, marker='.', markersize=4, label=office)
    
    dt_format = mdates.DateFormatter("%H:%M")
    ax.xaxis.set_major_formatter(dt_format)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    
    ax.set_title(f"All Offices - CO₂ on {date_str} (Raw Readings)", color="white", fontsize=14, pad=12)
    ax.set_xlabel("Time of Day", color="white", fontsize=11)
    ax.set_ylabel("CO₂ (ppm)", color="white", fontsize=11)
    
    ax.tick_params(colors="#aaa", labelsize=10)
    ax.grid(True, color="#2a2a3a", linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    
    # Put legend outside
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5), fontsize=8, ncol=2,
              facecolor="#1a1a2e", edgecolor="#444", labelcolor="white")
              
    plt.tight_layout()
    out_file = os.path.join(daily_dir, f"co2_all_offices_{date_str}.png")
    plt.savefig(out_file, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  [DONE] All offices plot for {date_str} saved.")

print(f"\n✅ Done. All daily aggregated plots saved to: {daily_dir}")
