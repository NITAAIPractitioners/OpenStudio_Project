"""Inspect both SQL files - find which one has data."""
import sqlite3
import pandas as pd
import os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sql_files = [
    os.path.join(root, "run", "eplusout.sql"),
    os.path.join(root, "eplusout.sql"),
]

for sql_path in sql_files:
    print(f"\n{'='*60}")
    print(f"SQL: {sql_path}")
    if not os.path.exists(sql_path):
        print("  NOT FOUND")
        continue
    size_mb = os.path.getsize(sql_path) / 1024 / 1024
    print(f"  Size: {size_mb:.2f} MB")
    conn = sqlite3.connect(sql_path)

    # List tables
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
    print(f"  Tables: {tables['name'].tolist()}")

    # Check ReportDataDictionary
    if 'ReportDataDictionary' in tables['name'].values:
        count = pd.read_sql_query("SELECT COUNT(*) as n FROM ReportDataDictionary", conn)
        print(f"  ReportDataDictionary rows: {count['n'][0]}")

        if count['n'][0] > 0:
            print("\n  -- All entries in ReportDataDictionary --")
            df = pd.read_sql_query(
                "SELECT ReportDataDictionaryIndex, KeyValue, Name, Units FROM ReportDataDictionary LIMIT 50",
                conn
            )
            print(df.to_string())
    else:
        print("  ReportDataDictionary table: NOT FOUND")

    conn.close()

print("\nDone.")
