"""Build a Bambu Studio project file with the print settings baked in.

Run after fish.py:  uv run python parts/soy_fish/make_project.py
Out:  out/soy_fish_project.3mf  (open it in Bambu Studio: printer, plate, process and filament
      settings all come with it). out/soy_fish.3mf stays a plain mesh with no settings.

How: the presets in bambu/ only list what differs from Bambu's system presets ("inherits"). The
Bambu Studio command line doesn't follow that chain for user presets, so this script copies in every
inherited value first, then asks Bambu Studio to arrange the fish on the plate and save a project.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BAMBU_APP = Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
SYSTEM = Path.home() / "Library/Application Support/BambuStudio/system/BBL"
MACHINE = SYSTEM / "machine" / "Bambu Lab P2S 0.4 nozzle.json"
PLATE = "Textured PEI Plate"


def flatten(kind: str, preset: Path) -> dict:
    """Merge a user preset with every system preset it inherits from."""
    user = json.loads(preset.read_text())
    out: dict = {}
    name = user.get("inherits", "")
    while name:
        d = json.loads((SYSTEM / kind / f"{name}.json").read_text())
        for k, v in d.items():
            out.setdefault(k, v)
        name = d.get("inherits", "")
    out.update(user)
    out["inherits"], out["from"] = "", "User"
    return out


def main() -> None:
    mesh = ROOT / "out" / "soy_fish.stl"
    if not mesh.exists():
        sys.exit("out/soy_fish.stl not found: run parts/soy_fish/fish.py first")
    for p in (BAMBU_APP, MACHINE):
        if not p.exists():
            sys.exit(f"missing {p} (is Bambu Studio installed?)")
    target = ROOT / "out" / "soy_fish_project.3mf"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        process = flatten("process", HERE / "bambu" / "process_soy_fish_vase.json")
        process["curr_bed_type"] = PLATE
        filament = flatten("filament", HERE / "bambu" / "filament_clear_petg_vase.json")
        (tmp / "process.json").write_text(json.dumps(process, indent=2))
        (tmp / "filament.json").write_text(json.dumps(filament, indent=2))
        cmd = [str(BAMBU_APP), "--debug", "1", "--arrange", "1", "--orient", "0",
               "--curr-bed-type", PLATE,
               "--load-settings", f"{MACHINE};{tmp / 'process.json'}",
               "--load-filaments", str(tmp / "filament.json"),
               "--outputdir", str(tmp), "--export-3mf", target.name, str(mesh)]
        res = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
        made = tmp / target.name
        if res.returncode != 0 or not made.exists():
            sys.exit(f"Bambu Studio failed (exit {res.returncode}):\n{res.stdout[-2000:]}{res.stderr[-2000:]}")
        made.replace(target)
    print(f"wrote {target.relative_to(ROOT)}: open it in Bambu Studio and slice; settings are embedded")


if __name__ == "__main__":
    main()
