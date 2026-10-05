#!/usr/bin/env python3
"""Adapt an Ellis PA-tool file generated for the SV08 (200 mm bed) to the Voron 2.4 350.

- Translates the pattern so it is centred on the 350 bed.
- Replaces G10/G11 with explicit retract moves (the Voron has no [firmware_retraction]).
- Rescales E from the SV08's EM 0.9475 to the Voron profile's EM 1.0.
- Swaps temps to Silk PLA @Voron24, restores the config PA at the end.
- Adds EXCLUDE_OBJECT_DEFINE so PRINT_START's adaptive mesh only covers the pattern.
"""
import re, sys
src, dst = sys.argv[1], sys.argv[2]
DX = DY = 75.0
E_SCALE = 1.0 / 0.9475
RETRACT, F_RETRACT = 0.6, 2100
PA_RESTORE = 0.055
lines = open(src).read().splitlines()

def shift(m):
    ax, v = m.group(1), float(m.group(2))
    return f"{ax}{v + (DX if ax == 'X' else DY):.4f}"

out, xs, ys, first_g10 = [], [], [], True
for ln in lines:
    code, sep, cmt = ln.partition(';')
    c = code.strip()
    if c.startswith('PRINT_START'):
        out.append("PRINT_START EXTRUDER=210 BED=60")
        continue
    if c == 'G10':
        if first_g10:                       # PURGE_LINE already left the filament retracted
            first_g10 = False
            out.append("; (initial retract skipped: PURGE_LINE ends retracted)")
            continue
        out.append(f"G1 E-{RETRACT} F{F_RETRACT} ; Retract")
        continue
    if c == 'G11':
        out.append(f"G1 E{RETRACT} F{F_RETRACT} ; Un-retract")
        continue
    if 'back to start value' in cmt and c.startswith('SET_PRESSURE_ADVANCE'):
        out.append(f"SET_PRESSURE_ADVANCE ADVANCE={PA_RESTORE} EXTRUDER=extruder ; Restore config PA")
        continue
    if re.match(r'G[01] ', c):
        c = re.sub(r'([XY])(-?\d+\.?\d*)', shift, c)
        c = re.sub(r'E(-?\d+\.?\d*)', lambda m: f"E{float(m.group(1)) * E_SCALE:.5f}", c)
        xs += [float(v) for v in re.findall(r'X(-?[\d.]+)', c)]
        ys += [float(v) for v in re.findall(r'Y(-?[\d.]+)', c)]
        out.append(c + (' ;' + cmt if sep else ''))
        continue
    out.append(ln)

x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
assert 30 <= x0 and x1 <= 350 and 25 <= y0 and y1 <= 350, (x0, x1, y0, y1)
hdr = [
    "; ### Adapted for Voron 2.4 350 from pa_pattern_sv08_pla.gcode ###",
    f"; shifted X+{DX} Y+{DY}; G10/G11 -> E-/+{RETRACT} @ {F_RETRACT // 60} mm/s; E x{E_SCALE:.4f} (EM 0.9475 -> 1.0)",
    "; Silk PLA 210/60; config PA 0.055 restored at end",
    f"EXCLUDE_OBJECT_DEFINE NAME=pa_pattern CENTER={(x0+x1)/2:.2f},{(y0+y1)/2:.2f} "
    f"POLYGON=[[{x0:.2f},{y0:.2f}],[{x1:.2f},{y0:.2f}],[{x1:.2f},{y1:.2f}],[{x0:.2f},{y1:.2f}]]",
]
# wrap the body (after PRINT_START, before PRINT_END) in the object
i_start = next(i for i, l in enumerate(out) if l.startswith('PRINT_START'))
i_end = next(i for i, l in enumerate(out) if l.startswith('PRINT_END'))
out = (hdr + out[:i_start + 1] + ["EXCLUDE_OBJECT_START NAME=pa_pattern"] +
       out[i_start + 1:i_end] + ["EXCLUDE_OBJECT_END NAME=pa_pattern"] + out[i_end:])
open(dst, 'w').write("\n".join(out) + "\n")
print(f"X {x0:.2f}..{x1:.2f}  Y {y0:.2f}..{y1:.2f}  lines {len(out)}")
