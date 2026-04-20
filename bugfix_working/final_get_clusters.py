import os
import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

BASE_PATH   = "KETI"
DATE_RANGE  = ("2013-08-23", "2013-08-31 23:59:59")

def load_sensor(office_path, file_name):
    path = os.path.join(office_path, file_name)
    if not os.path.isfile(path): return None
    try:
        df = pd.read_csv(path, header=None, names=["timestamp", "value"], skipinitialspace=True)
        if df.empty: return None
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        df = df.set_index("datetime").sort_index()
        df = df[~df.index.duplicated(keep="first")]
        return df["value"]
    except: return None

offices = sorted([d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))])
co2_data = {}
for office in offices:
    raw = load_sensor(os.path.join(BASE_PATH, office), "co2.csv")
    if raw is not None and not raw.empty:
        raw = raw.loc[DATE_RANGE[0]:DATE_RANGE[1]]
        if not raw.empty:
            co2_data[office] = raw

hourly_all = [s.resample("1H").mean().rename(o) for o, s in co2_data.items()]
hourly_df = pd.concat(hourly_all, axis=1).fillna(0)
corr = hourly_df.corr().fillna(0)
Z = linkage(squareform((1-corr + (1-corr).T)/2 - np.diag(np.diag(1-corr))), 'ward')
cluster_ids = fcluster(Z, t=0.3, criterion='distance')
office_to_cluster = {off: cid for off, cid in zip(hourly_df.columns, cluster_ids)}

with open("cluster_map.txt", "w") as f:
    for cid in sorted(list(set(cluster_ids))):
        members = [off for off, c in office_to_cluster.items() if c == cid]
        f.write(f"GROUP {cid}: {', '.join(members)}\n")
print("SUCCESS")
