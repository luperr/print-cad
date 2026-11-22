"""Shared print constants for the Bambu Lab P2S (0.4 mm nozzle, PLA/PETG).

All values are in millimetres unless noted. These are starting points: tune them
with test prints and record what you changed (and why) in a comment.

Keep this module free of imports so the build123d-mcp sandbox accepts it.
"""

# --- Printer -----------------------------------------------------------------
NOZZLE = 0.4
LAYER_HEIGHT = 0.2
# P2S build volume (X, Y, Z), checked against Bambu's P2S spec: 256 x 256 x 256 mm.
BED = (256.0, 256.0, 256.0)

# --- Fits & tolerances ---------------------------------------------------------
CLEARANCE_FIT = 0.2    # per side, for parts that slide together
CLEARANCE_PRESS = 0.1  # per side, for press/friction fits
CRUSH_RIB = 0.15       # per side interference for small ribs on a thin, flexible wall (they flex/crush to fit)
HOLE_COMP = 0.2        # added to hole diameters that must fit a shaft/pin (printed holes come out small)

# --- Design-for-printing limits --------------------------------------------------
MIN_WALL = 1.2         # 3 perimeters at 0.4 mm
MIN_FEATURE = 0.8      # smallest rib / pin / text stroke that prints reliably
MAX_OVERHANG_DEG = 45  # degrees from vertical; steeper needs support or a chamfer
MAX_BRIDGE = 20.0      # longest unsupported bridge to design for

# --- Fastener holes --------------------------------------------------------------
# Clearance holes are the final modelled diameters (they already include slop),
# so don't add HOLE_COMP on top.
M3_CLEARANCE = 3.4
M4_CLEARANCE = 4.5

# M3 heat-set insert hole. Check against the inserts you actually use: most
# M3 x 5.7 mm inserts want a 4.0-4.2 mm hole about 1 mm deeper than the insert.
M3_INSERT_D = 4.0
M3_INSERT_DEPTH = 5.0


def hole_d(nominal: float) -> float:
    """Modelled diameter for a hole that must accept a `nominal` shaft or pin."""
    return nominal + HOLE_COMP


def fit_gap(press: bool = False) -> float:
    """Per-side gap between two mating parts."""
    return CLEARANCE_PRESS if press else CLEARANCE_FIT


def check_bed(size: tuple[float, float, float], label: str = "part") -> bool:
    """Print a warning and return False if `size` (x, y, z) doesn't fit the bed."""
    over = [f"{ax}={s:.1f}>{b:.0f}" for ax, s, b in zip("XYZ", size, BED) if s > b]
    if over:
        print(f"WARNING: {label} is bigger than the P2S bed ({', '.join(over)}). "
              "Rotate it, or split it with mesh_tools.split().")
        return False
    return True
