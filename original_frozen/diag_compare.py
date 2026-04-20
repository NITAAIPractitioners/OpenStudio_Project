import os
import pandas as pd
import numpy as np

BASE_PATH = "KETI"
DATE_RANGE = ("2013-08-23", "2013-08-31 23:59:59")

def load_sensor(office, sensor_file):
    path = os.path.join(BASE_PATH, office, sensor_file)
    if not os.path.exists(path): return None
    df = pd.read_csv(path, header=None, names=["ts", "val"])
    df['dt'] = pd.to_datetime(df['ts'], unit='s')
    df = df.set_index('dt').sort_index()
    return df['val'].loc[DATE_RANGE[0]:DATE_RANGE[1]]

offices = sorted([d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))])

results = []

for off in offices:
    co2 = load_sensor(off, "co2.csv")
    pir = load_sensor(off, "pir.csv")
    
    # 1. Light Label (Already have it in previous map, but re-run logic briefly for consistency)
    lux = load_sensor(off, "light.csv")
    light_label = "Unknown"
    # (Bypass full baseline logic for speed, just use the results.md we read earlier)
    # Actually, I'll just load the saved labels
    
    co2_label = "Normal CO2"
    if co2 is not None and not co2.empty:
        peak = co2.max()
        evening = co2.between_time("18:00", "23:00").mean()
        
        # Check spikes (derivative spikes)
        diff = co2.diff().abs().dropna()
        spiky = (diff > 50).any() # threshold for sudden co2 jump
        
        if peak > 1000 and evening > 800: co2_label = "Extended CO2"
        elif peak > 1000: co2_label = "High CO2"
        elif peak < 600: co2_label = "Low CO2"
        elif spiky: co2_label = "Spiky CO2"
    
    pir_confirmed = False
    if pir is not None and not pir.empty:
        pir_confirmed = (pir > 0).any()
        pir_spikes = (pir > 0).sum()
    else:
        pir_spikes = 0
        
    results.append({'Office': off, 'CO2': co2_label, 'PIR_Spikes': pir_spikes})

# Load Light Mapping from saved file
light_map = {}
light_map_path = os.path.join("multi_sensor_analysis", "light", "light_behavior_map.md")
if os.path.exists(light_map_path):
    with open(light_map_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if "|" in line and "Group" not in line and "---" not in line:
                parts = line.split("|")
                group = parts[1].strip()
                ids = parts[3].strip().split(", ")
                for id in ids: light_map[id] = group

df_final = pd.DataFrame(results)
df_final['Light'] = df_final['Office'].map(light_map).fillna("Unknown")

# Task 1: Comparative Mapping
print("--- COMPARISON TABLE ---")
print(df_final[['Office', 'CO2', 'Light']].to_string(index=False))

# Task 2: Cross-tabulation
print("\n--- CROSS-TABULATION ---")
print(pd.crosstab(df_final['CO2'], df_final['Light']))

# Metrics
agree_count = 0
for idx, row in df_final.iterrows():
    c, l = row['CO2'], row['Light']
    if (c == "Extended CO2" and l == "Extended Hours") or \
       (c == "Low CO2" and l == "Low Occupancy") or \
       (c == "Normal CO2" and l == "Normal Office"):
        agree_count += 1

print(f"\nSimple Agreement Rate: {agree_count / len(df_final) * 100:.1f}%")

# PIR Eval
print("\n--- PIR SPIKE CHECK ---")
print(df_final.groupby(['CO2', 'Light'])['PIR_Spikes'].mean().unstack())
