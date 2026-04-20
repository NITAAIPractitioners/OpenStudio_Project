import os
import pandas as pd
import numpy as np
import sqlite3
import matplotlib.pyplot as plt
from pathlib import Path

# ─── 1. Configuration ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(r"c:\Users\me.com\Documents\engery\OpenStudio_Project")
FUSED_RESULTS_DIR = PROJECT_ROOT / "fused_results"
RUN_DIR = PROJECT_ROOT / "aswani_model" / "model" / "runs" / "B1b_eq20.0_oa0.01_inf0.5_20260418_184053"
SQL_PATH = RUN_DIR / "run" / "eplusout.sql"
OUTPUT_DIR = PROJECT_ROOT / "figures" / "audit_plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ZONE = "TZ_NW"
OFFICES = ["413", "415", "417", "419", "421", "423"]

# ─── 2. Data Loader for Simulation Truth ─────────────────────────────────────

def load_sql_var(sql_path, var_name, key_value):
    conn = sqlite3.connect(sql_path)
    q_idx = "SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE KeyValue = ? AND Name = ?"
    idx_df = pd.read_sql_query(q_idx, conn, params=(key_value.upper(), var_name))
    if idx_df.empty:
        conn.close(); return None
    idx = idx_df.iloc[0,0]
    q_data = "SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value FROM ReportData rd JOIN Time t ON rd.TimeIndex = t.TimeIndex WHERE rd.ReportDataDictionaryIndex = ?"
    df = pd.read_sql_query(q_data, conn, params=(int(idx),))
    conn.close()
    df["Year"] = 2013
    df["Hour_adj"] = df["Hour"].clip(upper=23)
    day_ov = (df["Hour"] == 24).astype(int)
    df["dt"] = pd.to_datetime(df[["Year", "Month", "Day", "Hour_adj"]].rename(columns={"Hour_adj":"hour", "Month":"month", "Day":"day", "Year":"year"})) \
               + pd.to_timedelta(df["Minute"], unit="m") + pd.to_timedelta(day_ov, unit="D")
    return df.groupby("dt")["Value"].mean().sort_index()

# ─── 3. Replication of test_unified_Aswani.py Injection Logic ────────────────

def get_injected_occ(fused_score):
    """Exact logic from test_unified_Aswani.py Lines 185-186"""
    return min(1.0, fused_score * 0.6) if fused_score >= 0.1 else 0.0

# ─── 4. Build Summed Audit ───────────────────────────────────────────────────
print(f"--- Summed Zone Integrity Audit (Using Actual Simulation Sources) ---")

# Step A: Load Fused Source CSVs (The CSVs the simulation actually reads)
dfs = []
for off in OFFICES:
    p = FUSED_RESULTS_DIR / f"{off}_fused_data.csv"
    if p.exists():
        df = pd.read_csv(p)
        df['dt'] = pd.to_datetime(df['dt'])
        # Apply scaling logic to the EXACT fused_score column in the CSV
        df[f'occ_{off}'] = df['fused_score'].apply(get_injected_occ)
        dfs.append(df.set_index('dt')[[f'occ_{off}']])

# Step B: Sum across offices
source_sum = pd.concat(dfs, axis=1).sum(axis=1)

# Step C: Load Simulation Results from SQL
sim_people = load_sql_var(SQL_PATH, "Zone People Occupant Count", ZONE)

# Step D: Align
start, end = "2013-08-23", "2013-08-31"
audit_df = pd.DataFrame({"source_sum": source_sum}).loc[start:end]
audit_df["sim_sum"] = sim_people.reindex(audit_df.index, method='ffill').fillna(0)

# ─── 5. Stats ────────────────────────────────────────────────────────────────
max_diff = np.max(np.abs(audit_df["source_sum"] - audit_df["sim_sum"]))
mean_diff = np.mean(np.abs(audit_df["source_sum"] - audit_df["sim_sum"]))
print(f"INTEGRITY CHECK (Source-to-SQL): Max Diff = {max_diff:.4f}")
print(f"INTEGRITY CHECK (Source-to-SQL): Mean Diff = {mean_diff:.4f}")

# ─── 6. Visualization ────────────────────────────────────────────────────────
plt.rcParams.update({'font.size': 11})
fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(audit_df.index, audit_df["source_sum"], color='#17becf', label='Sum of Injected Source CSVs (Aswani Scaling)', alpha=0.7)
ax.plot(audit_df.index, audit_df["sim_sum"], color='#d62728', linestyle='--', label='EnergyPlus SQL Predicted Population', alpha=0.8)
ax.set_title(f"Aswani Pipeline Audit: Source CSV Integration vs. EnergyPlus Execution (Zone {ZONE})")
ax.set_ylabel("Occupant Count"); ax.legend(); ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "audit_source_vs_sim.png", dpi=300)

# ─── 7. Output Final Evidence Table ──────────────────────────────────────────
evidence = audit_df.copy()
evidence["Error"] = evidence["source_sum"] - evidence["sim_sum"]
evidence.tail(20).to_csv(PROJECT_ROOT / "fused_schedule_source_integrity.csv")

print("Audit Evidence Generated (Source Integration Proof).")
