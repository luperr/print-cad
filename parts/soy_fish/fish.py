"""Soy fish lamp shade: a smooth, single-wall shell designed for spiral vase mode in clear PETG.

Run:  PYTHONPATH=. uv run python parts/soy_fish/fish.py
Out:  out/soy_fish.stl, out/soy_fish.3mf

Why a mesh generator and not build123d: the fish is one blended organic surface (body, fins,
scales, eye). Here it is built directly as a dense, smooth surface: a stack of horizontal
cross-sections, each a closed loop pushed outward by the surface details. That construction
guarantees the two things spiral vase mode needs:
  * every layer is exactly one closed outline (no islands), and
  * the outline never moves more than ~1 line width between layers (slopes are checked below).

Coordinates (as printed, mouth down on the bed):
  Z  up, mouth (Z=0) -> tail tip.
  X  dorsal (+X, back fin) to ventral (-X, belly).
  Y  the flat flanks; the eyes look along +Y and -Y.
The model is a closed solid. Slice it with spiral vase ON and bottom shell layers = 0,
which leaves the mouth open and the wall a single line (see README.md).
"""

from __future__ import annotations

import numpy as np
import trimesh
from scipy.interpolate import PchipInterpolator

from lib.printing import CLEARANCE_FIT, HOLE_COMP, check_bed

# --- Interface with the original glued thread ring ("Screw" in the download) -------------
RING_BORE_MIN = 37.76        # mm, narrowest measured bore of the thread ring (r 18.88-19.11)
# Neck radius that slides into the ring: fit clearance, plus half the usual printed-hole
# shrink because the ring's bore is itself a printed hole. Leaves a ~0.3 mm glue gap per side.
SPIGOT_R = RING_BORE_MIN / 2 - CLEARANCE_FIT - HOLE_COMP / 2
SPIGOT_DEPTH = 10.0          # mm, length of neck inside the ring (glue lap)
SHOULDER_TOP = 12.5          # mm, Z where the 40 deg seating shoulder ends
SHOULDER_R = 21.0            # mm, radius at the top of the shoulder (sits on the ring's top edge)
VASE_LINE_W = 0.70           # mm, slicer line width this is designed for (only used for reporting)

# --- Body profile -------------------------------------------------------------------------
# Z, back edge (+X), belly edge (-X), half-thickness (Y). The back is higher and more arched
# than the belly, like a sea bream. Each edge's slope stays <= ~0.85 per mm of height
# (about 40 deg) so a single vase line can follow it.
PROFILE = np.array([
    # z      back   belly  half-t
    [12.5,  21.0,  21.0,  21.0],
    [17.0,  24.3,  24.0,  24.0],   # lip bead around the mouth
    [20.5,  24.6,  23.6,  23.4],   # slight pinch behind the lips
    [30.0,  33.0,  29.0,  26.0],
    [46.0,  47.0,  38.5,  30.0],
    [64.0,  58.5,  46.5,  33.5],
    [82.0,  66.5,  53.0,  36.0],
    [98.0,  71.0,  57.5,  37.0],
    [112.0, 71.5,  59.0,  36.8],
    [126.0, 68.0,  57.0,  35.0],
    [142.0, 59.5,  50.0,  30.5],
    [158.0, 47.5,  40.0,  23.5],
    [174.0, 34.0,  29.0,  14.5],
    [188.0, 22.5,  19.5,   7.5],
    [197.0, 19.0,  17.5,   4.2],   # peduncle (tail stem)
    [206.0, 24.0,  22.0,   2.2],
    [216.0, 33.0,  31.0,   1.3],
    [226.0, 41.0,  40.0,   1.12],
    [229.0, 42.5,  42.5,   1.1],   # tail fin at full spread
])
TOP_Z = 235.0                # mm, tip of the tail's convex top edge
TAIL_MIN_HALF_T = 1.05       # mm, half-thickness floor of the tail fin (2 vase lines + gap)

# --- Surface details (all are outward displacements, in mm) ------------------------------
SCALE_DZ, SCALE_DX = 8.0, 9.4   # lattice row / column pitch
SCALE_R = 7.2                   # scale radius (overlaps neighbours like roof tiles)
SCALE_H = 0.8                   # height of a scale's free (upper) rim
SCALE_Z = (90.0, 172.0)         # scaled band (fades in/out)

EYE_X, EYE_Z = 24.0, 46.0       # eye centre on each flank
EYE_RING_R, EYE_RING_H, EYE_RING_S = 9.5, 1.1, 1.3
EYE_PUPIL_R, EYE_PUPIL_H = 5.6, 1.9

GILL_Z, GILL_BULGE, GILL_SPAN = 57.0, 23.0, 62.0  # gill arc: Z at X=0 is GILL_Z+GILL_BULGE
GILL_H, GILL_S = 0.9, 1.4
GILL_COVER_H = 0.35             # head side of the gill line sits this much proud

PEC_ROOT = (-15.0, 82.0)        # pectoral fin root (X, Z), just behind the gill
PEC_TILT_DEG = -16.0            # fin leans toward the belly
PEC_LEN, PEC_W, PEC_H = 48.0, 11.0, 3.0
PEC_RAY_PITCH = 3.2

DORSAL_Z = (98.0, 122.0, 136.0, 190.0)   # rise start, full, fall start, end
DORSAL_H = 12.0
ANAL_Z = (136.0, 154.0, 158.0, 192.0)
ANAL_H = 7.0
FIN_HALF_T = 1.35               # mm, half thickness of dorsal / anal fins at full height

TAIL_RAY_ORIGIN_Z = 192.0
TAIL_RAY_PITCH_RAD = 0.13
TAIL_RAY_H = 0.45

# --- Mesh resolution ---------------------------------------------------------------------
N_AROUND = 800               # points per cross-section
DZ = 0.45                    # mm between cross-sections


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def band(z, z0, z1, z2, z3):
    """0 below z0, ramps to 1 by z1, stays 1 to z2, ramps to 0 by z3."""
    return smoothstep(z0, z1, z) * (1 - smoothstep(z2, z3, z))


def section_params(z: np.ndarray):
    """Half-width a, half-thickness b, centre offset cx for each Z."""
    a = np.empty_like(z); b = np.empty_like(z); cx = np.zeros_like(z)
    spig = z <= SPIGOT_DEPTH
    a[spig] = b[spig] = SPIGOT_R
    sh = (z > SPIGOT_DEPTH) & (z <= SHOULDER_TOP)
    a[sh] = b[sh] = SPIGOT_R + (SHOULDER_R - SPIGOT_R) * (z[sh] - SPIGOT_DEPTH) / (SHOULDER_TOP - SPIGOT_DEPTH)
    body = (z > SHOULDER_TOP) & (z <= PROFILE[-1, 0])
    back, belly, half_t = (PchipInterpolator(PROFILE[:, 0], PROFILE[:, c])(z[body]) for c in (1, 2, 3))
    a[body], cx[body], b[body] = (back + belly) / 2, (back - belly) / 2, half_t
    top = z > PROFILE[-1, 0]
    zt0 = PROFILE[-1, 0]
    a[top] = PROFILE[-1, 1] * np.sqrt(np.clip((TOP_Z - z[top]) / (TOP_Z - zt0), 0, 1))
    a[top] = np.maximum(a[top], 1.6)
    b[top] = PROFILE[-1, 3]
    b = np.maximum(b, np.where(z > 200, TAIL_MIN_HALF_T, 0))
    return a, b, cx


def scales(X, Z):
    row = np.round(Z / SCALE_DZ)
    best = np.zeros_like(X)
    for dr in (-1, 0, 1):
        r = row + dr
        shift = (r % 2) * 0.5 * SCALE_DX
        col = np.round((X - shift) / SCALE_DX)
        for dc in (-1, 0, 1):
            cxs = (col + dc) * SCALE_DX + shift
            czs = r * SCALE_DZ
            dx, dz = X - cxs, Z - czs
            rho = np.sqrt(dx * dx + dz * dz) / SCALE_R
            plate = 1 - smoothstep(0.62, 1.0, rho)                 # flat tile, soft edge
            tilt = 0.25 + 0.75 * smoothstep(-0.9, 0.7, dz / SCALE_R)  # free rim toward the tail
            best = np.maximum(best, plate * tilt)
    return SCALE_H * best


def displacement(t, Z, a, b, cx):
    """Outward displacement (mm) at ellipse parameter t, height Z."""
    X = cx + a * np.cos(t)
    Yb = b * np.sin(t)                         # signed distance from the mid-plane
    flank = smoothstep(0.30, 0.65, np.abs(np.sin(t)))
    d = np.zeros_like(t)

    # gill arc (ridge + slightly proud gill cover on the head side)
    zg = GILL_Z + GILL_BULGE * (1 - np.clip(X / GILL_SPAN, -1, 1) ** 2)
    gill = GILL_H * np.exp(-((Z - zg) / GILL_S) ** 2) + GILL_COVER_H * (1 - smoothstep(zg - 1.5, zg + 1.5, Z))
    d += flank * gill * smoothstep(16, 26, Z)

    # scales: band above the gills, fading toward the peduncle and the fin edges
    sc_mask = flank * smoothstep(zg + 4, zg + 12, Z) * band(Z, SCALE_Z[0], SCALE_Z[0] + 8, SCALE_Z[1] - 14, SCALE_Z[1])
    d += sc_mask * scales(X, Z)

    # eye: raised rim + domed pupil
    r = np.hypot(X - EYE_X, Z - EYE_Z)
    eye = EYE_RING_H * np.exp(-((r - EYE_RING_R) / EYE_RING_S) ** 2)
    eye += EYE_PUPIL_H * np.clip(1 - (r / EYE_PUPIL_R) ** 2, 0, 1) ** 1.5
    d += smoothstep(0.45, 0.75, np.abs(np.sin(t))) * eye

    # pectoral fins: a ribbed leaf lying on each flank
    ang = np.radians(PEC_TILT_DEG)
    ux, uz = np.sin(ang), np.cos(ang)
    px, pz = X - PEC_ROOT[0], Z - PEC_ROOT[1]
    s = px * ux + pz * uz                      # along the fin
    q = px * uz - pz * ux                      # across the fin
    x = np.clip(s / PEC_LEN, 0, 1)
    half_w = PEC_W * np.sin(np.pi * np.clip(0.15 + 0.85 * x, 0, 1)) ** 0.8
    height = PEC_H * smoothstep(-7.0, 0.0, s) * (1 - x)
    across = 1 - smoothstep(half_w - 2.6, half_w, np.abs(q))
    rays = 0.8 + 0.2 * np.cos(2 * np.pi * q / PEC_RAY_PITCH)
    d += np.maximum(flank * height * across * rays, 0) * (s < PEC_LEN)

    # dorsal (+X edge) and anal (-X edge) fins: thin crests
    crest = 1 - smoothstep(FIN_HALF_T, FIN_HALF_T + 1.3, np.abs(Yb))
    d += (np.cos(t) > 0) * crest * DORSAL_H * band(Z, *DORSAL_Z)
    d += (np.cos(t) < 0) * crest * ANAL_H * band(Z, *ANAL_Z)

    # tail fin rays fanning out from the peduncle
    phi = np.arctan2(X, Z - TAIL_RAY_ORIGIN_Z)
    rays_t = 0.5 + 0.5 * np.cos(2 * np.pi * phi / TAIL_RAY_PITCH_RAD)
    d += TAIL_RAY_H * rays_t * smoothstep(186, 198, Z) * smoothstep(0.2, 0.5, np.abs(np.sin(t)))
    return d


def build() -> trimesh.Trimesh:
    z = np.unique(np.concatenate([
        np.arange(0.0, TOP_Z - 0.3, DZ), [SPIGOT_DEPTH, SHOULDER_TOP, TOP_Z - 0.3]]))
    a, b, cx = section_params(z)
    t = np.linspace(0, 2 * np.pi, N_AROUND, endpoint=False)
    T, Zg = np.meshgrid(t, z)
    A, B, CX = (np.broadcast_to(v[:, None], T.shape) for v in (a, b, cx))
    bx, by = CX + A * np.cos(T), B * np.sin(T)
    nx, ny = B * np.cos(T), A * np.sin(T)
    nn = np.hypot(nx, ny)
    D = displacement(T, Zg, A, B, CX)
    D[z <= SHOULDER_TOP] = 0.0
    px, py = bx + D * nx / nn, by + D * ny / nn

    nz, nt = T.shape
    verts = np.column_stack([px.ravel(), py.ravel(), Zg.ravel()])
    idx = np.arange(nz * nt).reshape(nz, nt)
    i0, i1 = idx[:-1], np.roll(idx[:-1], -1, axis=1)
    j0, j1 = idx[1:], np.roll(idx[1:], -1, axis=1)
    faces = np.concatenate([np.stack([i0, i1, j1], -1).reshape(-1, 3),
                            np.stack([i0, j1, j0], -1).reshape(-1, 3)])
    # flat caps (bottom is removed by the slicer with 0 bottom layers)
    bot_c, top_c = len(verts), len(verts) + 1
    verts = np.vstack([verts, [cx[0], 0, z[0]], [px[-1].mean(), py[-1].mean(), z[-1]]])
    ring_b, ring_t = idx[0], idx[-1]
    faces = np.concatenate([faces,
                            np.column_stack([np.full(nt, bot_c), np.roll(ring_b, -1), ring_b]),
                            np.column_stack([np.full(nt, top_c), ring_t, np.roll(ring_t, -1)])])
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
    body = zc < PROFILE[-1, 0]   # above this the tail edge closes; that thin fin is near-solid
    out = {
        "size_mm": (mesh.extents).round(1).tolist(),
        "triangles": len(mesh.faces),
        "watertight": mesh.is_watertight,
        "max_slope_deg_body": round(float(ang[body].max()), 1),
        "worst_z": round(float(zc[body][ang[body].argmax()]), 1),
        "area_over_45deg_pct": round(100 * area[body & (ang > 45)].sum() / area.sum(), 3),
        "area_over_50deg_pct": round(100 * area[body & (ang > 50)].sum() / area.sum(), 3),
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
