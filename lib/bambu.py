"""Bambu Studio helpers: build ready-to-print project files (.3mf with settings embedded) and slice them.

    from lib import bambu
    bambu.build_project([Path("out/part.stl")], Path("out/part_project.3mf"),
                        process={"inherits": "0.20mm Standard @BBL P2S", "wall_loops": "3"},
                        filament={"inherits": "Bambu PLA Basic @BBL P2S"})
    info = bambu.slice_project(Path("out/part_project.3mf"))   # {'time': '5h 2m', 'grams': 123.4, ...}

Presets are dicts in Bambu's own JSON format: name a system preset in "inherits" and add only the
settings you change. The Bambu Studio command line doesn't follow "inherits" for user presets, so
every inherited value is copied in first. Needs Bambu Studio installed (macOS paths below).
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

BAMBU_APP = Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
SYSTEM = Path.home() / "Library/Application Support/BambuStudio/system/BBL"
MACHINE = SYSTEM / "machine" / "Bambu Lab P2S 0.4 nozzle.json"
PLATE = "Textured PEI Plate"


class BambuError(RuntimeError):
    pass


def available() -> bool:
    return BAMBU_APP.exists() and MACHINE.exists()


def load_preset(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def flatten(kind: str, preset: dict) -> dict:
    """Merge a preset dict with every system preset it inherits from ("process" or "filament")."""
    out: dict = {}
    name = preset.get("inherits", "")
    while name:
        d = json.loads((SYSTEM / kind / f"{name}.json").read_text())
        for k, v in d.items():
            out.setdefault(k, v)
        name = d.get("inherits", "")
    out.update(preset)
    out["inherits"], out["from"] = "", "User"
    out.setdefault("compatible_printers", ["Bambu Lab P2S 0.4 nozzle"])
    return out


def build_project(meshes: list[Path], target: Path, process: dict, filament: dict,
                  plate: str = PLATE) -> Path:
    """Arrange `meshes` on one plate with these settings and save a Bambu project to `target`."""
    if not available():
        raise BambuError(f"Bambu Studio not found at {BAMBU_APP}")
    for m in meshes:
        if not Path(m).exists():
            raise BambuError(f"missing mesh {m}")
    target = Path(target).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        proc = flatten("process", process)
        proc["curr_bed_type"] = plate
        (tmp / "process.json").write_text(json.dumps(proc, indent=2))
        (tmp / "filament.json").write_text(json.dumps(flatten("filament", filament), indent=2))
        cmd = [str(BAMBU_APP), "--debug", "1", "--arrange", "1", "--orient", "0", "--curr-bed-type", plate,
               "--load-settings", f"{MACHINE};{tmp / 'process.json'}",
               "--load-filaments", str(tmp / "filament.json"),
               "--outputdir", str(tmp), "--export-3mf", target.name, *[str(Path(m).resolve()) for m in meshes]]
        res = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
        made = tmp / target.name
        if res.returncode != 0 or not made.exists():
            raise BambuError(f"Bambu Studio failed (exit {res.returncode}):\n{res.stdout[-1500:]}{res.stderr[-1500:]}")
        made.replace(target)
    return target


def slice_project(project: Path) -> dict:
    """Slice a project with its embedded settings; return time, grams, layers and travel stats."""
    with tempfile.TemporaryDirectory() as tmp:
        res = subprocess.run([str(BAMBU_APP), "--debug", "1", "--slice", "0", "--outputdir", tmp,
                              str(Path(project).resolve())], cwd=tmp, capture_output=True, text=True)
        gcodes = sorted(Path(tmp).glob("plate_*.gcode"))
        if res.returncode != 0 or not gcodes:
            raise BambuError(f"slicing failed (exit {res.returncode}):\n{res.stdout[-1500:]}")
        head = gcodes[0].read_text(errors="ignore")[:20000]
    get = lambda pat: (re.search(pat, head) or [None, None])[1]
    return {"time": get(r"model printing time: ([^;\n]+)"),
            "grams": float(get(r"total filament weight \[g\] : ([\d.]+)") or 0),
            "layers": int(get(r"total layer number: (\d+)") or 0),
            "plates": len(gcodes)}
