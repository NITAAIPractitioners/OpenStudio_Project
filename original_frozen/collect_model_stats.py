import sqlite3
import pandas as pd
from pathlib import Path

MODELS = {
    "Aswani-VAV": "aswani_model/model/runs/run_20260417_170034/run/eplusout.sql",
    "Ideal": "idealLoad_model/model/runs/run_20260417_170052/run/eplusout.sql"
}

def get_stats(db_path):
    if not Path(db_path).exists():
        return {"Error": "File not found"}
    
    conn = sqlite3.connect(db_path)
    # Area check
    area_df = pd.read_sql("SELECT RowName, Value FROM TabularDataWithStrings WHERE TableName='Input Verification and Summary Report' AND ColumnName='Area'", conn)
    area_nw = area_df[area_df['RowName'] == 'TZ_NW']['Value'].values[0] if not area_df.empty else "N/A"
    
    # People count check
    occ_df = pd.read_sql("SELECT Value FROM TimeSeriesData WHERE VariableName='Zone People Occupant Count' AND KeyValue='TZ_NW'", conn)
    mean_occ = occ_df['Value'].mean() if not occ_df.empty else 0
    
    # Count of People Objects in SQL (Optional)
    # Actually, check Num Spaces in Zone
    space_count = pd.read_sql("SELECT COUNT(*) as count FROM TabularDataWithStrings WHERE TableName='Input Verification and Summary Report' AND RowName='TZ_NW' AND ColumnName='Conditioned'", conn)
    
    conn.close()
    return {
        "Area_TZ_NW": area_nw,
        "Mean_Sim_Occ": mean_occ,
        "RecordCount": len(occ_df)
    }

if __name__ == "__main__":
    for name, path in MODELS.items():
        print(f"Stats for {name}:", get_stats(path))
