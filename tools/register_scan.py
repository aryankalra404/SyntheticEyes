"""Wraps GNM's skin onto the Infinite head scan, so its displacement map can be baked to GNM UVs.

    python3 tools/register_scan.py

Input (git-ignored): assets/third_party/lpshead/files/head.OBJ, from lpshead.zip in the McGuire
Computer Graphics Archive ("Infinite, 3D Head Scan by Lee Perry-Smith", CC BY 3.0).
Output: assets/gnm/wrapped_to_scan.npz, same layout as wrapped_to_mh.npz with scan_* keys
(x_gnm = scale * R @ x_scan + t).

Same method as tools/register_mh.py: similarity from landmarks, identity fit, smooth snap.
The landmarks are (x, y) picks in the scan's own front view (its units, +x subject's left,
+y up, +z out of the face), read off a gridded textured render and cast onto the surface.
The scan's eyes are closed, so four rings of skin around the eye pockets are not pulled to
it; the relief there is not used either.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mh_core  # noqa: E402
import register_mh  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SCAN_OBJ = REPO / "assets/third_party/lpshead/files/head.OBJ"
OUT = REPO / "assets/gnm/wrapped_to_scan.npz"

# GNM landmark id -> (x, y) in scan units, front view
PICKS = {
    27: (0.0000, 0.0010),     # nasion
    33: (0.0000, -0.0480),    # subnasale
    31: (-0.0180, -0.0450),   # alar bases
    35: (0.0173, -0.0453),
    51: (0.0000, -0.0637),    # top of the upper vermilion
    62: (0.0000, -0.0725),    # lip line
    57: (0.0000, -0.0787),    # bottom of the lower vermilion
    48: (-0.0197, -0.0733),   # mouth corners
    54: (0.0233, -0.0733),
    8: (0.0000, -0.1180),     # chin
    36: (-0.0496, -0.0069),   # outer and inner ends of the closed lash lines
    39: (-0.0150, -0.0046),
    42: (0.0154, -0.0048),
    45: (0.0488, -0.0077),
    17: (-0.0581, 0.0069),    # brow hair centreline: tail, middle, head
    19: (-0.0352, 0.0135),
    21: (-0.0138, 0.0096),
    22: (0.0119, 0.0112),
    24: (0.0333, 0.0123),
    26: (0.0562, 0.0054),
}
NOSE_TIP = 30                 # taken as the most forward point near the midline


def load_scan():
    V, VT, F, FT = mh_core.load_obj(SCAN_OBJ)
    tris, tri_uv = [], []
    for f, ft in zip(F, FT):
        for k in range(1, len(f) - 1):
            tris.append([f[0], f[k], f[k + 1]])
            tri_uv.append([ft[0], ft[k], ft[k + 1]])
    return V, VT, np.array(tris), np.array(tri_uv)


def main():
    args = register_mh.parse_args()
    V, _, T, _ = load_scan()
    ids = sorted(PICKS)
    tri, bary, _ = mh_core.cast_front(V, T, np.array([PICKS[k] for k in ids]))
    if (tri < 0).any():
        raise SystemExit(f"picks missed the scan: {[ids[i] for i in np.where(tri < 0)[0]]}")
    lm = (V[T[tri]] * bary[:, :, None]).sum(1)
    mid = np.where(np.abs(V[:, 0]) < 0.01)[0]
    tip = V[mid[V[mid, 2].argmax()]]
    print(f"[scan] {len(V)} vertices, {len(T)} triangles; nose tip at {np.round(tip, 4)}")
    register_mh.register(args, V, T, np.concatenate([lm, tip[None]]), np.array(ids + [NOSE_TIP]), OUT,
                         prefix="scan", lid_rings=4)


if __name__ == "__main__":
    main()
