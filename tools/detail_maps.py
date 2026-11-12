"""Skin detail maps for GNM tile 1001: pore/lip-crease normal map, roughness, albedo detail.

    python3 tools/detail_maps.py --seed 0                       # outputs/tmp/m2/detail/seed_0/
    python3 tools/detail_maps.py --seed 3 --out textures/tex_03 --pore-strength 1.1

Writes (all non-colour data except where noted):

    skin_normal.1001.png   4096²  tangent-space normal map, OpenGL convention (+G = +v),
                                  MikkTSpace tangent along +u. Pores, skin micro-furrows,
                                  vertical lip creases, fine lines under the lower lid and
                                  at the outer eye corner.
    skin_rough.1001.png    2048²  roughness 0..1, 8-bit grey. Shinier nose, forehead, lips.
    skin_detail.1001.png   4096²  albedo multiply map, linear light, 128 = x1.0 (value/128).
                                  Mottling, freckles, moles, redness, small veins, pore tint.
                                  Apply with apply_albedo_detail() (section 5).

Everything is built on the bare GNM template (`template_vertices`), the head the judges load.
Detail is placed on the surface, not in UV: pores are stamped through each texel's surface
Jacobian so they stay round where the unwrap stretches; low-frequency fields are 3D noise
sampled at each texel's surface point, so they are continuous across UV seams. Region weights
come from GNM's vertex groups, smoothed over the mesh.

numpy + scipy only (system python3). Same arguments, same bytes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates, zoom

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tex_core as tc  # noqa: E402

REPO = tc.REPO
TILE = 1001

# Per-region values. Each region is a weighted sum of GNM vertex groups; the result is
# blended with smoothed weights, so the lists only need to be roughly right.
REGIONS = {
    "nose": ["nose_region"],
    "forehead": ["forehead_region", "middle_brow_region"],
    "cheek": ["left_cheek_region", "right_cheek_region", "left_zygomatic_region",
              "right_zygomatic_region", "left_infraorbital_region", "right_infraorbital_region",
              "left_parotid_region", "right_parotid_region"],
    "chin": ["chin_region", "upper_lip_region", "lower_lip_region"],
    "lids": ["left_orbital_region", "right_orbital_region"],
    "temple": ["left_temple_region", "right_temple_region"],
    "brow": ["left_brow_region", "right_brow_region"],
    "lips": ["upper_lip", "lower_lip"],
    "ears": ["ears"],
}
#                pores/mm²  pore sigma mm  pore depth  micro  roughness  redness  freckles
PROFILE = {
    "default":  (1.8,       0.050,         0.6,        1.0,   0.52,      0.0,     0.15),
    "nose":     (5.5,       0.072,         1.25,       0.6,   0.34,      1.0,     1.0),
    "forehead": (4.6,       0.046,         0.75,       0.9,   0.40,      0.15,    0.6),
    "cheek":    (4.2,       0.060,         1.0,        1.0,   0.55,      0.8,     1.0),
    "chin":     (3.6,       0.055,         0.85,       0.9,   0.46,      0.3,     0.3),
    "lids":     (0.8,       0.035,         0.35,       1.3,   0.44,      0.2,     0.2),
    "temple":   (2.2,       0.045,         0.55,       1.0,   0.50,      0.0,     0.3),
    "brow":     (2.6,       0.050,         0.6,        0.8,   0.50,      0.0,     0.1),
    "lips":     (0.0,       0.040,         0.0,        0.0,   0.30,      0.0,     0.0),
    "ears":     (1.4,       0.040,         0.5,        0.8,   0.48,      0.3,     0.1),
}
FIELDS = ["density", "sigma", "depth", "micro", "rough", "red", "freckle"]

# Relief and colour scales at strength 1.0. Raised 2x (redness 1.6x) on 13 Nov: at the first values (pores
# 0.024 mm, micro 0.014 mm, mottling 3.5 %, redness 10 %) the grey head read as smooth plastic
# at face size and the colour detail could not be seen in a face render.
PORE_DEPTH_MM = 0.048
PORE_NORM_MM = PORE_DEPTH_MM * 1.17          # typical pore height, for tint and roughness
MICRO_DEPTH_MM = 0.028
LID_LINE_DEPTH_MM = 0.022
MOTTLE = 0.07
REDNESS = (0.016, 0.16, 0.136)              # 1.6x: at 2x the cheeks read as a blush patch

# Scanned micro-relief (tools/bake_scan.py): the displacement map of the Infinite head scan
# ("Infinite, 3D Head Scan by Lee Perry-Smith", CC BY 3.0) in GNM's UV layout. Where it is
# trusted it replaces the generated pores and micro-furrows; lids, brows, ears and lips stay
# generated. Without the file the maps are fully generated.
SCAN_HEIGHT = REPO / "assets/gnm/scan_height.npz"
SCAN_TILT_DEG = 4.5                         # mean normal tilt it is scaled to on nose, cheeks, forehead
SCAN_HIGHPASS_PX = 14                       # about 1.6 mm on the face: keeps pores and furrows only


# --------------------------------------------------------------------------- fields

def region_fields(d, T: tc.Texels, scan_brows: bool = False) -> dict[str, np.ndarray]:
    """Per-texel value of each PROFILE column, blended by smoothed region weights."""
    W = {}
    for name, groups in REGIONS.items():
        w = sum(tc.group(d, g, True).astype(np.float64) for g in groups)
        w = np.clip(w, 0, 1)
        iters = 3 if name == "lips" else 6
        W[name] = np.clip(tc.smooth_vertex_values(d, w, iters), 0, 1)
    # lips win over the chin/lip regions around them
    for k in W:
        if k != "lips":
            W[k] = W[k] * (1 - W["lips"])
    total = sum(W.values())
    W["default"] = np.clip(1 - total, 0, 1)
    total = total + W["default"]
    out = {f: np.zeros(len(d["template_vertices"])) for f in FIELDS}
    for name, w in W.items():
        for i, f in enumerate(FIELDS):
            out[f] += w * PROFILE[name][i]
    res = {f: T.attr(out[f] / total) for f in FIELDS}
    res["lips"] = T.attr(W["lips"] / total)
    res["veins"] = T.attr(np.clip(W["temple"] * 1.5 + W["lids"], 0, 1) / total)
    res["lid_s"], res["lid_w"] = lid_coords(d, T)
    # where a scanned relief may be used: not around the eyes (the scan's are closed), not the
    # brows (its own brow hair is in the relief), not the ears or the lips
    sockets = tc.group(d, "eye_sockets", True).astype(np.float64)
    near_eye = np.clip(4 * tc.smooth_vertex_values(d, sockets, 10), 0, 1)
    near_brow = np.clip(3 * tc.smooth_vertex_values(d, W["brow"], 6), 0, 1)     # brow tails reach the temple
    if scan_brows:                      # the albedo is the scan's own: its brow relief belongs
        near_brow = 0.0
    block = np.clip(near_eye + W["lids"] + near_brow + W["ears"] + W["lips"], 0, 1)
    res["scan_ok"] = T.attr(1 - block)
    return res


def lid_coords(d, T):
    """Per texel: distance below the lower-lid margin in mm (s) and a weight for the fine lines.

    The lower margin is the front rim of `eye_sockets` below the line between the corners.
    Past the outer corner the margin is continued as a line rising gently, so the lines there
    run along the lid direction and fan out toward the temple. Lines of constant s follow the lid.
    """
    V = d["template_vertices"] * 1000.0
    sock, ext = tc.group(d, "eye_sockets"), tc.group(d, "skin_exterior")
    q = d["quads"]
    mixed = sock[q].any(1) & (ext & ~sock)[q].any(1)
    rim = np.unique(q[mixed][sock[q][mixed]])
    P = T.pos
    s_all = np.zeros(len(P), dtype=np.float32)
    w_all = np.zeros(len(P), dtype=np.float32)
    for sign in (1.0, -1.0):
        r = rim[np.sign(V[rim, 0]) == sign]
        ox, oy = V[r, 0] * sign, V[r, 1]
        i_in, i_out = np.argmin(ox), np.argmax(ox)
        x_in, y_in, x_out, y_out = ox[i_in], oy[i_in], ox[i_out], oy[i_out]
        chord = y_in + (ox - x_in) / (x_out - x_in) * (y_out - y_in)
        low = np.where(oy <= chord + 1e-6)[0]
        order = np.argsort(ox[low])
        lx, ly = ox[low][order], oy[low][order]
        tx, ty = P[:, 0] * sign, P[:, 1]
        y_lid = np.interp(tx, lx, ly)
        past = tx > x_out
        y_lid[past] = y_out + 0.2 * (tx[past] - x_out)
        s = y_lid - ty
        near = ((np.sign(P[:, 0]) == sign) & (P[:, 2] > V[r, 2].mean() - 22)
                & (tx > x_in - 2) & (tx < x_out + 17) & (s > -8) & (s < 11))
        corner = smoothstep(x_out - 1, x_out + 4, tx)
        s_lo = 1.0 + (-5.0 - 1.0) * corner                   # under the lid from 1 mm; above the
        w = (smoothstep(s_lo, s_lo + 1.2, s) * (1 - smoothstep(5.5, 9.5, s))  # corner line too
             * smoothstep(x_in + 1, x_in + 6, tx) * (1 - smoothstep(x_out + 8, x_out + 16, tx)))
        w *= 1 - 0.45 * smoothstep(1.5, 8, np.abs(s))      # strongest close to the lid
        s_all[near] = s[near]
        w_all[near] = w[near]
    return s_all, w_all


class Noise3:
    """Smooth 3D value noise on a lattice over the head, sampled at surface points (mm)."""

    def __init__(self, rng, lo, hi, spacing):
        self.lo, self.spacing = lo - 3 * spacing, spacing
        shape = np.ceil((hi - self.lo) / spacing).astype(int) + 4
        g = gaussian_filter(rng.standard_normal(shape).astype(np.float32), 1.0)
        self.g = g / g.std()

    def __call__(self, pos):
        c = ((pos - self.lo) / self.spacing).T
        return map_coordinates(self.g, c, order=1, mode="nearest")


def fbm3(rng, pos, lo, hi, spacings, weights):
    acc = np.zeros(len(pos), dtype=np.float32)
    for s, w in zip(spacings, weights):
        acc += w * Noise3(rng, lo, hi, s)(pos)
    return acc / np.sqrt(np.sum(np.square(weights)))


def splat(T: tc.Texels, idx, sigma_mm, amp, size, max_radius=6):
    """Sum of surface-round Gaussians at texels `idx` (into T arrays), each sigma_mm wide.

    Kernel is evaluated through each centre texel's Jacobian, so a pore that is round on the
    surface becomes the right ellipse in UV. Returns a (size, size) float32 image.
    """
    out = np.zeros(size * size, dtype=np.float64)
    J = T.jac[idx]                                              # (P, 3, 2)
    smin = np.linalg.svd(J, compute_uv=False)[:, -1]
    rad = np.clip(np.ceil(3 * sigma_mm / np.maximum(smin, 1e-6)), 1, max_radius).astype(int)
    cx = T.xs[idx] + 0.5 + T.jitter[idx, 0]
    cy = T.ys[idx] + 0.5 + T.jitter[idx, 1]
    for r in np.unique(rad):
        sel = np.where(rad == r)[0]
        oy, ox = np.mgrid[-r:r + 1, -r:r + 1]
        ox, oy = ox.ravel(), oy.ravel()
        for chunk in np.array_split(sel, max(1, len(sel) // 60000)):
            ix = np.floor(cx[chunk])[:, None].astype(int) + ox[None]
            iy = np.floor(cy[chunk])[:, None].astype(int) + oy[None]
            dx = ix + 0.5 - cx[chunk][:, None]
            dy = iy + 0.5 - cy[chunk][:, None]
            Jc = J[chunk]
            sx = Jc[:, None, :, 0] * dx[..., None] + Jc[:, None, :, 1] * dy[..., None]
            d2 = (sx ** 2).sum(-1)
            w = amp[chunk][:, None] * np.exp(-0.5 * d2 / sigma_mm[chunk][:, None] ** 2)
            ok = (ix >= 0) & (ix < size) & (iy >= 0) & (iy < size)
            out += np.bincount((iy * size + ix)[ok], weights=w[ok], minlength=size * size)
    return out.reshape(size, size).astype(np.float32)


def scatter(rng, T: tc.Texels, density_per_mm2):
    """Texel indices of points scattered with the given surface density (Bernoulli per texel)."""
    area = T.mm_per_px() ** 2
    p = np.clip(density_per_mm2 * area, 0, 1)
    return np.where(rng.random(len(p)) < p)[0]


# --------------------------------------------------------------------------- maps

def scan_relief(T, F, size):
    """Scanned micro-relief in mm (size², locally zero-mean), where to use it (0..1), and how
    much of its valleys may darken the colour (low where the scan has stubble)."""
    z = np.load(SCAN_HEIGHT)
    raw, hit = z["height"], z["hit"]
    if raw.shape[0] != size:
        raise SystemExit(f"{SCAN_HEIGHT.name} is {raw.shape[0]} px; rebake with --size {size}")
    valid = (hit & T.mask).astype(np.float32)
    s = SCAN_HIGHPASS_PX
    hp = (raw - gaussian_filter(raw * valid, s) / np.maximum(gaussian_filter(valid, s), 1e-3)) * valid
    # away from island borders and misses, where the high-pass has only one side to look at
    inner = smoothstep(0.90, 0.99, gaussian_filter(valid, 3)) * valid
    ok = T.image(F["scan_ok"], 0.0) * inner
    core = ok > 0.5
    sd = float(hp[core].std())
    hp = 3.5 * sd * np.tanh(hp / (3.5 * sd))                     # sculpt seams and stretched streaks
    # drop patches with no fine detail (a smoothed sculpt layer) or far too much (seams)
    local = np.sqrt(gaussian_filter(hp * hp, 24) / np.maximum(gaussian_filter(valid, 24), 1e-3))
    rel = local / float(np.median(local[core]))
    w = ok * smoothstep(0.35, 0.6, rel) * (1 - smoothstep(2.2, 3.5, rel))
    w = np.minimum(gaussian_filter(w, 4), ok).astype(np.float32)
    # even out the local contrast a little: stubble on the scan's jaw is much rougher than its cheeks
    hp = hp * np.clip(np.maximum(rel, 1e-3) ** -0.6, 0.75, 1.3)
    # the map's displacement scale is unknown: set it from the slope it gives on the face
    hpad = np.pad(hp, 1, mode="edge")
    gx = (hpad[1:-1, 2:] - hpad[1:-1, :-2]) * 0.5 / np.maximum(T.image(np.linalg.norm(T.jac[:, :, 0], axis=1), 1.0), 1e-4)
    gy = (hpad[2:, 1:-1] - hpad[:-2, 1:-1]) * 0.5 / np.maximum(T.image(np.linalg.norm(T.jac[:, :, 1], axis=1), 1.0), 1e-4)
    face = (w > 0.9) & (T.image(F["density"], 0.0) > 3.0)
    gain = math.tan(math.radians(SCAN_TILT_DEG)) / float(np.hypot(gx, gy)[face].mean())
    print(f"[detail] scan relief on {100 * w[T.mask].mean():.0f}% of the skin, rms {1000 * gain * sd:.0f} um")
    calm = np.clip((1.45 - rel) / 0.45, 0.15, 1.0).astype(np.float32)
    return (hp * gain).astype(np.float32), w, calm


def height_map(rng, T, F, size, args, lo, hi):
    """Height in mm per texel (size², zero outside the islands) and the pore field."""
    t0 = time.time()
    # pores
    idx = scatter(rng, T, F["density"] * args.pore_density)
    sig = F["sigma"][idx] * rng.uniform(0.7, 1.35, len(idx)) * args.pore_size
    depth = PORE_DEPTH_MM * F["depth"][idx] * rng.uniform(0.6, 1.4, len(idx)) * args.pore_strength
    pores = splat(T, idx, sig, depth, size)
    print(f"[detail] {len(idx):,} pores in {time.time() - t0:.1f} s")

    # skin micro-furrows: ridged noise in texel space, scale-matched to the local texel size
    mpp = T.mm_per_px()
    k = T.image(mpp / 0.115, 1.0)                                # 1 = typical face density
    micro = np.zeros((size, size), dtype=np.float32)
    w_sum = np.zeros_like(micro)
    for s_px, centre in ((0.9, 0.75), (1.4, 1.0), (2.1, 1.4)):
        n = gaussian_filter(rng.standard_normal((size, size)).astype(np.float32), s_px)
        n /= n.std()
        ridged = -np.exp(-(n / 0.45) ** 2)                       # thin valleys at zero crossings
        w = np.exp(-0.5 * (np.log(k / centre) / 0.3) ** 2)
        micro += w * ridged
        w_sum += w
    micro /= np.maximum(w_sum, 1e-6)
    micro_amp = T.image(F["micro"] * MICRO_DEPTH_MM * args.micro_strength)
    mod = T.image(0.75 + 0.25 * fbm3(rng, T.pos, lo, hi, [6.0], [1.0]))
    h = -pores + micro * micro_amp * mod
    if args.scan_relief > 0 and SCAN_HEIGHT.exists():
        hs, w, calm = scan_relief(T, F, size)
        hs *= args.scan_relief
        # the scan carries the structure; a third of the generated grain stays on top of it, since
        # the bake cannot hold detail finer than a texel
        h = (1 - w) * h + w * (hs + 0.35 * h)
        # the same valleys drive the pore tint and pore roughness downstream
        cavity = np.clip(-hs / (1.6 * float(hs[w > 0.9].std())), 0, 1.5)
        pores = (1 - w) * pores + w * PORE_NORM_MM * cavity * calm
    elif args.scan_relief > 0:
        print(f"[detail] {SCAN_HEIGHT.name} not found: fully generated relief")

    # gentle 3D undulation (0.5-3 mm), not on the lips
    und = fbm3(rng, T.pos, lo, hi, [0.8, 2.0], [0.6, 1.0]) * 0.006
    h += T.image(und * (1 - F["lips"]))

    # lip creases: valleys of constant x (vertical lines on the lip), wavy and broken
    lips = F["lips"]
    on = lips > 0.02
    pos = T.pos[on]
    warp = 0.35 * fbm3(rng, pos, lo, hi, [1.2], [1.0])
    xgrid = np.arange(-40, 40, 0.01)
    n1 = gaussian_filter(rng.standard_normal(len(xgrid)), 22)     # 0.22 mm correlation
    n1 /= n1.std()
    nx = np.interp(pos[:, 0] + warp, xgrid, n1)
    valley = np.exp(-(nx / 0.32) ** 2)
    broken = np.clip(0.55 + 0.6 * fbm3(rng, pos, lo, hi, [0.9, 2.5], [0.7, 1.0]), 0, 1)
    fine = gaussian_filter(rng.standard_normal(len(xgrid)), 6)
    fine /= fine.std()
    valley2 = np.exp(-(np.interp(pos[:, 0] - warp, xgrid, fine) / 0.25) ** 2)
    crease = np.zeros(len(T.pos), dtype=np.float32)
    crease[on] = (0.045 * valley * broken + 0.012 * valley2) * args.lip_strength
    h -= T.image(crease * smoothstep(0.03, 0.35, lips))

    # fine lines under the lower lid and at the outer corner: valleys of constant s
    # (distance below the lid margin), wavy and broken, a coarse and a fine set
    on = F["lid_w"] > 1e-3
    if on.any() and args.lid_lines > 0:
        pos = T.pos[on]
        s = F["lid_s"][on] + 0.18 * fbm3(rng, pos, lo, hi, [1.5], [1.0])
        sgrid = np.arange(-12, 14, 0.01)
        n1 = gaussian_filter(rng.standard_normal(len(sgrid)), 32)    # ~0.3 mm correlation
        n1 /= n1.std()
        n2 = gaussian_filter(rng.standard_normal(len(sgrid)), 12)
        n2 /= n2.std()
        coarse = np.exp(-(np.interp(s, sgrid, n1) / 0.28) ** 2)
        fine = np.exp(-(np.interp(s, sgrid, n2) / 0.22) ** 2)
        broken = np.clip(0.3 + 0.75 * fbm3(rng, pos, lo, hi, [1.2, 3.5], [0.7, 1.0]), 0, 1)
        broken2 = np.clip(0.2 + 0.8 * fbm3(rng, pos, lo, hi, [0.8, 2.0], [0.7, 1.0]), 0, 1)
        line = np.zeros(len(T.pos), dtype=np.float32)
        line[on] = (LID_LINE_DEPTH_MM * coarse * broken + 0.35 * LID_LINE_DEPTH_MM * fine * broken2) \
            * F["lid_w"][on] * args.lid_lines
        h -= T.image(line)
    return h, pores


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def normal_map(T, h, size):
    """Tangent-space normals from height (mm). T along +u, B along +v (= up in the image)."""
    hp = np.pad(h, 1, mode="edge")
    dhdx = (hp[1:-1, 2:] - hp[1:-1, :-2]) * 0.5
    dhdy = (hp[2:, 1:-1] - hp[:-2, 1:-1]) * 0.5
    lu = T.image(np.linalg.norm(T.jac[:, :, 0], axis=1), 1.0)     # mm per texel along +x (= +u)
    lv = T.image(np.linalg.norm(T.jac[:, :, 1], axis=1), 1.0)     # mm per texel along +y (= -v)
    gx = dhdx / np.maximum(lu, 1e-4)
    gy = -dhdy / np.maximum(lv, 1e-4)
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    n[~T.mask] = (0, 0, 1)
    return n


def albedo_detail(rng, T, F, pores, size, args, lo, hi):
    """Linear multiply factor per texel and channel; 1 = no change."""
    N = len(T.pos)
    f = np.ones((N, 3), dtype=np.float32)
    # mottling: luminance and a blood-red component at a few mm and around a centimetre
    lum = fbm3(rng, T.pos, lo, hi, [2.5, 7.0, 16.0], [0.5, 0.8, 1.0])
    blood = fbm3(rng, T.pos, lo, hi, [3.0, 10.0], [0.7, 1.0])
    s = args.mottle_strength
    f *= (1 + MOTTLE * s * lum)[:, None]
    f *= np.stack([1 + 0.29 * MOTTLE * s * blood, 1 - MOTTLE * s * blood, 1 - 0.86 * MOTTLE * s * blood], 1)
    # redness on nose and cheeks, patchy
    red = np.clip(F["red"] * (0.75 + 0.35 * fbm3(rng, T.pos, lo, hi, [4.0, 9.0], [0.6, 1.0])), 0, 1.4)
    f *= np.stack([1 - REDNESS[0] * red, 1 - REDNESS[1] * red, 1 - REDNESS[2] * red], 1) ** args.redness
    # pores slightly darker and browner
    pt = pores[T.ys, T.xs] / PORE_NORM_MM
    pt = np.clip(pt, 0, 1.5) * args.pore_tint
    f *= np.stack([1 - 0.10 * pt, 1 - 0.13 * pt, 1 - 0.14 * pt], 1)

    # freckles and moles: a few hundred small brown spots, mostly nose and cheeks
    tint = np.zeros(size * size, dtype=np.float32)
    dens = F["freckle"] * 0.012 * args.freckles
    idx = scatter(rng, T, dens)
    if len(idx):
        sig = rng.uniform(0.18, 0.45, len(idx))
        amp = rng.uniform(0.25, 0.8, len(idx))
        tint += splat(T, idx, sig, amp, size, max_radius=12).ravel()
    n_moles = int(rng.integers(2, 7) * args.moles)
    face = np.where((F["lips"] < 0.05) & (F["density"] > 0.9))[0]
    if n_moles and len(face):
        mi = rng.choice(face, n_moles, replace=False)
        tint += 2.2 * splat(T, mi, rng.uniform(0.35, 0.8, n_moles), np.ones(n_moles), size,
                            max_radius=20).ravel()
    spot = np.clip(tint.reshape(size, size)[T.ys, T.xs], 0, 2.0)
    f *= np.stack([1 - 0.22 * spot, 1 - 0.30 * spot, 1 - 0.36 * spot], 1).clip(0.25, 1)

    # small veins near the temples and lids: faint blue-grey lines
    vm = F["veins"]
    cand = np.where(vm > 0.3)[0]
    if len(cand):
        vimg = vein_lines(rng, T, cand, size, int(26 * args.veins))
        vv = gaussian_filter(vimg, 1.2)[T.ys, T.xs] * vm
        f *= np.stack([1 - 0.10 * vv, 1 - 0.06 * vv, 1 - 0.015 * vv], 1)

    # none on the lips
    keep = smoothstep(0.05, 0.5, F["lips"])[:, None]
    f = f * (1 - keep) + keep
    return f


def vein_lines(rng, T, cand, size, count):
    img = np.zeros((size, size), dtype=np.float32)
    for _ in range(count):
        i = cand[rng.integers(len(cand))]
        x, y = T.xs[i] + 0.5, T.ys[i] + 0.5
        mpp = float(np.sqrt(np.linalg.norm(np.cross(T.jac[i, :, 0], T.jac[i, :, 1]))))
        step = 0.25 / mpp                                        # 0.25 mm steps
        length = int(rng.uniform(6, 22) / 0.25)                  # 6-22 mm long
        a = rng.uniform(0, 2 * np.pi)
        kappa = 0.0
        w = rng.uniform(0.25, 0.5) / mpp                         # width in px
        for _ in range(length):
            kappa = 0.85 * kappa + rng.normal(0, 0.06)
            a += kappa
            nx, ny = x + step * np.cos(a), y + step * np.sin(a)
            n = max(int(np.ceil(step)), 1)
            for t in np.linspace(0, 1, n + 1):
                px, py = int(x + t * (nx - x)), int(y + t * (ny - y))
                r = max(int(np.ceil(w)), 1)
                y0, y1, x0, x1 = max(py - r, 0), min(py + r + 1, size), max(px - r, 0), min(px + r + 1, size)
                if y1 > y0 and x1 > x0:
                    yy, xx = np.mgrid[y0:y1, x0:x1] + 0.5
                    dd = np.hypot(xx - (x + t * (nx - x)), yy - (y + t * (ny - y)))
                    img[y0:y1, x0:x1] = np.maximum(img[y0:y1, x0:x1], np.clip(w / 2 + 0.5 - dd, 0, 1))
            x, y = nx, ny
            if not (0 <= x < size and 0 <= y < size):
                break
    return img


def apply_albedo_detail(albedo_srgb_u8: np.ndarray, detail_u8: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Multiply an 8-bit sRGB albedo by skin_detail (128 = x1) in linear light. For section 5."""
    a = tc.srgb_to_linear(albedo_srgb_u8[..., :3] / 255.0)
    f = detail_u8[..., :3].astype(np.float64) / 128.0
    a = a * (1 + strength * (f - 1))
    return tc.to_u8(tc.linear_to_srgb(a))


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--size", type=int, default=4096, help="normal and albedo detail size")
    ap.add_argument("--rough-size", type=int, default=2048)
    ap.add_argument("--pore-strength", type=float, default=1.0)
    ap.add_argument("--pore-density", type=float, default=1.0)
    ap.add_argument("--pore-size", type=float, default=1.0)
    ap.add_argument("--micro-strength", type=float, default=1.0)
    ap.add_argument("--lip-strength", type=float, default=1.0)
    ap.add_argument("--lid-lines", type=float, default=1.0, help="fine lines under the lower lid")
    ap.add_argument("--mottle-strength", type=float, default=1.0)
    ap.add_argument("--redness", type=float, default=1.0)
    ap.add_argument("--freckles", type=float, default=1.0)
    ap.add_argument("--moles", type=float, default=1.0)
    ap.add_argument("--veins", type=float, default=1.0)
    ap.add_argument("--pore-tint", type=float, default=1.0)
    ap.add_argument("--scan-relief", type=float, default=1.0,
                    help="strength of the scanned micro-relief (0 = generated pores only)")
    ap.add_argument("--scan-brows", action="store_true",
                    help="keep the scan's relief under the brows (for the set that uses its colour)")
    ap.add_argument("--variation", type=float, default=0.1,
                    help="per-seed jitter of the strengths (0.1 = up to ±10 %%)")
    args = ap.parse_args()
    out = args.out or REPO / f"outputs/tmp/m2/detail/seed_{args.seed}"
    out.mkdir(parents=True, exist_ok=True)

    # small per-set variation of the strengths, from the seed
    vr = np.random.default_rng([args.seed, 99])
    for k in ("pore_strength", "pore_density", "pore_size", "micro_strength", "lip_strength",
              "mottle_strength", "redness", "freckles", "lid_lines"):
        setattr(args, k, getattr(args, k) * (1 + args.variation * vr.uniform(-1, 1)))

    t0 = time.time()
    d = tc.load_base()
    size = args.size
    T = tc.Texels(d, TILE, size)
    rng = np.random.default_rng([args.seed, 1])
    T.jitter = rng.uniform(-0.5, 0.5, (len(T.pos), 2))
    lo, hi = T.pos.min(0), T.pos.max(0)
    F = region_fields(d, T, args.scan_brows)
    print(f"[detail] {len(T.pos):,} texels, setup {time.time() - t0:.1f} s")

    h, pores = height_map(rng, T, F, size, args, lo, hi)
    n = normal_map(T, h, size)
    n = tc.fill_nearest(n, T.mask)
    tc.write_png(out / "skin_normal.1001.png", tc.to_u8(n * 0.5 + 0.5))
    print(f"[detail] normal done {time.time() - t0:.1f} s")

    # roughness at 2048: region values, a little rougher in pores, low-frequency variation
    rough = F["rough"] + 0.035 * fbm3(rng, T.pos, lo, hi, [3.0, 10.0], [0.6, 1.0])
    rough = rough + 0.10 * np.clip(pores[T.ys, T.xs] / PORE_NORM_MM, 0, 1)
    r_img = tc.fill_nearest(T.image(rough, 0.5), T.mask)
    f = size // args.rough_size
    r_img = r_img.reshape(args.rough_size, f, args.rough_size, f).mean((1, 3)) if f > 1 else r_img
    tc.write_png(out / "skin_rough.1001.png", tc.to_u8(np.clip(r_img, 0.05, 0.95)))
    print(f"[detail] roughness done {time.time() - t0:.1f} s")

    fac = albedo_detail(rng, T, F, pores, size, args, lo, hi)
    a_img = tc.fill_nearest(T.image(fac, 1.0), T.mask)
    tc.write_png(out / "skin_detail.1001.png", np.clip(a_img * 128 + 0.5, 0, 255).astype(np.uint8))
    meta = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in vars(args).items() if k != "out"}
    (out / "detail.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"[detail] albedo detail done, total {time.time() - t0:.1f} s -> {out}")


if __name__ == "__main__":
    main()
