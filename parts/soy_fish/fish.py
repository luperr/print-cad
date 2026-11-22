"""Soy fish lamp shade: a faithful, crisp re-creation of the sushi soy-sauce fish, built as a smooth
single-wall shell for spiral vase mode in clear PETG.

Run:  PYTHONPATH=. uv run python parts/soy_fish/fish.py
Out:  out/soy_fish.stl, out/soy_fish.3mf

Shape and markings follow the downloaded model (imports/soy_fish_lamp, Fish.stl), which replicates
the real soy fish: body outline, fin tabs, 4 rows of scales, double gill band, eye, three pectoral
fin bars, the プラ recycling mark (one side only) and the two-lobed tail. Positions below were
measured from that mesh (see README.md) and are given in the ORIGINAL's coordinates (Z_orig = -105
at the mouth, +105 at the tail tip); `oz()` converts them to this model's Z.

Changes from the original, all for vase-mode printing:
  * a 10 mm neck below the mouth plugs into the thread ring (crush ribs, no glue) instead of a glued butt joint;
  * the 25 mm pinch into the tail stem is stretched by 6 mm (it was up to 60 deg steep);
  * the tail lobe gets thinner toward its tip (side view only) so the top can close;
  * raised edges are shaped to <= ~55 deg instead of vertical, so a single line can follow them.

Why a mesh generator and not build123d: the fish is one blended organic surface. It is built as a
stack of horizontal cross-sections (rounded-oval body + flat fin tabs), each pushed outward by the
surface details. That guarantees every layer is exactly one closed outline, which vase mode needs.

Model axes (as printed, mouth down): Z up; X = back (+X, dorsal) to belly (-X); Y = flanks.
The model is a closed solid: slice it with spiral vase ON and bottom shell layers = 0.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter, gaussian_filter1d, map_coordinates

from lib.printing import CLEARANCE_FIT, CRUSH_RIB, HOLE_COMP, check_bed

HERE = Path(__file__).resolve().parent

# --- Interface with the original thread ring ("Screw" in the download) --------------------
# The ring stays screwed into the cap; the fish plugs into it (no glue) and can be lifted off.
RING_BORE_MIN = 37.76        # mm, narrowest measured bore of the thread ring (r 18.88-19.11)
# Neck radius: fit clearance, plus half the usual printed-hole shrink because the ring's bore
# is itself a printed hole. Leaves ~0.3 mm per side, taken up by the crush ribs below.
SPIGOT_R = RING_BORE_MIN / 2 - CLEARANCE_FIT - HOLE_COMP / 2
# Vertical crush ribs on the neck: press lightly into the (printed, slightly small) bore so the
# fish sits snug and can't spin. The thin vase wall flexes, so the fit tolerates print variation.
RIB_R = RING_BORE_MIN / 2 - HOLE_COMP / 2 + CRUSH_RIB   # mm, radius over the rib tops
RIB_COUNT = 6
RIB_W = 2.5                  # mm, rib width
RIB_LEAD_IN = 2.5            # mm, ribs ramp up from the bottom so the neck starts easily
SPIGOT_DEPTH = 10.0          # mm, neck length inside the ring; the fish body starts here
VASE_LINE_W = 0.70           # mm, slicer line width this is designed for (reporting only)

# --- Mapping original -> this model --------------------------------------------------------
ORIG_OFFSET = 114.94         # mm, original Z -104.94 (mouth) sits on the ring top at Z=10
STRETCH_Z0, STRETCH_Z1 = 155.0, 179.0   # mm (model Z before stretch), the pinch into the tail stem
STRETCH = 1.40               # that band is 40% taller (~9.6 mm) so its walls are printable
TAIL_SHIFT = (STRETCH_Z1 - STRETCH_Z0) * (STRETCH - 1)


def stretch(z):
    z = np.asarray(z, float)
    return np.where(z <= STRETCH_Z0, z,
                    np.where(z <= STRETCH_Z1, STRETCH_Z0 + (z - STRETCH_Z0) * STRETCH, z + TAIL_SHIFT))


def oz(z_orig):
    """Original model Z -> this model's Z."""
    return stretch(np.asarray(z_orig, float) + ORIG_OFFSET)


# --- Body + fin tabs, measured from the original every 3 mm -------------------------------
# z (model, before stretch), back edge (+X), belly edge (-X), half-thickness (Y),
# back tab height, belly tab height, back tab thickness, belly tab thickness.
# Body edges are the rounded-oval body without the tabs. Tab heights include ~1.5 mm of
# measuring baseline that is removed in _profile().
MEASURED = np.array([
    [14.9, 23.2, 24.9, 21.2, 2.2, 1.7, 13.4, 12.7],  # (mouth rim at 11.9 is replaced by the shoulder)
    [17.9, 27.6, 28.7, 21.3, 1.5, 1.5, 14.3, 13.3], [20.9, 30.9, 31.9, 22.9, 1.4, 1.5, 15.0, 15.9],
    [23.9, 33.6, 35.2, 24.7, 1.8, 1.2, 14.7, 16.4], [26.9, 36.5, 37.8, 26.4, 1.7, 1.4, 15.1, 13.1],
    [29.9, 39.7, 40.3, 28.3, 1.3, 1.4, 17.3, 13.8], [32.9, 42.1, 42.5, 29.8, 1.5, 1.8, 14.9, 15.3],
    [35.9, 44.6, 45.5, 31.1, 1.3, 1.1, 17.7, 16.5], [38.9, 46.6, 47.9, 31.8, 1.6, 1.1, 15.0, 16.3],
    [41.9, 48.8, 50.0, 32.6, 1.7, 1.1, 15.8, 16.7], [44.9, 51.4, 52.0, 33.5, 1.1, 1.1, 18.3, 16.8],
    [47.9, 53.3, 53.7, 34.3, 1.2, 1.5, 18.2, 16.7], [50.9, 55.0, 56.0, 35.1, 1.4, 1.0, 18.1, 16.8],
    [53.9, 57.0, 57.5, 36.5, 1.1, 1.3, 18.4, 18.8], [56.9, 58.3, 59.3, 36.4, 1.4, 1.2, 18.9, 18.6],
    [59.9, 60.0, 61.0, 36.3, 1.3, 0.9, 18.2, 17.5], [62.9, 61.7, 62.2, 36.5, 0.8, 1.0, 16.4, 17.6],
    [65.9, 62.1, 63.5, 36.7, 1.7, 2.0, 15.6, 13.2], [68.9, 63.2, 64.5, 37.0, 1.8, 5.3, 15.8, 11.4],
    [71.9, 64.6, 65.7, 37.0, 1.7, 8.0, 15.0, 13.1], [74.9, 66.0, 66.5, 37.0, 2.2, 8.7, 12.2, 13.5],
    [77.9, 66.4, 67.3, 37.0, 4.7, 8.4, 12.2, 13.6], [80.9, 67.3, 67.4, 37.0, 6.6, 8.8, 13.3, 13.7],
    [83.9, 67.7, 68.1, 36.9, 7.6, 8.5, 13.6, 13.8], [86.9, 67.6, 68.5, 36.7, 8.5, 8.5, 13.8, 13.9],
    [89.9, 67.8, 68.8, 36.5, 8.8, 8.0, 13.9, 13.7], [92.9, 68.4, 69.1, 36.3, 8.5, 6.3, 13.7, 13.3],
    [95.9, 69.0, 68.7, 36.1, 8.0, 4.0, 14.0, 12.6], [98.9, 68.5, 68.2, 35.8, 8.5, 1.6, 14.0, 15.7],
    [101.9, 68.5, 68.3, 35.5, 8.4, 0.7, 13.9, 18.0], [104.9, 68.1, 68.0, 35.1, 8.5, 0.7, 13.8, 18.2],
    [107.9, 67.8, 67.2, 34.7, 8.5, 1.0, 13.7, 20.3], [110.9, 67.3, 66.6, 34.6, 8.7, 1.1, 13.6, 18.6],
    [113.9, 66.9, 66.1, 34.7, 8.5, 1.1, 13.6, 17.9], [116.9, 66.1, 65.4, 34.6, 8.7, 1.7, 13.4, 13.9],
    [119.9, 65.1, 64.7, 33.3, 9.1, 4.3, 13.2, 12.3], [122.9, 64.3, 64.0, 32.1, 9.0, 6.5, 13.1, 12.6],
    [125.9, 63.3, 63.0, 31.4, 9.2, 7.9, 13.0, 12.6], [128.9, 62.2, 61.9, 31.3, 9.3, 8.6, 12.9, 12.6],
    [131.9, 61.3, 59.8, 31.3, 9.0, 9.9, 12.8, 12.2], [134.9, 60.1, 57.4, 30.4, 9.1, 11.2, 12.5, 12.3],
    [137.9, 58.4, 57.0, 27.9, 9.3, 10.2, 12.3, 11.9], [140.9, 56.3, 55.8, 27.0, 9.8, 9.9, 12.0, 11.6],
    [143.9, 55.5, 53.9, 26.5, 8.9, 10.0, 11.3, 11.3], [146.9, 53.4, 52.2, 26.2, 9.0, 9.8, 11.3, 11.2],
    [149.9, 51.6, 48.6, 24.7, 8.6, 11.5, 10.8, 10.7], [152.9, 49.6, 47.0, 22.6, 7.8, 11.0, 10.3, 10.4],
    [155.9, 46.0, 44.0, 21.3, 8.4, 11.7, 9.7, 9.9], [158.9, 43.4, 41.2, 20.4, 7.3, 12.1, 8.7, 9.6],
    [161.9, 40.9, 37.3, 19.5, 5.1, 13.3, 7.9, 8.8], [164.9, 37.7, 35.6, 17.4, 2.3, 11.3, 9.6, 8.4],
    [167.9, 32.7, 31.9, 15.2, 3.3, 8.8, 9.4, 7.6], [170.9, 30.2, 26.4, 13.3, 1.8, 6.7, 10.3, 7.6],
    [173.9, 23.9, 20.5, 11.2, 3.1, 4.4, 9.4, 7.9], [176.9, 18.4, 16.5, 8.6, 2.7, 4.4, 6.3, 5.3],
])
TAB_BASELINE = 1.5           # mm, measuring baseline in the tab columns
TAB_SMOOTH = 1.7             # rows (x3 mm): softens where fin tabs start and end, for vase mode
# Tail (already in final model Z): z, half-width, half-thickness. Original thickness is kept up to
# the widest point, then thinned so the lobe's rounded top closes on a thin, near-solid fin.
TAIL = np.array([
    [oz(64.0), 18.5, 6.1], [oz(68.0), 19.2, 4.4], [oz(72.0), 20.9, 5.1], [oz(76.0), 22.4, 6.1],
    [oz(80.0), 23.6, 7.2], [oz(84.0), 24.5, 8.3], [oz(88.0), 24.9, 9.0], [oz(92.0), 24.2, 8.2],
    [oz(96.0), 22.0, 5.0], [oz(100.0), 17.4, 2.2],
])
TOP_Z = float(oz(105.0))     # tail tip
TAIL_MIN_HALF_T = 1.15       # mm, thinnest tail half-thickness (two vase lines + a hairline gap)

# --- Surface details (original coordinates; heights in mm) --------------------------------
# Scales: crescent-topped wedges that rise toward the tail and end in a crisp upper edge.
SCALE_ROWS = [  # (Z of the upper edge at its middle, X centres)
    (3.4, (-49.0, -24.5, 0.0, 24.5, 49.0)),
    (19.0, (-36.7, -12.5, 12.5, 36.7)),
    (33.8, (-25.0, 0.0, 25.0)),
    (48.5, (-13.4, 13.4)),
]
SCALE_HALF_W = 12.0          # half width of a scale (neighbours touch)
SCALE_ARC = 6.5              # rise of the arched upper edge from its ends to its middle
SCALE_RAMP = 8.0             # length of the rising face below the edge
SCALE_EDGE = 3.5             # length of the drop above the edge (crisp but printable)
SCALE_H = 2.0                # height at the edge

EYE = (21.6, -83.2)          # centre (X, Z)
EYE_RING_R, EYE_RING_H, EYE_RING_S = 8.8, 1.5, 1.75
EYE_DOME_R, EYE_DOME_H = 4.4, 2.0

GILL_Z, GILL_SAG, GILL_X = -61.8, 3.5, (-41.0, 43.0)  # main band: Z at X=0, droop at the ends, X span
GILL_H, GILL_S = 1.1, 1.8
GILL_COVER_H = 0.45          # head side of the band sits this much proud
GILL2_Z, GILL2_SAG, GILL2_H, GILL2_S = -54.0, 2.5, 0.7, 0.9   # thin upper line, in two segments
GILL2_SEGMENTS = ((-40.0, -14.0), (14.0, 40.0))

BARS_X = (-53.5, -45.0, -36.5)  # pectoral fin bars (X at mid height)
BARS_Z = (-43.0, -19.5)      # bottom and top
BAR_LEAN = -3.0              # top end shifts this much in X
BAR_HALF_W, BAR_H = 1.7, 1.3

TAIL_LINE_Z, TAIL_LINE_HALF_X, TAIL_LINE_H = 59.0, 18.0, 0.6   # faint line at the tail stem

TAIL_FAN_ORIGIN = (0.0, 66.0)  # tail lobes radiate from here (X, Z)
TAIL_LOBE_ANG = (0.06, 0.62)   # lobe angle range from vertical, radians (each side)
TAIL_LOBE_H = 1.3

MARK_CENTRE = (0.0, -30.5)   # プラ mark centre (X, Z) on the +Y flank
MARK_H = 0.9
MARK_ON = True

# --- Mesh resolution ---------------------------------------------------------------------
N_AROUND = 1000              # points per cross-section
DZ = 0.35                    # mm between cross-sections


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def band(x, x0, x1, x2, x3):
    return smoothstep(x0, x1, x) * (1 - smoothstep(x2, x3, x))


def _profile():
    """Interpolators for the body edges, half-thickness and fin tabs (final model Z)."""
    m = MEASURED.copy()
    m[:, 1:] = gaussian_filter1d(m[:, 1:], 0.8, axis=0, mode="nearest")
    m[:, 4:6] = gaussian_filter1d(m[:, 4:6], TAB_SMOOTH, axis=0, mode="nearest")

    def tab(h):
        return np.clip(h - TAB_BASELINE, 0, None) * smoothstep(2.4, 3.6, h)

    z = np.concatenate([stretch(m[:, 0]), TAIL[:, 0]])
    cols = [np.concatenate([m[:, 1], TAIL[:, 1]]), np.concatenate([m[:, 2], TAIL[:, 1]]),
            np.concatenate([m[:, 3], TAIL[:, 2]]),
            np.concatenate([tab(m[:, 4]), np.zeros(len(TAIL))]),
            np.concatenate([tab(m[:, 5]), np.zeros(len(TAIL))]),
            np.concatenate([m[:, 6], np.full(len(TAIL), 6.0)]),
            np.concatenate([m[:, 7], np.full(len(TAIL), 6.0)])]
    return z, [PchipInterpolator(z, c) for c in cols]


def section_params(z: np.ndarray) -> dict:
    zs, (back, belly, half_t, tab_b, tab_v, tab_bt, tab_vt) = _profile()
    p = {k: np.zeros_like(z) for k in ("a", "b", "cx", "tab_b", "tab_v", "tab_bt", "tab_vt")}
    neck = z <= SPIGOT_DEPTH
    p["a"][neck] = p["b"][neck] = SPIGOT_R
    sh = (z > SPIGOT_DEPTH) & (z < zs[0])          # seating shoulder up to the first measured row
    f = (z[sh] - SPIGOT_DEPTH) / (zs[0] - SPIGOT_DEPTH)
    p["a"][sh] = SPIGOT_R + (float(back(zs[0]) + belly(zs[0])) / 2 - SPIGOT_R) * f
    p["b"][sh] = SPIGOT_R + (float(half_t(zs[0])) - SPIGOT_R) * f
    p["cx"][sh] = float(back(zs[0]) - belly(zs[0])) / 2 * f
    body = (z >= zs[0]) & (z <= zs[-1])
    zb = z[body]
    p["a"][body] = (back(zb) + belly(zb)) / 2
    p["cx"][body] = (back(zb) - belly(zb)) / 2
    p["b"][body] = half_t(zb)
    for k, fn in (("tab_b", tab_b), ("tab_v", tab_v), ("tab_bt", tab_bt), ("tab_vt", tab_vt)):
        p[k][body] = np.clip(fn(zb), 0, None)
    top = z > zs[-1]
    p["a"][top] = TAIL[-1, 1] * np.sqrt(np.clip((TOP_Z - z[top]) / (TOP_Z - zs[-1]), 0, 1))
    p["a"] = np.maximum(p["a"], np.where(top, 1.6, 0))
    p["b"][top] = TAIL[-1, 2]
    p["b"] = np.maximum(p["b"], np.where(z > oz(90), TAIL_MIN_HALF_T, 0))
    # body cross-section is a slightly boxy oval; round at the mouth and in the tail
    p["n"] = 2.0 + 0.45 * band(z, 18, 45, float(oz(40)), float(oz(60)))
    return p


def _mark_sampler():
    if not MARK_ON:
        return None
    d = np.load(HERE / "pura_mark.npz")
    res = float(d["res"])
    soft = gaussian_filter(d["mask"].astype(float), 0.35 / res)   # ~45 deg edges, not cliffs
    u0, v0 = float(d["u"][0]), float(d["v"][0])

    def sample(X, Z):
        u = -(X - MARK_CENTRE[0])                   # seen from +Y, model +X is on the left
        v = Z - oz(MARK_CENTRE[1])
        return map_coordinates(soft, [(v - v0) / res, (u - u0) / res], order=1, cval=0.0)
    return sample


def scales(X, Z):
    best = np.zeros_like(X)
    for z_edge0, xs in SCALE_ROWS:
        for xc in xs:
            dx = X - xc
            u = np.clip(np.abs(dx) / SCALE_HALF_W, 0, 1)
            ze = oz(z_edge0 - SCALE_ARC * (1 - np.sqrt(1 - u * u)))   # half-disc (scallop) edge
            s = ze - Z                               # >0 below the edge, <0 above
            prof = np.where(s >= 0, 1 - smoothstep(0.0, SCALE_RAMP, s), 1 - smoothstep(0.0, SCALE_EDGE, -s))
            lat = (1 - smoothstep(0.55, 1.0, u)) ** 0.7  # rounded, dying away toward the sides
            best = np.maximum(best, prof * lat)
    return SCALE_H * best


def displacement(P, X, Yb, Z, mark):
    """Outward displacement (mm) of the body surface at (X, Yb, Z)."""
    rel_y = np.abs(Yb) / np.maximum(P["b"], 1e-6)
    flank = smoothstep(0.35, 0.62, rel_y)
    d = np.zeros_like(X)

    # fin tabs: flat-topped flanges along the back and belly edges
    for h, thick, side in ((P["tab_b"], P["tab_bt"], 1), (P["tab_v"], P["tab_vt"], -1)):
        half = np.maximum(thick / 2, 2.0)
        d += (side * (X - P["cx"]) > 0) * h * (1 - smoothstep(half - 1.6, half + 0.2, np.abs(Yb)))

    # double gill band + slightly proud gill cover on the head side
    zg = oz(GILL_Z - GILL_SAG * (X / 42.0) ** 2)
    gill = GILL_H * np.exp(-((Z - zg) / GILL_S) ** 2) * band(X, GILL_X[0] - 1, GILL_X[0] + 3,
                                                             GILL_X[1] - 3, GILL_X[1] + 1)
    gill += GILL_COVER_H * (1 - smoothstep(zg - 1.5, zg + 1.2, Z)) * smoothstep(oz(-100), oz(-94), Z) \
        * band(X, GILL_X[0] - 6, GILL_X[0] + 2, GILL_X[1] - 2, GILL_X[1] + 6)
    zg2 = oz(GILL2_Z - GILL2_SAG * (X / 40.0) ** 2)
    for x0, x1 in GILL2_SEGMENTS:
        gill += GILL2_H * np.exp(-((Z - zg2) / GILL2_S) ** 2) * band(X, x0 - 0.5, x0 + 2, x1 - 2, x1 + 0.5)
    d += flank * gill

    # eye: raised ring + dome
    r = np.hypot(X - EYE[0], Z - oz(EYE[1]))
    eye = EYE_RING_H * np.exp(-((r - EYE_RING_R) / EYE_RING_S) ** 2)
    eye += EYE_DOME_H * np.clip(1 - (r / EYE_DOME_R) ** 2, 0, 1) ** 1.5
    d += flank * eye

    d += flank * scales(X, Z)

    # three slanted pectoral fin bars
    zb0, zb1 = oz(BARS_Z[0]), oz(BARS_Z[1])
    f = np.clip((Z - zb0) / (zb1 - zb0), 0, 1)
    for xb in BARS_X:
        xc = xb + BAR_LEAN * (f - 0.5)
        across = 1 - smoothstep(BAR_HALF_W - 0.9, BAR_HALF_W + 0.5, np.abs(X - xc))
        d += flank * BAR_H * across * band(Z, zb0 - 1.0, zb0 + 1.5, zb1 - 1.5, zb1 + 1.0)

    # faint line where the body meets the tail stem
    d += flank * TAIL_LINE_H * np.exp(-((Z - oz(TAIL_LINE_Z)) / 1.0) ** 2) \
        * (1 - smoothstep(TAIL_LINE_HALF_X - 3, TAIL_LINE_HALF_X, np.abs(X)))

    # tail: two raised fan lobes with a groove down the middle
    ox, oz0 = TAIL_FAN_ORIGIN[0], oz(TAIL_FAN_ORIGIN[1])
    ang = np.arctan2(np.abs(X - ox), np.maximum(Z - oz0, 1e-3))
    lobe = band(ang, TAIL_LOBE_ANG[0] - 0.03, TAIL_LOBE_ANG[0] + 0.05, TAIL_LOBE_ANG[1] - 0.12, TAIL_LOBE_ANG[1])
    lobe *= smoothstep(5.0, 12.0, np.hypot(X - ox, Z - oz0)) * (Z > oz0)
    d += smoothstep(0.25, 0.5, rel_y) * TAIL_LOBE_H * lobe

    # プラ recycling mark, +Y flank only
    if mark is not None:
        d += (Yb > 0) * flank * MARK_H * mark(X, Z)
    return d


def build() -> trimesh.Trimesh:
    z = np.unique(np.concatenate([np.arange(0.0, TOP_Z - 0.3, DZ), [SPIGOT_DEPTH, TOP_Z - 0.3]]))
    p = section_params(z)
    t = np.linspace(0, 2 * np.pi, N_AROUND, endpoint=False)
    T, Zg = np.meshgrid(t, z)
    P = {k: np.broadcast_to(v[:, None], T.shape) for k, v in p.items()}
    c, s = np.cos(T), np.sin(T)
    e = 2.0 / P["n"]
    cu, su = np.sign(c) * np.abs(c) ** e, np.sign(s) * np.abs(s) ** e      # superellipse point
    Xb, Yb = P["cx"] + P["a"] * cu, P["b"] * su
    nx = np.sign(cu) * np.abs(cu) ** (P["n"] - 1) / P["a"]                  # its outward normal
    ny = np.sign(su) * np.abs(su) ** (P["n"] - 1) / P["b"]
    nn = np.hypot(nx, ny)
    D = displacement(P, Xb, Yb, Zg, _mark_sampler())
    D[z <= SPIGOT_DEPTH + 1.0] = 0.0
    # crush ribs on the neck (the neck is round, so t is the angle around it)
    pitch = 2 * np.pi / RIB_COUNT
    off = np.abs(((T - pitch / 2) % pitch) - pitch / 2) * SPIGOT_R      # mm from the nearest rib centre
    rib = (1 - smoothstep(RIB_W / 2 - 0.6, RIB_W / 2, off)) * (RIB_R - SPIGOT_R)
    rib *= smoothstep(0.0, RIB_LEAD_IN, Zg) * (1 - smoothstep(SPIGOT_DEPTH, SPIGOT_DEPTH + 0.5, Zg))
    D = D + rib
    px, py = Xb + D * nx / nn, Yb + D * ny / nn

    nz, nt = T.shape
    verts = np.column_stack([px.ravel(), py.ravel(), Zg.ravel()])
    idx = np.arange(nz * nt).reshape(nz, nt)
    i0, i1 = idx[:-1], np.roll(idx[:-1], -1, axis=1)
    j0, j1 = idx[1:], np.roll(idx[1:], -1, axis=1)
    faces = np.concatenate([np.stack([i0, i1, j1], -1).reshape(-1, 3),
                            np.stack([i0, j1, j0], -1).reshape(-1, 3)])
    bot_c, top_c = len(verts), len(verts) + 1
    verts = np.vstack([verts, [0, 0, z[0]], [px[-1].mean(), py[-1].mean(), z[-1]]])
    faces = np.concatenate([faces,
                            np.column_stack([np.full(nt, bot_c), np.roll(idx[0], -1), idx[0]]),
                            np.column_stack([np.full(nt, top_c), idx[-1], np.roll(idx[-1], -1)])])
    mesh = trimesh.Trimesh(verts, faces, process=True)
    if mesh.volume < 0:
        mesh.invert()
    return mesh


def report(mesh: trimesh.Trimesh) -> dict:
    """Vase-mode checks: steepness of every wall face, single loop per layer, bulb clearance."""
    n, c = mesh.face_normals, mesh.triangles_center
    wall = (c[:, 2] > 0.05) & (c[:, 2] < TOP_Z - 0.6) & (np.abs(n[:, 2]) < 0.999)
    ang = np.degrees(np.arctan2(np.abs(n[wall, 2]), np.hypot(n[wall, 0], n[wall, 1])))
    area = mesh.area_faces[wall]
    zc = c[wall, 2]
    body = zc < TAIL[-1, 0]      # above this the tail edge closes on a thin, near-solid fin
    out = {
        "size_mm": mesh.extents.round(1).tolist(),
        "triangles": len(mesh.faces),
        "watertight": mesh.is_watertight,
        "max_slope_deg_body": round(float(ang[body].max()), 1),
        "worst_z": round(float(zc[body][ang[body].argmax()]), 1),
        "area_over_50deg_pct": round(100 * area[body & (ang > 50)].sum() / area.sum(), 3),
        "area_over_57deg_pct": round(100 * area[body & (ang > 57)].sum() / area.sum(), 3),
        "bulb_clearance_d": round(2 * (SPIGOT_R - VASE_LINE_W), 2),
        "spigot_od": round(2 * SPIGOT_R, 2),
    }
    loops = []
    for zz in np.arange(1.0, TOP_Z - 1, 3.0):
        s = mesh.section(plane_origin=[0, 0, zz], plane_normal=[0, 0, 1])
        loops.append(0 if s is None else len(s.entities))
    out["layers_with_more_than_one_loop"] = int(sum(l != 1 for l in loops))
    return out


part = build()

if __name__ == "__main__":
    from lib import mesh_tools as mt
    for k, v in report(part).items():
        print(f"  {k}: {v}")
    check_bed(tuple(part.extents), "soy_fish")
    mt.export(part, "soy_fish")
