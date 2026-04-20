import openstudio
import sys
from pathlib import Path

def audit_people(osm_path):
    if not Path(osm_path).exists():
        print(f"Error: {osm_path} not found")
        return
    
    print(f"\nAUDITING: {osm_path}")
    model = openstudio.model.Model.load(osm_path).get()
    peoples = model.getPeoples()
    print(f"Total People Objects: {len(peoples)}")
    
    counts = {}
    for p in peoples:
        space_name = "Unassigned"
        if p.space().is_initialized():
             space_name = p.space().get().name().get()
        counts[space_name] = counts.get(space_name, 0) + 1
        
    for s, c in counts.items():
        if c > 1:
            print(f"  WARNING: Space {s} has {c} People objects!")
        else:
            print(f"  Space {s}: {c} People object (OK)")

if __name__ == "__main__":
    audit_people("aswani_model/model/runs/run_20260417_170034/SDH_Level4_Aswani.osm")
    audit_people("idealLoad_model/model/runs/run_20260417_170052/SDH_Level4_IdealLoad.osm")
