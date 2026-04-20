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

# --- PARAMETER INJECTION (For Track B Experiments) ---
parser = argparse.ArgumentParser(description='Aswani Model Sensitivity Run.')
parser.add_argument('--eq_density', type=float, default=20.0, help='Equipment Density [W/m2]')
parser.add_argument('--eq_sch_type', type=str, default='Scaled', choices=['Scaled', 'Constant', 'Softer'], help='Equipment Schedule Strategy')
parser.add_argument('--oa_rate', type=float, default=0.010, help='Outdoor Air Rate per Person [m3/s/p]')
parser.add_argument('--infiltration', type=float, default=0.5, help='Infiltration rate [ACH]')
parser.add_argument('--sensible_fraction', type=float, default=0.577, help='Sensible Heat Fraction of People')
parser.add_argument('--stage', type=str, default='B1b', help='Experiment Stage ID')
parser.add_argument('--use_baseline', action='store_true', help='Force use of original non-sensor-fused schedules')
args = parser.parse_args()

# --- ENHANCED AUDIT LOGGER ---
audit_records = []
def log_audit(unit_id, section, target, action, detail="", value=""):
    audit_records.append({
        "Timestamp": pd.Timestamp.now(),
        "Unit": f"Unit {unit_id}",
        "Section": section,
        "Target_Object": target,
        "Action": action,
        "Engineering_Value": str(value),
        "Detail": detail
    })

logger = logging.getLogger("sdh_aswani_model")
logging.basicConfig(level=logging.INFO)
logger.info(f"Initializing Aswani Track B Experiment Stage: {args.stage}")

# --- EXPERIMENT PARAMETER AUDIT ---
log_audit(0, "Calibration", "MetaData", "ExperimentVars", 
          detail=f"Stage: {args.stage}",
          value=f"eq: {args.eq_density}, oa: {args.oa_rate}, inf: {args.infiltration}, sens_frac: {args.sensible_fraction}, is_baseline: {args.use_baseline}")

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

building = model.getBuilding()
building.setName("SDH_Level4_Aswani")
building.setNorthAxis(28)

model.getYearDescription().setCalendarYear(2013)
run_period = model.getRunPeriod()
run_period.setBeginMonth(8); run_period.setBeginDayOfMonth(23)
run_period.setEndMonth(8); run_period.setEndDayOfMonth(31)

EPW_PATH = PROJECT_ROOT / "Oakland_2013_AMY.epw"
if EPW_PATH.exists():
    openstudio.model.WeatherFile.setWeatherFile(model, openstudio.EpwFile(openstudio.path(str(EPW_PATH))))
else:
    raise FileNotFoundError(f"EPW weather file not found at {EPW_PATH}. Aborting build.")

# Sizing Control - Enabled for VAV conversion
sim_ctrl = model.getSimulationControl()
sim_ctrl.setDoZoneSizingCalculation(True)
sim_ctrl.setDoSystemSizingCalculation(True)
sim_ctrl.setDoPlantSizingCalculation(True)

# =========================================================================================
# UNIT 2: PHYSICAL ENVELOPE (Preserving Standard Aswani logic)
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
    space = openstudio.model.Space.fromFloorPrint(p, 3.0, model).get()
    space.setName(sname); space.setThermalZone(tz_map[tzn])
    
    for surface in space.surfaces():
        st = surface.surfaceType().lower()
        if st == "floor" or "roof" in st or "ceiling" in st:
            surface.setConstruction(slab_const)
        elif st == "wall":
            surface.setConstruction(ext_wall)
            cent = surface.centroid()
            is_peri = (abs(cent.x() - 0.0) < 0.1 or abs(cent.x() - 33.0) < 0.1 or 
                       abs(cent.y() - 0.0) < 0.1 or abs(cent.y() - 28.0) < 0.1)
            if is_peri: surface.setWindowToWallRatio(0.30)
            else: surface.setOutsideBoundaryCondition("Adiabatic")

# =========================================================================================
# UNIT 5: SCHEDULES
# =========================================================================================
def create_sch(model, n, p, wv):
    s = openstudio.model.ScheduleRuleset(model); s.setName(n); ds = s.defaultDaySchedule()
    for ts, v in p: h, m = map(int, ts.split(':')); ds.addValue(openstudio.Time(0, h, m, 0), v)
    r = openstudio.model.ScheduleRule(s); r.setApplySaturday(True); r.setApplySunday(True); rs = r.daySchedule(); rs.addValue(openstudio.Time(0, 24, 0, 0), wv)
    # Ensure Sizing Period Activity
    s.summerDesignDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)
    s.winterDesignDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)
    return s

sch_fb_occ = create_sch(model, "Occ_FB", [("08:00", 0.1), ("18:00", 1.0), ("24:00", 0.1)], 0.05)
sch_fb_gn = create_sch(model, "Gain_FB", [("08:00", 0.1), ("18:00", 1.0), ("24:00", 0.1)], 0.05)
act_sch = openstudio.model.ScheduleConstant(model); act_sch.setValue(130.0); act_sch.setName("Metabolic_Activity")

f_dir = PROJECT_ROOT / "fused_results"; space_sch_map = {}
for sname in space_map.keys():
    rid = sname.replace("Space_", ""); f_p = f_dir / f"{rid}_fused_data.csv"
    if f_p.exists() and not args.use_baseline:
        df = pd.read_csv(f_p); df['dt'] = pd.to_datetime(df['dt'])
        s_o = openstudio.model.ScheduleRuleset(model); s_o.setName(f"F_Occ_{rid}")
        s_g = openstudio.model.ScheduleRuleset(model); s_g.setName(f"F_Gain_{rid}")
        # Ensure Sizing Period Activity (Mandatory for VAV Autosizing)
        s_o.summerDesignDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)
        s_o.winterDesignDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)
        s_g.summerDesignDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)
        s_g.winterDesignDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)
        
        for d in df['dt'].dt.date.unique():
            # Pass 2: Decoupled Load Injection
            # People (s_o) scaled by 0.6, Equipment/Lights (s_g) with 0.3 floor
            rule_o = openstudio.model.ScheduleRule(s_o); rule_o.setStartDate(openstudio.Date(openstudio.MonthOfYear(d.month), d.day, 2013)); rule_o.setEndDate(openstudio.Date(openstudio.MonthOfYear(d.month), d.day, 2013))
            rule_g = openstudio.model.ScheduleRule(s_g); rule_g.setStartDate(openstudio.Date(openstudio.MonthOfYear(d.month), d.day, 2013)); rule_g.setEndDate(openstudio.Date(openstudio.MonthOfYear(d.month), d.day, 2013))
            
            day_name = pd.Timestamp(d).day_name()
            getattr(rule_o, f"setApply{day_name}")(True)
            getattr(rule_g, f"setApply{day_name}")(True)
            
            rs_o = rule_o.daySchedule(); rs_g = rule_g.daySchedule()
            day_d = df[df['dt'].dt.date == d].sort_values('dt')
            
            for _, row in day_d.iterrows():
                ti = row['dt'].time()
                if ti.hour == 0 and ti.minute == 0: continue
                val = float(row['fused_score'])
                
                # Logic: People = 60% of score, capped at 1.0, threshold 0.1
                o_val = min(1.0, val * 0.6) if val >= 0.1 else 0.0
                
                # Logic: Gains based on eq_sch_type
                if args.eq_sch_type == 'Scaled':
                    g_val = max(0.3, val) if val >= 0.1 else 0.2
                elif args.eq_sch_type == 'Constant':
                    g_val = 1.0
                elif args.eq_sch_type == 'Softer':
                    g_val = max(0.15, val) if val >= 0.1 else 0.1
                else:
                    g_val = max(0.3, val) if val >= 0.1 else 0.2
                
                rs_o.addValue(openstudio.Time(0, ti.hour, ti.minute, 0), o_val)
                rs_g.addValue(openstudio.Time(0, ti.hour, ti.minute, 0), g_val)
                
            last_val = float(day_d.iloc[-1]['fused_score'])
            rs_o.addValue(openstudio.Time(0, 24, 0, 0), min(1.0, last_val * 0.6) if last_val >= 0.1 else 0.0)
            
            # Last val for gains
            if args.eq_sch_type == 'Scaled':
                lg_val = max(0.3, last_val) if last_val >= 0.1 else 0.2
            elif args.eq_sch_type == 'Constant':
                lg_val = 1.0
            elif args.eq_sch_type == 'Softer':
                lg_val = max(0.15, last_val) if last_val >= 0.1 else 0.1
            else:
                lg_val = max(0.3, last_val) if last_val >= 0.1 else 0.2
            rs_g.addValue(openstudio.Time(0, 24, 0, 0), lg_val)
        space_sch_map[sname] = (s_o, s_g)
        log_audit(5, "Schedule", sname, "FusedAssignment", f"CSV found, baseline={args.use_baseline}, strategy={args.eq_sch_type}", f"Occ:{s_o.nameString()}, Gain:{s_g.nameString()}")
    else:
        space_sch_map[sname] = (sch_fb_occ, sch_fb_gn)
        status = "BaselineForced" if args.use_baseline else "CSV_Missing"
        log_audit(5, "Schedule", sname, "FallbackAssignment", f"Status: {status}", f"Occ:Occ_FB, Gain:Gain_FB")

# --- 4. DESIGN DAYS (Full DDY Integration for Autosizing) ---
ddy_path = MODEL_SCRIPT_DIR / "USA_CA_Oakland.Intl.AP.724930_TMY3.ddy"
if ddy_path.exists():
    print(f"Loading official DDY file: {ddy_path.name}")
    rt = openstudio.energyplus.ReverseTranslator()
    ddy_model_opt = rt.loadModel(openstudio.path(str(ddy_path)))
    if ddy_model_opt.is_initialized():
        ddy_model = ddy_model_opt.get()
        
        target_htg = "Oakland Intl AP Ann Htg 99.6% Condns DB"
        target_clg = "Oakland Intl AP Ann Clg .4% Condns DB=>MWB"
    
    found_htg = False
    found_clg = False
    
    for dd in ddy_model.getDesignDays():
        dname = dd.name().get()
        if target_htg in dname or target_clg in dname:
            dd.clone(model)
            print(f"  - Cloned DesignDay: {dname}")
            if target_htg in dname: found_htg = True
            if target_clg in dname: found_clg = True
            
    # Fallback if exact names not matched
    if not found_htg or not found_clg:
        for dd in ddy_model.getDesignDays():
            if not found_htg and dd.dayType() == "WinterDesignDay":
                dd.clone(model); print(f"  - Fallback cloned Heating DD: {dd.name().get()}"); found_htg = True
            if not found_clg and dd.dayType() == "SummerDesignDay":
                dd.clone(model); print(f"  - Fallback cloned Cooling DD: {dd.name().get()}"); found_clg = True
            if found_htg and found_clg: break
else:
    print(f"WARNING: DDY file not found at {ddy_path}. Sizing may fail.")

# =========================================================================================
# =========================================================================================
# UNIT 6: HVAC & LOAD ASSIGNMENT (VAV Conversion Step 1)
# =========================================================================================
sch_20 = openstudio.model.ScheduleConstant(model); sch_20.setValue(20.0)
sch_24 = openstudio.model.ScheduleConstant(model); sch_24.setValue(24.0)
# (Thermostat created inside loop for individual zone ownership)

oa_def = openstudio.model.DesignSpecificationOutdoorAir(model); oa_def.setOutdoorAirFlowperPerson(args.oa_rate)
pp_def = openstudio.model.PeopleDefinition(model); pp_def.setPeopleperSpaceFloorArea(0.05); pp_def.setSensibleHeatFraction(args.sensible_fraction)
lt_def = openstudio.model.LightsDefinition(model); lt_def.setWattsperSpaceFloorArea(11.0)
eq_def = openstudio.model.ElectricEquipmentDefinition(model); eq_def.setWattsperSpaceFloorArea(args.eq_density)

# --- 1. INITIALIZE AIR LOOP ---
air_loop = openstudio.model.AirLoopHVAC(model)
air_loop.setName("SDH_VAV_Base")

# --- 2. SUPPLY SIDE COMPONENTS (VAV + Reheat + CHW) ---
fan = openstudio.model.FanVariableVolume(model)
htg_coil = openstudio.model.CoilHeatingElectric(model)

# CHW Plant Loop Stub (Required for CoilCoolingWater)
chw_loop = openstudio.model.PlantLoop(model)
chw_loop.setName("CHW Loop")
chw_loop.setMaximumLoopTemperature(15.0)
chw_loop.setMinimumLoopTemperature(5.0)

# Sizing Parameters for Ventilation/Cooling
chw_loop.sizingPlant().setDesignLoopExitTemperature(6.7)
chw_loop.sizingPlant().setLoopDesignTemperatureDifference(5.0)

chw_pump = openstudio.model.PumpVariableSpeed(model)
chiller = openstudio.model.ChillerElectricEIR(model)
chw_pump.addToNode(chw_loop.supplyInletNode())
chiller.addToNode(chw_loop.supplyInletNode())

# CHW Setpoint Manager (Fixed 6.7 C)
chw_sat_sch = openstudio.model.ScheduleConstant(model); chw_sat_sch.setValue(6.7); chw_sat_sch.setName("CHW_Supply_6.7C")
chw_spm = openstudio.model.SetpointManagerScheduled(model, chw_sat_sch)
chw_spm.addToNode(chw_loop.supplyOutletNode())

# Cooling Coil (Water)
clg_coil = openstudio.model.CoilCoolingWater(model)
chw_loop.addDemandBranchForComponent(clg_coil)

# Outdoor Air System
oa_controller = openstudio.model.ControllerOutdoorAir(model)
oa_system = openstudio.model.AirLoopHVACOutdoorAirSystem(model, oa_controller)
oa_system.addToNode(air_loop.supplyInletNode())

# Add components to air loop supply side
htg_coil.addToNode(air_loop.supplyInletNode())
clg_coil.addToNode(air_loop.supplyInletNode())
fan.addToNode(air_loop.supplyInletNode())

# Setpoint Manager (SAT = 13.0 C Fixed for Step 1 Smoke Test)
sat_sch = openstudio.model.ScheduleConstant(model); sat_sch.setValue(13.0); sat_sch.setName("SAT_13C_Fixed")
spm = openstudio.model.SetpointManagerScheduled(model, sat_sch)
spm.addToNode(air_loop.supplyOutletNode())

# --- 3. SPACE ASSIGNMENT & DEMAND SIDE ---
visited_zones = set()
for sname in space_map.keys():
    space = model.getSpaceByName(sname).get(); s_o, s_g = space_sch_map[sname]
    
    # Pass 1: Capacity-Scaled Injection
    # Logic: OpenWorkspace = 8 peak, All others = 1 peak
    peak_cap = 8.0 if "OpenWorkspace" in sname else 1.0
    
    # Create unique definition to avoid side-effects across spaces
    pp_inst = openstudio.model.PeopleDefinition(model)
    pp_inst.setName(f"PeopleDef_{sname}")
    pp_inst.setNumberofPeople(peak_cap)
    pp_inst.setSensibleHeatFraction(args.sensible_fraction)
    
    openstudio.model.People(pp_inst).setSpace(space)
    space.people()[-1].setNumberofPeopleSchedule(s_o)
    space.people()[-1].setActivityLevelSchedule(act_sch)
    
    openstudio.model.Lights(lt_def).setSpace(space); space.lights()[-1].setSchedule(s_g)
    openstudio.model.ElectricEquipment(eq_def).setSpace(space); space.electricEquipment()[-1].setSchedule(s_g)
    openstudio.model.SpaceInfiltrationDesignFlowRate(model).setSpace(space); space.spaceInfiltrationDesignFlowRates()[-1].setAirChangesperHour(args.infiltration)
    space.setDesignSpecificationOutdoorAir(oa_def)

    tz = space.thermalZone().get()
    if tz.handle() not in visited_zones:
        # Restoration: Create a unique thermostat object per zone to ensure ownership
        tstat_zone = openstudio.model.ThermostatSetpointDualSetpoint(model)
        tstat_zone.setName(f"TStat_{tz.name().get()}")
        tstat_zone.setHeatingSetpointTemperatureSchedule(sch_20)
        tstat_zone.setCoolingSetpointTemperatureSchedule(sch_24)
        tz.setThermostatSetpointDualSetpoint(tstat_zone)
        
        # Create Reheat Coil
        reheat_coil = openstudio.model.CoilHeatingElectric(model)
        
        # Create VAV Reheat Terminal (Corrected Constructor: model, schedule, coil)
        terminal = openstudio.model.AirTerminalSingleDuctVAVReheat(model, model.alwaysOnDiscreteSchedule(), reheat_coil)
        
        # Configure Airflow (Optimized: 0.15 for better turn-down)
        terminal.setZoneMinimumAirFlowMethod("Constant")
        terminal.setConstantMinimumAirFlowFraction(0.15)
        
        air_loop.addBranchForZone(tz, terminal)
        
        # Sizing:Zone (Mandatory for VAV Autosizing)
        sz = openstudio.model.SizingZone(model, tz)
        sz.setZoneHeatingDesignSupplyAirTemperature(40.0) # Fixed Delta-T
        sz.setZoneCoolingDesignSupplyAirTemperature(13.0)
        
        visited_zones.add(tz.handle())

# =========================================================================================
# UNIT 7: OUTPUT & PHYSICS
# =========================================================================================
co2_outdoor_sch = openstudio.model.ScheduleConstant(model); co2_outdoor_sch.setName("Outdoor_CO2_400ppm"); co2_outdoor_sch.setValue(400.0)
contam = model.getZoneAirContaminantBalance(); contam.setCarbonDioxideConcentration(True); contam.setOutdoorCarbonDioxideSchedule(co2_outdoor_sch)

output_vars = [
    ("Zone Air Temperature",              "*", "TimeStep"),
    ("Zone Air Relative Humidity",        "*", "TimeStep"),
    ("Zone Air CO2 Concentration",        "*", "TimeStep"),
    ("Zone Air Terminal Sensible Heating Energy", "*", "TimeStep"),
    ("Zone People Occupant Count",        "*", "TimeStep"),
]
for vn, kv, fr in output_vars:
    ov = openstudio.model.OutputVariable(vn, model); ov.setKeyValue(kv); ov.setReportingFrequency(fr)

# =========================================================================================
# UNIT 8: SAVE & EXECUTE (VAULT LOGIC)
# =========================================================================================
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# Refined Run Name for Track B Tracking
run_name = f"{args.stage}_eq{args.eq_density}_oa{args.oa_rate}_inf{args.infiltration}_{timestamp}"
run_dir = RUNS_DIR / run_name
run_dir.mkdir(parents=True)

osm_path = run_dir / "SDH_Level4_Aswani.osm"
model.save(openstudio.path(str(osm_path)), True)
shutil.copy2(EPW_PATH, run_dir / "Oakland_2013_AMY.epw")

with open(run_dir / "workflow.osw", 'w') as f:
    json.dump({"seed_file": "SDH_Level4_Aswani.osm", "weather_file": "Oakland_2013_AMY.epw", "steps": []}, f, indent=4)

os_cli = r"C:\openstudioapplication-1.10.0\bin\openstudio.exe"
cmd = [os_cli, "run", "-w", "workflow.osw"]
logger.info(f"Executing Aswani simulation in Vault: {run_name}")
res = subprocess.run(cmd, check=False, cwd=str(run_dir), capture_output=True, text=True)

# Update Experiment Config
config_path = EXPERIMENT_ROOT / "experiment_config.json"
config = {
    "experiment_id": "aswani_model", 
    "latest_run_dir": run_name, 
    "last_sim_status": "SUCCESS" if res.returncode == 0 else "FAILED", 
    "weather_file": "Oakland_2013_AMY.epw"
}
with open(config_path, 'w') as f:
    json.dump(config, f, indent=4)

logger.info(f"Aswani model complete. Status: {config['last_sim_status']}")

# --- STEP 1 MANDATORY AUDIT ---
print("\n" + "="*60)
print("UNIT 9: STEP 1 MANDATORY AUDIT")
print("="*60)
air_loops = model.getAirLoopHVACs()
print(f"Number of AirLoopHVAC objects: {len(air_loops)}")
if len(air_loops) > 0:
    vav_loop = air_loops[0]
    print(f"Air Loop Name: {vav_loop.name().get()}")
    zones_served = vav_loop.thermalZones()
    print(f"Thermal Zones Served ({len(zones_served)}):")
    for z in zones_served:
        ideal_on = z.useIdealAirLoads()
        terminal = "None"
        if len(z.equipment()) > 0:
            terminal = z.equipment()[0].iddObject().name()
        print(f"  - {z.name().get()} | Terminal: {terminal} | IdealLoadsActive: {ideal_on}")

print(f"\nSizingZone objects found: {len(model.getSizingZones())}")
print(f"DesignDay objects found: {len(model.getDesignDays())}")
for dd in model.getDesignDays():
    print(f"  - DESIGN DAY: {dd.name().get()}")

print(f"\nSimulation Return Code: {res.returncode}")
if res.returncode == 0:
    print("STEP 1 SUCCESS: basic VAV AirLoop built and all 6 zones connected")
else:
    print("STEP 1 FAILED: Simulation error encountered.")

# --- WARNING EXTRACTION ---
print("\n" + "-"*60)
print("SPECIFIC WARNINGS AUDIT")
print("-"*60)
err_path = run_dir / "run" / "eplusout.err"
if err_path.exists():
    with open(err_path, 'r') as f:
        err_content = f.readlines()
    
    categories = {
        "Geometry Enclosure": ["enclosed", "surface"],
        "Ground Temperature": ["Ground Temperature"],
        "Minimum Air Flow": ["Minimum Air Flow", "ignores"]
    }
    
    for cat, keywords in categories.items():
        print(f"\n[{cat}]")
        found = False
        for line in err_content:
            if any(k.lower() in line.lower() for k in keywords):
                if "** Warning **" in line or "** Severe **" in line or "~~~" in line:
                    print(f"  {line.strip()}")
                    found = True
        if not found: print("  None detected.")

print("="*60 + "\n")

pd.DataFrame(audit_records).to_csv(run_dir / "aswani_model_audit.csv", index=False)
