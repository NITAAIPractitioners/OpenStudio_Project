"""
shared_validation.py
====================
All shared logic for validating EnergyPlus/OpenStudio simulation outputs
against KETI measured sensor data (Aug 23–31, 2013).

Project layout (one shared file + per-variable main files):
    shared_validation.py      ← this file
    validate_temperature.py
    validate_humidity.py
    validate_co2.py
    validate_pir.py
    validate_lighting.py
    outputs/temperature/
    outputs/humidity/
    outputs/co2/
    outputs/pir/
    outputs/lighting/

IMPORTANT:
  - The simulation already runs Aug 23–31 2013. Do NOT re-filter by date range here.
  - Only align on overlapping timestamps (inner join).
  - Do NOT resample unless necessary.
  - Preserve original sensor timestamps where possible.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import json
import matplotlib
matplotlib.use("Agg")          # non-interactive backend (safe on Windows)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ─── 1. Configuration ────────────────────────────────────────────────────────

# Absolute paths – all derived from this file's location
from pathlib import Path
_HERE = Path(__file__).parent
EXPERIMENT_ROOT = _HERE.parent
PROJECT_ROOT = EXPERIMENT_ROOT.parent

OUTPUT_ROOT = os.environ.get("VAL_OUT_DIR", str(_HERE / "outputs"))
KETI_DIR = os.environ.get("VAL_KETI_DIR", str(PROJECT_ROOT / "KETI"))
FUSED_DIR = os.environ.get("VAL_FUSED_DIR", str(PROJECT_ROOT / "fused_results"))

# Sensor resampling frequency for raw KETI data
SENSOR_FREQ = "10min"

# ─── 2. Space → Zone mapping ─────────────────────────────────────────────────
# Derived from eplusout.eio (People Internal Gains Nominal section).
# Only offices that have a dedicated fused schedule (F_OCC_xxx) are included
# as "fused" spaces; the fallback OCC_FB spaces are excluded here.
#
# Format: { office_id (str) : EnergyPlus zone name (str) }

SPACE_ZONE_MAP = {
    "413": "TZ_NW",
    "415": "TZ_NW",
    "417": "TZ_NW",
    "419": "TZ_NW",
    "421": "TZ_NW",
    "423": "TZ_NW",
    "442": "TZ_S",
    "446": "TZ_S",
    "448": "TZ_W",
    "452": "TZ_W",
    "462": "TZ_E",
    "422": "TZ_C",
    "424": "TZ_C",
}

# All unique zones that have at least one fused office
FUSED_ZONES = sorted(set(SPACE_ZONE_MAP.values()))

# ─── 3. Output directory helpers ─────────────────────────────────────────────

def get_output_dir(variable: str) -> str:
    """Return (and create) the output subdirectory for a given variable."""
    path = os.path.join(OUTPUT_ROOT, variable)
    os.makedirs(path, exist_ok=True)
    return path


# ─── 4. Load measured (KETI) sensor data ─────────────────────────────────────

def load_keti_sensor(office: str, sensor: str, freq: str = SENSOR_FREQ) -> pd.Series | None:
    """
    Load a raw KETI sensor CSV for a given office and sensor type.

    Parameters
    ----------
    office : str   e.g. "413"
    sensor : str   one of "temperature", "humidity", "co2", "pir", "light"
    freq   : str   pandas offset alias for resampling (default "10min")

    Returns
    -------
    pd.Series with DatetimeIndex (UTC→local handled as naive, already 2013),
    or None if file missing / unreadable.

    Raw files have no header: [unix_timestamp, value]
    """
    path = os.path.join(KETI_DIR, office, f"{sensor}.csv")
    if not os.path.exists(path):
        print(f"[WARN] Sensor file not found: {path}")
        return None
    try:
        df = pd.read_csv(
            path,
            header=None,
            names=["timestamp", "value"],
            skipinitialspace=True,
            on_bad_lines="skip",
        )
        # Coerce to numeric
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df = df.dropna()

        # Convert unix → datetime (UTC-8 = Oakland local time, stored naive)
        df["dt"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df["dt"] = df["dt"].dt.tz_convert("US/Pacific").dt.tz_localize(None)
        df = df.set_index("dt").sort_index()

        # Sanity check: Remove physical outliers that skew resampling
        # (e.g. sensor glitches reporting 500C or negative values)
        if sensor == "temperature":
            df = df[(df["value"] > 5) & (df["value"] < 50)]
        elif sensor == "humidity":
            df = df[(df["value"] >= 0) & (df["value"] <= 100)]
        elif sensor == "co2":
            df = df[(df["value"] > 300) & (df["value"] < 5000)]

        df = df[~df.index.duplicated(keep="first")]

        # Resample to uniform grid
        series = df["value"].resample(freq).mean()
        return series
    except Exception as exc:
        print(f"[ERROR] Loading {office}/{sensor}: {exc}")
        return None


# ─── 5. Load simulation output from SQL ──────────────────────────────────────

def get_sql_path():
    """Dynamically resolve the SQL path from environment or experiment_config.json."""
    env_path = os.environ.get("VAL_SQL_PATH")
    if env_path:
        return env_path
    
    config_path = EXPERIMENT_ROOT / "experiment_config.json"
    run_dir = os.environ.get("VAL_RUN_DIR")
    
    if not run_dir and config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            run_dir = config.get("latest_run_dir")
        except Exception:
            pass
            
    if run_dir:
        # Vault path: model/runs/run_xxx/run/eplusout.sql
        vault_path = EXPERIMENT_ROOT / "model" / "runs" / run_dir / "run" / "eplusout.sql"
        if vault_path.exists():
            return str(vault_path)
            
    # Fallback to static run dir
    return str(EXPERIMENT_ROOT / "model" / "run" / "eplusout.sql")

def load_simulation_variable(variable_name: str, zone_name: str) -> pd.Series | None:
    """
    Pull a hourly zone-level variable from the EnergyPlus SQLite output.

    Parameters
    ----------
    variable_name : str   EnergyPlus output variable name, e.g.
                          "Zone Air Temperature"
    zone_name     : str   EnergyPlus zone name, e.g. "TZ_NW"

    Returns
    -------
    pd.Series with DatetimeIndex (naive, local time), or None on error.

    EnergyPlus stores times as: Month, Day, Hour, Minute.
    The simulation year is 2013 (calibration year).
    """
    sql_path = get_sql_path()
    if not os.path.exists(sql_path):
        print(f"[ERROR] SQL file not found: {sql_path}")
        return None
    try:
        conn = sqlite3.connect(sql_path)

        # Look up the ReportDataDictionaryIndex for the requested variable+zone
        query_idx = """
            SELECT ReportDataDictionaryIndex
            FROM ReportDataDictionary
            WHERE KeyValue = ?
              AND Name = ?
            LIMIT 1
        """
        idx_df = pd.read_sql_query(query_idx, conn, params=(zone_name.upper(), variable_name))
        if idx_df.empty:
            print(f"[WARN] Variable '{variable_name}' for zone '{zone_name}' not found in SQL.")
            conn.close()
            return None

        rdd_idx = int(idx_df.iloc[0, 0])

        # Pull time + value
        query_data = """
            SELECT t.Month, t.Day, t.Hour, t.Minute, rd.Value
            FROM ReportData rd
            JOIN Time t ON rd.TimeIndex = t.TimeIndex
            WHERE rd.ReportDataDictionaryIndex = ?
            ORDER BY t.TimeIndex
        """
        df = pd.read_sql_query(query_data, conn, params=(rdd_idx,))
        conn.close()

        if df.empty:
            print(f"[WARN] No data returned for '{variable_name}' / '{zone_name}'.")
            return None

        # Build datetime: EnergyPlus Hour is 1-24. Hour=24 means end of day.
        # Pandas-friendly: subtract 1 hour from Hour=24.
        df["Year"] = 2013
        # EnergyPlus Hour 1..24; Minute 0..50 (for 10-min steps) or 0 (hourly)
        # Convert Hour=24 to next-day Hour=0
        df["Hour_adj"] = df["Hour"].clip(upper=23)
        day_overflow = (df["Hour"] == 24).astype(int)

        df["dt"] = pd.to_datetime(
            df[["Year", "Month", "Day", "Hour_adj"]]
            .rename(columns={"Hour_adj": "hour", "Month": "month", "Day": "day", "Year": "year"}),
            errors="coerce",
        ) + pd.to_timedelta(df["Minute"], unit="m") + pd.to_timedelta(day_overflow, unit="D")

        df = df.dropna(subset=["dt"])
        series = df.set_index("dt")["Value"]
        series = series[~series.index.duplicated(keep="first")].sort_index()
        return series

    except Exception as exc:
        print(f"[ERROR] Reading SQL for '{variable_name}' / '{zone_name}': {exc}")
        return None


# ─── 6. Timestamp alignment (inner join on overlapping timestamps) ────────────

def align_series(measured: pd.Series, simulated: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Align two time series on their overlapping timestamps using an inner join.

    - Measured data may be at 10-min resolution.
    - Simulated data is at hourly resolution (EnergyPlus default output).
    - We resample the measured data to hourly means so they share the same
      index before merging, then inner-join on that index.

    Returns
    -------
    (measured_aligned, simulated_aligned) – two Series with identical index,
    NaNs dropped.
    """
    # Resample measured to hourly to match simulation timestep
    meas_hourly = measured.resample("1h").mean()

    merged = pd.concat(
        {"measured": meas_hourly, "simulated": simulated},
        axis=1,
    ).dropna()

    return merged["measured"], merged["simulated"]


# ─── 7. RMSE ─────────────────────────────────────────────────────────────────

def compute_rmse(measured: pd.Series, simulated: pd.Series) -> float:
    """Compute Root Mean Squared Error between two aligned Series."""
    diff = measured.values - simulated.values
    return float(np.sqrt(np.mean(diff ** 2)))


def compute_mae(measured: pd.Series, simulated: pd.Series) -> float:
    """Compute Mean Absolute Error."""
    return float(np.mean(np.abs(measured.values - simulated.values)))


def compute_cv_rmse(measured: pd.Series, simulated: pd.Series) -> float:
    """Coefficient of Variation of RMSE (CV(RMSE)) in %."""
    rmse = compute_rmse(measured, simulated)
    mean_meas = float(np.mean(measured.values))
    if mean_meas == 0:
        return float("nan")
    return 100.0 * rmse / mean_meas


# ─── 8. Reusable plotting helper ─────────────────────────────────────────────

def plot_comparison(
    measured: pd.Series,
    simulated: pd.Series,
    title: str,
    ylabel: str,
    output_path: str,
    rmse: float | None = None,
    unit: str = "",
) -> None:
    """
    Plot measured vs simulated time series and save to file.

    Parameters
    ----------
    measured      : aligned measured Series
    simulated     : aligned simulated Series
    title         : plot title
    ylabel        : y-axis label
    output_path   : full path to save the PNG
    rmse          : if provided, shown in legend/annotation
    unit          : physical unit string (e.g. "°C", "%RH")
    """
    fig, ax = plt.subplots(figsize=(12, 4), dpi=120)

    ax.plot(measured.index, measured.values,
            color="#2196F3", linewidth=1.2, label="Measured (KETI)", alpha=0.85)
    ax.plot(simulated.index, simulated.values,
            color="#F44336", linewidth=1.2, linestyle="--", label="Simulated (EnergyPlus)", alpha=0.85)

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel(f"{ylabel} [{unit}]" if unit else ylabel, fontsize=11)
    ax.set_xlabel("Date / Time", fontsize=11)

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")

    legend_label = "Simulated (EnergyPlus)"
    if rmse is not None:
        legend_label += f"  |  RMSE = {rmse:.3f} {unit}"
    # Re-draw legend with RMSE info
    handles, labels = ax.get_legend_handles_labels()
    labels[1] = legend_label
    ax.legend(handles, labels, fontsize=9, loc="upper right")

    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"  [PLOT] Saved -> {output_path}")


# ─── 9. Metric saving helper ─────────────────────────────────────────────────

def save_metrics(metrics: dict, output_path: str) -> None:
    """
    Save a flat dict of metrics to a CSV file.

    Parameters
    ----------
    metrics     : {metric_name: value, ...}
    output_path : full path for the CSV
    """
    df = pd.DataFrame([metrics])
    df.to_csv(output_path, index=False)
    print(f"  [METRICS] Saved → {output_path}")


# ─── 10. Standalone test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("shared_validation.py - STEP 1 SELF-TEST")
    print("=" * 60)

    # -- Test 1: load a measured file --
    print("\n[TEST 1] Loading KETI temperature for office 413 ...")
    temp_413 = load_keti_sensor("413", "temperature")
    if temp_413 is not None:
        print(f"  OK - {len(temp_413)} rows")
        print(f"  Range: {temp_413.index[0]} to {temp_413.index[-1]}")
        print(f"  Sample values:\n{temp_413.head(5)}")
    else:
        print("  FAILED - could not load sensor data")

    # -- Test 2: load simulation temperature for TZ_NW --
    print("\n[TEST 2] Loading simulated Zone Air Temperature for TZ_NW ...")
    sim_temp = load_simulation_variable("Zone Air Temperature", "TZ_NW")
    if sim_temp is not None:
        print(f"  OK - {len(sim_temp)} rows")
        print(f"  Range: {sim_temp.index[0]} to {sim_temp.index[-1]}")
        print(f"  Sample values:\n{sim_temp.head(5)}")
    else:
        print("  FAILED - could not load simulation data")

    # -- Test 3: align --
    if temp_413 is not None and sim_temp is not None:
        print("\n[TEST 3] Aligning measured and simulated ...")
        meas_al, sim_al = align_series(temp_413, sim_temp)
        print(f"  OK - {len(meas_al)} overlapping hourly timestamps")
        merged = pd.DataFrame({"measured": meas_al, "simulated": sim_al})
        print(f"\n  Sample merged rows:\n{merged.head(8).to_string()}")

        rmse = compute_rmse(meas_al, sim_al)
        mae  = compute_mae(meas_al, sim_al)
        cvrmse = compute_cv_rmse(meas_al, sim_al)
        print(f"\n  RMSE     = {rmse:.4f} deg C")
        print(f"  MAE      = {mae:.4f} deg C")
        print(f"  CV(RMSE) = {cvrmse:.2f} %")
    else:
        print("\n[TEST 3] Skipped - missing data from tests 1 or 2.")

    print("\n[DONE] Step 1 self-test complete.\n")
