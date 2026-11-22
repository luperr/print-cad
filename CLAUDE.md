# print-cad conventions

User has no CAD experience. Explain choices in plain language, briefly.
Printer: Bambu Lab P2S, 0.4 mm nozzle. Slicer: Bambu Studio.

## Modifying an existing model: decide the path first
1. Check whether a STEP / .f3d / .scad / customizer source exists. Ask the user to grab it from
   the model page. Prefer it over STL.
2. STL + additive/subtractive edit (hole, tab, text, split, merge) -> mesh_tools (manifold3d).
   Don't push dense STLs through build123d booleans: it's slow and unreliable.
3. STL + dimension change -> measure with mesh_tools, rebuild parametrically in build123d,
   then overlay the original mesh in a render to compare.
Tell the user which path you chose and why, in one line.

## Modelling rules
- One folder per part in parts/. Parameters at the top of part.py, with units in comments.
- Import tolerances and sizes from lib/printing.py. Never hardcode clearances.
- Build incrementally with build123d-mcp: render after each major feature, measure the result,
  run validate() before export.
- Design for printing: flat face on the bed, overhangs <= 45 deg or chamfered, no unsupported
  bridges > 20 mm, walls >= MIN_WALL. Mention the print orientation you designed for.
- Fasteners and threads come from bd_warehouse, not hand-modelled.
- Export via lib/export.py. Outputs go to out/ only.

## Files
- imports/ is read-only. Never overwrite a downloaded file.
- Record the source URL and licence in each part's README.md. Respect non-commercial / no-derivative licences.
- Commit after each working change, with short messages.

## After each change
Show a render, list the key dimensions, and tell the user which file in out/ to drag into Bambu Studio.

## Workspace mechanics
- `part.py` is a pure model: it imports only build123d, bd_warehouse and `lib.printing`,
  and assigns the final shape to `part`. No export code in it. That way it runs both
  under `just build <part>` and in build123d-mcp via `execute_file(path="parts/<part>/part.py", result_name="part")`.
- The MCP sandbox only allows allowlisted imports; `lib.printing` passes because it has no
  imports. Keep it that way. `lib.mesh_tools` / `lib.export` are for `uv run`, not the MCP.
- Mesh edits that aren't a reusable part: write a short script (e.g. `parts/<name>/edit.py`)
  using `lib.mesh_tools` and run it with `PYTHONPATH=. uv run python parts/<name>/edit.py`.
- MCP useful tools: `execute_file`, `render_view`, `measure`, `validate`, `analyze_printability`
  (pass `build_volume="256 256 256"`, `min_perimeters=3`), `import_cad_file` (STEP/STL/3MF;
  STL imports are fine for renders/overlays but measure meshes with `just measure`).
- Commands: `just build|view|measure|new|test|clean`. `just view <part> imports/x.stl`
  overlays the original mesh in the OCP viewer.
- `just test` runs tests/smoke.py; run it after changing anything in lib/.
