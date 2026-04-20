import openstudio
import os

model_path = r"c:\Users\me.com\Documents\engery\OpenStudio_Project\SDH_Level4_Publication_Ready.osm"
if not os.path.exists(model_path):
    print("Model not found")
    exit()

vt = openstudio.osversion.VersionTranslator()
model = vt.loadModel(model_path).get()

# Step 1
print("=== STEP 1 ===")
tz_nw = model.getThermalZoneByName("TZ_NW")
if tz_nw.is_initialized():
    tz_nw = tz_nw.get()
    spaces = tz_nw.spaces()
    total_area = 0
    print("TZ_NW:")
    for space in spaces:
        print(f"  - {space.nameString()} : {space.floorArea()} m2")
        total_area += space.floorArea()
    print(f"Total area = {total_area} m2")
else:
    print("TZ_NW not found")

# Step 2
print("\n=== STEP 2 ===")
for space in tz_nw.spaces():
    occ_sch = "None"
    gn_sch = "None"
    source = "fused"
    
    if len(space.people()) > 0:
        sch = space.people()[0].numberofPeopleSchedule()
        if sch.is_initialized(): occ_sch = sch.get().nameString()
    
    if len(space.lights()) > 0:
        sch = space.lights()[0].schedule()
        if sch.is_initialized(): gn_sch = sch.get().nameString()
    
    if "FB" in occ_sch or "FB" in gn_sch:
        source = "fallback"
    
    print(f"{space.nameString()} -> Occupancy: {occ_sch} | Gains: {gn_sch} | Source: {source}")

# Step 3
print("\n=== STEP 3 ===")
num_spaces = len(tz_nw.spaces())
total_area_nw = sum([s.floorArea() for s in tz_nw.spaces()])
total_people = sum([p.peopleDefinition().peopleperSpaceFloorArea().get() * s.floorArea() for s in tz_nw.spaces() for p in s.people()])
total_lights_w = sum([l.lightsDefinition().wattsperSpaceFloorArea().get() * s.floorArea() for s in tz_nw.spaces() for l in s.lights()])
total_equipped_w = sum([e.electricEquipmentDefinition().wattsperSpaceFloorArea().get() * s.floorArea() for s in tz_nw.spaces() for e in s.electricEquipment()])
print(f"Number of spaces in TZ_NW: {num_spaces}")
print(f"Total people load: {total_people} persons")
print(f"Total lighting load: {total_lights_w} W")
print(f"Total equipment load: {total_equipped_w} W")

# Step 4
print("\n=== STEP 4 ===")
for space in tz_nw.spaces():
    ext_walls = 0
    windows = 0
    adiab_walls = 0
    for surf in space.surfaces():
        if surf.surfaceType() == "Wall":
            if surf.outsideBoundaryCondition() == "Outdoors":
                ext_walls += 1
                windows += len(surf.subSurfaces())
            elif surf.outsideBoundaryCondition() == "Adiabatic":
                adiab_walls += 1
    print(f"{space.nameString()} -> Ext walls: {ext_walls}, Windows: {windows}, Adiabatic walls: {adiab_walls}")

# Step 5
print("\n=== STEP 5 ===")
for space in tz_nw.spaces():
    area = space.floorArea()
    ppl = sum([p.peopleDefinition().peopleperSpaceFloorArea().get() for p in space.people()]) if space.people() else 0
    lt = sum([l.lightsDefinition().wattsperSpaceFloorArea().get() for l in space.lights()]) if space.lights() else 0
    eq = sum([e.electricEquipmentDefinition().wattsperSpaceFloorArea().get() for e in space.electricEquipment()]) if space.electricEquipment() else 0
    
    inf_ach = 0
    inf_sch = "None"
    if len(space.spaceInfiltrationDesignFlowRates()) > 0:
        inf = space.spaceInfiltrationDesignFlowRates()[0]
        if inf.airChangesperHour():
            inf_ach = inf.airChangesperHour()
        if inf.schedule().is_initialized(): inf_sch = inf.schedule().get().nameString()
            
    print(f"{space.nameString()}: PPL/m2={ppl:.4f}, LT W/m2={lt:.2f}, EQ W/m2={eq:.2f}, Inf ACH={inf_ach}, Inf= {inf_sch}")

print(f"TZ_NW Use Ideal Air Loads: {tz_nw.useIdealAirLoads()}")
tstat = tz_nw.thermostatSetpointDualSetpoint()
if tstat.is_initialized():
    print(f"TZ_NW Has Thermostat: True ({tstat.get().nameString()})")
else:
    print("TZ_NW Has Thermostat: False")

# Step 6
print("\n=== STEP 6 ===")
import csv
import glob
for space in list(tz_nw.spaces())[:2]:
    rid = space.nameString().replace("Space_", "")
    f_p = f"c:\\Users\\me.com\\Documents\\engery\\OpenStudio_Project\\fused_results\\{rid}_fused_data.csv"
    if os.path.exists(f_p):
        with open(f_p, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            occ_list = [float(r['occupied']) for r in rows if r['occupied'] != '']
            gain_list = [float(r['fused_score']) for r in rows if r['fused_score'] != '']
            
            print(f"{space.nameString()} fused occ (first 10): {occ_list[:10]}")
            print(f"{space.nameString()} fused gain (first 10): {gain_list[:10]}")
            if occ_list:
                print(f"{space.nameString()} fused occ min/max/mean: {min(occ_list)}/{max(occ_list)}/{sum(occ_list)/len(occ_list)}")
            if gain_list:
                print(f"{space.nameString()} fused gain min/max/mean: {min(gain_list)}/{max(gain_list)}/{sum(gain_list)/len(gain_list)}")
    else:
        print(f"{space.nameString()}: {f_p} not found")

# Step 7
print("\n=== STEP 7 ===")
tz_s = model.getThermalZoneByName("TZ_S")
if tz_s.is_initialized():
    tz_s = tz_s.get()
    print(f"Compare TZ_NW vs TZ_S:")
    print(f"Spaces: TZ_NW={len(tz_nw.spaces())}, TZ_S={len(tz_s.spaces())}")
    a_nw = sum([s.floorArea() for s in tz_nw.spaces()])
    a_s = sum([s.floorArea() for s in tz_s.spaces()])
    print(f"Area: TZ_NW={a_nw} m2, TZ_S={a_s} m2")
    
    p_s = sum([p.peopleDefinition().peopleperSpaceFloorArea().get() * s.floorArea() for s in tz_s.spaces() for p in s.people()])
    lt_s = sum([l.lightsDefinition().wattsperSpaceFloorArea().get() * s.floorArea() for s in tz_s.spaces() for l in s.lights()])
    eq_s = sum([e.electricEquipmentDefinition().wattsperSpaceFloorArea().get() * s.floorArea() for s in tz_s.spaces() for e in s.electricEquipment()])
    print(f"People: TZ_NW={total_people}, TZ_S={p_s}")
    print(f"Lights: TZ_NW={total_lights_w}, TZ_S={lt_s}")
    print(f"Equipment: TZ_NW={total_equipped_w}, TZ_S={eq_s}")
    
    win_nw = 0
    ext_nw = 0
    for s in tz_nw.spaces():
        for surf in s.surfaces():
            if surf.outsideBoundaryCondition() == "Outdoors":
                ext_nw += 1
                win_nw += len(surf.subSurfaces())
    win_s = 0
    ext_s = 0
    for s in tz_s.spaces():
        for surf in s.surfaces():
            if surf.outsideBoundaryCondition() == "Outdoors":
                ext_s += 1
                win_s += len(surf.subSurfaces())
    
    print(f"Ext Walls: TZ_NW={ext_nw}, TZ_S={ext_s}")
    print(f"Windows: TZ_NW={win_nw}, TZ_S={win_s}")
