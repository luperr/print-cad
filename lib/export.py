"""Export a build123d part to out/<name>.stl, .step and .3mf."""

from __future__ import annotations

from pathlib import Path

from build123d import Shape, export_step

from lib import mesh_tools as mt
from lib.printing import check_bed

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def export_part(part: Shape, name: str, tolerance: float = 0.001,
                angular_tolerance: float = 0.1) -> dict[str, Path]:
    """Write STL + STEP + 3MF for `part` into out/, print its size, and check the bed.

    `tolerance` is the mesh chord error in mm (smaller = smoother curves, bigger file).
    The mesh is cleaned (degenerate triangles removed) so slicers get a watertight solid.
    """
    if not part.is_valid:
        print(f"WARNING: {name} is not a valid solid; the exported mesh may be broken.")
    OUT.mkdir(exist_ok=True)
    paths = {"stl": OUT / f"{name}.stl", "step": OUT / f"{name}.step", "3mf": OUT / f"{name}.3mf"}

    mesh = mt.from_build123d(part, tolerance=tolerance, angular_tolerance=angular_tolerance)
    mesh.export(paths["stl"])
    mesh.export(paths["3mf"])
    export_step(part, paths["step"])

    bb = part.bounding_box()
    size = (bb.size.X, bb.size.Y, bb.size.Z)
    print(f"{name}: {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} mm, "
          f"volume {part.volume / 1000:.2f} cm^3")
    print(f"  min ({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f})  "
          f"max ({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.2f})")
    if abs(bb.min.Z) > 1e-6:
        print(f"  note: lowest point is at Z={bb.min.Z:.2f}; the slicer will drop it onto the bed.")
    if not mesh.is_watertight:
        print("  WARNING: exported mesh is not watertight; check the model before printing.")
    check_bed(size, name)
    for p in paths.values():
        print(f"  -> {p.relative_to(ROOT)}")
    return paths
