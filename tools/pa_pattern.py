#!/usr/bin/env python3
"""Ellis-style pressure-advance pattern for the Voron 2.4 350 (Klipper).

Nested 90-degree chevrons ("<<<<"), one per PA value, with 3 walls each.
- Layer 1 is printed slowly: an anchor frame, PA x1000 labels, then the chevrons.
- Layers 2-4 are printed at full perimeter speed and accel, which is where PA shows.
Every chevron is preceded by SET_PRESSURE_ADVANCE. The config PA is restored at the end.
"""
import math, sys

# ---- test range ----------------------------------------------------------
PA_START, PA_END, PA_STEP = 0.0, 0.08, 0.005
PA_RESTORE = 0.055                     # [extruder] pressure_advance in printer.cfg

# ---- machine / material ---------------------------------------------------
BED_T, HOTEND_T = 60, 210              # Silk PLA @Voron24
CENTER = (175.0, 175.0)
SAFE_X, SAFE_Y = (30.0, 350.0), (25.0, 350.0)   # stepper position_min/max
FIL_AREA = math.pi * (1.75 / 2) ** 2
EM = 1.0

# ---- pattern geometry -----------------------------------------------------
W = 0.45                               # line width
H1, H = 0.25, 0.20                     # first / other layer heights
LAYERS = 4
L = 20.0                               # chevron arm length
WALLS = 3
GAP = 2.0                              # clear gap between chevrons, perpendicular to arms
FRAME_LOOPS = 3
FRAME_CLEAR = 3.0

# ---- speeds (mm/s) / accel --------------------------------------------------
V_FAST, V_L1, V_LABEL, V_TRAVEL, V_Z = 100, 30, 15, 300, 10
ACCEL = 3000                           # perimeter_acceleration in the slicer profile
RETRACT, V_RETRACT = 0.6, 35
ZHOP = 0.4                             # layer-change travel only

S = W - H * (1 - math.pi / 4)          # centre spacing of touching lines
R2 = math.sqrt(2)
ARM = L / R2                           # arm extent in X and in Y
PITCH = (WALLS * S - S + W + GAP) * R2 # X distance between chevron vertices
DIG_W, DIG_H, DIG_GAP = 1.6, 3.2, 1.0  # 7-segment label glyphs

pa_values = []
v = PA_START
while v <= PA_END + 1e-9:
    pa_values.append(round(v, 4))
    v += PA_STEP
N = len(pa_values)

# Pattern block size: from the first vertex to the last arm end.
pat_w = (N - 1) * PITCH + (WALLS - 1) * S * R2 + ARM
label_y_off = ARM + 2.0                # label baseline above the chevron centre line
blk_h_top = label_y_off + DIG_H        # top of labels above the centre line

def label_span(j):
    """(text, left x, width) of the PA x1000 label over chevron j, relative to x0."""
    txt = str(int(round(pa_values[j] * 1000)))
    tw = len(txt) * DIG_W + (len(txt) - 1) * DIG_GAP
    cx = j * PITCH + (WALLS - 1) / 2 * S * R2 + ARM
    return txt, cx - tw / 2, tw


LABELS = list(range(0, N, 2))
# Content extents relative to (x0, yc): chevrons plus labels, then the frame around them.
c_left = min(0.0, min(label_span(j)[1] for j in LABELS)) - W / 2
c_right = max(pat_w, max(label_span(j)[1] + label_span(j)[2] for j in LABELS)) + W / 2
in_w = c_right - c_left + 2 * FRAME_CLEAR
in_h = ARM + blk_h_top + 2 * FRAME_CLEAR
fx0, fy0 = CENTER[0] - in_w / 2, CENTER[1] - in_h / 2
x0 = fx0 + FRAME_CLEAR - c_left        # vertex of chevron 0, wall 0
yc = fy0 + FRAME_CLEAR + ARM           # chevron centre line

# 7-segment glyph strokes on a 1 x 2 grid (origin bottom-left)
GLYPH = {
    '0': [[(0,0),(1,0),(1,2),(0,2),(0,0)]],
    '1': [[(1,0),(1,2)]],
    '2': [[(0,2),(1,2),(1,1),(0,1),(0,0),(1,0)]],
    '3': [[(0,2),(1,2),(1,0),(0,0)], [(0,1),(1,1)]],
    '4': [[(0,2),(0,1),(1,1)], [(1,2),(1,0)]],
    '5': [[(1,2),(0,2),(0,1),(1,1),(1,0),(0,0)]],
    '6': [[(1,2),(0,2),(0,0),(1,0),(1,1),(0,1)]],
    '7': [[(0,2),(1,2),(1,0)]],
    '8': [[(0,0),(1,0),(1,2),(0,2),(0,0)], [(0,1),(1,1)]],
    '9': [[(0,0),(1,0),(1,2),(0,2),(0,1),(1,1)]],
}


class G:
    def __init__(self):
        self.out, self.x, self.y, self.z = [], None, None, 0.0
        self.e_total, self.t = 0.0, 0.0
        self.retracted = True          # PURGE_LINE ends retracted, Z2
        self.path = []                 # (layer, kind, x1, y1, x2, y2) for plotting
        self.layer = 0

    def emit(self, s):
        self.out.append(s)

    def retract(self):
        if not self.retracted:
            self.emit(f"G1 E-{RETRACT:.2f} F{V_RETRACT*60}")
            self.retracted = True

    def unretract(self):
        if self.retracted:
            self.emit(f"G1 E{RETRACT:.2f} F{V_RETRACT*60}")
            self.retracted = False

    def travel(self, x, y, retract_over=1.0):
        d = math.hypot(x - self.x, y - self.y) if self.x is not None else 99
        if d < 1e-6:
            return
        if d > retract_over:
            self.retract()
        self.emit(f"G0 X{x:.3f} Y{y:.3f} F{V_TRAVEL*60}")
        if self.x is not None:
            self.path.append((self.layer, 't', self.x, self.y, x, y))
        self.t += d / V_TRAVEL
        self.x, self.y = x, y

    def extrude(self, x, y, h, v):
        d = math.hypot(x - self.x, y - self.y)
        self.unretract()
        area = (W - h) * h + math.pi * (h / 2) ** 2
        e = EM * area * d / FIL_AREA
        self.emit(f"G1 X{x:.3f} Y{y:.3f} E{e:.5f} F{v*60}")
        self.path.append((self.layer, 'e', self.x, self.y, x, y))
        self.e_total += e
        self.t += d / v
        self.x, self.y = x, y

    def polyline(self, pts, h, v, retract_over=1.0):
        self.travel(*pts[0], retract_over=retract_over)
        for p in pts[1:]:
            self.extrude(*p, h, v)


def chevron_walls(j):
    """Wall polylines for chevron j, alternating direction so wall-to-wall hops are tiny."""
    walls = []
    for i in range(WALLS):
        vx = x0 + j * PITCH + i * S * R2
        top, vert, bot = (vx + ARM, yc + ARM), (vx, yc), (vx + ARM, yc - ARM)
        k = j * WALLS + i                     # global wall index -> alternate direction
        walls.append([top, vert, bot] if k % 2 == 0 else [bot, vert, top])
    return walls


def build():
    g = G()
    e = g.emit
    e("; Pressure advance pattern (Ellis-style), generated for Voron 2.4 350")
    e(f"; PA {PA_START}..{PA_END} step {PA_STEP} ({N} chevrons), labels = PA x 1000")
    e(f"; fast layers: {V_FAST} mm/s @ {ACCEL} mm/s^2, line {W} x {H} mm, {LAYERS} layers")
    pmin_x, pmax_x = fx0 - FRAME_LOOPS * S, fx0 + in_w + FRAME_LOOPS * S
    pmin_y, pmax_y = fy0 - FRAME_LOOPS * S, fy0 + in_h + FRAME_LOOPS * S
    e(f"EXCLUDE_OBJECT_DEFINE NAME=pa_pattern CENTER={CENTER[0]:.1f},{CENTER[1]:.1f} "
      f"POLYGON=[[{pmin_x:.2f},{pmin_y:.2f}],[{pmax_x:.2f},{pmin_y:.2f}],"
      f"[{pmax_x:.2f},{pmax_y:.2f}],[{pmin_x:.2f},{pmax_y:.2f}]]")
    e(f"PRINT_START EXTRUDER={HOTEND_T} BED={BED_T}")
    e("G90")
    e("M83")
    e("G92 E0")
    e("M106 S0")
    e(f"SET_VELOCITY_LIMIT ACCEL={ACCEL}")
    e("EXCLUDE_OBJECT_START NAME=pa_pattern")

    z = 0.0
    for layer in range(LAYERS):
        g.layer = layer
        h = H1 if layer == 0 else H
        z = round(z + h, 3)
        g.retract()
        e(f";LAYER:{layer} Z={z}")
        if layer == 0:
            g.travel(fx0, fy0)                         # at PURGE_LINE's Z2
        else:
            e(f"G1 Z{z + ZHOP:.3f} F{V_Z*60}")
            g.travel(*chevron_walls(0)[0][0])
        e(f"G1 Z{z:.3f} F{V_Z*60}")
        g.z = z
        if layer == 1:
            e("M106 S255")
        if layer == 0:
            e(f"SET_PRESSURE_ADVANCE ADVANCE={PA_RESTORE}")
            e("M117 PA test: frame")
            for k in range(FRAME_LOOPS):
                o = k * S
                a, b = fx0 - o, fy0 - o
                c, d = fx0 + in_w + o, fy0 + in_h + o
                g.polyline([(a, b), (c, b), (c, d), (a, d), (a, b + S * 0.5)], h, V_L1)
            e("M117 PA test: labels")
            for j in LABELS:
                txt, lx, _ = label_span(j)
                lx, ly = x0 + lx, yc + label_y_off
                for ci, ch in enumerate(txt):
                    gx = lx + ci * (DIG_W + DIG_GAP)
                    for stroke in GLYPH[ch]:
                        pts = [(gx + px * DIG_W, ly + py * DIG_H / 2) for px, py in stroke]
                        g.polyline(pts, h, V_LABEL, retract_over=1.5)
        v = V_L1 if layer == 0 else V_FAST
        for j, pa in enumerate(pa_values):
            walls = chevron_walls(j)
            g.travel(*walls[0][0])                     # retracts if > 1 mm
            e(f"SET_PRESSURE_ADVANCE ADVANCE={pa:.4f}")
            if layer > 0:
                e(f"M117 L{layer+1}/{LAYERS} PA {pa:.3f}")
            for w_pts in walls:
                g.polyline(w_pts, h, v)
    g.retract()
    e("EXCLUDE_OBJECT_END NAME=pa_pattern")
    e(f"SET_PRESSURE_ADVANCE ADVANCE={PA_RESTORE}")
    e("M107")
    e("PRINT_END")
    e(f"; filament used [mm] = {g.e_total:.1f}")
    e(f"; estimated move time (excl. start) = {g.t/60:.1f} min")
    return g


if __name__ == "__main__":
    g = build()
    xs = [c for p in g.path for c in (p[2], p[4])]
    ys = [c for p in g.path for c in (p[3], p[5])]
    print(f"N={N} pitch={PITCH:.3f} S={S:.3f} frame_in={in_w:.1f}x{in_h:.1f}")
    print(f"X {min(xs):.2f}..{max(xs):.2f}  Y {min(ys):.2f}..{max(ys):.2f}")
    print(f"E {g.e_total:.1f} mm  moves {g.t/60:.1f} min  lines {len(g.out)}")
    assert SAFE_X[0] <= min(xs) and max(xs) <= SAFE_X[1], "X out of range"
    assert SAFE_Y[0] <= min(ys) and max(ys) <= SAFE_Y[1], "Y out of range"
    out = sys.argv[1] if len(sys.argv) > 1 else "PA_Pattern_Voron.gcode"
    open(out, "w").write("\n".join(g.out) + "\n")
    if len(sys.argv) > 2:                               # optional preview PNG
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(1, 2, figsize=(16, 7))
        for ax, lay in zip(axs, (0, 1)):
            for (ly, k, a, b, c, d) in g.path:
                if ly != lay:
                    continue
                if k == 'e':
                    ax.plot([a, c], [b, d], 'k-', lw=1.2)
                else:
                    ax.plot([a, c], [b, d], 'r:', lw=0.5)
            ax.set_aspect('equal'); ax.set_title(f"layer {lay+1}")
        fig.tight_layout(); fig.savefig(sys.argv[2], dpi=110)
        print("preview", sys.argv[2])
