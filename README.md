# SDH Occupancy Sensor Fusion Audit

This repository contains the finalized technical audit dossier for the Sutardja Dai Hall (SDH) occupancy modeling pipeline. It provides the empirical justification and peer-reviewed methodology for the sensor-fused occupancy schedules used in the building energy simulations.

## 📚 Main Documentation

The audit is divided into three primary technical documents:

1.  **[Occupancy Sensor Fusion Justification](occupancy_sensor_fusion_justification.md)**
    *   **Purpose**: The core technical proof for the sensor fusion methodology.
    *   **Key Content**: Derivation of the 20-minute CO₂ lag, office-wide clustering validation (0.55 weight), and ASHRAE vs. Fused performance metrics.

2.  **[Daily Occupancy Explanation](daily_occupancy_explanation.md)**
    *   **Purpose**: Rationalizing the day-to-day variability of human presence.
    *   **Key Content**: Justification for non-repeating schedules and alignment with the KETI empirical dataset.

3.  **[Comprehensive Occupancy Modeling](comprehensive_occupancy_modeling.md)**
    *   **Purpose**: Modular architectural summary.
    *   **Key Content**: Integration logic for EnergyPlus and OpenStudio workflow.

## 🚀 Repository Contents

- `/validation`: Python scripts for RMSE calculation (CO₂, Temperature, Humidity).
- `/scripts`: Automated dossier generation and sensitivity analysis plotting.
- `.gitignore`: Configured to exclude heavy simulation binaries and raw datasets while preserving audit integrity.

---
**Maintained by**: NITAAIPractitioners
**Last Audit Date**: April 2026
