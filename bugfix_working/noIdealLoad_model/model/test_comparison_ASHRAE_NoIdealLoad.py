import os
import pandas as pd
from datetime import datetime
from pathlib import Path
import openstudio
import logging
import subprocess
import json
import shutil
import argparse

# --- PARAMETER INJECTION (For Comparison Experiments) ---
parser = argparse.ArgumentParser(description='NoIdealLoad Model Comparison Run.')
parser.add_argument('--schedule_mode', type=str, default='fused', choices=['fused', 'ashrae'], help='Schedule strategy')
parser.add_argument('--eq_density', type=float, default=20.0, help='Equipment Density [W/m2]')
# BUG13-FIX: added --eq_sch_type to match Aswani comparison arg interface.
# NoIdealLoad always uses the 'Scaled' strategy but accepting the argument prevents
# argparse rejection if an orchestrator passes --eq_sch_type uniformly to all three models.
parser.add_argument('--eq_sch_type', type=str, default='Scaled', choices=['Scaled', 'Constant', 'Softer'], help='Equipment Schedule Strategy (always Scaled for NoIdealLoad)')
parser.add_argument('--oa_rate', type=float, default=0.010, help='Outdoor Air Rate per Person [m3/s/p]')
parser.add_argument('--infiltration', type=float, default=0.5, help='Infiltration rate [ACH]')
parser.add_argument('--stage', type=str, default='Comp', help='Experiment Stage ID')
args = parser.parse_args()

logger = logging.getLogger("sdh_noidealload_comparison")
logging.basicConfig(level=logging.INFO)
logger.info(f"Initializing NoIdealLoad Comparison Run: Mode={args.schedule_mode}, Eq={args.eq_density}")

# --- PATH CONFIGURATION ---
MODEL_SCRIPT_DIR = Path(__file__).parent
EXPERIMENT_ROOT = MODEL_SCRIPT_DIR.parent
PROJECT_ROOT = EXPERIMENT_ROOT.parent
RUNS_DIR = MODEL_SCRIPT_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

# =========================================================================================
# UNIT 1: SIMULATION SETUP
# =========================================================================================
model = openstudio.model.Model()
building = model.getBuilding(); building.setName("SDH_Level4_NoIdealLoad_Comp"); building.setNorthAxis(28)
yd = model.getYearDescription(); yd.setCalendarYear(2013)
run_period = model.getRunPeriod(); run_period.setBeginMonth(8); run_period.setBeginDayOfMonth(23); run_period.setEndMonth(8); run_period.setEndDayOfMonth(31)

EPW_PATH = PROJECT_ROOT / "Oakland_2013_AMY.epw"
if EPW_PATH.exists(): openstudio.model.WeatherFile.setWeatherFile(model, openstudio.EpwFile(openstudio.path(str(EPW_PATH))))
else: raise FileNotFoundError(f"[BUG11-FIX] EPW not found: {EPW_PATH}. Aborting build.")

# =========================================================================================
# UNIT 2: PHYSICAL ENVELOPE
# =========================================================================================
gfrc = openstudio.model.StandardOpaqueMaterial(model, "MediumSmooth", 0.0254); gfrc.setThermalConductivity(0.5); gfrc.setDensity(2100); gfrc.setSpecificHeat(840); gfrc.setSolarAbsorptance(0.7)
insul = openstudio.model.StandardOpaqueMaterial(model, "MediumSmooth", 0.100); insul.setThermalConductivity(0.04); insul.setDensity(40); insul.setSpecificHeat(1210)
conc = openstudio.model.StandardOpaqueMaterial(model, "MediumSmooth", 0.200); conc.setThermalConductivity(1.7); conc.setDensity(2300); conc.setSpecificHeat(880)
gyp = openstudio.model.StandardOpaqueMaterial(model, "MediumSmooth", 0.0127); gyp.setThermalConductivity(0.16); gyp.setDensity(800); gyp.setSpecificHeat(1090)
slab_conc = openstudio.model.StandardOpaqueMaterial(model, "MediumSmooth", 0.400); slab_conc.setThermalConductivity(1.7); slab_conc.setDensity(2300); slab_conc.setSpecificHeat(880)

ext_wall = openstudio.model.Construction(model); [ext_wall.insertLayer(i, m) for i, m in enumerate([gfrc, insul, conc, gyp])]
glass_mat = openstudio.model.SimpleGlazing(model); glass_mat.setSolarHeatGainCoefficient(0.35); glass_mat.setUFactor(2.0)
glazing_const = openstudio.model.Construction(model); glazing_const.insertLayer(0, glass_mat)
slab_const = openstudio.model.Construction(model); slab_const.insertLayer(0, slab_conc)

def_set = openstudio.model.DefaultConstructionSet(model)
ext_surfs = openstudio.model.DefaultSurfaceConstructions(model); ext_surfs.setWallConstruction(ext_wall); ext_surfs.setRoofCeilingConstruction(slab_const)
def_set.setDefaultExteriorSurfaceConstructions(ext_surfs)
ext_sub_surfs = openstudio.model.DefaultSubSurfaceConstructions(model); ext_sub_surfs.setFixedWindowConstruction(glazing_const)
def_set.setDefaultExteriorSubSurfaceConstructions(ext_sub_surfs)
building.setDefaultConstructionSet(def_set)

# =========================================================================================
# UNIT 3: GEOMETRY
# =========================================================================================
space_map = {
    "Space_413": (0.0, 24.0, 3.5, 4.0, "TZ_NW"), "Space_415": (3.5, 24.0, 3.5, 4.0, "TZ_NW"),
    "Space_417": (7.0, 24.0, 3.5, 4.0, "TZ_NW"), "Space_419": (10.5, 24.0, 3.5, 4.0, "TZ_NW"),
    "Space_421": (14.0, 24.0, 3.5, 4.0, "TZ_NW"), "Space_423": (17.5, 24.0, 3.5, 4.0, "TZ_NW"),
    "Space_425": (21.0, 24.0, 3.5, 4.0, "TZ_NE"), "Space_462": (26.0, 24.0, 3.5, 4.0, "TZ_E"),
    "Space_464": (29.5, 24.0, 3.5, 4.0, "TZ_E"), "OpenWorkspace": (5.0, 12.0, 17.5, 7.0, "TZ_C"),
    "Space_418": (7.0, 19.5, 3.5, 4.0, "TZ_C"), "Space_422": (10.5, 19.5, 3.5, 4.0, "TZ_C"),
    "Space_424": (14.0, 19.5, 3.5, 4.0, "TZ_C"), "Space_426": (17.5, 19.5, 3.5, 4.0, "TZ_C"),
    "Space_434": (0.0, 0.0, 3.5, 4.0, "TZ_W"), "Space_451": (3.5, 0.0, 3.5, 4.0, "TZ_W"),
    "Space_450": (7.0, 0.0, 3.5, 4.0, "TZ_W"), "Space_449": (10.5, 0.0, 3.5, 4.0, "TZ_W"),
    "Space_453": (0.0, 4.0, 3.5, 4.0, "TZ_W"), "Space_448": (3.5, 4.0, 3.5, 4.0, "TZ_W"),
    "Space_452": (0.0, 8.0, 3.5, 4.0, "TZ_W"), "Space_442": (5.0, 8.0, 3.5, 4.0, "TZ_S"),
    "Space_444": (8.5, 8.0, 3.5, 4.0, "TZ_S"), "Space_446": (12.0, 8.0, 3.5, 4.0, "TZ_S"),
}
tz_map = {}
for tz_n in set([v[4] for v in space_map.values()]):
    tz = openstudio.model.ThermalZone(model); tz.setName(tz_n); tz_map[tz_n] = tz

for sname, (x, y, w, l, tzn) in space_map.items():
    p = openstudio.Point3dVector([openstudio.Point3d(x, y, 0), openstudio.Point3d(x, y+l, 0), openstudio.Point3d(x+w, y+l, 0), openstudio.Point3d(x+w, y, 0)])
    space = openstudio.model.Space.fromFloorPrint(p, 3.0, model).get(); space.setName(sname); space.setThermalZone(tz_map[tzn])
    for surface in space.surfaces():
        st = surface.surfaceType().lower()
        if st == "floor" or "roof" in st or "ceiling" in st: surface.setConstruction(slab_const)
        elif st == "wall":
            surface.setConstruction(ext_wall); cent = surface.centroid(); is_peri = (abs(cent.x() - 0.0) < 0.1 or abs(cent.x() - 33.0) < 0.1 or abs(cent.y() - 0.0) < 0.1 or abs(cent.y() - 28.0) < 0.1)
            if is_peri: surface.setWindowToWallRatio(0.30)
            else: surface.setOutsideBoundaryCondition("Adiabatic")

# =========================================================================================
# UNIT 5: SCHEDULES
# =========================================================================================
def create_sch(model, n, p, wv):
    s = openstudio.model.ScheduleRuleset(model); s.setName(n); ds = s.defaultDaySchedule()
    for ts, v in p: h, m = map(int, ts.split(':')); ds.addValue(openstudio.Time(0, h, m, 0), v)
    r = openstudio.model.ScheduleRule(s); r.setApplySaturday(True); r.setApplySunday(True); rs = r.daySchedule(); rs.addValue(openstudio.Time(0, 24, 0, 0), wv)
    return s

sch_ashrae = create_sch(model, "ASHRAE_Schedules", [("08:00", 0.1), ("18:00", 1.0), ("24:00", 0.1)], 0.1)
# BUG5-FIX: soft fallback schedules (weekend=0.05) match unified scripts
sch_fb_occ = create_sch(model, "Occ_FB",  [("08:00", 0.1), ("18:00", 1.0), ("24:00", 0.1)], 0.05)
sch_fb_gn  = create_sch(model, "Gain_FB", [("08:00", 0.1), ("18:00", 1.0), ("24:00", 0.1)], 0.05)
act_sch = openstudio.model.ScheduleConstant(model); act_sch.setValue(130.0); act_sch.setName("Metabolic_Activity")

space_sch_map = {}
if args.schedule_mode == 'ashrae':
    for sname in space_map.keys(): space_sch_map[sname] = (sch_ashrae, sch_ashrae)
else:
    f_dir = PROJECT_ROOT / "fused_results"
    for sname in space_map.keys():
        rid = sname.replace("Space_", ""); f_p = f_dir / f"{rid}_fused_data.csv"
        if f_p.exists():
            df = pd.read_csv(f_p); df['dt'] = pd.to_datetime(df['dt'])
            s_o = openstudio.model.ScheduleRuleset(model); s_o.setName(f"F_Occ_{rid}")
            s_g = openstudio.model.ScheduleRuleset(model); s_g.setName(f"F_Gain_{rid}")
            for d in df['dt'].dt.date.unique():
                rule_o = openstudio.model.ScheduleRule(s_o); rule_o.setStartDate(openstudio.Date(openstudio.MonthOfYear(d.month), d.day, 2013)); rule_o.setEndDate(openstudio.Date(openstudio.MonthOfYear(d.month), d.day, 2013))
                rule_g = openstudio.model.ScheduleRule(s_g); rule_g.setStartDate(openstudio.Date(openstudio.MonthOfYear(d.month), d.day, 2013)); rule_g.setEndDate(openstudio.Date(openstudio.MonthOfYear(d.month), d.day, 2013))
                day_name = pd.Timestamp(d).day_name(); getattr(rule_o, f"setApply{day_name}")(True); getattr(rule_g, f"setApply{day_name}")(True)
                rs_o = rule_o.daySchedule(); rs_g = rule_g.daySchedule(); day_d = df[df['dt'].dt.date == d].sort_values('dt')
                for _, row in day_d.iterrows():
                    ti = row['dt'].time(); val = float(row['fused_score'])
                    if ti.hour == 0 and ti.minute == 0: continue
                    o_val = min(1.0, val * 0.6) if val >= 0.1 else 0.0
                    g_val = max(0.3, val) if val >= 0.1 else 0.2
                    rs_o.addValue(openstudio.Time(0, ti.hour, ti.minute, 0), o_val)
                    rs_g.addValue(openstudio.Time(0, ti.hour, ti.minute, 0), g_val)
                last_val = float(day_d.iloc[-1]['fused_score'])
                rs_o.addValue(openstudio.Time(0, 24, 0, 0), min(1.0, last_val * 0.6) if last_val >= 0.1 else 0.0)
                rs_g.addValue(openstudio.Time(0, 24, 0, 0), max(0.3, last_val) if last_val >= 0.1 else 0.2)
            space_sch_map[sname] = (s_o, s_g)
        else:
            space_sch_map[sname] = (sch_fb_occ, sch_fb_gn)  # BUG5-FIX: soft fallback, not ASHRAE block

# =========================================================================================
# UNIT 6: LOAD ASSIGNMENT (HVAC OFF)
# =========================================================================================
oa_def = openstudio.model.DesignSpecificationOutdoorAir(model); oa_def.setOutdoorAirFlowperPerson(args.oa_rate)
lt_def = openstudio.model.LightsDefinition(model); lt_def.setWattsperSpaceFloorArea(11.0)
eq_def = openstudio.model.ElectricEquipmentDefinition(model); eq_def.setWattsperSpaceFloorArea(args.eq_density)

for sname in space_map.keys():
    space = model.getSpaceByName(sname).get(); s_o, s_g = space_sch_map.get(sname, (sch_ashrae, sch_ashrae))
    peak_cap = 8.0 if "OpenWorkspace" in sname else 1.0
    pp_inst = openstudio.model.PeopleDefinition(model); pp_inst.setName(f"PeopleDef_{sname}"); pp_inst.setNumberofPeople(peak_cap); pp_inst.setSensibleHeatFraction(0.577)
    openstudio.model.People(pp_inst).setSpace(space); space.people()[-1].setNumberofPeopleSchedule(s_o); space.people()[-1].setActivityLevelSchedule(act_sch)
    openstudio.model.Lights(lt_def).setSpace(space); space.lights()[-1].setSchedule(s_g)
    openstudio.model.ElectricEquipment(eq_def).setSpace(space); space.electricEquipment()[-1].setSchedule(s_g)
    openstudio.model.SpaceInfiltrationDesignFlowRate(model).setSpace(space); space.spaceInfiltrationDesignFlowRates()[-1].setAirChangesperHour(args.infiltration)
    space.setDesignSpecificationOutdoorAir(oa_def)
    # NO THERMOSTATS / NO IDEAL AIR LOADS (HVAC remains OFF)

# =========================================================================================
# UNIT 7: OUTPUT VARIABLES
# =========================================================================================
co2_outdoor_sch = openstudio.model.ScheduleConstant(model); co2_outdoor_sch.setName("Outdoor_CO2_400ppm"); co2_outdoor_sch.setValue(400.0)
contam = model.getZoneAirContaminantBalance(); contam.setCarbonDioxideConcentration(True); contam.setOutdoorCarbonDioxideSchedule(co2_outdoor_sch)
for vn in ["Zone Air Temperature", "Zone Air Relative Humidity", "Zone Air CO2 Concentration", "Zone People Occupant Count"]:
    openstudio.model.OutputVariable(vn, model).setReportingFrequency("TimeStep")

# =========================================================================================
# UNIT 8: SAVE & EXECUTE
# =========================================================================================
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
run_name = f"{args.schedule_mode}_eq{args.eq_density}_oa{args.oa_rate}_inf{args.infiltration}_{timestamp}"
run_dir = RUNS_DIR / run_name; run_dir.mkdir(parents=True)
model.save(openstudio.path(str(run_dir / "model.osm")), True)
shutil.copy2(EPW_PATH, run_dir / "weather.epw")
with open(run_dir / "workflow.osw", 'w') as f: json.dump({"seed_file": "model.osm", "weather_file": "weather.epw", "steps": []}, f, indent=4)

os_cli = r"C:\openstudioapplication-1.10.0\bin\openstudio.exe"
subprocess.run([os_cli, "run", "-w", "workflow.osw"], cwd=str(run_dir), capture_output=True, check=True)

with open(EXPERIMENT_ROOT / "experiment_config.json", 'w') as f:
    json.dump({"experiment_id": "noIdealLoad_comp", "latest_run_dir": run_name}, f, indent=4)
print(f"DONE: {run_name}")
