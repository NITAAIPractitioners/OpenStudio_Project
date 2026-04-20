"""Verify the SQL now contains the expected output variables after re-run."""
import sqlite3
import pandas as pd
import os

SQL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "run", "eplusout.sql")
print(f"SQL path: {SQL}")
print(f"Exists: {os.path.exists(SQL)}")
if os.path.exists(SQL):
    size_mb = os.path.getsize(SQL) / 1024 / 1024
    print(f"Size: {size_mb:.2f} MB")

conn = sqlite3.connect(SQL)

# Show all tables
tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
print(f"\nTables: {tables['name'].tolist()}")

# Show all dictionary entries
df = pd.read_sql_query(
    "SELECT ReportDataDictionaryIndex, KeyValue, Name, Units FROM ReportDataDictionary ORDER BY Name",
    conn
)
print(f"\nReportDataDictionary ({len(df)} rows):")
print(df.to_string())

# Count actual data rows
count = pd.read_sql_query("SELECT COUNT(*) as n FROM ReportData", conn)
print(f"\nReportData rows: {count['n'][0]}")

conn.close()
