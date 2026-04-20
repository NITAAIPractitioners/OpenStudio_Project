import os
import pandas as pd
import numpy as np

BASE_PATH = r"C:\Users\me.com\Documents\engery\OpenStudio_Project\original_frozen\KETI"
OFFICE = "413"

def load_sensor(sensor_name):
    path = os.path.join(BASE_PATH, OFFICE, f"{sensor_name}.csv")
    df = pd.read_csv(path, header=None, names=["t", "v"], usecols=[0, 1])
    # Filter to numeric only, coerce errors
    df['v'] = pd.to_numeric(df['v'], errors='coerce')
    df = df.dropna()
    df['dt'] = pd.to_datetime(df['t'], unit='s')
    df = df.set_index('dt')['v'].sort_index()
    return df

print(f"Loading high-frequency data for Office {OFFICE}...")
light = load_sensor("light")
co2 = load_sensor("co2")

# Resample to 1-minute intervals to maintain high resolution while aligning timestamps
print("Resampling to 1-minute buckets...")
l_res = light.resample("1min").mean().ffill().bfill()
c_res = co2.resample("1min").mean().interpolate().bfill().ffill()

common_idx = l_res.index.intersection(c_res.index)
l_res = l_res.loc[common_idx]
c_res = c_res.loc[common_idx]

# Calculate derivatives (rate of change)
print("Calculating derivatives...")
l_diff = l_res.diff().fillna(0)
c_diff = c_res.diff().fillna(0)

# We want only the "turn ON" events (positive spikes) for light
l_diff_positive = l_diff.clip(lower=0)

results = []
# Sweep lag from 0 to 60 minutes
print("Running Cross-Correlation Sweep (0 to 60 minutes)...")
for shift_mins in range(0, 61):
    shifted_c_diff = c_diff.shift(-shift_mins) 
    corr = l_diff_positive.corr(shifted_c_diff)
    if not np.isnan(corr):
        results.append((shift_mins, corr))

best_lag, max_corr = max(results, key=lambda x: x[1])

print("\n=== RESULTS ===")
print(f"Calculated optimal physical lag in Office {OFFICE}: {best_lag} minutes")
print(f"Correlation score at {best_lag} minutes: {max_corr:.4f}")

# Also check top 5 lags
print("\nTop 5 lag candidates:")
results.sort(key=lambda x: x[1], reverse=True)
for i in range(5):
    print(f"  {results[i][0]} mins: {results[i][1]:.4f}")
