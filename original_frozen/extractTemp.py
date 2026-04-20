import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
selected_offices = [
    "413", "415", "417", "419", "421", "423",
     "422", "424", 
    "442", "446", "448", "452", "454", "456", "458", "462"
]

base_path = "KETI"

def load_temp(office_path):

    df = pd.read_csv(
        os.path.join(office_path,"temperature.csv"),
        header=None,
        names=["timestamp","temp"]
    )

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.set_index("datetime")

    df = df.resample("10min").mean()

    return df["temp"]



temps = []

for office in selected_offices:
    office_path = os.path.join(base_path, office)
    temps.append(load_temp(office_path))

sensor_temp = pd.concat(temps, axis=1).mean(axis=1)

conn = sqlite3.connect("eplusout.sql")

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
WHERE rdd.Name = 'Zone Mean Air Temperature'
AND rdd.ReportingFrequency = 'Zone Timestep'
ORDER BY rd.TimeIndex
"""

temp_df = pd.read_sql(query, conn)

print("Rows:", len(temp_df))
print(temp_df.head())
temp_df["Value"] = pd.to_numeric(temp_df["Value"], errors="coerce")

temp_df["datetime"] = pd.to_datetime(
    temp_df[["Year","Month","Day","Hour","Minute"]]
)

temp_df = temp_df.set_index("datetime")
sim_temp = temp_df["Value"]
sim_temp.index = sim_temp.index.map(lambda x: x.replace(year=2013))
print("Simulation points:", len(sim_temp))
print("Sensor points:", len(sensor_temp))
print(sensor_temp.isna().sum())
data = pd.concat([sim_temp, sensor_temp], axis=1).dropna()
data.columns = ["Simulated","Measured"]
print("Aligned rows:", len(data))
plt.figure(figsize=(10,4))

data["Simulated"].plot(label="Simulated")
data["Measured"].plot(label="Measured")

plt.legend()
plt.ylabel("Temperature (°C)")
plt.title("Temperature Validation – Level 4")
plt.show()