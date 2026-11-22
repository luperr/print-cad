"""STL / 3MF helpers: load, measure, repair, mesh booleans, split, export.

Booleans run in manifold3d (fast and robust on dense meshes). trimesh handles
file I/O, inspection and repair. Use these for edits to STL-only models;
use build123d for anything you need to dimension parametrically.

    from lib import mesh_tools as mt
    base = mt.load("imports/bracket.stl")
    hole = mt.cylinder(d=3.4, h=50, center=(10, 0, 0))
    mt.export(mt.difference(base, hole), "bracket_with_hole")
"""

from __future__ import annotations

import sys
from functools import reduce
from pathlib import Path
from typing import Iterable, Union

import manifold3d as mf
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

MeshLike = Union[trimesh.Trimesh, mf.Manifold, str, Path]


# --- Loading & inspection ------------------------------------------------------

def load(path: str | Path, verbose: bool = True) -> trimesh.Trimesh:
    """Load an STL/3MF/OBJ as a single trimesh and report whether it is watertight."""
    mesh = trimesh.load(str(path), force="mesh")
    if verbose:
        status = "watertight" if mesh.is_watertight else "NOT watertight (try repair())"
        print(f"{Path(path).name}: {len(mesh.faces)} triangles, {status}")
    return mesh


def _circle_fit(pts: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Least-squares circle through 2D points -> (center, radius, relative residual)."""
    A = np.column_stack([pts, np.ones(len(pts))])
    b = (pts ** 2).sum(axis=1)
    (a0, a1, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    center = np.array([a0 / 2, a1 / 2])
    r = float(np.sqrt(max(c + center @ center, 0.0)))
    resid = float(np.std(np.linalg.norm(pts - center, axis=1) - r) / r) if r > 0 else np.inf
    return center, r, resid


def _point_in_poly(p: np.ndarray, poly: np.ndarray) -> bool:
    x, y = p
    xs, ys = poly[:, 0], poly[:, 1]
    xs2, ys2 = np.roll(xs, -1), np.roll(ys, -1)
    cond = (ys > y) != (ys2 > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xint = xs + (y - ys) * (xs2 - xs) / (ys2 - ys)
    return bool(np.count_nonzero(cond & (x < xint)) % 2)


def find_circles(mesh: trimesh.Trimesh, levels: Iterable[float] = (0.25, 0.5, 0.75),
                 max_resid: float = 0.01) -> list[dict]:
    """Rough guess at round holes and bosses, found by slicing along X, Y and Z.

    Returns dicts with axis, kind ('hole' or 'boss/outer'), diameter, center (the
    two in-plane coordinates) and the slice positions it was seen at.
    """
    lo, hi = mesh.bounds
    found: dict[tuple, dict] = {}
    for ax in range(3):
        normal = np.zeros(3)
        normal[ax] = 1
        keep = [i for i in range(3) if i != ax]
        for f in levels:
            origin = lo.copy()
            origin[ax] = lo[ax] + f * (hi[ax] - lo[ax])
            sec = mesh.section(plane_origin=origin, plane_normal=normal)
            if sec is None:
                continue
            loops = [d[:, keep] for d in sec.discrete if len(d) >= 4]
            for i, loop in enumerate(loops):
                pts = loop[:-1] if np.allclose(loop[0], loop[-1]) else loop
                if len(pts) < 8:
                    continue
                center, r, resid = _circle_fit(pts)
                if resid > max_resid or r < 0.2:
                    continue
                depth = sum(_point_in_poly(pts[0], other)
                            for j, other in enumerate(loops) if j != i)
                kind = "hole" if depth % 2 else "boss/outer"
                key = ("XYZ"[ax], kind, round(2 * r, 1), *np.round(center, 1))
                entry = found.setdefault(key, {
                    "axis": "XYZ"[ax], "kind": kind, "diameter": round(2 * r, 2),
                    "center": tuple(round(float(c), 2) for c in center),
                    "center_axes": "".join("XYZ"[k] for k in keep), "seen_at": []})
                entry["seen_at"].append(round(float(origin[ax]), 2))
    return sorted(found.values(), key=lambda e: (e["axis"], e["kind"], -e["diameter"]))


def measure(path_or_mesh: str | Path | trimesh.Trimesh, holes: bool = True) -> dict:
    """Bounding box, volume, surface area and a rough round-hole guess. Prints a summary."""
    mesh = path_or_mesh if isinstance(path_or_mesh, trimesh.Trimesh) else load(path_or_mesh, verbose=False)
    lo, hi = mesh.bounds
    info = {
        "triangles": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "bodies": int(mesh.body_count),
        "bbox_min": tuple(round(float(v), 3) for v in lo),
        "bbox_max": tuple(round(float(v), 3) for v in hi),
        "size": tuple(round(float(v), 3) for v in hi - lo),
        "volume_mm3": round(float(mesh.volume), 2) if mesh.is_watertight else None,
        "area_mm2": round(float(mesh.area), 2),
    }
    if holes:
        info["circles"] = find_circles(mesh)

    sx, sy, sz = info["size"]
    print(f"size        {sx:.2f} x {sy:.2f} x {sz:.2f} mm")
    print(f"bbox        min {info['bbox_min']}  max {info['bbox_max']}")
    print(f"volume      {info['volume_mm3']} mm^3" + ("" if info["watertight"] else " (not watertight)"))
    print(f"area        {info['area_mm2']} mm^2")
    print(f"triangles   {info['triangles']}, bodies {info['bodies']}, watertight {info['watertight']}")
    for c in info.get("circles", []):
        print(f"circle      {c['kind']:<10} dia {c['diameter']:.2f} along {c['axis']} "
              f"at {c['center_axes']}={c['center']} (slices {c['seen_at']})")
    return info


def clean(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Merge duplicate vertices and drop degenerate / duplicate triangles (in place)."""
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    return mesh


def repair(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Clean, fix normals and fill small holes. Returns a repaired copy."""
    m = mesh.copy()
    before = m.is_watertight
    clean(m)
    trimesh.repair.fix_normals(m)
    m.fill_holes()
    trimesh.repair.fix_normals(m)
    print(f"repair: watertight {before} -> {m.is_watertight}")
    return m


def drop_to_bed(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Translate so the lowest point sits at Z=0."""
    m = mesh.copy()
    m.apply_translation([0, 0, -m.bounds[0][2]])
    return m


# --- trimesh <-> manifold3d ---------------------------------------------------------

def to_manifold(mesh: trimesh.Trimesh) -> mf.Manifold:
    """Convert a trimesh to a manifold3d Manifold (raises if the mesh isn't solid)."""
    mg = mf.Mesh64(vert_properties=np.asarray(mesh.vertices, dtype=np.float64),
                   tri_verts=np.asarray(mesh.faces, dtype=np.uint64))
    man = mf.Manifold(mg)
    if man.status() != mf.Error.NoError:
        mg.merge()
        man = mf.Manifold(mg)
    if man.status() != mf.Error.NoError:
        raise ValueError(f"mesh is not a closed solid ({man.status()}); run repair() first")
    return man


def from_manifold(man: mf.Manifold) -> trimesh.Trimesh:
    """Convert a manifold3d Manifold back to a trimesh."""
    mg = man.to_mesh64()
    verts = np.asarray(mg.vert_properties)[:, :3]
    return trimesh.Trimesh(vertices=verts, faces=np.asarray(mg.tri_verts), process=True)


def _as_manifold(obj: MeshLike) -> mf.Manifold:
    if isinstance(obj, mf.Manifold):
        return obj
    if isinstance(obj, (str, Path)):
        obj = load(obj, verbose=False)
    if isinstance(obj, trimesh.Trimesh):
        return to_manifold(obj)
    # build123d shapes: tessellate on the fly
    return to_manifold(from_build123d(obj))


# --- Booleans -------------------------------------------------------------------------

def union(*objs: MeshLike) -> trimesh.Trimesh:
    """Join meshes / build123d shapes / file paths into one solid."""
    return from_manifold(reduce(lambda a, b: a + b, map(_as_manifold, objs)))


def difference(base: MeshLike, *cutters: MeshLike) -> trimesh.Trimesh:
    """Subtract every cutter from base."""
    result = _as_manifold(base)
    for c in cutters:
        result = result - _as_manifold(c)
    return from_manifold(result)


def intersection(*objs: MeshLike) -> trimesh.Trimesh:
    """Keep only the volume shared by all inputs."""
    return from_manifold(reduce(lambda a, b: a ^ b, map(_as_manifold, objs)))


# --- Primitives (quick cutters/tabs without build123d) -------------------------------

def box(size: tuple[float, float, float], center: tuple[float, float, float] = (0, 0, 0)) -> trimesh.Trimesh:
    """Axis-aligned box of `size` (x, y, z) centred at `center`."""
    m = trimesh.creation.box(extents=size)
    m.apply_translation(center)
    return m


def cylinder(d: float, h: float, center: tuple[float, float, float] = (0, 0, 0),
             axis: str = "z", sections: int = 96) -> trimesh.Trimesh:
    """Cylinder of diameter `d` and length `h` along `axis`, centred at `center`."""
    m = trimesh.creation.cylinder(radius=d / 2, height=h, sections=sections)
    if axis == "x":
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    elif axis == "y":
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    m.apply_translation(center)
    return m


# --- build123d bridge ---------------------------------------------------------------------

def from_build123d(part, tolerance: float = 0.01, angular_tolerance: float = 0.1) -> trimesh.Trimesh:
    """Tessellate a build123d shape into a watertight trimesh for mesh booleans."""
    verts, tris = part.tessellate(tolerance, angular_tolerance)
    mesh = trimesh.Trimesh(vertices=[(v.X, v.Y, v.Z) for v in verts], faces=tris, process=True)
    # OCC leaves zero-area triangles at sphere poles (e.g. where two fillets meet).
    clean(mesh)
    if not mesh.is_watertight:
        # Fall back to OCC's STL writer, which shares edge discretisation between faces.
        import tempfile
        from build123d import export_stl
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "part.stl"
            export_stl(part, p, tolerance=tolerance, angular_tolerance=angular_tolerance)
            mesh = clean(trimesh.load(str(p), force="mesh"))
    if mesh.volume < 0:
        mesh.invert()
    return mesh


# --- Splitting & export --------------------------------------------------------------------

def split(mesh: MeshLike, plane: str | tuple = "z", at: float | None = None
          ) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    """Cut a model in two. Returns (positive side, negative side).

    plane: 'x', 'y' or 'z' (cut perpendicular to that axis at `at`, default the
           middle of the bounding box), or (normal, origin) tuples for any plane.
    """
    man = _as_manifold(mesh)
    if isinstance(plane, str):
        ax = "xyz".index(plane.lower())
        normal = [0.0, 0.0, 0.0]
        normal[ax] = 1.0
        bb = man.bounding_box()  # (xmin, ymin, zmin, xmax, ymax, zmax)
        offset = at if at is not None else (bb[ax] + bb[ax + 3]) / 2
    else:
        normal, origin = (np.asarray(v, dtype=float) for v in plane)
        normal = normal / np.linalg.norm(normal)
        offset = float(normal @ origin)
        normal = normal.tolist()
    pos, neg = man.split_by_plane(normal, offset)
    return from_manifold(pos), from_manifold(neg)


def export(mesh: trimesh.Trimesh, name: str, three_mf: bool = True) -> dict[str, Path]:
    """Write out/<name>.stl (and .3mf), print the size and check it fits the bed."""
    from lib.printing import check_bed

    OUT.mkdir(exist_ok=True)
    paths = {"stl": OUT / f"{name}.stl"}
    mesh.export(paths["stl"])
    if three_mf:
        paths["3mf"] = OUT / f"{name}.3mf"
        try:
            mesh.export(paths["3mf"])
        except Exception as exc:
            print(f"note: 3MF export skipped ({exc})")
            paths.pop("3mf")
    size = mesh.bounds[1] - mesh.bounds[0]
    print(f"{name}: {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} mm, watertight {mesh.is_watertight}")
    check_bed(tuple(size), name)
    for p in paths.values():
        print(f"  -> {p.relative_to(ROOT)}")
    return paths


if __name__ == "__main__":
    # `python -m lib.mesh_tools <file>` prints measurements.
    for arg in sys.argv[1:]:
        print(f"== {arg}")
        measure(arg)
