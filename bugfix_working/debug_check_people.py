import openstudio
import sys

def check_model_people(osm_path, target_zone_name):
    print(f"\nAnalyzing: {osm_path}")
    model = openstudio.model.Model.load(osm_path).get()
    
    tz = model.getThermalZoneByName(target_zone_name).get()
    total_people_count = 0
    spaces = tz.spaces()
    print(f"Zone {target_zone_name} contains {len(spaces)} spaces.")
    
    for space in spaces:
        people_objs = space.people()
        print(f"  Space {space.name().get()}: {len(people_objs)} People objects.")
        for p in people_objs:
            defn = p.peopleDefinition()
            count = defn.numberofPeople().get() if defn.numberofPeople().is_initialized() else "Variable"
            print(f"    - People Object: {p.name().get()} | Capacity: {count}")
            if isinstance(count, float):
                total_people_count += count
    
    print(f"Total Theoretical Max Occupancy in {target_zone_name}: {total_people_count}")

if __name__ == "__main__":
    check_model_people("aswani_model/model/runs/run_20260417_170034/SDH_Level4_Aswani.osm", "TZ_NW")
    check_model_people("idealLoad_model/model/runs/run_20260417_170052/SDH_Level4_IdealLoad.osm", "TZ_NW")
