"""Example: flat mounting plate with four M3 clearance holes.

Print orientation: flat on the bed, as modelled. No supports needed.
The bottom edge is left sharp so the plate sits flat with no overhang;
the vertical corners and the top edge get the 2 mm fillet.
Build with `just build _example`.
"""

from build123d import Axis, Box, Cylinder, Pos, fillet

from lib.printing import M3_CLEARANCE

# --- Parameters (mm) --------------------------------------------------------
LENGTH = 60.0          # X
WIDTH = 40.0           # Y
THICKNESS = 6.0        # Z
HOLE_D = M3_CLEARANCE  # M3 clearance hole diameter
HOLE_INSET = 5.0       # hole centre distance from each edge
EDGE_FILLET = 2.0      # fillet radius on vertical corners and top edge

# --- Model -----------------------------------------------------------------------
plate = Box(LENGTH, WIDTH, THICKNESS)
plate = fillet(plate.edges().filter_by(Axis.Z), radius=EDGE_FILLET)
plate = fillet(plate.edges().group_by(Axis.Z)[-1], radius=EDGE_FILLET)

dx = LENGTH / 2 - HOLE_INSET
dy = WIDTH / 2 - HOLE_INSET
for x in (-dx, dx):
    for y in (-dy, dy):
        plate -= Pos(x, y, 0) * Cylinder(HOLE_D / 2, THICKNESS * 2)

# Bottom face at Z=0, centred on X/Y.
part = Pos(0, 0, THICKNESS / 2) * plate
