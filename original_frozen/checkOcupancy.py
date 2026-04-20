import pandas as pd
import matplotlib.pyplot as plt
import os

# =========================
# SETTINGS
# =========================
base_path = "KETI"

selected_offices = [
    "413", "415", "417", "419", "421", "423",
    "418", "422", "424", "426",
    "442", "446", "448", "452", "454", "456", "458", "462"
]

output_root = "office_plots"
daytime_only = True
day_start = "07:00"
day_end = "19:00"

# =========================
# PROCESS ONE OFFICE
# =========================
def process_office_full(office_path):
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

    def normalize(series):
        base = series.quantile(0.1)
        top = series.quantile(0.9)
        if top - base > 0:
            return ((series - base) / (top - base)).clip(0, 1)
        return pd.Series(0, index=series.index)

    df_10["co2_rate"] = df_10["CO2"].diff().clip(-50, 50)

    rate_base = df_10["co2_rate"].quantile(0.1)
    rate_max = df_10["co2_rate"].quantile(0.9)

    if rate_max - rate_base > 0:
        df_10["co2_rate_norm"] = (
            (df_10["co2_rate"] - rate_base) / (rate_max - rate_base)
        ).clip(0, 1)
    else:
        df_10["co2_rate_norm"] = 0

    df_10["lux_norm"] = normalize(df_10["Light"])
    df_10["pir_norm"] = normalize(df_10["PIR"])

    df_10["occ_index"] = (
        0.5 * df_10["pir_norm"] +
        0.2 * df_10["co2_rate_norm"] +
        0.3 * df_10["lux_norm"]
    )

    return df_10


# =========================
# SAVE PLOTS FOR ONE DAY
# =========================
def save_day_plots(df, office_name, date_str, save_folder):
    day = pd.to_datetime(date_str).date()
    day_df = df[df.index.date == day].copy()

    if day_df.empty:
        return False

    if daytime_only:
        day_df = day_df.between_time(day_start, day_end)

    if day_df.empty:
        return False

    os.makedirs(save_folder, exist_ok=True)

    # -------- Raw signals plot --------
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)

    axes[0].plot(day_df.index, day_df["CO2"])
    axes[0].set_title(f"Office {office_name} - CO2 - {date_str}")
    axes[0].set_ylabel("CO2")

    axes[1].plot(day_df.index, day_df["PIR"])
    axes[1].set_title(f"Office {office_name} - PIR - {date_str}")
    axes[1].set_ylabel("PIR")

    axes[2].plot(day_df.index, day_df["Light"])
    axes[2].set_title(f"Office {office_name} - Light - {date_str}")
    axes[2].set_ylabel("Light")

    axes[3].plot(day_df.index, day_df["occ_index"])
    axes[3].set_title(f"Office {office_name} - Occupancy Index - {date_str}")
    axes[3].set_ylabel("Occ Index")
    axes[3].set_xlabel("Time")

    plt.tight_layout()
    raw_path = os.path.join(save_folder, f"{office_name}_{date_str}_raw.png")
    plt.savefig(raw_path, dpi=200, bbox_inches="tight")
    plt.close()

    # -------- Normalized signals plot --------
    plt.figure(figsize=(14, 6))
    plt.plot(day_df.index, day_df["pir_norm"], label="PIR norm")
    plt.plot(day_df.index, day_df["co2_rate_norm"], label="CO2 rate norm")
    plt.plot(day_df.index, day_df["lux_norm"], label="Light norm")
    plt.plot(day_df.index, day_df["occ_index"], label="Occupancy Index", linewidth=2)

    plt.title(f"Office {office_name} - Normalized Signals - {date_str}")
    plt.xlabel("Time")
    plt.ylabel("Normalized value")
    plt.legend()
    plt.tight_layout()

    norm_path = os.path.join(save_folder, f"{office_name}_{date_str}_normalized.png")
    plt.savefig(norm_path, dpi=200, bbox_inches="tight")
    plt.close()

    # -------- Save CSV for that day too --------
    csv_path = os.path.join(save_folder, f"{office_name}_{date_str}_data.csv")
    day_df.to_csv(csv_path)

    return True


# =========================
# MAIN LOOP
# =========================
def main():
    os.makedirs(output_root, exist_ok=True)

    total_saved = 0
    summary_rows = []

    for office in selected_offices:
        office_path = os.path.join(base_path, office)

        if not os.path.isdir(office_path):
            print(f"Folder missing: {office}")
            summary_rows.append([office, "missing_folder", 0])
            continue

        try:
            df = process_office_full(office_path)

            unique_days = sorted(pd.Series(df.index.date).astype(str).unique())
            office_output = os.path.join(output_root, office)

            office_saved = 0
            for date_str in unique_days:
                save_folder = os.path.join(office_output, date_str)
                ok = save_day_plots(df, office, date_str, save_folder)
                if ok:
                    office_saved += 1
                    total_saved += 1
                    print(f"Saved plots for office {office} on {date_str}")

            summary_rows.append([office, "processed", office_saved])

        except Exception as e:
            print(f"Error in office {office} -> {e}")
            summary_rows.append([office, f"error: {e}", 0])

    summary_df = pd.DataFrame(summary_rows, columns=["office", "status", "days_saved"])
    summary_df.to_csv(os.path.join(output_root, "summary.csv"), index=False)

    print("\nDone.")
    print(f"Total office-days saved: {total_saved}")
    print(f"Summary file: {os.path.join(output_root, 'summary.csv')}")


if __name__ == "__main__":
    main()