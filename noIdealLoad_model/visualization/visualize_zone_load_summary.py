"""
visualize_zone_load_summary.py — noIdealLoad_model
=========================================
Standalone script to aggregate per-office loads to Zone TZ_NW level.
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
OUTPUT_DIR = EXPERIMENT_ROOT / "outputs" / "summary"

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

    print(f"--- noIdealLoad_model: Visualization - Zone Internal Gain Summary ---")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(sql_path)
    
    # In NoIdealLoad, we are mostly interested in internal gains (People/Lights/Equipment)
    query = """
        SELECT rdd.KeyValue, rdd.Name, SUM(rd.Value) as TotalValue
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name IN ('Zone Lights Electricity Energy', 'Zone Electric Equipment Electricity Energy', 'Zone People Total Heating Energy')
        GROUP BY rdd.KeyValue, rdd.Name
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No internal gain data found.")
        return

    # Aggregate to Zone level (KeyValue is usually the Zone name for these variables)
    zone_summary = df.pivot(index='KeyValue', columns='Name', values='TotalValue')
    
    plt.figure(figsize=(10, 6))
    zone_summary.plot(kind='bar', stacked=True, ax=plt.gca(), cmap='viridis')
    plt.title("Total Internal Gains by Thermal Zone (Calibration Window)")
    plt.ylabel("Energy [Joules]")
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "zone_load_summary.png")
    plt.close()
    
    print("  [PLOT] Saved zone_load_summary.png")

if __name__ == "__main__":
    main()
