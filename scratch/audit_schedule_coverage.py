"""
Audit: which spaces in the model have fused vs fallback schedules,
and what is the zone-level fused coverage? Cross-reference with RMSE results.
"""
import os, sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

import pandas as pd

# Same space_map as test.py
space_map = {
    "Space_413": "TZ_NW", "Space_415": "TZ_NW",
    "Space_417": "TZ_NW", "Space_419": "TZ_NW",
    "Space_421": "TZ_NW", "Space_423": "TZ_NW",
    "Space_425": "TZ_NE",
    "Space_462": "TZ_E",  "Space_464": "TZ_E",
    "OpenWorkspace": "TZ_C",
    "Space_418": "TZ_C",  "Space_422": "TZ_C",
    "Space_424": "TZ_C",  "Space_426": "TZ_C",
    "Space_434": "TZ_W",  "Space_451": "TZ_W",
    "Space_450": "TZ_W",  "Space_449": "TZ_W",
    "Space_453": "TZ_W",  "Space_448": "TZ_W",  "Space_452": "TZ_W",
    "Space_442": "TZ_S",  "Space_444": "TZ_S",  "Space_446": "TZ_S",
}

FUSED_DIR = "fused_results"

print("=" * 75)
print("SCHEDULE SOURCE AUDIT: Which spaces use FUSED vs FALLBACK schedules")
print("=" * 75)

rows = []
for sname, zone in space_map.items():
    rid = sname.replace("Space_", "")
    fused_file = os.path.join(FUSED_DIR, f"{rid}_fused_data.csv")
    has_fused = os.path.exists(fused_file)
    # Also check if KETI sensor exists for this office
    keti_temp = os.path.join("KETI", rid, "temperature.csv")
    has_keti = os.path.exists(keti_temp)
    rows.append({
        "Space": sname,
        "Zone": zone,
        "Office_ID": rid,
        "Has_Fused_Schedule": "YES" if has_fused else "NO  (Fallback)",
        "Has_KETI_Sensor": "YES" if has_keti else "NO",
    })

df = pd.DataFrame(rows)
print(df.to_string(index=False))

print("\n" + "=" * 75)
print("ZONE-LEVEL FUSED COVERAGE SUMMARY")
print("=" * 75)

summary = []
for zone in sorted(df["Zone"].unique()):
    zdf = df[df["Zone"] == zone]
    total = len(zdf)
    fused = (zdf["Has_Fused_Schedule"] == "YES").sum()
    has_keti = (zdf["Has_KETI_Sensor"] == "YES").sum()
    pct = 100 * fused / total
    summary.append({
        "Zone":           zone,
        "Total_Spaces":   total,
        "Fused_Spaces":   fused,
        "Fallback_Spaces":total - fused,
        "Fused_%":        f"{pct:.0f}%",
        "KETI_Sensors":   has_keti,
    })

sdf = pd.DataFrame(summary)

# Merge with RMSE results
rmse_data = {
    "TZ_C":  {"RMSE_C": 0.6734, "ASHRAE14": "PASS"},
    "TZ_E":  {"RMSE_C": 1.5575, "ASHRAE14": "PASS"},
    "TZ_NE": {"RMSE_C": "N/A",  "ASHRAE14": "N/A"},
    "TZ_NW": {"RMSE_C": 7.1837, "ASHRAE14": "FAIL"},
    "TZ_S":  {"RMSE_C": 0.5187, "ASHRAE14": "PASS"},
    "TZ_W":  {"RMSE_C": 0.6430, "ASHRAE14": "PASS"},
}
sdf["RMSE_C"]   = sdf["Zone"].map(lambda z: rmse_data.get(z, {}).get("RMSE_C", "N/A"))
sdf["ASHRAE14"] = sdf["Zone"].map(lambda z: rmse_data.get(z, {}).get("ASHRAE14", "N/A"))

print(sdf.to_string(index=False))

print("\n" + "=" * 75)
print("KEY FINDING")
print("=" * 75)
print("""
  TZ_NW  -> 100% fused (all 6 offices: 413,415,417,419,421,423) -> RMSE=7.18C FAIL
  TZ_C   -> 40%  fused (422, 424 fused | OpenWorkspace, 418, 426 fallback) -> RMSE=0.67C PASS
  TZ_E   -> 50%  fused (462 fused | 464 fallback)                           -> RMSE=1.56C PASS
  TZ_S   -> 67%  fused (442, 446 fused | 444 fallback)                      -> RMSE=0.52C PASS
  TZ_W   -> 29%  fused (448, 452 fused | 434,449,450,451,453 fallback)      -> RMSE=0.64C PASS
  TZ_NE  -> 0%   fused (425 fallback only, no KETI sensor)                  -> no KETI to compare

  ! TZ_NW is the ONLY fully-fused zone AND it has the highest RMSE.
  ! MBE = -6.58C => simulation is 6.58C COLDER than the measured KETI sensors.
  ! Cause: the NW offices (413-423) run much warmer than the 24C cooling setpoint.
  !        The idealised HVAC (IdealAirLoads) forces the zone to 24C while
  !        the real sensors record 27-32C solar/equipment-driven peaks.
""")
