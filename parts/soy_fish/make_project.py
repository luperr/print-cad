"""Build a Bambu Studio project file with the print settings baked in.

Run after fish.py:  uv run python parts/soy_fish/make_project.py
Out:  out/soy_fish_project.3mf (clear PETG) and out/soy_fish_project_pla.3mf (opaque PLA)
      (open one in Bambu Studio: printer, plate, process and filament
      settings all come with it). out/soy_fish.3mf stays a plain mesh with no settings.

The presets live in bambu/; lib/bambu.py resolves what they inherit and runs Bambu Studio.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from lib import bambu  # noqa: E402


FILAMENTS = {"petg": "filament_clear_petg_vase.json", "pla": "filament_pla_vase.json"}


def build_project(mesh: Path, target: Path, filament_overrides: dict | None = None,
                  material: str = "petg") -> None:
    """Arrange `mesh` on a P2S plate with the soy fish presets and save a Bambu project to `target`."""
    if not mesh.exists():
        sys.exit(f"{mesh.relative_to(ROOT)} not found: run the generator first")
    filament = bambu.load_preset(HERE / "bambu" / FILAMENTS[material])
    filament.update(filament_overrides or {})
    try:
        bambu.build_project([mesh], target, bambu.load_preset(HERE / "bambu" / "process_soy_fish_vase.json"), filament)
    except bambu.BambuError as e:
        sys.exit(str(e))
    print(f"wrote {target.relative_to(ROOT)}: open it in Bambu Studio and slice; settings are embedded")


def main() -> None:
    build_project(ROOT / "out" / "soy_fish.stl", ROOT / "out" / "soy_fish_project.3mf")            # clear PETG
    build_project(ROOT / "out" / "soy_fish.stl", ROOT / "out" / "soy_fish_project_pla.3mf", material="pla")


if __name__ == "__main__":
    main()
