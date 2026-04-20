"""
visualize_schedules.py — noIdealLoad_model
=========================================
Standalone script to visualize EnergyPlus schedules from SQL.
Targets the specific NoIdealLoad experiment.
"""

import os
import sys
import json
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# --- LOCAL PATH DISCOVERY ---
_HERE = Path(__file__).parent
EXPERIMENT_ROOT = _HERE.parent
CONFIG_PATH = EXPERIMENT_ROOT / "experiment_config.json"
OUTPUT_DIR = EXPERIMENT_ROOT / "outputs" / "schedules"

def load_config():
    if not CONFIG_PATH.exists(): return None
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def get_sql_path(config):
    run_dir = config["latest_run_dir"]
    return EXPERIMENT_ROOT / "model" / "runs" / run_dir / "run" / "eplusout.sql"

def plot_schedules(sql_path):
    if not sql_path.exists():
        print(f"[ERROR] SQL not found: {sql_path}")
        return

    conn = sqlite3.connect(sql_path)
    
    # Get all schedule values
    query = """
        SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value, rdd.Name, rdd.KeyValue
        FROM ReportData rd
        JOIN Time t ON rd.TimeIndex = t.TimeIndex
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = 'Schedule Value'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No schedule data found.")
        return

    df['dt'] = pd.to_datetime({'year': 2013, 'month': df['Month'], 'day': df['Day'], 'hour': df['Hour'].clip(upper=23), 'minute': df['Minute']})
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Plot top 5 unique schedules as example
    unique_sch = df['KeyValue'].unique()[:8]
    for sch_name in unique_sch:
        sch_df = df[df['KeyValue'] == sch_name].sort_values('dt')
        
        plt.figure(figsize=(10, 4))
        plt.plot(sch_df['dt'], sch_df['Value'], label=sch_name, color='darkorange')
        plt.title(f"Schedule: {sch_name}")
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        fname = sch_name.replace(" ", "_").replace(":", "_")
        plt.savefig(OUTPUT_DIR / f"{fname}.png")
        plt.close()
        print(f"  [PLOT] Saved {fname}.png")

def main():
    config = load_config()
    if not config: return
    sql_path = get_sql_path(config)
    print(f"--- noIdealLoad_model: Visualization - Schedules ---")
    plot_schedules(sql_path)

if __name__ == "__main__":
    main()
