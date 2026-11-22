# print-cad

A small workspace for designing and remixing 3D-printable parts with code, built around a
**Bambu Lab P2S** (0.4 mm nozzle) and **Bambu Studio**. It's set up to be driven by
[Claude Code](https://claude.com/claude-code): you describe what you want in plain language and it
models, measures, renders and exports the part. Every script here also runs on its own.

## Requirements

- **macOS** (tested on macOS 26 / Apple Silicon). Linux should work for everything except the Bambu
  Studio project step.
- **[uv](https://docs.astral.sh/uv/)**: installs Python 3.12 and every library for you.
  `brew install uv`
- **[just](https://just.systems/)**: short commands for common tasks. `brew install just`
- **[Bambu Studio](https://bambulab.com/en/download/studio)**: the slicer. Some scripts also use its
  command line to build ready-to-print project files.
- Optional: **VS Code** with the **OCP CAD Viewer** extension, for an interactive 3D view (`just view`).
- Optional: **Claude Code**, to design parts by conversation (see [Using it with Claude Code](#using-it-with-claude-code)).

You don't need to install Python yourself; uv picks the version in `.python-version`.

## Setup

```sh
git clone https://github.com/luperr/print-cad.git
cd print-cad
uv sync        # creates .venv with Python 3.12 + build123d, trimesh, manifold3d, ...
just test      # quick check that everything works (builds the example, does some mesh edits)
```

## How to use

### Just want to print the soy fish?
```sh
just soy-fish
```
Then open **`out/soy_fish_project.3mf`** in Bambu Studio. Printer, plate, filament and vase-mode
settings are all embedded, so slice and print. Read [`parts/soy_fish/README.md`](parts/soy_fish/README.md)
first for the bulb size limit, which other parts you need from the original download, and assembly.

### Everyday commands

| Command | What it does |
|---|---|
| `just` | list all commands |
| `just new <name>` | start a new part: copies `parts/_example` to `parts/<name>` |
| `just build <name>` | run `parts/<name>/part.py` and write STL + STEP + 3MF to `out/` |
| `just view <name> [imports/x.stl]` | build and show it in the OCP viewer, optionally overlaid on an original mesh |
| `just measure <file>` | size, volume and round holes of any STL/3MF |
| `just soy-fish` | regenerate the soy fish and its Bambu Studio project |
| `just test` | smoke tests (run after changing anything in `lib/`) |
| `just clean` | empty `out/` |

### Making a new part
1. `just new bracket`, then edit `parts/bracket/part.py`. All dimensions are parameters at the top, in mm.
2. `just build bracket` and drag `out/bracket.3mf` into Bambu Studio.
3. Fill in `parts/bracket/README.md`: source, licence and print settings.

### Remixing a downloaded model
Put the download in its own folder under `imports/` and never edit it there. Then pick a path:
- **A STEP / .f3d / .scad source exists:** use it; it's far easier to change than an STL.
- **STL, and you want to add or cut something** (a hole, tab, text, a split): `lib/mesh_tools.py`
  does fast, reliable mesh booleans.
- **STL, and you want to change its dimensions:** measure it, rebuild it in build123d, and overlay
  the original with `just view` to compare.

## How it's organised

```
parts/<name>/      one folder per part: the model script plus a README (source, licence, print notes)
lib/               shared helpers
  printing.py        printer limits and tolerances (clearances, min wall, overhang, hole sizes)
  mesh_tools.py      load / measure / repair / boolean / split STL and 3MF meshes
  export.py          export a build123d part to STL + STEP + 3MF in out/
  build.py           what `just build` / `just view` run
imports/           downloaded models, read-only (third-party downloads stay out of git; part READMEs link the source)
out/               generated files to drag into the slicer (not committed; rebuild any time)
tests/smoke.py     end-to-end checks of the toolchain
```

### Config files and why they're there

| File | Purpose |
|---|---|
| `pyproject.toml`, `uv.lock` | the Python libraries and their exact versions, so everyone gets the same setup |
| `.python-version` | pins Python 3.12 (build123d's CAD kernel needs it) |
| `justfile` | the `just` commands above |
| `lib/printing.py` | **the place to tune for your printer**: fit clearances, hole compensation, minimum wall, bed size. Parts import these, never hard-code them. |
| `CLAUDE.md` | house rules Claude Code follows here: explain choices plainly, design for printing, record sources and licences, commit after each change |
| `.mcp.json` | connects Claude Code to [build123d-mcp](https://pypi.org/project/build123d-mcp/), a CAD server it uses to build, measure and render parts step by step |
| `.gitignore` | keeps generated files (`out/`), downloads, caches and personal settings out of git |

If your printer isn't a P2S with a 0.4 mm nozzle, start with `lib/printing.py` (bed size, nozzle,
clearances). Part READMEs and Bambu presets assume a P2S, so adjust print settings to match.

## Using it with Claude Code

Open the folder in Claude Code and ask in plain language, for example:
- "Make a wall hook for a 20 mm dowel, printable without supports."
- "Here's a model I downloaded (it's in imports/). Add a 6 mm hole through the base."
- "Make this lamp shade print in vase mode in clear PETG."

It follows `CLAUDE.md`. It picks the editing approach and says why, renders after each step, checks
printability, exports to `out/`, and tells you which file to drag into Bambu Studio. The CAD server
in `.mcp.json` starts automatically; approve it the first time Claude Code asks.

## Licence

The workspace (code, tools and original parts) is free software under the
**GNU General Public License v3.0 or later**; see [`LICENSE`](LICENSE). You can use, change and share
it. If you share a modified version, it must stay under the GPL with its source available.

**Exception: remixed parts keep their source's licence.** `parts/soy_fish/` is derived from Soy Fish
Lamp models licensed CC BY-NC, so that folder and everything it generates is shared under the same
**CC BY-NC** terms: share and remix freely with credit, but **no selling** prints or files. Each part's
README states its licence.
