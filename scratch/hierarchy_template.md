# Hierarchy of Dominant Error Sources (Zone-Level Evidence)

| Layer | Factor | Sensitivity Shift | $\Delta$ CO2 RMSE (NW) | $\Delta$ Temp RMSE (NW) | Global Consistency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Level 1** | **Occupancy** | Baseline $\rightarrow$ Fused | -73 ppm | -0.33 °C | ✅ Consistently dominant |
| **Level 2** | **Ventilation** | OA $0.005 \rightarrow 0.015$ | -46 ppm | -0.17 °C | 📈 Strongest CO2 control |
| **Level 3** | **Internal Loads** | Density $10 \rightarrow 25$ | -15 ppm | -0.26 °C | 🌡️ Thermal response anchor |
| **Level 4** | **Infiltration** | ACH $0.5 \rightarrow 0.1$ | +14 ppm (Worse) | -0.10 °C (Better) | ⚖️ Air Quality/Thermal Trade-off |
| **Level 5** | **Heat Split**| Sensible $0.55 \rightarrow 0.65$ | [PENDING] | [PENDING] | [PENDING] |

**Notes:**
- **Infiltration** acts as "hidden ventilation". Reducing it improves thermal fit but causes CO2 accumulation.
- **Equipment Schedule** shape (Constant vs Softer) showed significant instability in humidity, reinforcing the choice of a **Scaled Fused** approach.
- **Golden Model (B4)** selection is driven by minimizing CO2 RMSE in the Golden Zone (TZ_NW).
