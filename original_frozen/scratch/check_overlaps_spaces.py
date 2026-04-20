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
        if dist < 0.0001:
            space1 = s1.space().get().nameString() if s1.space().is_initialized() else "N/A"
            space2 = s2.space().get().nameString() if s2.space().is_initialized() else "N/A"
            overlaps.append((s1.nameString(), space1, s2.nameString(), space2, dist))

print(f"Total overlapping surfaces: {len(overlaps)}")
for s1_name, sp1, s2_name, sp2, d in overlaps:
    print(f"Overlap: {s1_name} ({sp1}) and {s2_name} ({sp2})")
