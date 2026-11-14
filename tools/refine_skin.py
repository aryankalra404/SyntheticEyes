"""Refine the eyebrows and the fine skin detail of a finished texture set, in UV space.

    python3 tools/refine_skin.py                         # sets 01-08, in place
    python3 tools/refine_skin.py --sets 01 05 --preview outputs/tmp/refine   # before/after crops

Runs on the shipped files of textures/tex_NN, so it needs neither Blender, GNM nor the source
skins. tools/build_textures.py calls it as the last step of assembling a set. Sets with the
scan's own skin (tex_09) are left alone: their brows and skin are photographed.

Eyebrows. The drawn brows of sets 01-08 are opaque strands pasted on untouched skin, with a
hard outline. A real brow (tex_09) has a soft layer of pigment and shadow under the hairs,
hairs of uneven darkness, and fine stray hairs around the edge. This step
  1. finds the brow by darkness against a closed-off background, keeps the two big components
     above the eye pockets;
  2. inpaints the skin under the hairs and unmixes each texel into skin + hair coverage;
  3. rebuilds the brow: a soft under-layer, per-strand variation of coverage and shade (noise
     smeared along the hair direction, line-integral convolution), crossing strands thinned,
     sparse stray hairs added just outside the outline. The residual of the unmixing is added
     back, so the pores between the hairs stay;
  4. gives the hairs a little relief in the normal map and makes the brow rougher.

Skin. On the light sets the albedo carries about two thirds of the scan's fine detail and half
of its mid-scale detail (measured on cheeks and forehead). The band of log-luminance at
1.5 px and the band between 1.5 and 6 px (about 0.17 and 0.7 mm on the face) are raised
toward the scan's level, by a gain measured per set and capped, with a soft limit on large
excursions. Detail that is already there is amplified; nothing is invented. Chroma is kept.

Deterministic: same files in, same bytes out. set.json records that a set has been refined,
and a refined set is skipped, so the step never applies twice. To redo it, restore the set's
files first (git checkout -- textures/tex_NN).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as nd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tex_core as tc  # noqa: E402

REPO = tc.REPO
VERSION = 1

# Both brows of every set, with margin, in 4096-px UV coordinates (x0, y0, x1, y1). The brows are
# drawn in the same place on GNM's UVs in every set; the eye pockets start below EYE_TOP.
BROW_BOX = (1400, 1180, 2720, 1610)
EYE_TOP = 1440

# Skin regions measured for the gains: both cheeks and the forehead (4096-px UV, x0, y0, x1, y1)
MEASURE = ((1600, 1700, 1900, 2000), (2200, 1700, 2500, 2000), (1900, 950, 2200, 1150))
FINE_SIGMA, MID_SIGMA = 1.5, 6.0
TARGET_FINE, TARGET_MID = 0.015, 0.026     # rms of the two bands on tex_09, rounded down
MAX_GAIN_FINE, MAX_GAIN_MID = 1.45, 1.6
SOFT_LIMIT = 0.05                          # log-luminance; larger boosts are squashed

BROW = dict(
    under_dark=0.20,        # how much the under-layer darkens the skin at full density
    under_tint=0.15,        # and how far it pulls its colour toward the hair
    cover_var=0.16,         # per-strand spread of coverage
    shade_var=0.30,         # per-strand spread of hair brightness
    cross_keep=0.6,         # coverage kept where strands cross (low orientation coherence)
    strays_per_brow=80,
    stray_len=(6.0, 16.0),  # px; 1 px is about 0.11 mm on the brow
    stray_alpha=(0.12, 0.32),
    head_fade=(0.55, 70.0), # coverage at the inner end of each brow, and the px over which it recovers
    relief=0.35,            # normal-map slope per unit of coverage gradient
    rough_add=0.10,         # roughness added at full brow density
)


def luma(lin):
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def soft_clip(x, s):
    return s * np.tanh(x / s)


def blur_masked(img, w, sigma):
    """Normalised convolution: the average of img over the texels where w > 0."""
    if img.ndim == 3:
        num = np.stack([nd.gaussian_filter(img[..., c] * w, sigma) for c in range(img.shape[2])], -1)
        den = nd.gaussian_filter(w, sigma)
        return num / np.maximum(den, 1e-6)[..., None], den
    num, den = nd.gaussian_filter(img * w, sigma), nd.gaussian_filter(w, sigma)
    return num / np.maximum(den, 1e-6), den


# ---- eyebrows ---------------------------------------------------------------------------------

def brow_mask(Y, y0):
    """Hair darkness in [0, 1] and the brow region (bool), on the crop of BROW_BOX."""
    bg = nd.gaussian_filter(nd.grey_closing(Y, size=(81, 81)), 4)
    dark = np.clip(1.0 - Y / np.maximum(bg, 1e-4), 0.0, 1.0)
    core = nd.binary_dilation(dark > 0.3, iterations=4)
    lab, n = nd.label(core)
    if n == 0:
        return dark, np.zeros_like(core)
    idx = np.arange(1, n + 1)
    area = nd.sum(core, lab, idx)
    cy = np.array([c[0] for c in nd.center_of_mass(core, lab, idx)]) + y0
    keep = [i for i, a, c in sorted(zip(idx, area, cy), key=lambda z: -z[1]) if a > 3000 and c < EYE_TOP][:2]
    region = np.isin(lab, keep)
    return dark, region


def orientation(a, sigma):
    """Hair direction (unit vectors along the strands), coherence in [0, 1] and edge energy."""
    gx, gy = nd.sobel(a, 1), nd.sobel(a, 0)
    jxx, jxy, jyy = (nd.gaussian_filter(v, sigma) for v in (gx * gx, gx * gy, gy * gy))
    phi = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2       # along the strand, not across
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-9)
    return np.cos(phi), np.sin(phi), coh, jxx + jyy


def lic(noise, tx, ty, steps=14):
    """Line-integral convolution: noise averaged along the direction field, both ways."""
    h, w = noise.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    acc = noise.copy()
    for sign in (1.0, -1.0):
        px, py = xx.copy(), yy.copy()
        dx, dy = sign * tx, sign * ty
        for _ in range(steps):
            px += dx
            py += dy
            acc += nd.map_coordinates(noise, [py, px], order=1, mode="nearest")
            ix = np.clip(np.rint(px).astype(int), 0, w - 1)
            iy = np.clip(np.rint(py).astype(int), 0, h - 1)
            nx, ny = tx[iy, ix], ty[iy, ix]
            flip = np.where(nx * dx + ny * dy < 0, -1.0, 1.0)   # the field has no sign: keep going
            dx, dy = nx * flip, ny * flip
    out = acc / (2 * steps + 1)
    return (out - out.mean()) / (out.std() + 1e-9)


def strays(rng, ring, tx, ty, count, p):
    """Sparse fine hairs: short tapered strokes along the brow's flow, as coverage."""
    h, w = ring.shape
    out = np.zeros((h, w), np.float32)
    flat = ring.ravel() / ring.sum()
    centres = rng.choice(flat.size, size=count, p=flat)
    for c in centres:
        cy, cx = divmod(int(c), w)
        L = rng.uniform(*p["stray_len"])
        a0 = rng.uniform(*p["stray_alpha"])
        ang = np.arctan2(ty[cy, cx], tx[cy, cx]) + rng.normal(0.0, 0.15)
        bend = rng.normal(0.0, 0.012)
        for s in np.arange(0.0, L, 0.5):
            u = s / L
            th = ang + bend * s
            x = cx + np.cos(th) * (s - L / 2)
            y = cy + np.sin(th) * (s - L / 2)
            xi, yi = int(np.floor(x)), int(np.floor(y))
            if not (1 <= xi < w - 2 and 1 <= yi < h - 2):
                continue
            a = a0 * (1.0 - u) ** 0.6                       # thick at the root, fine at the tip
            for oy in (0, 1):
                for ox in (0, 1):
                    d2 = (xi + ox - x) ** 2 + (yi + oy - y) ** 2
                    out[yi + oy, xi + ox] = max(out[yi + oy, xi + ox], a * np.exp(-d2 / 0.45))
    return out


def refine_brows(lin, normal, rough, seed, p=BROW):
    """Rebuild the brows in place on the BROW_BOX crop. Returns a dict of what was measured."""
    x0, y0, x1, y1 = BROW_BOX
    crop = lin[y0:y1, x0:x1].astype(np.float32)
    Y = luma(crop)
    dark, region = brow_mask(Y, y0)
    if not region.any():
        return {"brows": "not found"}
    M = nd.binary_dilation(region, iterations=22)
    clean = (~nd.binary_dilation(region, iterations=3)) & (dark < 0.08)
    skin, den = blur_masked(crop, clean.astype(np.float32), 14)
    wide, _ = blur_masked(crop, clean.astype(np.float32), 40)
    trust = smoothstep(0.05, 0.3, den)[..., None]               # no hard switch between the two
    skin = skin * trust + wide * (1 - trust)
    hair_px = region & (dark > 0.6)
    hair = np.median(crop[hair_px], axis=0) if hair_px.sum() > 50 else crop[region].min(axis=0)
    Ys, Yh = luma(skin), float(luma(hair))
    alpha = np.where(region, np.clip((Ys - Y) / np.maximum(Ys - Yh, 1e-4), 0.0, 1.0), 0.0)
    # only texels that are clearly darker than their surroundings are hair; a skin estimate a
    # little too light (in the socket's shadow) must not turn plain skin into faint hair
    alpha *= smoothstep(0.12, 0.3, dark)
    model_old = skin * (1 - alpha[..., None]) + hair * alpha[..., None]
    residual = crop - model_old

    rng = np.random.default_rng([int(seed), 77])
    tx, ty, coh, energy = orientation(alpha, 3.0)
    btx, bty, _, _ = orientation(alpha, 14.0)
    v_cover = lic(rng.random(alpha.shape, np.float32), tx, ty)
    v_shade = lic(rng.random(alpha.shape, np.float32), tx, ty)
    cover = np.clip(1.0 - 0.08 + p["cover_var"] * v_cover, 0.45, 1.0)
    # crossing strands: low coherence where there are strands at all. A solid dark core has no
    # edges, so its coherence means nothing and it is left alone.
    textured = smoothstep(0.1, 0.3, energy / max(np.percentile(energy[region], 90), 1e-9))
    crossing = (1.0 - smoothstep(0.15, 0.55, coh)) * textured
    cover *= 1.0 - (1.0 - p["cross_keep"]) * crossing
    # the head of a brow (nearest the nose) is sparse; the drawn ones start as a solid block
    lab, nlab = nd.label(nd.binary_dilation(region, iterations=6))
    mid = 2048 - x0
    xs = np.arange(alpha.shape[1])[None, :]
    lo_c, span = p["head_fade"]
    for i in range(1, nlab + 1):
        cols = np.flatnonzero((lab == i).any(axis=0))
        end = cols.max() if abs(cols.max() - mid) < abs(cols.min() - mid) else cols.min()
        fade = lo_c + (1 - lo_c) * smoothstep(0.0, span, np.abs(xs - end))
        cover = np.where(lab == i, cover * fade, cover)
    A = alpha * cover

    dens = nd.gaussian_filter(alpha, 9)
    dens = np.clip(dens / max(np.percentile(dens[region], 95), 1e-4), 0, 1)
    # stray hairs grow out of the edge of the brow, not in a ring around it
    ring = M & (alpha < 0.25) & (dens > 0.12) & (dens < 0.55)
    per = 0
    if ring.sum() > 1000:
        per = p["strays_per_brow"] * int(nd.label(region)[1])
        A = np.maximum(A, strays(rng, ring.astype(np.float64) * (0.6 - dens), btx, bty, per, p))

    shade = np.clip(1.0 + p["shade_var"] * v_shade, 0.6, 1.6)[..., None]
    warm = np.array([1.04, 1.0, 0.94], np.float32)
    hair_new = np.clip(hair * shade * np.where(shade > 1, warm, 1.0), 0, 1)
    D = dens[..., None]
    under = (skin * (1 - p["under_tint"] * D) + hair * p["under_tint"] * D) * (1 - p["under_dark"] * D)
    model_new = under * (1 - A[..., None]) + hair_new * A[..., None]
    new = np.clip(model_new + residual, 0, 1)
    feather = nd.gaussian_filter(M.astype(np.float32), 4)[..., None]
    lin[y0:y1, x0:x1] = crop * (1 - feather) + new * feather

    # normal: hairs a little raised (tangent space, OpenGL: +G is +V, image rows run down)
    n = normal[y0:y1, x0:x1].astype(np.float32) / 127.5 - 1.0
    gx, gy = nd.sobel(A, 1) / 8.0, nd.sobel(A, 0) / 8.0
    n[..., 0] -= p["relief"] * gx * feather[..., 0]
    n[..., 1] += p["relief"] * gy * feather[..., 0]
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    normal[y0:y1, x0:x1] = tc.to_u8((n + 1.0) * 0.5)

    # roughness (half resolution): the brow is matte next to the skin's sheen
    r0, r1, c0, c1 = y0 // 2, (y0 + dens.shape[0]) // 2, x0 // 2, (x0 + dens.shape[1]) // 2
    small = nd.zoom(dens * feather[..., 0], 0.5, order=1)[: r1 - r0, : c1 - c0]
    rough[r0:r1, c0:c1] = np.clip(rough[r0:r1, c0:c1] + 255 * p["rough_add"] * small, 0, 255).astype(np.uint8)
    return {"brow_components": int(nd.label(region)[1]), "hair_linear": [round(float(c), 4) for c in hair],
            "stray_hairs": int(per)}


# ---- skin -------------------------------------------------------------------------------------

def bands(L):
    g1 = nd.gaussian_filter(L, FINE_SIGMA)
    g6 = nd.gaussian_filter(L, MID_SIGMA)
    return L - g1, g1 - g6


def measure(lin):
    fine, mid = [], []
    for x0, y0, x1, y1 in MEASURE:
        L = np.log(luma(lin[y0:y1, x0:x1]) + 1e-4)
        bf, bm = bands(L)
        fine.append(bf.std())
        mid.append(bm.std())
    return float(np.mean(fine)), float(np.mean(mid))


def refine_skin(lin, keep_out=None):
    """Raise the fine and mid bands of log-luminance toward the scan's level. Returns the gains."""
    f0, m0 = measure(lin)
    gf = float(np.clip(TARGET_FINE / f0, 1.0, MAX_GAIN_FINE))
    gm = float(np.clip(TARGET_MID / m0, 1.0, MAX_GAIN_MID))
    if gf == 1.0 and gm == 1.0:
        return {"gain_fine": 1.0, "gain_mid": 1.0, "before": [round(f0, 5), round(m0, 5)]}
    L = np.log(luma(lin) + 1e-4).astype(np.float32)
    bf, bm = bands(L)
    add = soft_clip((gf - 1) * bf + (gm - 1) * bm, SOFT_LIMIT)
    if keep_out is not None:
        add *= 1.0 - keep_out
    lin *= np.exp(add)[..., None]
    np.clip(lin, 0, 1, out=lin)
    f1, m1 = measure(lin)
    return {"gain_fine": round(gf, 3), "gain_mid": round(gm, 3),
            "before": [round(f0, 5), round(m0, 5)], "after": [round(f1, 5), round(m1, 5)]}


# ---- a set ------------------------------------------------------------------------------------

def refine_set(folder: Path, seed: int, preview: Path | None = None) -> dict | None:
    folder = Path(folder)
    meta_path = folder / "set.json"
    meta = json.loads(meta_path.read_text())
    if "refine" in meta:
        print(f"[refine] {folder.name}: already refined (v{meta['refine'].get('version')}), skipped")
        return None
    if "scan's colour map" in meta.get("eyebrows", {}).get("source", ""):
        print(f"[refine] {folder.name}: photographed skin and brows, left as they are")
        return None
    srgb = tc.read_png(folder / "skin.1001.png")
    normal = tc.read_png(folder / "skin_normal.1001.png").copy()
    rough = tc.read_png(folder / "skin_rough.1001.png").copy()
    lin = tc.srgb_to_linear(srgb.astype(np.float32) / 255.0).astype(np.float32)
    before = srgb.copy() if preview else None

    brow = refine_brows(lin, normal, rough, seed)
    keep = np.zeros(lin.shape[:2], np.float32)                    # the brows are done: leave them
    x0, y0, x1, y1 = BROW_BOX
    Yb = luma(lin[y0:y1, x0:x1])
    _, region = brow_mask(Yb, y0)
    keep[y0:y1, x0:x1] = nd.gaussian_filter(nd.binary_dilation(region, iterations=24).astype(np.float32), 6)
    skin = refine_skin(lin, keep)

    out = tc.to_u8(tc.linear_to_srgb(lin))
    tc.write_png(folder / "skin.1001.png", out)
    tc.write_png(folder / "legacy" / "skin.png", out)
    tc.write_png(folder / "skin_normal.1001.png", normal)
    tc.write_png(folder / "skin_rough.1001.png", rough)
    meta["refine"] = {"version": VERSION, "tool": "tools/refine_skin.py", "brows": brow, "skin": skin,
                      "note": "brows rebuilt (under-layer, strand variation, stray hairs, relief, roughness); "
                              "fine and mid skin detail raised toward the scan's level"}
    meta_path.write_text(json.dumps(meta, indent=1) + "\n")
    print(f"[refine] {folder.name}: brows {brow}, skin {skin}")
    if preview:
        write_preview(preview, folder.name, before, out)
    return meta["refine"]


def write_preview(where: Path, name: str, before, after):
    from PIL import Image
    where.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = BROW_BOX
    crops = [(x0 + 160, y0 + 60, x1 - 160, y1 - 50), (1600, 1700, 1900, 2000)]
    rows = []
    for c in crops:
        a, b = Image.fromarray(before[c[1]:c[3], c[0]:c[2]]), Image.fromarray(after[c[1]:c[3], c[0]:c[2]])
        if a.width < 600:
            a, b = (im.resize((im.width * 2, im.height * 2), Image.LANCZOS) for im in (a, b))
        row = Image.new("RGB", (a.width, a.height * 2 + 6), (20, 20, 20))
        row.paste(a, (0, 0))
        row.paste(b, (0, a.height + 6))
        rows.append(row)
    for i, r in enumerate(rows):
        r.save(where / f"{name}_{'brows' if i == 0 else 'cheek'}_before_after.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sets", nargs="*", default=[f"{i:02d}" for i in range(1, 9)])
    ap.add_argument("--root", type=Path, default=REPO / "textures")
    ap.add_argument("--preview", type=Path, default=None, help="write before/after crops here")
    args = ap.parse_args()
    for nn in args.sets:
        folder = args.root / f"tex_{nn}"
        seed = json.loads((folder / "set.json").read_text()).get("detail_maps", {}).get("seed", int(nn))
        refine_set(folder, seed, args.preview)


if __name__ == "__main__":
    main()
