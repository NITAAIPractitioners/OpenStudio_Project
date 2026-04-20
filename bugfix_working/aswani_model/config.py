"""
config.py — Aswani Model Experiment Configuration
===================================================
Single source of truth for all paths in this experiment.
Update SQL_PATH when you run a new simulation.
"""

from pathlib import Path

# ─── Root paths ───────────────────────────────────────────────────────────────
EXPERIMENT_DIR  = Path(__file__).parent                     # .../aswani_model/
PROJECT_DIR     = EXPERIMENT_DIR.parent                     # .../OpenStudio_Project/

# ─── Simulation output ────────────────────────────────────────────────────────
# Update this to the latest timestamped run folder after each simulation
RUN_FOLDER      = PROJECT_DIR / "run_aswani_20260416_122137" / "run"
SQL_PATH        = RUN_FOLDER / "eplusout.sql"
IDF_PATH        = RUN_FOLDER / "in.idf"
ERR_PATH        = RUN_FOLDER / "eplusout.err"

# ─── Sensor data ──────────────────────────────────────────────────────────────
KETI_DIR        = PROJECT_DIR / "KETI"
FUSED_DIR       = PROJECT_DIR / "fused_results"

# ─── Outputs ──────────────────────────────────────────────────────────────────
OUTPUT_ROOT     = EXPERIMENT_DIR / "outputs"
OUT_TEMPERATURE = OUTPUT_ROOT / "temperature"
OUT_HUMIDITY    = OUTPUT_ROOT / "humidity"
OUT_CO2         = OUTPUT_ROOT / "co2"
OUT_SCHEDULES   = OUTPUT_ROOT / "schedules"
OUT_LOADS       = OUTPUT_ROOT / "loads"
OUT_SUMMARY     = OUTPUT_ROOT / "summary"

# ─── Naming conventions ───────────────────────────────────────────────────────
# Plots  : aswani_{variable}_{zone}.png      e.g. aswani_temperature_TZ_NW.png
# Metrics: aswani_{variable}_metrics.csv     e.g. aswani_temperature_metrics.csv
# Summary: aswani_validation_summary.csv
EXPERIMENT_TAG  = "aswani"
