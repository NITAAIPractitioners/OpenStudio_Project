import openstudio
model = openstudio.model.Model.load(openstudio.path("debug_after_match.osm")).get()
surfaces = model.getSurfaces()
overlaps = []
for i in range(len(surfaces)):
    s1 = surfaces[i]
    c1 = s1.centroid()
    for j in range(i + 1, len(surfaces)):
        s2 = surfaces[j]
        c2 = s2.centroid()
        dist = (c1.x() - c2.x())**2 + (c1.y() - c2.y())**2 + (c1.z() - c2.z())**2
        if dist < 0.0001: # 0.1 mm precision
            overlaps.append((s1.nameString(), s2.nameString(), dist))

print(f"Total overlapping surfaces (by centroid): {len(overlaps)}")
for s1_name, s2_name, d in overlaps:
    print(f"Overlap: {s1_name} and {s2_name} (Dist: {d:.8f})")
