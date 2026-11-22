"""Clarity test: a short band cut from the fish, printed with the real settings at 3 nozzle temperatures.

Run after fish.py:  PYTHONPATH=. uv run python parts/soy_fish/make_test_band.py
Out:  out/soy_fish_test_band.stl and one Bambu project per temperature:
      out/soy_fish_test_band_240C.3mf, _250C.3mf, _260C.3mf

Why three files: Bambu Studio re-sends the filament temperature at every layer, so a temperature
change inserted mid-print only lasts one layer. Each project instead carries its own temperature.

The band holds a row of scale edges plus plain flank, so each print shows both the see-through
clarity of smooth wall and how crisp the raised edges come out (~20 min, ~6 g each). Hold them
against a light and pick the clearest one without bubbles, stringing or sagging edges; then set
that temperature in bambu/filament_clear_petg_vase.json and rerun make_project.py.
"""

from __future__ import annotations

from lib import mesh_tools as mt

from make_project import ROOT, build_project  # same folder

BAND = (112.0, 127.0)            # mm, fish Z range to cut: includes the lowest row of scale edges (~118)
TEMPS = (240, 250, 260)          # C


def main() -> None:
    fish = mt.load(ROOT / "out" / "soy_fish.stl")
    lo, hi = BAND
    band = mt.intersection(fish, mt.box((400.0, 400.0, hi - lo), center=(0, 0, (lo + hi) / 2)))
    paths = mt.export(mt.drop_to_bed(band), "soy_fish_test_band", three_mf=False)
    for t in TEMPS:
        build_project(paths["stl"], ROOT / "out" / f"soy_fish_test_band_{t}C.3mf",
                      {"nozzle_temperature": [str(t)] * 3,
                       "nozzle_temperature_initial_layer": [str(t)] * 3,
                       "filament_settings_id": [f"Clear PETG Vase {t}C test"]})


if __name__ == "__main__":
    main()
