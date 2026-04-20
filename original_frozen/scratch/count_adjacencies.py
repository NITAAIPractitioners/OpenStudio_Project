import openstudio
model = openstudio.model.Model.load(openstudio.path("debug_after_match.osm")).get()
count = 0
for surface in model.getSurfaces():
    if surface.outsideBoundaryCondition() == "Surface":
        count += 1
print(f"Total internal surface adjacencies: {count}")
