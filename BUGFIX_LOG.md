# BUGFIX_LOG.md
## SDH Level 4 — Bug Fix Log

**Strategy:** All fixes applied only to `bugfix_working/`. `original_frozen/` is never touched.
Each fix is atomic (one bug at a time), verified to parse cleanly, and confirmed not to exist in `original_frozen/`.

---

## Priority 1 — Infrastructure & Crash Prevention

---

### BUG 8 ✅ FIXED
**Date:** 2026-04-18
**File:** `bugfix_working/aswani_model/validation/validate_temperature.py`
**Lines changed:** 77–81 (before fix) → 77–83 (after fix)

**Bug:** When a zone had zero available KETI temperature sensor files, `measured_series` was an empty list. The `else` branch accessed `measured_series[0]` unconditionally, causing an `IndexError` crash. `validate_humidity.py` had the correct 3-branch guard; `validate_temperature.py` was missing the middle and final branches.

**Change made (minimal):**
```python
# BEFORE
else:
    measured = measured_series[0]

# AFTER
elif len(measured_series) == 1:
    measured = measured_series[0]
else:
    measured = pd.Series()  # BUG8-FIX: graceful empty instead of IndexError
```

**Test performed:** `ast.parse()` confirms valid Python. Verified BUG8-FIX marker present in bugfix copy; absent in original_frozen.

**Impact on metrics/results:** **None.** This is a crash-prevention fix only. No calculation path changed for zones with sensor data. Zones with zero sensor files now gracefully skip instead of crashing the entire script.

**Changes scientific/model results?** No.

---

### BUG 1 ✅ FIXED
**Date:** 2026-04-18
**File:** `bugfix_working/aswani_model/validation/aggregate_performance_matrix.py`
**Lines changed:** 92 (before fix) → 92–96 (after fix)

**Bug:** Two `def main()` functions existed in the same file. Python silently overwrites the first with the second at module load time. The first `main()` (lines 92–154) was dead code — unreachable and never executed. The second `main()` (lines 189–278) was the only one that ran; it includes `--run_id` Track B support and markdown output.

**Change made (minimal):**
Renamed the first block from `def main()` to `def _legacy_main_stub()`. Added a 4-line comment block explaining why. No logic was changed in either block.

**Test performed:**
`ast.parse()` + regex count confirms exactly 1 `def main()` and 1 `def _legacy_main_stub()` in bugfix copy. original_frozen still has 2 `def main()`.

**Impact on metrics/results:** **None.** The second `main()` was already the active one. Renaming the dead first block changes no behavior.

**Changes scientific/model results?** No.

---

### BUG 3 ✅ FIXED
**Date:** 2026-04-18
**File:** `bugfix_working/validation/aggregate_baseline_comparison.py`

**Bug (two issues in one file):**
1. No `main()` function and no `if __name__ == "__main__"` block — running the script did nothing.
2. `output_dir = Path("validation/outputs")` was a relative path from the current working directory, not from the file's location. The script would create outputs in the wrong place when called from any directory other than the project root.

**Changes made (minimal):**
1. Added `_HERE = Path(__file__).resolve().parent` constant for absolute path anchoring.
2. Changed `output_dir = Path("validation/outputs")` → `output_dir = _HERE / "outputs"`.
3. Added a `main()` function with a configurable `runs` list and an informative guard message when the list is empty.
4. Added `if __name__ == "__main__": main()` block.

**Test performed:**
`ast.parse()` confirmed valid Python. Executed the script directly: printed `"[INFO] No run directories configured..."` and exited with RC=0. No crash, no output to wrong directory.

**Impact on metrics/results:** **None.** Script was previously entirely non-functional (did nothing). Now it is callable but only processes runs when the `runs` list is populated. No existing output files are affected.

**Changes scientific/model results?** No.

---

### BUG 11 ✅ FIXED
**Date:** 2026-04-18
**Files changed (6):**
- `bugfix_working/aswani_model/model/test_unified_Aswani.py` line 62
- `bugfix_working/aswani_model/model/test_comparison_ASHRAE_Aswani.py` line 42
- `bugfix_working/idealLoad_model/model/test_unified_IdealLoad.py` line 59
- `bugfix_working/idealLoad_model/model/test_comparison_ASHRAE_IdealLoad.py` line 42
- `bugfix_working/noIdealLoad_model/model/test_unified_NoIdealLoad.py` line 59
- `bugfix_working/noIdealLoad_model/model/test_comparison_ASHRAE_NoIdealLoad.py` line 42

**Bug:** The EPW weather file assignment block used `if EPW_PATH.exists(): ...` with no `else`. If the EPW file was missing (e.g. wrong working directory, mounted drive not connected), the model was silently built and saved without a weather file. EnergyPlus then failed to run, but `subprocess.run(..., check=False)` silently swallowed the failure. The `experiment_config.json` was written as "FAILED" but no exception was raised, and downstream validation scripts would silently fail with "SQL not found".

**Change made (minimal — same in all 6 scripts):**
```python
# BEFORE
if EPW_PATH.exists(): openstudio.model.WeatherFile.setWeatherFile(...)

# AFTER
if EPW_PATH.exists(): openstudio.model.WeatherFile.setWeatherFile(...)
else: raise FileNotFoundError(f"[BUG11-FIX] EPW not found: {EPW_PATH}. Aborting build.")
```

**Test performed:**
All 6 scripts: `ast.parse()` → OK, `BUG11-FIX` marker present in bugfix_working, absent in original_frozen. Confirmed with automated check (all OK: True).

**Impact on metrics/results:** **None.** EPW file exists in the project (`Oakland_2013_AMY.epw`). The `else` branch will only trigger if the file is missing. No existing simulation behavior changes.

**Changes scientific/model results?** No.

---

## Pending — Priority 2 (result-affecting fixes)

- BUG 2: `run_all_validations.py` — missing Not-Ideal, stale IDs, wrong key names
- BUG 12: `aggregate_performance_matrix.py` — hardcoded stale run IDs
- BUG 4: `test_comparison_ASHRAE_Aswani.py` — missing `setSensibleHeatFraction(0.577)` on pp_inst
- BUG 5: Fallback schedule inconsistency between unified and comparison scripts

**⚠️ Awaiting user approval before proceeding to Priority 2.**
These fixes may affect reported validation metrics. Re-runs will be required to compare old vs new results.

---

## Priority 2 — Result-Affecting Fixes

---

### BUG 12 ✅ FIXED
**Date:** 2026-04-18
**File:** `bugfix_working/aswani_model/validation/aggregate_performance_matrix.py`
**Lines changed:** 13–20

**Bug:** The `MODELS` dict hardcoded three specific historical run timestamps:
- `"Aswani-VAV": run_20260417_181516`
- `"Ideal": run_20260417_174456`
- `"Not-Ideal": run_20260417_174813`

Any new simulation run would silently produce results from the old vault unless these strings were manually updated.

**Change made:**
Added `find_latest_run(model_root)` helper (sorts candidate dirs by `stat().st_mtime`, returns the name of the most-recently-modified). MODELS dict entries no longer contain a `"run"` key statically; it is populated at startup by the helper. The resolved run is printed to stdout so the user can see which run was selected.

**Test performed:** Dry-ran resolution logic; confirmed:
- `Aswani-VAV` → `fused_eq20.0_oa0.01_inf0.5_20260417_215432` (sql_exists=True)
- `Ideal` → `fused_eq20.0_oa0.01_inf0.5_20260417_215527` (sql_exists=True)
- `Not-Ideal` → `fused_eq20.0_oa0.01_inf0.5_20260417_221254` (sql_exists=True)

**Impact on metrics/results:** ⚠️ **May change reported results.** The previously hardcoded runs may differ from the latest runs. This is intentional and correct — after any new simulation the aggregator will now automatically use those new results.

**Changes scientific/model results?** Yes — if new simulations have been run since the hardcoded dates, the reported RMSE/MAE values will differ. This is the desired behavior.

---

### BUG 2 ✅ FIXED
**Date:** 2026-04-18
**File:** `bugfix_working/aswani_model/run_all_validations.py`

**Bug (three issues):**
1. `Not-Ideal` model completely missing from MODELS dict — three-way comparison was impossible
2. Key names `"Ideal_Loads"` and `"VAV_Reheat"` did not match `aggregate_performance_matrix.py` canonical names `"Ideal"` and `"Aswani-VAV"` — output CSVs would be saved to wrong paths
3. Hardcoded run IDs that would become stale after any new simulation
4. `VAL_SQL_PATH` was not set, causing `shared_validation.py` to search the wrong vault for Ideal and Not-Ideal models

**Change made:**
- Added `Not-Ideal` model with its own `model_root`
- Renamed keys to canonical `"Aswani-VAV"`, `"Ideal"`, `"Not-Ideal"`
- Replaced hardcoded run IDs with `find_latest_run(model_root)` helper (same logic as BUG 12 fix)
- Added `VAL_SQL_PATH` to the environment per-model so each model's own vault SQL is used
- Added early-exit guards when run dir or SQL is missing

**Test performed:** Parse OK; confirmed all 3 canonical names present; confirmed all stale IDs absent; confirmed original_frozen unchanged.

**Impact on metrics/results:** ⚠️ **Changes coverage of comparison.** Previously: 2 models, stale runs. Now: 3 models, latest runs. This corrects the comparison rather than distorting it.

**Changes scientific/model results?** Yes — adds the previously-missing Not-Ideal model to the validation output.

---

### BUG 4 ✅ FIXED
**Date:** 2026-04-18
**File:** `bugfix_working/aswani_model/model/test_comparison_ASHRAE_Aswani.py`
**Line changed:** 175

**Bug:** `pp_inst.setSensibleHeatFraction(0.577)` was missing from the per-space `PeopleDefinition` object in the Aswani comparison script. All other 5 scripts call this method. Without it, EnergyPlus uses its internal default of 0.5, meaning Aswani comparison runs had a different sensible/latent metabolic split than Ideal and Not-Ideal comparison runs.

**Change made (one line):**
```python
# BEFORE
pp_inst.setName(f"PeopleDef_{sname}"); pp_inst.setNumberofPeople(peak_cap)

# AFTER
pp_inst.setName(f"PeopleDef_{sname}"); pp_inst.setNumberofPeople(peak_cap); pp_inst.setSensibleHeatFraction(0.577)  # BUG4-FIX
```

**Test performed:** Parse OK; BUG4-FIX marker present; original_frozen untouched; old pattern without fraction confirmed gone.

**Impact on metrics/results:** ⚠️ **Will change simulation output on next run.** Sensible heat from people increases from EnergyPlus default (0.5) to calibrated value (0.577). This will slightly raise zone temperatures and reduce latent load in Aswani comparison runs, making the thermal balance consistent with Ideal and Not-Ideal runs. **A re-run of the Aswani comparison scripts is required to see the corrected metrics.**

**Changes scientific/model results?** Yes — sensible heat fraction changes from 0.5 → 0.577 in Aswani comparison runs only. Unified Aswani script already had 0.577 and is unaffected.

---

### BUG 5 ✅ FIXED
**Date:** 2026-04-18
**Files changed (3):**
- `bugfix_working/aswani_model/model/test_comparison_ASHRAE_Aswani.py`
- `bugfix_working/idealLoad_model/model/test_comparison_ASHRAE_IdealLoad.py`
- `bugfix_working/noIdealLoad_model/model/test_comparison_ASHRAE_NoIdealLoad.py`

**Bug:** When `schedule_mode=fused` was requested, spaces without a KETI fused CSV fell back to `(sch_ashrae, sch_ashrae)` — the full ASHRAE block schedule (weekend value = 0.1). The unified scripts for the same models fell back to `(sch_fb_occ, sch_fb_gn)` — softer schedules with weekend value = 0.05. This created an asymmetry: 11 un-instrumented spaces used 0.1 weekend occupancy in comparison runs but 0.05 in unified runs, making cross-comparison of results misleading.

**Change made (per script):**
1. Added two new schedule objects after `sch_ashrae`:
```python
sch_fb_occ = create_sch(model, "Occ_FB",  [...], 0.05)
sch_fb_gn  = create_sch(model, "Gain_FB", [...], 0.05)
```
2. Changed fused `else` branch fallback from `(sch_ashrae, sch_ashrae)` to `(sch_fb_occ, sch_fb_gn)`.
The `ashrae` mode branch is unchanged: when `schedule_mode=ashrae`, all 24 spaces still use `sch_ashrae`.

**Test performed:** Parse OK on all 3 scripts; `BUG5-FIX` marker confirmed in all 3; `sch_fb_occ, sch_fb_gn)  # BUG5-FIX` present in fused else-branch of all 3; original_frozen confirmed untouched.

**Impact on metrics/results:** ⚠️ **Will change simulation output for fused-mode comparison runs.** The 11 fallback spaces will have lower weekend internal gains (0.05 vs 0.1 fraction). For Aug 23–31 (which contains weekends), this will reduce predicted temperature and CO2 in zones with fallback spaces on weekends. The effect is small but real. **A re-run of all three comparison scripts with `--schedule_mode fused` is required to see corrected results.**

**Changes scientific/model results?** Yes — applies only to `fused` comparison runs, only affects 11 un-instrumented spaces, only on weekends. ASHRAE-mode runs are completely unaffected.

---

## Pending — Priority 3 (robustness/cleanup)

BUG 9, 10, 13, 14, 15, 6, 7 — awaiting user confirmation.


---

## Pending — Priority 3 (robustness/cleanup)

BUG 9, 10, 13, 14, 15, 6, 7 — awaiting Priority 2 completion.
