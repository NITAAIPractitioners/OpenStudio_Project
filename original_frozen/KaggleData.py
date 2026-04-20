import pandas as pd
import glob
import matplotlib.pyplot as plt
import os
import pandas as pd
import os

def process_office_raw(office_path):


    def load_sensor(file_name):
        df = pd.read_csv(
            os.path.join(office_path, file_name),
            header=None,
            names=["timestamp", "value"],
            skipinitialspace=True
        )
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        return df[["datetime", "value"]]

    co2   = load_sensor("co2.csv").rename(columns={"value": "CO2"})
    pir   = load_sensor("pir.csv").rename(columns={"value": "PIR"})
    light = load_sensor("light.csv").rename(columns={"value": "Light"})

    df = co2.merge(pir, on="datetime", how="outer")
    df = df.merge(light, on="datetime", how="outer")
    df = df.sort_values("datetime").set_index("datetime")

    df_10 = pd.DataFrame()
    df_10["CO2"] = df["CO2"].resample("10min").mean()
    df_10["Light"] = df["Light"].resample("10min").mean()
    df_10["PIR"] = df["PIR"].resample("10min").sum()

    df_10["PIR"] = df_10["PIR"].fillna(0)
    df_10["CO2"] = df_10["CO2"].ffill().bfill()
    df_10["Light"] = df_10["Light"].ffill().bfill()

    # Normalization
    def normalize(series):
        base = series.quantile(0.1)
        top  = series.quantile(0.9)
        if top - base > 0:
            return ((series - base) / (top - base)).clip(0,1)
        else:
            return 0

    # --- CO2 rate of change ---
    df_10["co2_rate"] = df_10["CO2"].diff()

    # Remove extreme spikes (sensor noise)
    df_10["co2_rate"] = df_10["co2_rate"].clip(-50, 50)

    rate_base = df_10["co2_rate"].quantile(0.1)
    rate_max  = df_10["co2_rate"].quantile(0.9)

    if rate_max - rate_base > 0:
        df_10["co2_rate_norm"] = (
            (df_10["co2_rate"] - rate_base) /
            (rate_max - rate_base)
        ).clip(0,1)
    else:
        df_10["co2_rate_norm"] = 0
            
    df_10["lux_norm"] = normalize(df_10["Light"])
    df_10["pir_norm"] = normalize(df_10["PIR"])

    

    return df_10

    # Return FULL dataframe instead of only occ_index
    return df_10
def process_office(office_path):

    def load_sensor(file_name):
        df = pd.read_csv(
            os.path.join(office_path, file_name),
            header=None,
            names=["timestamp", "value"],
            skipinitialspace=True
        )
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        return df[["datetime", "value"]]

    co2   = load_sensor("co2.csv").rename(columns={"value": "CO2"})
    pir   = load_sensor("pir.csv").rename(columns={"value": "PIR"})
    light = load_sensor("light.csv").rename(columns={"value": "Light"})

    df = co2.merge(pir, on="datetime", how="outer")
    df = df.merge(light, on="datetime", how="outer")
    df = df.sort_values("datetime").set_index("datetime")

    df_10 = pd.DataFrame()
    df_10["CO2"] = df["CO2"].resample("10min").mean()
    df_10["Light"] = df["Light"].resample("10min").mean()
    df_10["PIR"] = df["PIR"].resample("10min").sum()
 
    df_10["PIR"] = df_10["PIR"].fillna(0)
    df_10["CO2"] = df_10["CO2"].ffill().bfill()
    df_10["Light"] = df_10["Light"].ffill().bfill()

    # Normalization
    def normalize(series):
        base = series.quantile(0.1)
        top  = series.quantile(0.9)
        if top - base > 0:
            return ((series - base) / (top - base)).clip(0,1)
        else:
            return 0

    # --- CO2 rate of change ---
    df_10["co2_rate"] = df_10["CO2"].diff()

    # Remove extreme spikes (sensor noise)
    df_10["co2_rate"] = df_10["co2_rate"].clip(-50, 50)

    rate_base = df_10["co2_rate"].quantile(0.1)
    rate_max  = df_10["co2_rate"].quantile(0.9)

    if rate_max - rate_base > 0:
        df_10["co2_rate_norm"] = (
            (df_10["co2_rate"] - rate_base) /
            (rate_max - rate_base)
        ).clip(0,1)
    else:
        df_10["co2_rate_norm"] = 0
            
    df_10["lux_norm"] = normalize(df_10["Light"])
    df_10["pir_norm"] = normalize(df_10["PIR"])

    df_10["occ_index"] = (
        0.5*df_10["pir_norm"] +
        0.2*df_10["co2_rate_norm"] +
        0.3*df_10["lux_norm"]
    )

    return df_10["occ_index"]

selected_offices = [
    "413", "415", "417", "419", "421", "423",
    "418", "422", "424", "426",
    "442", "446", "448", "452", "454", "456", "458", "462"
]

base_path = "KETI"

all_occ = []

for office in selected_offices:
    office_path = os.path.join(base_path, office)

    if os.path.isdir(office_path):
        try:
            occ = process_office(office_path)
            all_occ.append(occ)
            print("Processed:", office)
        except Exception as e:
            print("Error in", office, "->", e)
    else:
        print("Folder missing:", office)
full_index = pd.date_range(
    start="2013-08-23 00:00:00",
    end="2013-08-31 23:50:00",
    freq="10min"
)

aligned = []

for occ in all_occ:
    occ = occ.reindex(full_index)
    occ = occ.fillna(0)
    aligned.append(occ)

floor_occ = pd.concat(aligned, axis=1).mean(axis=1)
schedule_df = floor_occ.to_frame(name="occ")

schedule_df.reset_index(inplace=True)
schedule_df.columns = ["DateTime", "Occupancy"]

schedule_df.to_csv("level4_occ_schedule.csv", index=False)

print("Schedule exported:", len(schedule_df))
floor_occ.index = pd.to_datetime(floor_occ.index)

floor_occ_df = floor_occ.to_frame(name="occ")

floor_occ_df["hour"] = floor_occ_df.index.hour
floor_occ_df["weekday"] = floor_occ_df.index.dayofweek

weekday_profile = (
    floor_occ_df[floor_occ_df["weekday"] < 5]
    .groupby("hour")["occ"]
    .mean()
)

weekend_profile = (
    floor_occ_df[floor_occ_df["weekday"] >= 5]
    .groupby("hour")["occ"]
    .mean()
)
weekday_data = floor_occ_df[floor_occ_df["weekday"] < 5]
print(len(floor_occ_df))
print(len(weekday_data))
weekday_profile = (
    floor_occ_df[floor_occ_df["weekday"] < 5]
    .groupby("hour")["occ"]
    .mean()
)

weekend_profile = (
    floor_occ_df[floor_occ_df["weekday"] >= 5]
    .groupby("hour")["occ"]
    .mean()
)
import matplotlib.pyplot as plt

plt.figure(figsize=(10,4))
weekday_profile.plot(label="Weekday")
weekend_profile.plot(label="Weekend")
plt.legend()
plt.title("Typical Daily Occupancy Profile - Level 4")
plt.ylabel("Occupancy Index")
plt.show()
