import os
import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

# ── Config ────────────────────────────────────────────────────────────────────
BASE_PATH   = "KETI"
DATE_RANGE  = ("2013-08-23", "2013-08-31 23:59:59")
OUTPUT_DIR  = "office_csv_tables"
os.makedirs(OUTPUT_DIR, exist_ok=True)

for res in ["raw", "10min", "hourly"]:
    os.makedirs(os.path.join(OUTPUT_DIR, res), exist_ok=True)

# ── Load Target Data ──────────────────────────────────────────────────────────
def load_sensor(office_path, file_name):
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
    except Exception:
        return None
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.set_index("datetime").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df["value"]

print("1. Loading raw CO2 data for all offices...")
offices = sorted([d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))])
co2_data = {}
for office in offices:
    raw = load_sensor(os.path.join(BASE_PATH, office), "co2.csv")
    if raw is not None and not raw.empty:
        raw = raw.loc[DATE_RANGE[0]:DATE_RANGE[1]]
        if not raw.empty:
            co2_data[office] = raw

print(f"Loaded {len(co2_data)} offices.")

# ── Group Similar Offices ─────────────────────────────────────────────────────
# We identify similar offices by clustering their average hourly CO2 profile.
print("\n2. Finding 'similar' offices to group together...")
# Resample to hourly and fillna temporarily just to get similarity
hourly_all = []
for office, series in co2_data.items():
    s = series.resample("1H").mean().rename(office)
    hourly_all.append(s)

hourly_df = pd.concat(hourly_all, axis=1).fillna(0)

# Calculate correlation matrix
corr = hourly_df.corr().fillna(0)
# Convert to distance
dist = 1 - corr
# Perform hierarchical clustering
# Since dist matrix might not be completely symmetric due to float issues
dist_condensed = squareform((dist + dist.T) / 2 - np.diag(np.diag(dist)))
Z = linkage(dist_condensed, 'ward')
order = leaves_list(Z)
# These are the offices sorted such that similar ones are adjacent
sorted_offices = [hourly_df.columns[i] for i in order]

print(f"Offices sorted by similarity: {sorted_offices}")

# ── Export CSV Tables by Day ──────────────────────────────────────────────────
print("\n3. Generating CSV tables for each day...")

# Gather all unique days
all_days = set()
for s in co2_data.values():
    all_days.update(s.index.normalize().unique())

for day_start in sorted(all_days):
    date_str = day_start.strftime("%Y-%m-%d")
    day_end = day_start + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    
    # 1. Raw
    raw_list = []
    for off in sorted_offices:
        s = co2_data[off].loc[day_start:day_end]
        if not s.empty:
            raw_list.append(s.rename(off))
    
    if raw_list:
        # Outer join of raw timestamps (can be sparse)
        df_raw = pd.concat(raw_list, axis=1)
        # 2. 10min resample
        df_10m = df_raw.resample("10min").mean()
        # 3. Hourly resample
        df_1h = df_raw.resample("1H").mean()
        
        # Save to CSV
        raw_path = os.path.join(OUTPUT_DIR, "raw", f"co2_raw_{date_str}.csv")
        m10_path = os.path.join(OUTPUT_DIR, "10min", f"co2_10min_{date_str}.csv")
        h1_path = os.path.join(OUTPUT_DIR, "hourly", f"co2_hourly_{date_str}.csv")
        
        df_raw.to_csv(raw_path)
        df_10m.to_csv(m10_path)
        df_1h.to_csv(h1_path)
        print(f"  [EXPORTED] {date_str} -> raw, 10min, hourly.")

print("\n✅ Done. All CSV tables generated and saved to:", OUTPUT_DIR)
