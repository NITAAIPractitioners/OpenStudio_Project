# SDH Level 4: Parameter Comparison — energy.pdf vs test.py

## Sources
- **energy.pdf** — "Energy Modeling of Sutardja Dai Hall Level 4 Using OpenStudio" (Safaa Khaled Hdaib, Feb 2026)
- **d.pdf** — Zhou, Hu & Tomlin, "Model Comparison of a Data-Driven and a Physical Model for Simulating HVAC Systems" ([arXiv:1603.05951](https://arxiv.org/abs/1603.05951)), referenced as [4] in energy.pdf. This paper is the original source for the 6-zone partitioning of SDH Level 4.

---

## Parameter Comparison

| # | Parameter | energy.pdf Recommended | test.py Current Value | Match? |
|---|-----------|----------------------|----------------------|--------|
| 1 | **Total Floor Area** | ≈1,870 m² | 45.634 × 41 = **1,871 m²** | ✅ Match |
| 2 | **Floor-to-Ceiling Height** | 3.0 m | 3 m | ✅ Match |
| 3 | **Thermal Zones** | 6 polygon zones | **1 single zone** | ❌ **Mismatch** |
| 4 | **Concrete Thickness** | 0.40–0.60 m (heavy slab) | 0.20 m | ⚠️ Low (see note) |
| 5 | **Concrete Density** | (not specified, implied heavyweight) | 2300 kg/m³ | ✅ Reasonable |
| 6 | **Wall Construction** | GFRC + insulation + concrete + gypsum (4 layers) | insulation + concrete (2 layers) | ⚠️ Simplified |
| 7 | **Wall U-value** | ≈0.35 W/m²K | Hardcoded insulation (0.08m, k=0.04) — **not using `wall_u` param** | ❌ **Mismatch** |
| 8 | **Roof U-value** | ≈0.25 W/m²K | Same insulation as wall — **not using `roof_u` param** | ❌ **Mismatch** |
| 9 | **Floor Slab** | Heavy concrete, 0.4–0.6 m equivalent | Concrete only, 0.20 m | ⚠️ Thin |
| 10 | **Window U-factor** | 2.0 W/m²K | 2.5 (passed as param) | ❌ **Mismatch** |
| 11 | **SHGC** | 0.35 | 0.35 | ✅ Match |
| 12 | **WWR** | 0.25–0.35 | 0.40 | ❌ **Too high** |
| 13 | **LPD (Lighting)** | 10–12 W/m² | **26.7 W/m²** | ❌ **~2.5× too high** |
| 14 | **EPD (Equipment)** | 15–25 W/m² | **33.7 W/m²** | ❌ **~1.5× too high** |
| 15 | **Infiltration** | Not specified (ASHRAE ventilation: 10 L/s-person) | 0.5 ACH (param) | ⚠️ No reference |
| 16 | **HVAC System** | VAV with Reheat (ASHRAE System 7) | **Ideal Loads Air System** | ❌ **Mismatch** |
| 17 | **Heating Setpoint** | 20°C | **5°C** (free-floating) | ❌ **Mismatch** |
| 18 | **Cooling Setpoint** | 24°C | **50°C** (free-floating) | ❌ **Mismatch** |
| 19 | **North Axis** | Not specified in PDF | 28° | ⚠️ Unverified |
| 20 | **Building Orientation** | Not specified | 28° | ⚠️ Unverified |

---

## Detailed Analysis of Discrepancies

### 1. Geometry: Single Zone vs 6 Zones
> [!IMPORTANT]
> energy.pdf (following Zhou et al. / d.pdf) specifies **6 thermal zones** (NW, NE, W, E, Center, South). test.py models the entire floor as **one rectangular box**. This is the biggest structural difference.

While a single-zone "super zone" approach is simpler and may be acceptable for initial calibration, it cannot capture the inter-zone temperature differences that the KETI sensors measure across different offices.

### 2. Wall & Roof U-values: Parameters Not Used
> [!WARNING]
> `wall_u` and `roof_u` are passed as function arguments but **never actually used** inside `build_model()`. The insulation layer is hardcoded to 0.08m thickness and 0.04 W/mK conductivity for both walls and roof. The effective U-value of the wall assembly is approximately:
> - Insulation R = 0.08/0.04 = 2.0 m²K/W
> - Concrete R = 0.20/1.7 = 0.12 m²K/W
> - Total R ≈ 2.12 → **U ≈ 0.47 W/m²K** (vs recommended 0.35)

### 3. Window U-factor: 2.5 vs 2.0
The test call passes `glass_u = 2.5`, but energy.pdf recommends **2.0 W/m²K** for the double-pane low-e system in SDH.

### 4. WWR: 0.40 vs 0.25–0.35
test.py uses a 40% window-to-wall ratio, but energy.pdf recommends **25–35%**. This will over-estimate solar heat gain and heat loss through glazing.

### 5. Lighting Power Density: 26.7 vs 10–12 W/m²
> [!CAUTION]
> This is the **largest numerical discrepancy**. test.py uses 26.7 W/m², which is **more than double** the energy.pdf recommendation of 10–12 W/m². The PDF notes that SDH uses WattStopper tri-level dimming controls, meaning actual lighting loads should be even lower than the nameplate LPD.

### 6. Equipment Power Density: 33.7 vs 15–25 W/m²
test.py uses 33.7 W/m², which exceeds the recommended range. Peffer et al. report ~63 kW across all office floors. For one floor of ~1,870 m², that yields roughly **33.7 W/m²** if all 63 kW is on one floor — but the 63 kW figure is spread across **multiple floors (4–7)**, so per-floor EPD should be closer to **15–25 W/m²**.

### 7. HVAC & Thermostats: Free-Floating vs Controlled
test.py sets heating at 5°C and cooling at 50°C to simulate a **free-floating** building. This is intentionally different from the real SDH system (VAV reheat, 20°C heat / 24°C cool). This may be a deliberate choice for calibration (comparing free-float temperatures to measured data), but it does not represent real operational conditions.

---

## Summary of Required Fixes

| Priority | Fix | Action |
|----------|-----|--------|
| 🔴 High | LPD too high | Change from 26.7 → **11 W/m²** |
| 🔴 High | EPD too high | Change from 33.7 → **20 W/m²** |
| 🔴 High | Wall/Roof U not applied | Wire `wall_u` and `roof_u` params to actual insulation thickness calculation |
| 🟡 Medium | Glass U-factor | Change default from 2.5 → **2.0** |
| 🟡 Medium | WWR too high | Change from 0.40 → **0.30** |
| 🟡 Medium | Floor slab too thin | Increase concrete from 0.20m → **0.40m** |
| 🟠 Consider | Single zone | Consider splitting into 6 zones per Zhou et al. |
| 🟠 Consider | HVAC type | Switch from Ideal Loads to VAV Reheat if simulating real operations |
| 🟠 Consider | Thermostats | Set to 20°C/24°C if simulating real operations |
