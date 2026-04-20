# idealLoad_model — Experiment Notes

## Experiment Description
Implementing a unified Ideal Loads model for SDH Level 4 to establish a controlled baseline.

**Current Step:** `[Step 1: Base HVAC Verification]`

## What Changed vs. Previous Version
- Migrated from free-floating (NoIdealLoad) to 6-zone aggregated Ideal Loads.
- Corrected thermostat setpoints from 20-24°C.
- Added explicit CO2 contaminants with 400ppm outdoor ref.

## Validation Results Summary

| Metric | Target | Result | Status |
|--------|--------|--------|--------|
| Temp RMSE | < 2.0°C | — | — |
| CO2 MAE | < 50ppm | — | — |
| Humidity | — | — | — |

## Comparison Summary
- (To be filled after running comparisons)
