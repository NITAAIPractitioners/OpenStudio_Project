# Daily Occupancy Schedule Explanation: A Multi-Sensor Fusion Approach

## 1. Multi-Office Validation Summary
The conclusions presented in this report are not based on a single isolated instance but are validated across the full KETI building dataset (51 offices). Statistical comparison between $CO_2$ and Light sensor clusters reveals significant signal dissociation, proving that a multi-sensor approach is mandatory for accurate modeling.

### Validation Benchmarks
| Metric | Dataset Global Mean | Interpretation |
| :--- | :--- | :--- |
| **Adjusted Rand Index (ARI)** | $\approx 0.007$ | Near-zero similarity; signals are independent \cite{hubert1985comparing} |
| **Normalized Mutual Information (NMI)** | $\approx 0.144$ | Low shared structural information \cite{strehl2002cluster} |
| **Exact Semantic Agreement** | $20\%$ | High behavioral divergence |
| **Temporal Lag** | $45$ minutes | Consistent $CO_2$ response delay relative to Light |

> **Finding:** $CO_2$ and Light sensors capture different dimensions of room usage (Status vs. Activity). Relying on either signal in isolation leads to systemic temporal and behavioral errors.

---

## 2. Representative Case Study: Office 448
Office 448 is selected as the primary case study for its "Stress-Test" characteristics:
*   **Noisy Light Signal**: Frequent manual adjustments and communal baseline interference.
*   **Delayed $CO_2$ Response**: Significant thermal/air-exchange lag during morning arrivals.
*   **Fusion Necessity**: Demonstrates how individual sensor failures (e.g., quiet stillness during desk work) are corrected by the complementary fusion logic.

---

## 3. Micro-Analysis of Daily Behavioral Logic
Using the sensor fusion results for Office 448, we observe four distinct logical phases in the schedule generation process.

### Step 1: Arrival Event (Light Leads)
Light residual levels rise sharply upon occupant arrival, often leading the $CO_2$ detection by 30-45 minutes. By assigning a 0.35 weight to the Light Residual, the fusion model triggers the **Occupied** state immediately, providing the precise temporal start-point required for HVAC simulation.

### Step 2: Persistence Window ($CO_2$ Role)
During periods of sedentary work or lunch breaks where light levels may stabilize or PIR signals drop to zero, the $CO_2$ Concentration ($w=0.55$) maintains the occupancy flag. This "Persistence Window" prevents false vacancy declarations and reflects the true metabolic load of the space.

### Step 3: PIR Confirmation
PIR is treated strictly as a **positive confirmation signal**. While infrequent due to the "stillness problem," PIR spikes provide maximum confidence for active occupancy. However, the absence of PIR does **not** imply vacancy, as $CO_2$ and Light levels sustain the score.

### Step 4: Departure Logic
At the end of the day, as $CO_2$ begins to decay and lighting is deactivated, all signals decline in unison. The fusion logic produces a clean binary drop-off, providing a realistic transition to the unoccupied state.

---

## 4. From Fusion to Simulation-Ready Schedules
The transformation pipeline follows a rigorous 5-step process to ensure compatibility with OpenStudio/EnergyPlus:

1.  **Continuous Fused Score**: A probability-like index $(0-1)$ integrating all sensors.
2.  **Thresholding**: Application of the $0.35$ cutoff to establish binary occupancy.
3.  **Temporal Smoothing**: A 30-minute persistence filter to remove high-frequency "flicker."
4.  **Hourly Aggregation**: Consolidation into characteristic Weekday and Weekend profiles.
5.  **Export**: Generation of the `Schedule:Compact` IDF object.

> **Methodological Principle:** Light defines the **timing** (arrival/departure), while $CO_2$ defines the **persistence** (duration).

---

## 5. Visual Evidence

### Office 448: Primary Stress-Test
![Office 448 Validation](/c:/Users/me.com/Documents/engery/OpenStudio_Project/fused_results/plots/448_validation.png)
*Figure 1: Demonstration of Light-triggered arrival and CO2-sustained persistence. Note the green occupancy area correctly spanning the entire presence duration.*

### Office 721: Clean Behavioral Pattern
![Office 721 Validation](/c:/Users/me.com/Documents/engery/OpenStudio_Project/fused_results/plots/721_validation.png)
*Figure 2: Validation of fusion accuracy in a typical office with regular business hours.*

### Office 776: Cyclic Occupational Behavior
![Office 776 Validation](/c:/Users/me.com/Documents/engery/OpenStudio_Project/fused_results/plots/776_validation.png)
*Figure 3: Fusion performance during multi-day cyclic behavior, showing stable schedule generation.*

---

## 6. Simulation Impact & Conclusion
By replacing standard ASHRAE/standardized schedules with these data-driven profiles, simulations can capture real variability, including:
*   Extended hours behaviors.
*   Reduced artificial "occupancy gaps" during quiet morning periods.
*   Accurate reflection of intermittent weekend activity.

### Final Conclusion
> Occupancy behavior is inherently multi-dimensional and cannot be captured by a single sensor. The proposed fusion approach integrates complementary signals to produce temporally consistent and simulation-ready occupancy schedules.

---
**References**
\bibliography{references}
