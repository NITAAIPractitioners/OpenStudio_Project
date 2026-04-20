import openstudio
model = openstudio.model.Model.load(openstudio.path("debug_after_match.osm")).get()
tiny_count = 0
for surface in model.getSurfaces():
    area = surface.grossArea()
    if area < 0.01: # 0.01 m2 is very small
        print(f"Tiny Surface: {surface.nameString()}, Area: {area:.6f} m2, Type: {surface.surfaceType()}")
        tiny_count += 1
print(f"Total tiny surfaces (< 0.01 m2): {tiny_count}")
