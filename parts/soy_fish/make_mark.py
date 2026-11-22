"""Draw the Japanese plastic-recycling mark (プラ) that sits on the soy fish's +Y flank.

Run once (needs matplotlib and the macOS Hiragino font):
    uv run --with matplotlib python parts/soy_fish/make_mark.py
Writes parts/soy_fish/pura_mark.npz, a 0.1 mm height mask that fish.py embosses onto the flank.

Layout measured from the original model (imports/soy_fish_lamp, Fish.stl): a rounded-square frame
made of two chasing arrows, with the katakana プラ inside. Coordinates here are "as seen looking at
the +Y flank": u to the right (= -X in model space), v up (= Z). Origin = centre of the frame.
"""

from pathlib import Path

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MPath
from matplotlib.textpath import TextPath
from scipy import ndimage as ndi

FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
RES = 0.1                    # mm per pixel
HALF_W, HALF_H = 21.0, 17.5  # mm, frame outer half-size
STROKE = 3.4                 # mm, frame line width
CORNER_R = 6.0               # mm, outer corner radius
ARROW_W, ARROW_H = 11.0, 7.0  # mm, arrowhead base width and length
# left side (+X in model): arrowhead pointing up, apex at v=+7; frame gap above it up to v=+9
LEFT_ARROW_APEX, LEFT_GAP_TOP = 7.0, 9.0
# right side (-X in model): arrowhead pointing down, apex at v=+5.5; frame gap below it down to v=+1.5
RIGHT_ARROW_APEX, RIGHT_GAP_BOTTOM = 5.5, 1.5
TEXT_BOX = (-13.0, 14.0, -10.5, 11.0)  # u0, u1, v0, v1 for プラ


def rounded_rect_sdf(u, v, hw, hh, r):
    qx, qy = np.abs(u) - (hw - r), np.abs(v) - (hh - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def triangle(u, v, pts):
    return MPath(pts).contains_points(np.column_stack([u.ravel(), v.ravel()])).reshape(u.shape)


def main() -> None:
    us = np.arange(-HALF_W - 8, HALF_W + 8, RES)
    vs = np.arange(-HALF_H - 4, HALF_H + 4, RES)
    U, V = np.meshgrid(us, vs)

    d = rounded_rect_sdf(U, V, HALF_W, HALF_H, CORNER_R)
    frame = (d <= 0) & (d > -STROKE)
    side = HALF_W - STROKE / 2   # centre line of the vertical strokes
    left_base = LEFT_ARROW_APEX - ARROW_H
    frame &= ~((U < -HALF_W + STROKE + 0.5) & (V > left_base) & (V < LEFT_GAP_TOP))
    right_base = RIGHT_ARROW_APEX + ARROW_H
    frame &= ~((U > HALF_W - STROKE - 0.5) & (V > RIGHT_GAP_BOTTOM) & (V < right_base))
    up_arrow = triangle(U, V, [(-side - ARROW_W / 2, left_base), (-side + ARROW_W / 2, left_base),
                               (-side, LEFT_ARROW_APEX)])
    down_arrow = triangle(U, V, [(side - ARROW_W / 2, right_base), (side + ARROW_W / 2, right_base),
                                 (side, RIGHT_ARROW_APEX)])

    tp = TextPath((0, 0), "プラ", size=10, prop=FontProperties(fname=FONT))
    ext = tp.get_extents()
    u0, u1, v0, v1 = TEXT_BOX
    sx, sy = (u1 - u0) / ext.width, (v1 - v0) / ext.height
    verts = (tp.vertices - [ext.x0, ext.y0]) * [sx, sy] + [u0, v0]
    # Fill glyph outlines with the even-odd rule so counters (holes) stay open.
    polys = MPath(verts, tp.codes).to_polygons()
    inside = np.zeros(U.size, int)
    pts = np.column_stack([U.ravel(), V.ravel()])
    for poly in polys:
        inside += MPath(poly).contains_points(pts)
    text = (inside % 2 == 1).reshape(U.shape)

    mask = frame | up_arrow | down_arrow | text
    mask = ndi.binary_opening(mask, iterations=2)  # drop slivers thinner than ~0.4 mm
    out = Path(__file__).with_name("pura_mark.npz")
    np.savez_compressed(out, u=us, v=vs, mask=mask, res=RES)
    print(f"wrote {out}: {mask.shape}, {mask.mean() * 100:.1f}% filled")

    try:  # preview next to the scratch renders, if that folder exists
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        prev = Path(__file__).resolve().parents[2] / "scratch" / "renders"
        if prev.exists():
            plt.figure(figsize=(6, 5)); plt.imshow(mask, origin="lower", cmap="gray_r",
                                                   extent=[us[0], us[-1], vs[0], vs[-1]])
            plt.title("pura mark as seen from +Y"); plt.savefig(prev / "pura_mark.png", dpi=80)
    except Exception as e:  # preview is optional
        print("preview skipped:", e)


if __name__ == "__main__":
    main()
