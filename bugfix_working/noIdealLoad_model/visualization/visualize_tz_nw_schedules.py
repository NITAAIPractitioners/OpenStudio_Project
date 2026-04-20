"""
visualize_tz_nw_schedules.py — noIdealLoad_model
=========================================
Standalone script to visualize sensor fusion vs EP outputs for TZ_NW.
Targets the specific NoIdealLoad experiment.
"""

import os
import sys
import json
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# --- LOCAL PATH DISCOVERY ---
_HERE = Path(__file__).parent
EXPERIMENT_ROOT = _HERE.parent
PROJECT_ROOT = EXPERIMENT_ROOT.parent
CONFIG_PATH = EXPERIMENT_ROOT / "experiment_config.json"
OUTPUT_DIR = EXPERIMENT_ROOT / "outputs" / "tz_nw"

def load_config():
    if not CONFIG_PATH.exists(): return None
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def get_sql_path(config):
    run_dir = config["latest_run_dir"]
    return EXPERIMENT_ROOT / "model" / "runs" / run_dir / "run" / "eplusout.sql"

def main():
    config = load_config()
    if not config: return
    sql_path = get_sql_path(config)
    
    if not sql_path.exists():
        print(f"[ERROR] SQL not found: {sql_path}")
        return

    print(f"--- noIdealLoad_model: Visualization - TZ_NW Validation ---")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(sql_path)
    
    # Check Occupant Count for TZ_NW
    query = """
        SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value
        FROM ReportData rd
        JOIN Time t ON rd.TimeIndex = t.TimeIndex
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = 'Zone People Occupant Count' AND rdd.KeyValue = 'TZ_NW'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No occupancy data for TZ_NW found.")
        return

    df['dt'] = pd.to_datetime({'year': 2013, 'month': df['Month'], 'day': df['Day'], 'hour': df['Hour'].clip(upper=23), 'minute': df['Minute']})
    
    plt.figure(figsize=(12, 5))
    plt.plot(df['dt'], df['Value'], label="Simulated Occupants (TZ_NW)", color='blue')
    plt.title("TZ_NW Reconstructed Occupancy Flow")
    plt.ylabel("Persons")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(OUTPUT_DIR / "tz_nw_occupancy.png")
    plt.close()
    print("  [PLOT] Saved tz_nw_occupancy.png")

if __name__ == "__main__":
    main()
