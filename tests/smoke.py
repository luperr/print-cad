"""Smoke tests for the workspace. Run with `just test`.

1. New part: build parts/_example, check 60 x 40 x 6 mm and four 3.4 mm holes.
2. Mesh edit: 30 mm test cube in imports/, subtract a 10 mm through-hole and
   union a 20 x 10 x 3 mm tab with mesh_tools; result must be watertight.
3. Hybrid: union a build123d-modelled ring boss onto the edited cube via
   from_build123d; also split it and check no volume is lost.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from build123d import Cylinder, Pos, chamfer, Axis  # noqa: E402

from lib import mesh_tools as mt  # noqa: E402
from lib.build import load_part  # noqa: E402
from lib.export import export_part  # noqa: E402
from lib.printing import M3_CLEARANCE  # noqa: E402

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def poly_area(r: float, n: int) -> float:
    """Area of the n-gon trimesh uses to approximate a circle of radius r."""
    return 0.5 * n * r * r * math.sin(2 * math.pi / n)


# --- 1. New part ------------------------------------------------------------------
print("1. new part (parts/_example)")
part = load_part("_example")
paths = export_part(part, "_example")
bb = part.bounding_box()
check(close(bb.size.X, 60, 1e-3) and close(bb.size.Y, 40, 1e-3) and close(bb.size.Z, 6, 1e-3),
      f"B-rep size 60 x 40 x 6 (got {bb.size.X:.3f} x {bb.size.Y:.3f} x {bb.size.Z:.3f})")
check(close(bb.min.Z, 0, 1e-6), "bottom face sits at Z=0")
check(part.is_valid, "solid is valid")
info = mt.measure(paths["stl"])
check(info["watertight"], "exported STL is watertight")
holes = [c for c in info["circles"] if c["axis"] == "Z" and c["kind"] == "hole"]
centers = sorted(c["center"] for c in holes)
check(len(holes) == 4, f"found 4 vertical holes (got {len(holes)})")
check(all(close(c["diameter"], M3_CLEARANCE, 0.02) for c in holes), "hole diameters are 3.4 mm")
check(centers == sorted((x, y) for x in (-25.0, 25.0) for y in (-15.0, 15.0)),
      f"holes are 5 mm in from each edge (centres {centers})")
reloaded = mt.load(paths["3mf"])
check(close(reloaded.volume, part.volume, part.volume * 0.005), "3MF reloads with matching volume")

# --- 2. Mesh edit ------------------------------------------------------------------
print("2. mesh edit (imports/test_cube.stl)")
cube_path = ROOT / "imports" / "test_cube.stl"
if not cube_path.exists():  # imports/ is read-only: create the fixture once, never overwrite
    cube = trimesh.creation.box(extents=(30, 30, 30))
    cube.apply_translation((0, 0, 15))
    cube.export(cube_path)
cube = mt.load(cube_path)
hole = mt.cylinder(d=10, h=40, center=(0, 0, 15), sections=96)
tab = mt.box((20, 10, 3), center=(25, 0, 1.5))  # sticks out of the +X face, on the bed
edited = mt.union(mt.difference(cube, hole), tab)
expected = 30 ** 3 - poly_area(5, 96) * 30 + 20 * 10 * 3
check(edited.is_watertight, "result is watertight")
check(close(edited.volume, expected, 0.5), f"volume {edited.volume:.1f} == expected {expected:.1f}")
check(close(edited.bounds[1][0], 35, 1e-4), "tab reaches X=35")
mt.export(edited, "smoke_mesh_edit")

# --- 3. Hybrid ----------------------------------------------------------------------
print("3. hybrid (build123d ring boss on the imported mesh)")
ring = Cylinder(8, 5) - Cylinder(5, 5)
ring = chamfer(ring.edges().group_by(Axis.Z)[-1].filter_by(lambda e: e.radius > 7), 1.0)
ring = Pos(0, 0, 30 + 2.5) * ring  # sits on the cube's top face, around the hole
hybrid = mt.union(edited, ring)
check(hybrid.is_watertight, "hybrid is watertight")
gain = hybrid.volume - edited.volume
check(close(gain, ring.volume, ring.volume * 0.01),
      f"volume gained {gain:.1f} ~= ring volume {ring.volume:.1f}")
check(close(hybrid.bounds[1][2], 35, 1e-3), "boss top at Z=35")
mt.export(hybrid, "smoke_hybrid")

top, bottom = mt.split(hybrid, "z", at=15)
check(top.is_watertight and bottom.is_watertight, "split halves are watertight")
check(close(top.volume + bottom.volume, hybrid.volume, 0.5), "split keeps total volume")
check(close(top.bounds[0][2], 15, 1e-4) and close(bottom.bounds[1][2], 15, 1e-4),
      "split plane is at Z=15, positive side first")

print()
if failures:
    print(f"{len(failures)} check(s) FAILED")
    sys.exit(1)
print("all smoke tests passed")
