# Aswani Model — Experiment Notes

## Experiment Description

**Model name:** `SDH_Level4_Aswani.osm`  
**Simulation period:** August 23–31, 2013  
**Weather file:** Oakland 2013 AMY EPW  
**Run folder:** `run_aswani_20260416_115620/`

This experiment implements a **zone-level VAV abstraction** following Aswani et al. (2012).  
The 21 VAV terminals of SDH Level 4 are aggregated into 6 thermal zones, each controlled by  
a `ZoneHVACIdealLoadsAirSystem` triggered via `setUseIdealAirLoads(True)`.

---

## What Changed vs. Previous Model (NoIdealLoad Baseline)

| Parameter | NoIdealLoad (Baseline) | Aswani Model |
|---|---|---|
| HVAC | Off (free-floating) | Ideal Loads, zone-level |
| Thermostat | Defined, not applied | Applied: 20°C / 24°C |
| SAT Reset | None | Schedule-based (11.1/14.4/16.7°C) |
| CO₂ tracking | Enabled | Enabled (400 ppm outdoor ref) |
| Sizing | Off | Off (Ideal Loads, no autosizing) |
| EMS | None | Planned for Step 2 |

---

## Validation Results Summary

> Fill in after running `run_all_validations.py`

### Temperature

| Zone | RMSE (°C) | MAE (°C) | CV(RMSE) % | ASHRAE Pass (<30%) |
|---|---|---|---|---|
| TZ_NW | — | — | — | — |
| TZ_NE | — | — | — | — |
| TZ_E  | — | — | — | — |
| TZ_C  | — | — | — | — |
| TZ_W  | — | — | — | — |
| TZ_S  | — | — | — | — |

### Humidity

| Zone | RMSE (%) | MAE (%) | CV(RMSE) % | Pass |
|---|---|---|---|---|
| TZ_NW | — | — | — | — |

### CO₂

| Zone | RMSE (ppm) | MAE (ppm) | CV(RMSE) % | Pass |
|---|---|---|---|---|
| TZ_NW | — | — | — | — |

---

## Key Observations

- [ ] Zone temperatures bound between 20–24°C during occupied hours?
- [ ] Ideal Loads visible in `in.idf` as `ZoneHVAC:IdealLoadsAirSystem`?
- [ ] No Severe errors in `eplusout.err`?
- [ ] RMSE improvement vs. NoIdealLoad baseline?

---

## Next Steps

- [ ] **Step 2**: Add EMS SAT reset (11.1/14.4/16.7°C dynamic override)
- [ ] **Step 3**: Enable EMS actuators for all 6 zones
- [ ] **Step 4**: Compare full Aswani + EMS vs. baseline metrics
- [ ] Update this file with final CV(RMSE) values for publication

---

## File Naming Conventions

| Type | Pattern | Example |
|---|---|---|
| Plot | `aswani_{variable}_{zone}.png` | `aswani_temperature_TZ_NW.png` |
| Metrics CSV | `aswani_{variable}_metrics.csv` | `aswani_temperature_metrics.csv` |
| Summary | `aswani_validation_summary.csv` | — |
| Run folder | `run_aswani_{YYYYMMDD_HHMMSS}/` | `run_aswani_20260416_115620/` |
