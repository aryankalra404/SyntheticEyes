"""Writes assets/mh_landmarks.json: MakeHuman surface points matching GNM's 68 landmarks.

    python3 tools/pick_mh_landmarks.py

Run once; the JSON is committed and tools/register_mh.py only reads it. Each landmark is
stored the way GNM stores its own (three vertex indices and barycentric weights), because
the MakeHuman head is too coarse for single vertices to sit on the lip edge or lid margin.

Where the points come from, all in the front view of the unmodified base mesh:
- nose, lips and chin: read off a gridded render of the head with a skin applied, so the
  lip points sit on the painted vermilion border, not on a guess from geometry
- eyes: the lid opening is where the eyeball helper shows in front of the body mesh; the
  outer corner is its end, the inner corner is read off the render, and the lid points
  sit at the same fractions between the corners as GNM's
- brows: centreline of the default eyebrow card, at the same fractions as GNM's five
The subject's left half (+X) is picked and mirrored. Jaw landmarks 0-16 are not used
except the chin; the dense fit handles the jaw line.
"""

from __future__ import annotations

import json

import numpy as np

import mh_core

# (x, y) in MakeHuman decimetres, front view, subject's left half. Keys are GNM landmark ids.
MIDLINE = {
    27: 7.320,  # nasion, deepest point of the bridge
    28: 7.170,
    29: 7.054,
    30: 6.925,  # nose tip
    33: 6.800,  # subnasale
    51: 6.700,  # top of the upper vermilion
    62: 6.616,  # lower edge of the upper lip
    66: 6.602,  # upper edge of the lower lip
    57: 6.497,  # bottom of the lower vermilion
    8: 6.205,   # chin
}
LEFT = {
    34: (0.100, 6.828),  # nostril sill
    35: (0.165, 6.845),  # alar base
    54: (0.252, 6.613),  # mouth corner
    64: (0.240, 6.611),  # inner corner
}
UPPER_LIP = [(0.0, 6.700), (0.04, 6.705), (0.08, 6.715), (0.12, 6.707), (0.14, 6.700),
             (0.18, 6.682), (0.21, 6.658), (0.235, 6.632), (0.252, 6.613)]
LOWER_LIP = [(0.0, 6.497), (0.08, 6.500), (0.12, 6.510), (0.16, 6.535), (0.20, 6.565),
             (0.23, 6.590), (0.252, 6.613)]
LIP_GAP_UPPER_Y, LIP_GAP_LOWER_Y = 6.617, 6.602

# Fractions measured on the GNM template landmarks.
UPPER_LIP_FRAC = {52: 0.362, 53: 0.691}   # x / mouth-corner x
LOWER_LIP_FRAC = {56: 0.448, 55: 0.736}
INNER_LIP_FRAC = {63: 0.532, 65: 0.534}
UPPER_LID_FRAC = {43: 0.327, 44: 0.703}   # inner corner -> outer corner
LOWER_LID_FRAC = {47: 0.303, 46: 0.720}
BROW_FRAC = {22: 0.04, 23: 0.203, 24: 0.484, 25: 0.797, 26: 0.96}
MIRROR = {42: 39, 43: 38, 44: 37, 45: 36, 46: 41, 47: 40, 22: 21, 23: 20, 24: 19, 25: 18,
          26: 17, 34: 32, 35: 31, 52: 50, 53: 49, 54: 48, 55: 59, 56: 58, 63: 61, 64: 60,
          65: 67}
LID_INSET = 0.006  # dm outside the opening, so the point is on the lid margin
# The eyeball only shows from x = 0.204; the lids meet further in, past the caruncle.
INNER_CANTHUS = (0.170, 7.268)


def lid_points(V, T):
    """Eye opening of the subject's left eye from eyeball-helper visibility."""
    eye = mh_core.load_obj(mh_core.BASE_OBJ, "helper-l-eye")
    eye_T = mh_core.triangulate(np.array(eye[2]))
    step = 0.002
    xs, ys = np.arange(0.10, 0.56, step), np.arange(7.12, 7.46, step)
    gx, gy = np.meshgrid(xs, ys)
    xy = np.stack([gx.ravel(), gy.ravel()], 1)
    _, _, zb = mh_core.cast_front(V, T, xy)
    _, _, ze = mh_core.cast_front(V, eye_T, xy)
    open_ = (ze > zb + 1e-4).reshape(gx.shape)
    cols = np.where(open_.any(0))[0]
    xi, xo = INNER_CANTHUS[0], xs[cols[-1]]
    yo = ys[np.where(open_[:, cols[-1]])[0]].mean()
    out = {42: INNER_CANTHUS, 45: (xo + LID_INSET, yo)}
    for table, upper in ((UPPER_LID_FRAC, True), (LOWER_LID_FRAC, False)):
        for k, f in table.items():
            col = int(round((xi + f * (xo - xi) - xs[0]) / step))
            rows = np.where(open_[:, col])[0]
            out[k] = (xs[col], ys[rows[-1]] + LID_INSET if upper else ys[rows[0]] - LID_INSET)
    return out, (xi, xo)


def brow_points():
    """Centreline of the default eyebrow card on the subject's left side."""
    B, _, _, _ = mh_core.load_obj(mh_core.MH_DIR / "makehuman_system_assets/eyebrows/eyebrow001/eyebrow001.obj")
    B = B[B[:, 0] > 0]
    x0, x1 = B[:, 0].min(), B[:, 0].max()
    out = {}
    for k, f in BROW_FRAC.items():
        x = x0 + f * (x1 - x0)
        near = B[np.abs(B[:, 0] - x) < 0.06]
        out[k] = (x, 0.5 * (near[:, 1].min() + near[:, 1].max()))
    return out


def interp(poly, x):
    p = np.array(poly)
    return float(np.interp(x, p[:, 0], p[:, 1]))


def main():
    V, _, F, _ = mh_core.load_head()
    T = mh_core.triangulate(F)
    picks = {k: (0.0, y) for k, y in MIDLINE.items()}
    picks.update(LEFT)
    corner_x, inner_x = LEFT[54][0], LEFT[64][0]
    for k, f in UPPER_LIP_FRAC.items():
        picks[k] = (f * corner_x, interp(UPPER_LIP, f * corner_x))
    for k, f in LOWER_LIP_FRAC.items():
        picks[k] = (f * corner_x, interp(LOWER_LIP, f * corner_x))
    picks[63] = (INNER_LIP_FRAC[63] * inner_x, LIP_GAP_UPPER_Y)
    picks[65] = (INNER_LIP_FRAC[65] * inner_x, LIP_GAP_LOWER_Y)
    lids, opening = lid_points(V, T)
    picks.update(lids)
    picks.update(brow_points())
    for k, m in MIRROR.items():
        picks[m] = (-picks[k][0], picks[k][1])

    ids = sorted(picks)
    tri, bary, _ = mh_core.cast_front(V, T, np.array([picks[k] for k in ids]))
    if (tri < 0).any():
        raise SystemExit(f"picks missed the mesh: {[ids[i] for i in np.where(tri < 0)[0]]}")
    records = []
    for k, t, w in zip(ids, tri, bary):
        verts = T[t]
        records.append({"gnm": int(k), "verts": [int(v) for v in verts],
                        "weights": [round(float(x), 6) for x in w],
                        "position": [round(float(x), 5) for x in (V[verts] * w[:, None]).sum(0)]})
    out = {"mesh": "MakeHuman base.obj (hm08), body group, decimetres, +Y up, +Z forward",
           "note": "landmark = sum(weights * vertices[verts]); gnm is the index into GNM's 68",
           "landmarks": records}
    mh_core.LANDMARKS_JSON.write_text(json.dumps(out, indent=1) + "\n")
    print(f"[pick] {len(records)} landmarks -> {mh_core.LANDMARKS_JSON.relative_to(mh_core.REPO)}")
    print(f"[pick] left eye opening x {opening[0]:.3f} .. {opening[1]:.3f} dm")


if __name__ == "__main__":
    main()
