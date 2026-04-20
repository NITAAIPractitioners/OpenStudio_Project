import pandas as pd
import numpy as np

# -------------------------------------------------------
# FILE PATHS
# -------------------------------------------------------
noaa_csv = "Oakland_2013_Aug23_31.csv"
tmy_epw = "USA_CA_Oakland.Intl.AP.724930_TMYx.2009-2023.epw"
output_epw = "Oakland_2013_AMY.epw"

# -------------------------------------------------------
# Load NOAA processed data
# -------------------------------------------------------
noaa = pd.read_csv(noaa_csv, parse_dates=["datetime_utc"], index_col="datetime_utc")
noaa.index = noaa.index.tz_localize(None)

# -------------------------------------------------------
# Read EPW file
# -------------------------------------------------------
with open(tmy_epw, "r") as f:
    lines = f.readlines()

header = lines[:8]
data_lines = lines[8:]

# Convert EPW data to dataframe
epw_data = []
for line in data_lines:
    parts = line.strip().split(",")
    epw_data.append(parts)

epw_df = pd.DataFrame(epw_data)
# -------------------------------------------------------
# Replace Aug 23–31 based on Month-Day-Hour (ignore year)
# -------------------------------------------------------

# Ensure numeric types
epw_df[1] = epw_df[1].astype(int)  # Month
epw_df[2] = epw_df[2].astype(int)  # Day
epw_df[3] = epw_df[3].astype(int)  # Hour (1–24)

for _, row in noaa.iterrows():
    dt = row.name   # <-- FIXED

    month = dt.month
    day = dt.day
    hour = dt.hour + 1  # EPW hour format (1–24)

    mask = (
        (epw_df[1] == month) &
        (epw_df[2] == day) &
        (epw_df[3] == hour)
    )

    epw_df.loc[mask, 6] = f"{row['airC']:.1f}"
    epw_df.loc[mask, 7] = f"{row['dewC']:.1f}"





# -------------------------------------------------------
# Write new EPW
# -------------------------------------------------------
with open(output_epw, "w") as f:
    f.writelines(header)
    for _, row in epw_df.iterrows():
        f.write(",".join(row.astype(str)) + "\n")

print("AMY EPW created:", output_epw)