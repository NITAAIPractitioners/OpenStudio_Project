import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import KaggleData
import numpy as np
# --------------------------------------------------
# 1️⃣ Connect to EnergyPlus SQL file
# --------------------------------------------------
conn = sqlite3.connect("eplusout.sql")   # adjust path if needed

query = """
SELECT
    t.Year,
    t.Month,
    t.Day,
    t.Hour,
    t.Minute,
    rd.Value
FROM ReportData rd
JOIN ReportDataDictionary rdd
  ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
JOIN Time t
  ON rd.TimeIndex = t.TimeIndex
WHERE rdd.Name = 'Electric Equipment Electricity Rate'
AND rdd.ReportingFrequency = 'Zone Timestep'
ORDER BY rd.TimeIndex
"""
equip_df = pd.read_sql(query, conn)

print("Rows:", len(equip_df))
print(equip_df.head())

equip_df["Value"] = pd.to_numeric(equip_df["Value"], errors="coerce")

equip_df["datetime"] = pd.to_datetime(
    equip_df[["Year","Month","Day","Hour","Minute"]]
)

equip_df = equip_df.set_index("datetime")

equip_power = equip_df["Value"]

print("Final rows:", len(equip_power))
'''
equip_power.plot(figsize=(10,4), title="Electric Equipment Electricity Rate")
plt.ylabel("Power (W)")
plt.show()

plt.figure(figsize=(10,4))
values_one_day = KaggleData.floor_occ.values[:144]
plt.plot(values_one_day, label="Input Schedule")

sim_norm = equip_power.values[:144] / equip_power.max()
plt.plot(sim_norm, label="Simulated Power (normalized)")

plt.legend()
plt.show()
'''

design_power = 33.7 * 1871
print(design_power)
values_one_day = KaggleData.floor_occ.values[:144]
expected = design_power * values_one_day
diff = expected - equip_power.values[:144]
print("Max difference:", np.max(np.abs(diff)))
plt.plot(expected, label="Expected Power")
plt.plot(equip_power.values[:144], label="Simulated Power")
plt.legend()
plt.show()