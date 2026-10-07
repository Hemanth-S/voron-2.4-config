#!/usr/bin/env python3
"""Ellis extrusion-multiplier cubes for the Voron 2.4 350, sliced headless with PrusaSlicer.

Uses Ellis' labelled 30x30x3 cubes (EM value debossed on the underside), one cube per EM value,
printed ONE AT A TIME (PrusaSlicer sequential printing), so a failure only costs one cube.
PrusaSlicer has no per-object EM, so the slicer EM stays at the filament profile's value and each
cube gets `M221 S<em*100>` right after its EXCLUDE_OBJECT_START (reset to 100 after the END).

Layout: 3x3 grid on 90 mm centres (60 mm gaps), filled in EM order front-left -> back-right.
The Eddy hangs at nozzle (-47, -7) only ~3 mm above the nozzle tip, i.e. level with a finished
3 mm cube, so no finished cube may come within its reach (47 mm + ~8 mm coil). PrusaSlicer enforces
this with extruder_clearance_radius = 55.

Ellis EM settings applied on top of the profiles: infill 40%, 2 bottom / 10 top layers,
no minimum layer time. (Monotonic top, 100% top line width, no ironing come from the print profile.)

usage: em_cubes.py --filament "PLA @Voron24" --out EM_Cubes_PLA.gcode [--em 0.90,0.92,...]
"""
import argparse, os, re, struct, subprocess, tempfile

PS = "/Applications/Original Prusa Drivers/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"
CFG = os.path.expanduser("~/Library/Application Support/PrusaSlicer")
CUBES = os.path.expanduser("~/Downloads/3D Printing/Tuning/Print-Tuning-Guide-main/test_prints/"
                           "extrusion_multiplier_cubes/labeled/EM_0.8-1.2/EM_Cube-%.3f.stl")
# print-profile keys that segfault the PrusaSlicer 2.9 CLI
BAD_PRINT_KEYS = ("bed_temperature_extruder", "wipe_tower_extruder")

ap = argparse.ArgumentParser()
ap.add_argument("--printer", default="Voron24")
ap.add_argument("--print", dest="print_", default="0.2mm 0.4nozzle @Voron24")
ap.add_argument("--filament", required=True)
ap.add_argument("--em", default="0.90,0.92,0.94,0.96,0.98,1.00,1.02")
ap.add_argument("--out", required=True)
a = ap.parse_args()
ems = [float(x) for x in a.em.split(",")]
assert len(ems) >= 1

# 3x3 grid, 90 mm centres; nozzle X 100..280 / Y 70..250 stays inside the Eddy mesh area
GRID = [(x, y) for y in (70, 160, 250) for x in (100, 190, 280)]
assert len(ems) <= len(GRID), "max 9 cubes"
plan = [(em, *GRID[i]) for i, em in enumerate(ems)]

tmp = tempfile.mkdtemp(prefix="emcubes_")
print_ini = os.path.join(tmp, "print.ini")
with open(os.path.join(CFG, "print", a.print_ + ".ini")) as f, open(print_ini, "w") as o:
    o.writelines(l for l in f if not l.startswith(BAD_PRINT_KEYS))

files = []
for em, cx, cy in plan:
    d = open(CUBES % em, "rb").read(); n = struct.unpack("<I", d[80:84])[0]
    out = bytearray(d[:84])
    for i in range(n):
        o = 84 + i * 50; out += d[o:o+12]
        for v in range(3):
            x, y, z = struct.unpack("<fff", d[o+12+v*12:o+24+v*12])
            out += struct.pack("<fff", x + cx - 15, y + cy - 15, z)
        out += d[o+48:o+50]
    fn = os.path.join(tmp, f"EM_{int(round(em * 1000)):04d}.stl"); open(fn, "wb").write(out); files.append(fn)

raw = os.path.join(tmp, "raw.gcode")
r = subprocess.run([PS, "--export-gcode", "--merge", "--dont-arrange",
                    "--load", os.path.join(CFG, "printer", a.printer + ".ini"), "--load", print_ini,
                    "--load", os.path.join(CFG, "filament", a.filament + ".ini"),
                    "--fill-density", "40%", "--bottom-solid-layers", "2", "--top-solid-layers", "10",
                    "--slowdown-below-layer-time", "0",
                    "--complete-objects", "--extruder-clearance-radius", "55", "--extruder-clearance-height", "20",
                    "--output", raw] + files,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
assert r.returncode == 0, f"PrusaSlicer exit {r.returncode}:\n{r.stdout[-800:]}"

L = open(raw).read().split("\n")
out, n_ins = [], 0
for l in L:
    out.append(l)
    if l.startswith("EXCLUDE_OBJECT_START"):
        em = int(re.search(r"EM_(\d{4})", l).group(1)) / 1000
        out += [f"M221 S{em * 100:.0f}", f"M117 EM {em:.2f}"]; n_ins += 1
    elif l.startswith("EXCLUDE_OBJECT_END"):
        out.append("M221 S100")
i = next(i for i, l in enumerate(out) if l.startswith("PRINT_END"))
out[i:i] = ["M221 S100"]
rows = " | ".join(f"Y{cy}: " + " ".join(f"{em:.2f}" for em, _, y in plan if y == cy) for cy in (70, 160, 250))
hdr = [f"; ===== Ellis EM cubes ({a.filament}), labelled underside, ONE AT A TIME. Left->right {rows} =====",
       "; EM per cube via M221 (slicer EM from the filament profile). Infill 40%, bottom 2, top 10."]
open(a.out, "w").write("\n".join(hdr + out))
temps = re.search(r"^PRINT_START.*$", "\n".join(L), re.M).group(0)
print(f"{a.out}: {len(plan)} cubes, M221 inserts {n_ins}, {temps}")
print(rows)
