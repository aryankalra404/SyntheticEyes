"""Shared helpers for the texture tools (numpy only, runs in system python3 or Blender).

- rasterize(): face id + barycentrics per texel for a set of UV triangles
- mesh_texels(): 3D position, surface Jacobian and vertex attributes per texel of a UDIM tile
- fill_nearest(): pad everything outside the UV islands from the nearest island texel
- srgb <-> linear, 8/16-bit PNG writing without PIL (deterministic bytes)

GNM data comes from assets/gnm/base.npz (tools/export_gnm.py). Positions are taken from
`template_vertices`, the bare head the judges load, in millimetres.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
BASE_NPZ = REPO / "assets/gnm/base.npz"


def load_base(path: Path = BASE_NPZ) -> dict[str, np.ndarray]:
    d = np.load(path, allow_pickle=False)
    return {k: d[k] for k in d.files}


def group_names(d) -> list[str]:
    return [str(n) for n in d["vertex_group_names"]]


def group(d, name: str, weights: bool = False) -> np.ndarray:
    i = group_names(d).index(name)
    return d["vertex_group_weights"][i] if weights else d["vertex_group_masks"][i]


def tile_triangles(d, tile: int) -> tuple[np.ndarray, np.ndarray]:
    """Vertex indices (T, 3) and tile-local UVs (T, 3, 2) of the triangles in a UDIM tile."""
    q, t = d["quads"], d["quad_udim_tiles"]
    uv = d["quad_uvs_udim"].reshape(len(q), 4, 2) - np.array([tile - 1001, 0.0])
    sel = np.where(t == tile)[0]
    tri = np.concatenate([q[sel][:, [0, 1, 2]], q[sel][:, [0, 2, 3]]])
    tuv = np.concatenate([uv[sel][:, [0, 1, 2]], uv[sel][:, [0, 2, 3]]])
    return tri, tuv


def rasterize(tuv: np.ndarray, size: int, depth: np.ndarray | None = None):
    """Face id (size, size; -1 = empty) and barycentrics (size, size, 3) per texel centre.

    Row 0 is the top of the image (v = 1), as in a PNG. With `depth` (T, 3) the
    nearest-to-viewer (largest depth) triangle wins and a depth map is returned too.
    """
    fid = np.full((size, size), -1, dtype=np.int32)
    zbuf = np.full((size, size), -np.inf)
    bary = np.zeros((size, size, 3), dtype=np.float32)
    px = np.empty_like(tuv)
    px[..., 0] = tuv[..., 0] * size - 0.5
    px[..., 1] = (1.0 - tuv[..., 1]) * size - 0.5
    lo = np.clip(np.floor(px.min(1)).astype(int), 0, size - 1)
    hi = np.clip(np.ceil(px.max(1)).astype(int), 0, size - 1)
    for f in range(len(px)):
        (x0, y0), (x1, y1) = lo[f], hi[f]
        a, b, c = px[f]
        det = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(det) < 1e-12:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        w1 = ((xs - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (ys - a[1])) / det
        w2 = ((b[0] - a[0]) * (ys - a[1]) - (xs - a[0]) * (b[1] - a[1])) / det
        w0 = 1.0 - w1 - w2
        eps = -1e-6
        inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if not inside.any():
            continue
        yy, xx = ys[inside], xs[inside]
        w = np.stack([w0[inside], w1[inside], w2[inside]], -1)
        if depth is not None:
            z = w[:, 0] * depth[f, 0] + w[:, 1] * depth[f, 1] + w[:, 2] * depth[f, 2]
            near = z > zbuf[yy, xx]
            yy, xx, w, z = yy[near], xx[near], w[near], z[near]
            zbuf[yy, xx] = z
        fid[yy, xx] = f
        bary[yy, xx] = w
    if depth is not None:
        return fid, bary, zbuf
    return fid, bary


class Texels:
    """Per-texel geometry of one UDIM tile on the GNM template.

    pos   (N, 3) mm        surface point of each covered texel
    jac   (N, 3, 2) mm/px  dP/dx, dP/dy for one texel step right (+x) and down (+y)
    ys,xs (N,)             texel coordinates of the covered texels
    """

    def __init__(self, d, tile: int, size: int, verts: np.ndarray | None = None):
        self.size = size
        V = (d["template_vertices"] if verts is None else verts).astype(np.float64) * 1000.0
        tri, tuv = tile_triangles(d, tile)
        fid, bary = rasterize(tuv, size)
        self.mask = fid >= 0
        self.ys, self.xs = np.nonzero(self.mask)
        self.fid = fid[self.mask]
        self.bary = bary[self.mask].astype(np.float64)
        self.tri = tri
        P = V[tri]                                           # (T, 3, 3)
        self.pos = np.einsum("nk,nkc->nc", self.bary, P[self.fid])
        # Jacobian per triangle: solve [e1 e2] = J [d1 d2] with UV edges in texel units.
        px = np.stack([tuv[..., 0] * size, (1.0 - tuv[..., 1]) * size], -1)
        d1, d2 = px[:, 1] - px[:, 0], px[:, 2] - px[:, 0]
        e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
        D = np.stack([d1, d2], -1)                           # (T, 2, 2) columns d1, d2
        E = np.stack([e1, e2], -1)                           # (T, 3, 2)
        det = np.linalg.det(D)
        ok = np.abs(det) > 1e-12
        Dinv = np.zeros_like(D)
        Dinv[ok] = np.linalg.inv(D[ok])
        self.tri_jac = E @ Dinv                              # (T, 3, 2)
        self.jac = self.tri_jac[self.fid]

    def attr(self, values: np.ndarray) -> np.ndarray:
        """Interpolate a per-vertex attribute (V,) or (V, C) to the covered texels."""
        vals = values[self.tri][self.fid]                    # (N, 3[, C])
        if vals.ndim == 2:
            return np.einsum("nk,nk->n", self.bary, vals)
        return np.einsum("nk,nkc->nc", self.bary, vals)

    def image(self, values: np.ndarray, fill=0.0) -> np.ndarray:
        """Scatter per-texel values back into a (size, size[, C]) array."""
        shape = (self.size, self.size) + values.shape[1:]
        out = np.full(shape, fill, dtype=np.float32)
        out[self.ys, self.xs] = values
        return out

    def mm_per_px(self) -> np.ndarray:
        """Geometric-mean surface length of one texel, per covered texel (mm)."""
        a = np.linalg.norm(np.cross(self.jac[:, :, 0], self.jac[:, :, 1]), axis=1)
        return np.sqrt(a)


def smooth_vertex_values(d, values: np.ndarray, iterations: int) -> np.ndarray:
    """Umbrella smoothing of a per-vertex value over the quad mesh edges."""
    q = d["quads"]
    edges = np.concatenate([q[:, [0, 1]], q[:, [1, 2]], q[:, [2, 3]], q[:, [3, 0]]])
    edges = np.unique(np.sort(edges, 1), axis=0)
    n = len(d["template_vertices"])
    deg = np.bincount(edges.ravel(), minlength=n).astype(np.float64)
    deg[deg == 0] = 1
    x = values.astype(np.float64).copy()
    for _ in range(iterations):
        acc = np.zeros_like(x)
        np.add.at(acc, edges[:, 0], x[edges[:, 1]])
        np.add.at(acc, edges[:, 1], x[edges[:, 0]])
        x = 0.5 * x + 0.5 * acc / (deg if x.ndim == 1 else deg[:, None])
    return x


def fill_nearest(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Copy each texel outside `mask` from the nearest texel inside it."""
    from scipy.ndimage import distance_transform_edt
    _, (iy, ix) = distance_transform_edt(~mask, return_indices=True)
    return img[iy, ix]


def fill_smooth(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Texels inside `mask` are kept; the rest is filled by push-pull (averaged down until
    full, pulled back up with a small blur), so the padding outside the UV islands is a soft
    continuation of their borders instead of the streaks a nearest-texel fill leaves.
    img: (S, S, C) float, S a power of two."""
    levels = [(img * mask[..., None], mask.astype(np.float64))]
    while levels[-1][1].shape[0] > 1:
        c, w = levels[-1]
        h, wd = w.shape
        levels.append((c.reshape(h // 2, 2, wd // 2, 2, -1).sum((1, 3)), w.reshape(h // 2, 2, wd // 2, 2).sum((1, 3))))
    c, w = levels[-1]
    filled = c / np.maximum(w, 1e-8)[..., None]
    for c, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(filled, 2, 0), 2, 1)
        for axis in (0, 1):
            pad = np.pad(up, [(1, 1) if a == axis else (0, 0) for a in range(3)], mode="edge")
            lo = pad[:-2] if axis == 0 else pad[:, :-2]
            hi = pad[2:] if axis == 0 else pad[:, 2:]
            up = 0.25 * lo + 0.5 * up + 0.25 * hi
        k = np.clip(w, 0, 1)[..., None]
        filled = k * (c / np.maximum(w, 1e-8)[..., None]) + (1 - k) * up
    return filled


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def to_u8(x: np.ndarray) -> np.ndarray:
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def write_png(path: Path, img: np.ndarray, level: int = 6) -> None:
    """8-bit grey/RGB/RGBA PNG, no timestamps or metadata, so reruns are byte-identical."""
    img = np.ascontiguousarray(img)
    if img.dtype != np.uint8:
        raise TypeError("write_png wants uint8")
    h, w = img.shape[:2]
    ch = 1 if img.ndim == 2 else img.shape[2]
    ctype = {1: 0, 3: 2, 4: 6}[ch]
    raw = np.empty((h, 1 + w * ch), dtype=np.uint8)
    raw[:, 0] = 0
    raw[:, 1:] = img.reshape(h, w * ch)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw.tobytes(), level)))
        f.write(chunk(b"IEND", b""))


def read_png(path: Path) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(path))
