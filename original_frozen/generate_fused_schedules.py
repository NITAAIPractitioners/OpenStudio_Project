import os
import pandas as pd
import numpy as np
# import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
BASE_PATH = "KETI"
FREQ = "10min"
CO2_LAG = "45min"
RESULT_DIR = "fused_results"
PLOTS_DIR = os.path.join(RESULT_DIR, "plots")

# Fusion Weights
W_CO2 = 0.55
W_LIGHT = 0.35
W_PIR = 0.10

# Binarization
OCC_THRESHOLD = 0.35
PERSISTENCE_WINDOW = "30min"

def log(msg):
    print(f"[FUSION] {msg}")

def ensure_dirs():
    if not os.path.exists(RESULT_DIR): os.makedirs(RESULT_DIR)
    if not os.path.exists(PLOTS_DIR): os.makedirs(PLOTS_DIR)

# ── Step 1: Data Ingestion ────────────────────────────────────────────────────
def load_and_resample(off, sensor):
    path = os.path.join(BASE_PATH, off, f"{sensor}.csv")
    if not os.path.exists(path): return None
    
    try:
        # KETI files typically have no headers: [unix_timestamp, reading]
        df = pd.read_csv(path, header=None, names=["timestamp", "value"], skipinitialspace=True, on_bad_lines='skip')
        
        # Check if first few values of 'value' are numeric
        if not pd.to_numeric(df['value'].head(5), errors='coerce').notnull().all():
            log(f"  Warning: {off}/{sensor} does not appear to contain numeric data. Skipping.")
            return None

        df['dt'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        df = df.dropna(subset=['dt'])
        df = df.set_index('dt').sort_index()
        # Remove duplicates
        df = df[~df.index.duplicated(keep="first")]
        return df["value"].resample(FREQ).mean().interpolate().bfill().ffill()
    except Exception as e:
        log(f"  Error loading {off}/{sensor}: {e}")
        return None

# ── Step 4: PIR Processing ────────────────────────────────────────────────────
def process_pir(pir):
    if pir is None: return None
    pir_binary = (pir > 0).astype(int)
    # 30min rolling max ensures transition persistence
    return pir_binary.rolling(PERSISTENCE_WINDOW).max().fillna(0)

# ── Step 8: IDF Generator ─────────────────────────────────────────────────────
def generate_idf_compact(office, hourly_weekday, hourly_weekend):
    """Generates a Schedule:Compact object for EnergyPlus/OpenStudio."""
    name = f"Occupancy_Office_{office}"
    idf = f"Schedule:Compact,\n"
    idf += f"  {name},                !- Name\n"
    idf += f"  Any Number,             !- Schedule Type Limits Name\n"
    
    # Weekdays
    idf += f"  Through: 12/31,         !- Field 1\n"
    idf += f"  For: Weekdays,          !- Field 2\n"
    for hour in range(24):
        val = hourly_weekday[hour]
        idf += f"  Until: {hour+1:02}:00, {val:.3f},\n"
        
    # Weekends (Saturdays/Sundays)
    idf += f"  For: Weekends,          !- Field 3\n"
    for hour in range(24):
        val = hourly_weekend[hour]
        idf += f"  Until: {hour+1:02}:00, {val:.3f},\n"
        
    # All Other Days
    idf += f"  For: AllOtherDays,      !- Field 4\n"
    for hour in range(24):
        val = hourly_weekend[hour]
        idf += f"  Until: {hour+1:02}:00, {val:.3f};\n"
        
    return idf

# ── Main Pipeline ─────────────────────────────────────────────────────────────
def main():
    ensure_dirs()
    offices = [d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))]
    log(f"Found {len(offices)} offices. Starting pipeline...")

    # Step 3: Global Light Baseline
    log("Calculating global Light baseline...")
    all_light = {}
    for off in offices:
        l = load_and_resample(off, "light")
        if l is not None: all_light[off] = l
    
    if not all_light:
        log("Error: No light data found in KETI directory.")
        return

    # Building-wide median across all offices
    light_matrix = pd.concat(all_light.values(), axis=1).interpolate().bfill().ffill()
    building_baseline = light_matrix.median(axis=1)

    summary_stats = []

    for idx, off in enumerate(offices):
        if off != "413": continue # Only process 413 as requested
        log(f"[{idx+1}/{len(offices)}] Processing {off}...")
        
        co2 = load_and_resample(off, "co2")
        pir = load_and_resample(off, "pir")
        light = all_light.get(off)
        
        if co2 is None or light is None:
            log(f"  Missing CO2 or Light for {off}. Skipping.")
            continue

        # Sync all to same index (Light matrix index is most complete)
        common_idx = light_matrix.index
        co2 = co2.reindex(common_idx).interpolate()
        light = light.reindex(common_idx).interpolate()
        if pir is not None: pir = pir.reindex(common_idx).fillna(0)
        else: pir = pd.Series(0, index=common_idx)

        # Step 2: Normalize CO2
        c_low, c_high = co2.quantile(0.10), co2.quantile(0.90)
        if c_high == c_low: c_high += 1 # Avoid div by zero
        co2_score = ((co2 - c_low) / (c_high - c_low)).clip(0, 1)

        # Step 3: Light Residual Score
        light_res = (light - building_baseline).clip(lower=0)
        l_high = light_res.quantile(0.90)
        if l_high == 0: l_high = 1
        light_score = (light_res / l_high).clip(0, 1)

        # Step 4: PIR Score
        pir_score = process_pir(pir)

        # Step 5: Align CO2 (Lag Correction)
        steps = int(pd.Timedelta(CO2_LAG) / pd.Timedelta(FREQ))
        co2_aligned = co2_score.shift(-steps).ffill()

        # Step 6: Weighted Fusion
        fused = (W_CO2 * co2_aligned + W_LIGHT * light_score + W_PIR * pir_score).clip(0, 1)

        # Step 7: Binarization
        occ_binary = (fused >= OCC_THRESHOLD).astype(int)
        # Smoothing window
        occ_clean = occ_binary.rolling(PERSISTENCE_WINDOW).max().fillna(0)

        # ── Data Export ───────────────────────────────────────────────────────
        out_df = pd.DataFrame({
            "co2_raw": co2,
            "co2_score": co2_score,
            "light_score": light_score,
            "pir_score": pir_score,
            "fused_score": fused,
            "occupied": occ_clean
        })
        out_df.to_csv(os.path.join(RESULT_DIR, f"{off}_fused_data.csv"))

        # Step 8: Schedules
        out_df['hour'] = out_df.index.hour
        out_df['weekday'] = out_df.index.weekday < 5 # 0-4 are Mon-Fri
        
        wd_profile = out_df[out_df['weekday']].groupby('hour')['occupied'].mean()
        we_profile = out_df[~out_df['weekday']].groupby('hour')['occupied'].mean()

        # IDF Snippet
        idf_str = generate_idf_compact(off, wd_profile, we_profile)
        with open(os.path.join(RESULT_DIR, f"{off}_schedule.idf"), "w") as f:
            f.write(idf_str)

        # ── Visualization (Disabled: Matplotlib missing) ──────────────────────
        # Plotting logic removed for stability in the current environment.

        summary_stats.append({
            "Office": off,
            "Mean_Occupancy": occ_clean.mean(),
            "Peak_Hours_WD": wd_profile.idxmax(),
            "Data_Points": len(out_df)
        })

    # Summary Report
    summary_df = pd.DataFrame(summary_stats)
    summary_df.to_csv(os.path.join(RESULT_DIR, "building_summary.csv"), index=False)
    log(f"All done. Results saved in {RESULT_DIR}")

if __name__ == "__main__":
    main()
