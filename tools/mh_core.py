"""Numpy-only helpers for the MakeHuman base mesh (hm08) used as the skin source.

MakeHuman coordinates: decimetres, +Y up, +Z out of the face, subject's left at +X.
Same axes as GNM, so MakeHuman -> GNM is a similarity with scale close to 0.1.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
MH_DIR = REPO / "assets/third_party/makehuman"
BASE_OBJ = MH_DIR / "base_mesh/base.obj"
LANDMARKS_JSON = REPO / "assets/mh_landmarks.json"

# GNM's skin reaches the upper chest, so the crop keeps neck and shoulders, not arms.
CROP_Y_MIN = 4.4
CROP_X_MAX = 1.9


def load_obj(path: Path, group: str | None = None):
    """Returns vertices, uvs, faces (vertex ids) and face uv ids. Faces keep their arity."""
    V, VT, F, FT, g = [], [], [], [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("v "):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                VT.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("g "):
                g = line.split()[1]
            elif line.startswith("f ") and (group is None or g == group):
                toks = [t.split("/") for t in line.split()[1:]]
                F.append([int(t[0]) - 1 for t in toks])
                FT.append([int(t[1]) - 1 if len(t) > 1 and t[1] else -1 for t in toks])
    return np.array(V), np.array(VT), F, FT


def load_group_vertices(path: Path, group: str) -> np.ndarray:
    V, _, F, _ = load_obj(path, group)
    return V[np.unique(np.concatenate([np.asarray(f) for f in F]))]


def load_head():
    """Body group of base.obj cropped to head, neck and shoulders.

    Returns V (all base vertices, dm), VT, quads (n, 4) and quad uv ids (n, 4).
    """
    V, VT, F, FT = load_obj(BASE_OBJ, "body")
    F, FT = np.array(F), np.array(FT)
    P = V[F]
    keep = (P[:, :, 1].min(1) > CROP_Y_MIN) & (np.abs(P[:, :, 0]).max(1) < CROP_X_MAX)
    return V, VT, F[keep], FT[keep]


def triangulate(F: np.ndarray, FT: np.ndarray | None = None):
    T = np.concatenate([F[:, [0, 1, 2]], F[:, [0, 2, 3]]])
    if FT is None:
        return T
    return T, np.concatenate([FT[:, [0, 1, 2]], FT[:, [0, 2, 3]]])


def vertex_normals(V: np.ndarray, T: np.ndarray) -> np.ndarray:
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    out = np.zeros_like(V)
    for k in range(3):
        np.add.at(out, T[:, k], n)
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-20)


def cast_front(V: np.ndarray, T: np.ndarray, xy: np.ndarray, chunk: int = 4000):
    """Casts rays along -Z from in front of the face at each (x, y).

    Returns the front-most front-facing triangle per point (-1 for a miss), its
    barycentric weights and the depth z.
    """
    xy = np.atleast_2d(np.asarray(xy, dtype=np.float64))
    P = V[T]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    lo, hi = xy.min(0) - 1e-6, xy.max(0) + 1e-6
    sel = np.where((n[:, 2] > 0) & (P[:, :, 0].max(1) >= lo[0]) & (P[:, :, 0].min(1) <= hi[0])
                   & (P[:, :, 1].max(1) >= lo[1]) & (P[:, :, 1].min(1) <= hi[1]))[0]
    P = P[sel]
    a, b, c = P[:, 0, :2], P[:, 1, :2], P[:, 2, :2]
    den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    tri = np.full(len(xy), -1, dtype=np.int64)
    bary = np.zeros((len(xy), 3))
    depth = np.full(len(xy), -np.inf)
    for s in range(0, len(xy), chunk):
        q = xy[s:s + chunk]
        dx, dy = q[:, None, 0] - c[None, :, 0], q[:, None, 1] - c[None, :, 1]
        w0 = ((b[:, 1] - c[:, 1])[None] * dx + (c[:, 0] - b[:, 0])[None] * dy) / den[None]
        w1 = ((c[:, 1] - a[:, 1])[None] * dx + (a[:, 0] - c[:, 0])[None] * dy) / den[None]
        w2 = 1 - w0 - w1
        z = w0 * P[None, :, 0, 2] + w1 * P[None, :, 1, 2] + w2 * P[None, :, 2, 2]
        z[(w0 < -1e-9) | (w1 < -1e-9) | (w2 < -1e-9)] = -np.inf
        best = z.argmax(1)
        rows = np.arange(len(q))
        hit = np.isfinite(z[rows, best])
        tri[s:s + chunk] = np.where(hit, sel[best], -1)
        bary[s:s + chunk] = np.stack([w0[rows, best], w1[rows, best], w2[rows, best]], 1)
        depth[s:s + chunk] = z[rows, best]
    return tri, bary, depth
