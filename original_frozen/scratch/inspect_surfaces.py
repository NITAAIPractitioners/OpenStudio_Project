import openstudio
model = openstudio.model.Model.load(openstudio.path("debug_after_match.osm")).get()
target_indices = [111, 117, 123, 129, 135, 161, 165, 166, 167, 168]
for surface in model.getSurfaces():
    name = surface.nameString()
    # Assuming names are like "Surface 161"
    if any(f"Surface {i}" == name for i in target_indices) or any(f"Surface {i}" in name for i in target_indices):
        print(f"Name: {name}, Type: {surface.surfaceType()}, BC: {surface.outsideBoundaryCondition()}")
        if surface.outsideBoundaryCondition() == "Surface":
            adj = surface.adjacentSurface()
            if adj.is_initialized():
                print(f"  Adjacent to: {adj.get().nameString()}")
