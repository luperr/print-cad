# print-cad task runner. Run `just` to list recipes.

export PYTHONPATH := justfile_directory()

default:
    @just --list

# Build parts/<part>/part.py and export STL/STEP/3MF to out/
build part:
    uv run python -m lib.build {{part}}

# Print size, volume and round holes of an STL/3MF
measure file:
    uv run python -m lib.mesh_tools {{file}}

# Build and send to the OCP CAD Viewer (open it in VS Code first)
view part *overlay:
    uv run python -m lib.build {{part}} --view {{ if overlay != "" { "--overlay " + overlay } else { "" } }}

# Scaffold parts/<part>/ from parts/_example
new part:
    @test ! -e parts/{{part}} || (echo "parts/{{part}} already exists" && exit 1)
    cp -R parts/_example parts/{{part}}
    @perl -pi -e 's/_example/{{part}}/g' parts/{{part}}/README.md parts/{{part}}/part.py
    @echo "created parts/{{part}}/ (edit part.py, then: just build {{part}})"

# Run the smoke tests
test:
    uv run python tests/smoke.py

# Empty out/
clean:
    find out -mindepth 1 ! -name .gitkeep -delete
