"""Scan test: the Infinite head scan's maps next to ours, same patches, same scale.

    python3 -I tools/scan_compare.py [--out outputs/tmp/scan]

Inputs (git-ignored):
    assets/third_party/lpshead/files/   lpshead.zip from the McGuire Computer Graphics Archive
                                        (Infinite, 3D Head Scan by Lee Perry-Smith, CC BY 3.0)
    assets/gnm/base.npz                 GNM template and UDIM UVs
    outputs/tmp/m2/eurasian_f_young/skin.1001.png, outputs/tmp/m2/detail/seed_0/*.png   ours

For forehead, cheek and nose it finds the patch on both heads from 3D landmarks (offsets from
the nose tip), measures texels per mm from the UV layout around it, and crops 24 x 24 mm
resampled to 20 px/mm. Columns: scan colour, our colour (bake x detail layer), scan relief,
our relief. Relief is shaded with the same light from the scan's displacement and from our
tangent-space normal map, each normalised to the same contrast (the scan's displacement
scale is not known), so compare structure, not depth.

The scan is in ZBrush units; 915 mm per unit, from its cranial breadth (0.166) and length
(0.220) against an average adult male head (155 x 197 mm), good to about +-4 %.
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[1]
SCAN = REPO / "assets/third_party/lpshead/files"
SCAN_MM_PER_UNIT = 915.0
PATCH_MM = 24.0
OUT_PX_PER_MM = 20.0
# (name, offset from the nose tip in mm (x lateral, y up) on GNM, then on the scan). The scan's
# head is pitched back, so the same anatomy sits lower relative to its most forward vertex;
# its offsets were set by drawing the boxes on both maps (--where) and moving them to match.
PATCHES = (("forehead", (0.0, 80.0), (0.0, 72.0)),
           ("cheek", (40.0, 12.0), (40.0, -6.0)),
           ("nose", (0.0, 4.0), (0.0, -8.0)))
LIGHT = np.array([-0.45, 0.55, 0.70])


def load_obj(path):
    v, vt, faces = [], [], []
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append([float(c) for c in p[1:4]])
        elif p[0] == "vt":
            vt.append([float(c) for c in p[1:3]])
        elif p[0] == "f":
            faces.append([[int(c) - 1 for c in w.split("/")[:2]] for w in p[1:]])
    v, vt = np.array(v), np.array(vt)
    fv = np.array([[c[0] for c in f[:4]] for f in faces if len(f) == 4])
    ft = np.array([[c[1] for c in f[:4]] for f in faces if len(f) == 4])
    return v * SCAN_MM_PER_UNIT, fv, vt[ft]


def load_gnm():
    d = np.load(REPO / "assets/gnm/base.npz", allow_pickle=False)
    tiles = d["quad_udim_tiles"]
    keep = tiles == 1001
    return d["template_vertices"].astype(np.float64) * 1000.0, d["quads"][keep], \
        d["quad_uvs"][keep].astype(np.float64)


def quad_area(P):
    a = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    b = np.cross(P[:, 2] - P[:, 0], P[:, 3] - P[:, 0])
    if a.ndim == 1:      # 2D
        return 0.5 * (np.abs(a) + np.abs(b))
    return 0.5 * (np.linalg.norm(a, axis=1) + np.linalg.norm(b, axis=1))


def locate(V, quads, uvs, offset):
    """UV centre and texels-per-mm (per unit UV) of the surface patch at nose tip + offset."""
    used = np.unique(quads)
    front = used[V[used, 2] > V[used, 2].max() - 80.0]
    tip = front[np.argmax(V[front, 2])]
    target = V[tip, :2] + np.array(offset)
    near = front[np.linalg.norm(V[front, :2] - target, axis=1) < 4.0]
    vid = near[np.argmax(V[near, 2])]                         # most forward surface there
    centre3 = V[vid]
    cents = V[quads].mean(axis=1)
    close = np.linalg.norm(cents - centre3, axis=1) < 10.0
    area3 = quad_area(V[quads[close]]).sum()
    area_uv = quad_area(uvs[close]).sum()
    uv_per_mm = np.sqrt(area_uv / area3)
    q = np.where(close)[0][np.argmin(np.linalg.norm(cents[close] - centre3, axis=1))]
    corner = np.argmin(np.linalg.norm(V[quads[q]] - centre3, axis=1))
    return uvs[q, corner], uv_per_mm


def crop(img, uv, uv_per_mm, mode):
    """24 mm square around uv (v up), resampled to 20 px/mm."""
    w, h = img.size
    half_px = PATCH_MM / 2 * uv_per_mm * w
    cx, cy = uv[0] * w, (1.0 - uv[1]) * h
    box = (int(cx - half_px), int(cy - half_px), int(cx + half_px), int(cy + half_px))
    n = int(PATCH_MM * OUT_PX_PER_MM)
    return img.crop(box).resize((n, n), Image.LANCZOS if mode != "I" else Image.BILINEAR), \
        half_px * 2 / PATCH_MM


def shade_height(h):
    gy, gx = np.gradient(h)
    n = np.dstack([-gx, gy, np.ones_like(h) * np.std(np.hypot(gx, gy)) * 3])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return (n * (LIGHT / np.linalg.norm(LIGHT))).sum(axis=2)


def shade_normal(rgb):
    n = rgb[..., :3].astype(np.float64) / 255.0 * 2.0 - 1.0
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return (n * (LIGHT / np.linalg.norm(LIGHT))).sum(axis=2)


def to_grey(s):
    s = (s - s.mean()) / (s.std() + 1e-9)
    return Image.fromarray(np.clip(128 + 38 * s, 0, 255).astype(np.uint8)).convert("RGB")


def our_colour(skin, detail):
    a = (np.asarray(skin, dtype=np.float64)[..., :3] / 255.0) ** 2.2
    f = np.asarray(detail, dtype=np.float64)[..., :3] / 128.0
    return Image.fromarray(np.clip((a * f) ** (1 / 2.2) * 255, 0, 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "outputs/tmp/scan")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    sV, sQ, sUV = load_obj(SCAN / "head.OBJ")
    gV, gQ, gUV = load_gnm()
    s_col = Image.open(SCAN / "lambertian.jpg").convert("RGB")
    s_bump = Image.open(SCAN / "bump.png")
    s_bump = Image.fromarray(np.asarray(s_bump, dtype=np.float32), mode="F")
    m2 = REPO / "outputs/tmp/m2"
    g_skin = Image.open(m2 / "eurasian_f_young/skin.1001.png").convert("RGB")
    g_det = Image.open(m2 / "detail/seed_0/skin_detail.1001.png").convert("RGB")
    g_nrm = Image.open(m2 / "detail/seed_0/skin_normal.1001.png").convert("RGB")

    n = int(PATCH_MM * OUT_PX_PER_MM)
    cols = ("scan colour", "our colour", "scan relief", "our relief")
    sheet = Image.new("RGB", (n * 4 + 50, n * len(PATCHES) + 28), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    for c, name in enumerate(cols):
        draw.text((50 + c * n + 6, 8), name, fill=(230, 230, 230))
    for r, (name, g_off, s_off) in enumerate(PATCHES):
        s_uv, s_k = locate(sV, sQ, sUV, s_off)
        g_uv, g_k = locate(gV, gQ, gUV, g_off)
        sc, s_ppm = crop(s_col, s_uv, s_k, "RGB")
        sb, _ = crop(s_bump, s_uv, s_k, "F")
        gs, g_ppm = crop(g_skin, g_uv, g_k, "RGB")
        gd, _ = crop(g_det, g_uv, g_k, "RGB")
        gn, _ = crop(g_nrm, g_uv, g_k, "RGB")
        b_ppm = s_ppm * s_bump.size[0] / s_col.size[0]
        tiles = [sc, our_colour(gs, gd), to_grey(shade_height(np.asarray(sb, dtype=np.float64))),
                 to_grey(shade_normal(np.asarray(gn)))]
        for c, t in enumerate(tiles):
            sheet.paste(t, (50 + c * n, 28 + r * n))
            t.save(args.out / f"{name}_{c}_{cols[c].replace(' ', '_')}.png")
        draw.text((4, 28 + r * n + 6), name, fill=(230, 230, 230))
        print(f"[scan] {name:8s} scan colour {s_ppm:.1f} px/mm, scan displacement {b_ppm:.1f} px/mm, "
              f"ours {g_ppm:.1f} px/mm at 4096")
    sheet.save(args.out / "compare.png")
    print(f"[scan] wrote {args.out / 'compare.png'}")


if __name__ == "__main__":
    main()
