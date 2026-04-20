import os
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# SETTINGS
# =========================
base_path = "KETI"

selected_offices = [
    "413", "415", "417", "419", "421", "423",
    "418", "422", "424", "426",
    "442", "446", "448", "452", "454", "456", "458", "462"
]

output_root = "raw_sensor_day_plots"
daytime_only = False           # set True if you want only part of the day
day_start = "07:00"
day_end = "19:00"


# =========================
# LOAD ONE SENSOR AS-IS
# =========================
def load_sensor_exact(office_path, file_name, col_name):
    file_path = os.path.join(office_path, file_name)

    df = pd.read_csv(
        file_path,
        header=None,
        names=["timestamp", col_name],
        skipinitialspace=True
    )

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.sort_values("datetime")

    return df[["datetime", col_name]]


# =========================
# FILTER ONE DAY ONLY
# =========================
def filter_one_day(df, date_str):
    day = pd.to_datetime(date_str).date()
    out = df[df["datetime"].dt.date == day].copy()

    if daytime_only and not out.empty:
        out = out.set_index("datetime").between_time(day_start, day_end).reset_index()

    return out


# =========================
# SAVE ONE OFFICE-DAY PLOT
# =========================
def save_raw_day_plot(office_path, office_name, date_str, save_folder):
    try:
        co2_df = load_sensor_exact(office_path, "co2.csv", "CO2")
        pir_df = load_sensor_exact(office_path, "pir.csv", "PIR")
        light_df = load_sensor_exact(office_path, "light.csv", "Light")
    except Exception as e:
        print(f"Could not load files for office {office_name}: {e}")
        return False

    co2_day = filter_one_day(co2_df, date_str)
    pir_day = filter_one_day(pir_df, date_str)
    light_day = filter_one_day(light_df, date_str)

    if co2_day.empty and pir_day.empty and light_day.empty:
        return False

    os.makedirs(save_folder, exist_ok=True)

    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=False)

    # CO2
    if not co2_day.empty:
        axes[0].plot(co2_day["datetime"], co2_day["CO2"], marker="o", markersize=2, linewidth=1)
    axes[0].set_title(f"Office {office_name} - Raw CO2 - {date_str}")
    axes[0].set_ylabel("CO2")
    axes[0].grid(True, alpha=0.3)

    # PIR
    if not pir_day.empty:
        axes[1].plot(pir_day["datetime"], pir_day["PIR"], marker="o", markersize=2, linewidth=1)
    axes[1].set_title(f"Office {office_name} - Raw PIR - {date_str}")
    axes[1].set_ylabel("PIR")
    axes[1].grid(True, alpha=0.3)

    # Light
    if not light_day.empty:
        axes[2].plot(light_day["datetime"], light_day["Light"], marker="o", markersize=2, linewidth=1)
    axes[2].set_title(f"Office {office_name} - Raw Light - {date_str}")
    axes[2].set_ylabel("Light")
    axes[2].set_xlabel("Exact sensor timestamp")
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()

    plot_path = os.path.join(save_folder, f"{office_name}_{date_str}_raw_exact_time.png")
    plt.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close()

    # Save the raw day data too
    if not co2_day.empty:
        co2_day.to_csv(os.path.join(save_folder, f"{office_name}_{date_str}_co2_raw.csv"), index=False)
    if not pir_day.empty:
        pir_day.to_csv(os.path.join(save_folder, f"{office_name}_{date_str}_pir_raw.csv"), index=False)
    if not light_day.empty:
        light_day.to_csv(os.path.join(save_folder, f"{office_name}_{date_str}_light_raw.csv"), index=False)

    return True


# =========================
# GET ALL DAYS AVAILABLE IN AN OFFICE
# =========================
def get_all_days_for_office(office_path):
    days = set()

    sensor_files = [
        ("co2.csv", "CO2"),
        ("pir.csv", "PIR"),
        ("light.csv", "Light")
    ]

    for file_name, col_name in sensor_files:
        file_path = os.path.join(office_path, file_name)
        if os.path.exists(file_path):
            df = load_sensor_exact(office_path, file_name, col_name)
            sensor_days = set(df["datetime"].dt.date.astype(str).unique())
            days.update(sensor_days)

    return sorted(days)


# =========================
# MAIN
# =========================
def main():
    os.makedirs(output_root, exist_ok=True)

    summary = []

    for office in selected_offices:
        office_path = os.path.join(base_path, office)

        if not os.path.isdir(office_path):
            print(f"Missing folder: {office}")
            summary.append([office, "missing_folder", 0])
            continue

        try:
            office_days = get_all_days_for_office(office_path)
            saved_count = 0

            for date_str in office_days:
                save_folder = os.path.join(output_root, office, date_str)
                ok = save_raw_day_plot(office_path, office, date_str, save_folder)

                if ok:
                    saved_count += 1
                    print(f"Saved raw exact-time plot for office {office} on {date_str}")

            summary.append([office, "processed", saved_count])

        except Exception as e:
            print(f"Error in office {office}: {e}")
            summary.append([office, f"error: {e}", 0])

    summary_df = pd.DataFrame(summary, columns=["office", "status", "days_saved"])
    summary_df.to_csv(os.path.join(output_root, "summary.csv"), index=False)

    print("\nFinished.")
    print(f"Summary saved to: {os.path.join(output_root, 'summary.csv')}")


if __name__ == "__main__":
    main()