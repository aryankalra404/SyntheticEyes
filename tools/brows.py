"""Eyebrow strands grown per head on the brow painted in the set's albedo. Pure numpy, no bpy.

tools/build_scene.py calls `grow(...)` on whatever vertices it builds (template or identity) with
the albedo of the set the scene is built with (--texture), and gets the same binding arrays
tools/lashes.py and tools/vellus.py return (triangle, barycentrics, offset in the triangle's
frame, radius per point, points per hair), so the brows follow shape keys and bones like the
lashes do.

Why: the carried Mindfront brows were modelled for MakeHuman's brow and land beside the paint
on GNM heads, and tex_09 (the scan) has no carried set at all, so its brow was paint only and
read flat in the eye close-up. Here every hair roots on the painted brow of this set:
- where: inside GNM's left/right_brow_region, kept only where the albedo is darker than the skin
  around it (luminance under BROW_DARK of a local skin level that leaves dark pixels out), and
  more likely the darker it is;
- how many: 450 to 600 per brow, POINTS points each; 6 to 11 mm long in the body, 3.5 to 5 mm at
  the inner end and the tail; radius 45 um at the root to 14 um at the tip (thinner tips were
  under a third of a pixel in the eye close-up and blended into the lit skin as straw);
- direction (on the skin): the inner third grows up and out (about 60 deg above the line to the
  temple); the body follows the brow's arch toward the temple, its top row leaning down and its
  bottom row leaning up so the two meet along the middle; 8 deg of scatter, and one hair in
  twenty-five is a stray up to 20 deg off (at 12 deg and 1 in 15 the tail read as tangled wool);
- lying flat: 8 to 15 deg off the skin at the root, curving back so the tip is 0.3 to 0.8 mm
  above the skin. Each point is laid on the skin under it (the plane of the nearest vertex) at
  that height, so the hair follows the brow ridge. No hair passes through skin: the crossing
  test of tools/lashes.py, and a hair that crosses is lifted until it clears (or dropped).
"""

from __future__ import annotations

import numpy as np

from lashes import crosses

POINTS = 6
COUNT = (450, 600)              # per brow, inclusive
LENGTH_BODY = (0.006, 0.011)    # m
LENGTH_ENDS = (0.0035, 0.005)    # m, at the inner end and the tail
ROOT_RADIUS = 0.000045          # m
TIP_RADIUS = 0.000014
ROOT_ANGLE = (8.0, 15.0)        # deg off the skin at the root
TIP_HEIGHT = (0.0003, 0.0008)   # m above the skin at the tip
ROOT_SINK = 0.00005             # m the root starts under the skin
INNER_ANGLE = 60.0              # deg above the line to the temple, inner third
MEET = 20.0                     # deg the top and bottom rows lean toward the middle line
SCATTER = 8.0                   # deg
STRAY_RATE = 1.0 / 25.0
STRAY = 20.0                    # deg, at most
BROW_DARK = (0.10, 0.30)        # 1 - luminance / skin level: no hair below the first, full weight at the second
SKIN_BLUR = 0.006               # m, about how far "the skin around it" reaches
UV_METRE = 0.40                 # m of face per unit of GNM's tile 1001 (brow region: 5.3 cm over 0.13 u)
CANDIDATES = 40000              # per brow, roots drawn before keeping those on the paint
REGIONS = {"L": "left_brow_region", "R": "right_brow_region"}


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def frames(A, B, C):
    """Per-triangle orthonormal frame rows (edge, normal x edge, normal); as tools/lashes.py."""
    e1 = unit(B - A)
    n = unit(np.cross(B - A, C - A))
    return np.stack([e1, np.cross(n, e1), n], 1)


def box_blur(a, r, axis):
    c = np.cumsum(np.pad(a, [(r + 1, r) if i == axis else (0, 0) for i in range(a.ndim)], mode="edge"), axis=axis)
    hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
    lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
    return (hi - lo) / (2 * r + 1)


def blur(a, r):
    for _ in range(3):
        a = box_blur(box_blur(a, r, 0), r, 1)
    return a


def darkness_map(albedo):
    """1 - luminance / local skin level over the image (rows top to bottom, as a file reads).
    The skin level is a wide blur of the luminance in which pixels darker than their surround
    (the paint itself) are left out, so a thick brow does not darken its own reference."""
    L = 0.2126 * albedo[..., 0] + 0.7152 * albedo[..., 1] + 0.0722 * albedo[..., 2]
    r = max(1, int(round(SKIN_BLUR / UV_METRE * L.shape[1] / 3.0)))
    ref = blur(L, r)
    for _ in range(2):
        w = (L > 0.9 * ref).astype(np.float64)
        ref = blur(L * w, r) / np.maximum(blur(w, r), 1e-6)
    return 1.0 - L / np.maximum(ref, 1e-6)


def sample(img, uv):
    """Bilinear lookup of img (rows top to bottom) at tile UVs (n, 2)."""
    h, w = img.shape[:2]
    x = np.clip(uv[:, 0] * w - 0.5, 0, w - 1.001)
    y = np.clip((1.0 - uv[:, 1]) * h - 0.5, 0, h - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = x - x0, y - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
            + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)


def vertex_normals(V, T):
    n = np.zeros_like(V)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    for i in range(3):
        np.add.at(n, T[:, i], fn)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    return n * np.sign((n * (V - V.mean(0))).sum(1, keepdims=True))      # outward


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def grow_side(V, triangles, tri_uv, names, masks, dark, side, rng, vn):
    region = masks[names.index(REGIONS[side])]
    sel = np.where(region[triangles].all(1))[0]
    T = triangles[sel]
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(B - A, C - A), axis=1)
    pick = rng.choice(len(T), size=CANDIDATES, p=area / area.sum())
    r1, r2 = np.sqrt(rng.random(CANDIDATES)), rng.random(CANDIDATES)
    bary = np.stack([1.0 - r1, r1 * (1.0 - r2), r1 * r2], 1)
    uv = (tri_uv[sel][pick] * bary[:, :, None]).sum(1)
    d = sample(dark, uv)
    w = np.clip((d - BROW_DARK[0]) / (BROW_DARK[1] - BROW_DARK[0]), 0.0, 1.0)
    ok = np.where(w > 0)[0]
    n = int(rng.integers(COUNT[0], COUNT[1] + 1))
    if len(ok) < n:
        print(f"[brows] {side}: only {len(ok)} candidate roots on the paint, wanted {n}")
        n = len(ok)
    keep = rng.choice(ok, size=n, replace=False, p=w[ok] / w[ok].sum())
    keep.sort()
    tri, bary = sel[pick[keep]], bary[keep]
    A, B, C = V[triangles[tri, 0]], V[triangles[tri, 1]], V[triangles[tri, 2]]
    root = A * bary[:, :1] + B * bary[:, 1:2] + C * bary[:, 2:3]
    F = frames(A, B, C)
    normal = F[:, 2] * np.sign((F[:, 2] * (root - V.mean(0))).sum(1, keepdims=True))

    # brow coordinates: u along the brow (0 inner end, 1 tail), v across it (+1 top row, -1 bottom)
    sign = 1.0 if side == "L" else -1.0
    lat = root[:, 0] * sign
    lo, hi = np.percentile(lat, [1.5, 98.5])
    u = np.clip((lat - lo) / (hi - lo), 0.0, 1.0)
    bins = np.linspace(0, 1, 11)
    mid = 0.5 * (bins[1:] + bins[:-1])
    yc, hw = np.zeros(len(mid)), np.zeros(len(mid))
    for k in range(len(mid)):
        m = (u >= bins[k]) & (u <= bins[k + 1])
        ys = root[m, 1] if m.sum() >= 8 else root[np.argsort(np.abs(u - mid[k]))[:8], 1]
        yc[k] = np.median(ys)
        hw[k] = max(0.5 * (np.percentile(ys, 90) - np.percentile(ys, 10)), 0.0015)
    yc = np.convolve(np.pad(yc, 1, mode="edge"), [0.25, 0.5, 0.25], "valid")
    hw = np.convolve(np.pad(hw, 1, mode="edge"), [0.25, 0.5, 0.25], "valid")
    v = np.clip((root[:, 1] - np.interp(u, mid, yc)) / np.interp(u, mid, hw), -1.0, 1.0)
    slope = np.gradient(yc, mid * (hi - lo))                       # dy / d(lateral), the arch
    arch = np.degrees(np.arctan(np.interp(u, mid, slope)))

    # direction on the skin, as an angle from the line to the temple toward up
    body = arch - MEET * v
    s = smoothstep(0.22, 0.42, u)
    theta = (1 - s) * INNER_ANGLE + s * body + rng.normal(0.0, SCATTER, n)
    stray = rng.random(n) < STRAY_RATE
    theta[stray] += rng.choice([-1.0, 1.0], int(stray.sum())) * rng.uniform(SCATTER, STRAY, int(stray.sum()))
    out = np.array([sign, 0.0, 0.0])[None] - (normal * sign * normal[:, :1])
    out = unit(out)
    up = unit(np.array([0.0, 1.0, 0.0])[None] - normal * normal[:, 1:2] - out * (out[:, 1:2]))
    th = np.radians(theta)[:, None]
    along = out * np.cos(th) + up * np.sin(th)

    ends = np.minimum(smoothstep(0.0, 0.25, u), 1.0 - smoothstep(0.8, 1.0, u))
    length = rng.uniform(LENGTH_ENDS[0] + (LENGTH_BODY[0] - LENGTH_ENDS[0]) * ends,
                         LENGTH_ENDS[1] + (LENGTH_BODY[1] - LENGTH_ENDS[1]) * ends)
    a0 = np.tan(np.radians(rng.uniform(*ROOT_ANGLE, n)))
    tip = rng.uniform(*TIP_HEIGHT, n)
    q = np.linspace(0.0, 1.0, POINTS)

    # skin under the hairs: vertices and triangles near this brow
    centre = root.mean(0)
    near_v = np.where(np.linalg.norm(V - centre, axis=1) < 0.045)[0]
    near_t = triangles[(np.linalg.norm(V[triangles].mean(1) - centre, axis=1) < 0.045)]
    skin_tris = (V[near_t[:, 0]], V[near_t[:, 1]], V[near_t[:, 2]])

    def lay(lift):
        """Hair points: walk along the skin, at height h(s) above the plane of the nearest vertex."""
        S = length[:, None] * q[None]
        h = (a0[:, None] * S * (1.0 - q[None]) + tip[:, None] * q[None] ** 2) * lift[:, None]
        h[:, 0] = -ROOT_SINK
        P = root[:, None, :] + along[:, None, :] * S[..., None]
        flat = P.reshape(-1, 3)
        j = near_v[np.argmin(((flat[:, None, :] - V[near_v][None]) ** 2).sum(-1), axis=1)]
        nn = vn[j]
        flat = flat - ((flat - V[j]) * nn).sum(1, keepdims=True) * nn
        P = flat.reshape(n, POINTS, 3)
        nn = nn.reshape(n, POINTS, 3)
        nn[:, 0] = normal
        P[:, 0] = root
        return P + nn * h[..., None]

    lift = np.ones(n)
    for _ in range(12):
        pts = lay(lift)
        seg0, seg1 = pts[:, 1:-1].reshape(-1, 3), pts[:, 2:].reshape(-1, 3)
        hit = np.concatenate([crosses(seg0[c:c + 400], seg1[c:c + 400], *skin_tris)
                              for c in range(0, len(seg0), 400)]).reshape(n, POINTS - 2).any(1)
        if not hit.any():
            break
        lift[hit] *= 1.3
    good = ~hit
    lifted = int((lift > 1).sum())
    print(f"[brows] {side}: {int(good.sum())} hairs ({lifted} lifted to clear the skin, "
          f"{int((~good).sum())} dropped), {len(ok)} of {CANDIDATES} candidate roots on the paint")

    radius = (ROOT_RADIUS + (TIP_RADIUS - ROOT_RADIUS) * q ** 1.2)[None, :] * rng.uniform(0.9, 1.1, (n, 1))
    base = root
    off = np.einsum("nij,npj->npi", F, pts - base[:, None, :])
    g = np.where(good)[0]
    return (np.repeat(triangles[tri[g]], POINTS, 0).astype(np.int32), np.repeat(bary[g], POINTS, 0),
            off[g].reshape(-1, 3), radius[g].reshape(-1).astype(np.float32),
            np.full(len(g), POINTS, dtype=np.int32), pts[g].reshape(-1, 3))


def grow(V, triangles, tri_uv, names, masks, albedo, seed=0):
    """Brows of both sides on vertices V (GNM coordinates: +Y up, +Z forward, metres).

    triangles: the skin triangles (n, 3) of tile 1001; tri_uv: their UVs in that tile (n, 3, 2).
    albedo: the set's skin.1001 image as floats (rows top to bottom, as a file reads; any size).
    Returns tri, bary, off, radius, count and the hair points, as tools/lashes.py grow()."""
    names = list(names)
    dark = darkness_map(np.asarray(albedo, dtype=np.float64))
    vn = vertex_normals(V, triangles)
    parts = [grow_side(V, triangles, tri_uv, names, masks, dark, side,
                       np.random.default_rng([seed, 11, i]), vn) for i, side in enumerate(("L", "R"))]
    return tuple(np.concatenate([p[k] for p in parts]) for k in range(6))
