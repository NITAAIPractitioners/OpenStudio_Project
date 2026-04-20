import pandas as pd
import numpy as np

# File path
file_path = "724930-23230-2013"

# ISD-Lite fixed-width column specs (official NOAA format)
col_widths = [4, 3, 3, 3, 6, 6, 6, 6, 6, 6, 6, 6]

col_names = [
    "year", "month", "day", "hour",
    "air_temp_tenthsC",
    "dew_point_tenthsC",
    "slp",
    "wind_dir",
    "wind_spd",
    "sky",
    "cloud",
    "precip"
]

# Read fixed width file
df = pd.read_fwf(file_path, widths=col_widths, names=col_names)

# Convert temperature fields (tenths °C → °C)
df["airC"] = df["air_temp_tenthsC"].replace(9999, np.nan) / 10.0
df["dewC"] = df["dew_point_tenthsC"].replace(9999, np.nan) / 10.0

# Create datetime index (UTC)
df["datetime_utc"] = pd.to_datetime(
    df[["year", "month", "day", "hour"]],
    utc=True
)

df.set_index("datetime_utc", inplace=True)
df.index = df.index.tz_convert("America/Los_Angeles")
# Keep only Aug 23–31
df = df.loc["2013-08-23":"2013-08-31 23:00"]

print(df[["airC", "dewC"]].head())
print("\nTotal rows:", len(df))
# -------------------------------------------------------
# Convert to Local Time (PDT)
# -------------------------------------------------------
df.index = df.index.tz_convert("America/Los_Angeles")

# -------------------------------------------------------
# Prepare clean dataframe for saving
# -------------------------------------------------------
df_to_save = df[["airC", "dewC"]].copy()

# Move datetime index into column
df_to_save["datetime_utc"] = df_to_save.index

# Reorder columns
df_to_save = df_to_save[["datetime_utc", "airC", "dewC"]]

# Remove timezone info (EPW expects naive local time)
df_to_save["datetime_utc"] = df_to_save["datetime_utc"].dt.tz_localize(None)

# Save CSV
df_to_save.to_csv("Oakland_2013_Aug23_31.csv", index=False)

print("CSV saved successfully.")