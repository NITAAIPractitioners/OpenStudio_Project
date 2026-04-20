import os
import pandas as pd
import numpy as np

BASE_PATH = r"C:\Users\me.com\Documents\engery\OpenStudio_Project\original_frozen\KETI"
OUTPUT_DIR = r"C:\Users\me.com\Documents\engery\OpenStudio_Project\scratch\daily_lags"

def load_sensor(office, sensor_name):
    path = os.path.join(BASE_PATH, office, f"{sensor_name}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, header=None, names=["t", "v"], usecols=[0, 1])
    df['v'] = pd.to_numeric(df['v'], errors='coerce')
    df = df.dropna()
    df['dt'] = pd.to_datetime(df['t'], unit='s')
    df = df.set_index('dt')['v'].sort_index()
    # Remove duplicates
    df = df[~df.index.duplicated(keep="first")]
    return df

def calculate_daily_lags():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    offices = [d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))]
    
    total_offices_processed = 0
    total_days_saved = 0
    
    for office in offices:
        print(f"Processing Office {office}...")
        light = load_sensor(office, "light")
        co2 = load_sensor(office, "co2")
        
        if light is None or co2 is None or light.empty or co2.empty:
            print(f"  Missing data for {office}. Skipping.")
            continue
            
        # Resample
        l_res = light.resample("1min").mean().ffill().bfill()
        c_res = co2.resample("1min").mean().interpolate().bfill().ffill()
        
        common_idx = l_res.index.intersection(c_res.index)
        if len(common_idx) == 0:
            continue
        l_res = l_res.loc[common_idx]
        c_res = c_res.loc[common_idx]
        
        l_diff = l_res.diff().fillna(0)
        c_diff = c_res.diff().fillna(0)
        
        l_diff_positive = l_diff.clip(lower=0)
        
        results_by_day = []
        
        df_merged = pd.DataFrame({
            'l_diff_pos': l_diff_positive,
            'c_diff': c_diff
        })
        
        for date, group in df_merged.groupby(df_merged.index.date):
            if group['l_diff_pos'].std() == 0 or group['c_diff'].std() == 0:
                continue
                
            day_results = []
            for shift_mins in range(0, 61):
                # Shift across the full dataframe to avoid edge condition losses
                shifted_c_diff = df_merged['c_diff'].shift(-shift_mins)
                
                slice_l = group['l_diff_pos']
                slice_c = shifted_c_diff.loc[group.index]
                
                corr = slice_l.corr(slice_c)
                if not np.isnan(corr):
                    day_results.append((shift_mins, corr))
            
            if day_results:
                best_lag, max_corr = max(day_results, key=lambda x: x[1])
                # Filter out extremely weak correlations to avoid random noise matching
                if max_corr > 0.01:
                    results_by_day.append({
                        "Date": date,
                        "Optimal_Lag_Minutes": best_lag,
                        "Correlation_Score": round(float(max_corr), 4)
                    })
                    
        if results_by_day:
            out_df = pd.DataFrame(results_by_day)
            out_path = os.path.join(OUTPUT_DIR, f"{office}_daily_lags.csv")
            out_df.to_csv(out_path, index=False)
            print(f"  Saved daily lags to {out_path} ({len(out_df)} days)")
            total_offices_processed += 1
            total_days_saved += len(out_df)
        else:
            print(f"  No valid daily lags found for {office}.")
            
    print(f"\nCompleted! Processed {total_offices_processed} offices and extracted lag for {total_days_saved} valid days.")

if __name__ == "__main__":
    calculate_daily_lags()
