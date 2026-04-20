import os
import pandas as pd
import numpy as np

def load_keti(path, freq="1min"):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, header=None, names=["timestamp", "value"], skipinitialspace=True, on_bad_lines='skip')
    # Filter bad lines if necessary
    if not pd.to_numeric(df['value'].head(5), errors='coerce').notnull().all():
        return None
        
    df['dt'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
    df = df.dropna(subset=['dt']).set_index('dt').sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df['value'].resample(freq).mean().interpolate().bfill().ffill()

def build_wide_lag():
    base = "KETI"
    if not os.path.exists(base): return
    offices = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    
    office_lags = []
    for off in offices:
        path_co2 = f"{base}/{off}/co2.csv"
        path_pir = f"{base}/{off}/pir.csv"
        
        co2 = load_keti(path_co2)
        pir = load_keti(path_pir)
        if co2 is None or pir is None:
            continue
            
        common_idx = co2.index.intersection(pir.index)
        if len(common_idx) < 100: continue
        co2 = co2.loc[common_idx]
        pir = pir.loc[common_idx]
        
        pir_bin = (pir > 0).astype(int)
        
        co2_clean = co2.interpolate().ffill().bfill()
        pir_clean = pir_bin.interpolate().ffill().bfill()
        
        co2_norm = (co2_clean - co2_clean.mean()) / (co2_clean.std() + 1e-9)
        pir_smoothed = pir_clean.rolling(30, center=True).mean().fillna(0)
        pir_norm = (pir_smoothed - pir_smoothed.mean()) / (pir_smoothed.std() + 1e-9)
        
        corrs = []
        for lag in range(45 + 1):
            if lag == 0: corr = pir_norm.corr(co2_norm)
            else: corr = pir_norm.corr(co2_norm.shift(-lag))
            corrs.append(corr)
            
        # Optional: check if the correlation is meaningful at all.
        if np.max(corrs) > 0.1:
            office_lags.append(np.argmax(corrs))

    if not office_lags:
        print("Not enough data to calculate building-wide lag.")
        return

    median_lag = np.median(office_lags)
    mean_lag = np.mean(office_lags)

    print("--- BUILDING-WIDE CO2 Response Lag Analysis ---")
    print(f"Offices Analyzed: {len(office_lags)}")
    print(f"Algorithm: Cross-Correlation of PIR and CO2 Concentration.")
    print(f"Calculated Mean Lag: {mean_lag:.1f} minutes")
    print(f"Calculated Median (Geometric Shift) Delay: {median_lag:.1f} minutes")
    print(f"Interquartile Range (25th-75th): {np.percentile(office_lags, 25):.1f} to {np.percentile(office_lags, 75):.1f} minutes")
    if 20 <= median_lag <= 29:
        print("Proof Successful: Building-wide Median Lag safely falls within the empirical 20-29 minute window.")
    else:
        print("Note: Calculated lag does not match expected 20-29 window.")
    print("-----------------------------------------------------")

if __name__ == "__main__":
    build_wide_lag()
