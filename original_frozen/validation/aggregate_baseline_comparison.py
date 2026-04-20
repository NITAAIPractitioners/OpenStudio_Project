import os
import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path

def extract_nw_metrics(run_dir):
    """Extracted core validation logic to avoid dependencies."""
    sql_path = Path(run_dir) / "run" / "eplusout.sql"
    if not sql_path.exists():
        return None
    
    conn = sqlite3.connect(sql_path)
    
    def get_var(var_name, key_value):
        query = f"""
        SELECT Value, TimeIndex 
        FROM ReportData 
        INNER JOIN ReportDataDictionary ON ReportData.ReportDataDictionaryIndex = ReportDataDictionary.ReportDataDictionaryIndex
        WHERE Name = '{var_name}' AND KeyValue = '{key_value}'
        """
        return pd.read_sql_query(query, conn)

    # Note: Extracting just NW Zone for this comparison
    metrics = {}
    for var, key in [
        ("Zone Air Temperature", "TZ_NW"),
        ("Zone Air Relative Humidity", "TZ_NW"),
        ("Zone Air CO2 Concentration", "TZ_NW"),
        ("Zone People Occupant Count", "TZ_NW")
    ]:
        df = get_var(var, key)
        if df.empty:
            print(f"  MISSING: {var} for {key}")
            conn.close()
            return None
        metrics[var] = round(df['Value'].mean(), 2)
    
    conn.close()
    return {
        "Sim_Temp_Avg": metrics["Zone Air Temperature"],
        "Sim_Hum_Avg": metrics["Zone Air Relative Humidity"],
        "Sim_CO2_Avg": metrics["Zone Air CO2 Concentration"],
        "Sim_Occ_Avg": metrics["Zone People Occupant Count"]
    }

def generate_table(results):
    df = pd.DataFrame(results)
    output_dir = Path("validation/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / "baseline_schedule_comparison.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nFinal Comparison Table Saved to: {csv_path}")
    return df
