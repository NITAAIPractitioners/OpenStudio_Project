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
def load_humidity(office_path):

    df = pd.read_csv(
        os.path.join(office_path, "humidity.csv"),
        header=None,
        names=["timestamp", "hum"]
    )

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.set_index("datetime")

    # convert to 10-minute resolution
    df = df.resample("10min").mean()

    return df["hum"]


hums = []

for office in selected_offices:
    office_path = os.path.join(base_path, office)
    hums.append(load_humidity(office_path))

# average humidity across offices
sensor_hum = pd.concat(hums, axis=1).mean(axis=1)

print("Sensor humidity points:", len(sensor_hum))




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
WHERE rdd.Name = 'Zone Air Relative Humidity'
AND rdd.ReportingFrequency = 'Zone Timestep'
ORDER BY rd.TimeIndex
"""

rh_df = pd.read_sql(query, conn)
rh_df["Value"] = pd.to_numeric(rh_df["Value"], errors="coerce")

rh_df["datetime"] = pd.to_datetime(
    rh_df[["Year","Month","Day","Hour","Minute"]]
)

rh_df = rh_df.set_index("datetime")

sim_hum = rh_df["Value"]
sim_hum.index = sim_hum.index.map(lambda x: x.replace(year=2013))
data_hum = pd.concat([sim_hum, sensor_hum], axis=1).dropna()

data_hum.columns = ["Simulated", "Measured"]

print("Aligned rows:", len(data_hum))
import matplotlib.pyplot as plt

plt.figure(figsize=(10,4))

data_hum["Simulated"].plot(label="Simulated")
data_hum["Measured"].plot(label="Measured")

plt.legend()
plt.ylabel("Relative Humidity (%)")
plt.title("Humidity Validation – Level 4")
plt.show()
import numpy as np

rmse = np.sqrt(((data_hum["Simulated"] - data_hum["Measured"])**2).mean())

cvrmse = rmse / data_hum["Measured"].mean() * 100

nmbe = (
    (data_hum["Simulated"] - data_hum["Measured"]).mean()
    / data_hum["Measured"].mean()
) * 100

print("RMSE:", rmse)
print("CVRMSE:", cvrmse,"%")
print("NMBE:", nmbe,"%")