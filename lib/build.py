"""Build a part: run parts/<name>/part.py, export it, optionally show it in the viewer.

    uv run python -m lib.build <name> [--view] [--overlay imports/original.stl]

part.py must assign the final build123d shape to a variable called `part`.
It stays a pure model (no export code), so build123d-mcp can also run it
directly with execute_file for rendering and measuring.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_part(name: str):
    path = ROOT / "parts" / name / "part.py"
    if not path.exists():
        sys.exit(f"no such part: {path.relative_to(ROOT)}")
    ns = runpy.run_path(str(path), run_name="part")
    if "part" not in ns:
        sys.exit(f"{path.relative_to(ROOT)} must assign the final shape to `part`")
    return ns["part"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="folder name under parts/")
    ap.add_argument("--view", action="store_true", help="send to the OCP CAD Viewer")
    ap.add_argument("--overlay", help="STL/3MF to show semi-transparent next to the part")
    args = ap.parse_args()

    from lib.export import export_part

    part = load_part(args.name)
    export_part(part, args.name)

    if args.view or args.overlay:
        from ocp_vscode import get_port, show

        if get_port() is None:
            sys.exit("No OCP CAD Viewer is running. Open this folder in VS Code, click the "
                     "OCP icon in the sidebar to start the viewer, then run this again.")
        objs, names, alphas = [part], [args.name], [1.0]
        if args.overlay:
            from build123d import import_stl
            objs.append(import_stl(str(ROOT / args.overlay)))
            names.append(Path(args.overlay).stem)
            alphas.append(0.35)
        try:
            show(*objs, names=names, alphas=alphas)
        except Exception as exc:
            print(f"viewer not reachable ({exc}). Open this folder in VS Code and "
                  "start the OCP CAD Viewer (OCP icon in the sidebar), then retry.")


if __name__ == "__main__":
    main()
