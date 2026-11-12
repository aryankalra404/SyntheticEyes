"""Procedural iris + sclera textures for GNM eye-interior tiles 1002 (left) and 1004 (right).

    python3 tools/make_iris.py --measure                      # assets/gnm/eye_uv.json
    python3 tools/make_iris.py --color brown --seed 3 --out outputs/tmp/m2/iris/brown
    python3 tools/make_iris.py --all --seed 0                 # six colours + sheet in outputs/tmp/m2/iris

numpy + scipy only (system python3). Same arguments, same bytes.

The eye-interior tile is a disc centred on (0.5, 0.5): pupil, iris and sclera are concentric
rings of the GNM mesh, and +u points to the subject's left (+X), +v up, for both eyes. So the
nasal corner is at -u for the left eye and +u for the right eye. The pupil is geometry (GNM's
`pupils_000` expression moves its ring), so the texture keeps the pupil disc near-black up to
the measured pupil-edge radius and lets the mesh set the size.

Left and right share colour and structure parameters (drawn from --seed) and use different
noise seeds, as real eyes do.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tex_core as tc  # noqa: E402

REPO = tc.REPO
EYE_UV_JSON = REPO / "assets/gnm/eye_uv.json"
TILES = {"L": 1002, "R": 1004}

# sRGB 0-255. base = deep stroma, fibre = light stroma, pupillary = zone inside the collarette,
# collarette = the ring itself, limbal = dark outer ring, ruff = pupil margin.
PALETTE = {
    "dark_brown": dict(base=(34, 19, 11), fibre=(78, 46, 26), pupillary=(48, 27, 14),
                       collarette=(96, 60, 34), limbal=(16, 10, 7), ruff=(22, 13, 8), freckles=0.5),
    "brown": dict(base=(66, 37, 18), fibre=(132, 84, 46), pupillary=(80, 44, 20),
                  collarette=(150, 98, 52), limbal=(27, 16, 9), ruff=(30, 17, 9), freckles=0.7),
    "hazel": dict(base=(78, 72, 38), fibre=(146, 134, 78), pupillary=(122, 70, 28),
                  collarette=(168, 112, 52), limbal=(36, 36, 22), ruff=(34, 20, 10), freckles=0.5),
    "green": dict(base=(56, 82, 52), fibre=(122, 150, 96), pupillary=(138, 108, 48),
                  collarette=(150, 142, 82), limbal=(26, 40, 30), ruff=(34, 22, 12), freckles=0.3),
    "blue": dict(base=(56, 90, 136), fibre=(150, 180, 212), pupillary=(104, 116, 118),
                 collarette=(172, 186, 202), limbal=(26, 40, 64), ruff=(36, 26, 20), freckles=0.15),
    "grey": dict(base=(92, 102, 110), fibre=(172, 180, 184), pupillary=(118, 116, 106),
                 collarette=(182, 186, 186), limbal=(42, 48, 56), ruff=(36, 28, 22), freckles=0.15),
}
COLORS = list(PALETTE)


# --------------------------------------------------------------------------- measurement

def measure(d) -> dict:
    """UV radii of the eye rings and the rest-pose lid opening, per eye, from base.npz."""
    names = tc.group_names(d)
    W = d["vertex_group_weights"]
    V = d["template_vertices"] * 1000.0
    out = {"source": "assets/gnm/base.npz template_vertices; tools/make_iris.py --measure",
           "uv_centre": [0.5, 0.5], "uv_axes": "+u = subject's left (+X), +v = up, both eyes"}
    for side, tile in TILES.items():
        tri, tuv = tc.tile_triangles(d, tile)
        vi, k = np.unique(tri.ravel(), return_index=True)
        uv = tuv.reshape(-1, 2)[k]
        r = np.round(np.linalg.norm(uv - 0.5, axis=1), 5)
        rings = {}
        for g in ("pupils", "irises", "scleras"):
            m = W[names.index(g)][vi] > 1e-4
            rings[g] = r[m]
        only_iris = (W[names.index("irises")][vi] > 1e-4) & (W[names.index("pupils")][vi] <= 1e-4)
        pupil_edge = float(rings["pupils"].max())
        iris_outer = float(r[only_iris].max())
        sclera_inner = float(rings["scleras"].min())
        sclera_outer = float(rings["scleras"].max())
        # 3D radius of each ring around the eye axis, for the record
        centre = V[vi[r == 0]][0]
        joint = d["joint_positions"][2 if side == "L" else 3] * 1000.0
        axis = (centre - joint) / np.linalg.norm(centre - joint)
        rel = V[vi] - joint
        perp = np.linalg.norm(rel - np.outer(rel @ axis, axis), axis=1)
        ring_mm = {f"{u:.4f}": round(float(perp[r == u].mean()), 3) for u in np.unique(r)}
        out[side] = {
            "tile": tile,
            "pupil_edge": pupil_edge,
            "iris_outer_ring": iris_outer,
            "sclera_inner_ring": sclera_inner,
            "limbus": round((iris_outer + sclera_inner) / 2, 5),
            "sclera_outer": sclera_outer,
            "pupil_edge_mm": ring_mm[f"{pupil_edge:.4f}"],
            "limbus_mm": round((ring_mm[f"{iris_outer:.4f}"] + ring_mm[f"{sclera_inner:.4f}"]) / 2, 3),
            "ring_radius_mm": ring_mm,
            "lid_opening": lid_opening(d, side, tile, V),
        }
    return out


def lid_opening(d, side, tile, V, half_mm=18.0, n=360, bins=72):
    """Rest-pose visible part of the globe, seen from the front, as UV radius per angle.

    Orthographic z-buffer along +Z: skin triangles against the front of the eye-interior
    surface. A globe texel is visible where it is nearer the viewer than any skin.
    Returns {"angles_deg": [...], "radius": [...]} with angle measured in UV from +u.
    """
    tri, tuv = tc.tile_triangles(d, tile)
    vi = np.unique(tri.ravel())
    uv_v = np.zeros((len(V), 2))
    uv_v[tri.ravel()] = tuv.reshape(-1, 2)
    centre = V[vi][np.argmin(np.linalg.norm(uv_v[vi] - 0.5, axis=1))]
    lo = centre[:2] - half_mm

    def to_win(P):
        return np.stack([(P[..., 0] - lo[0]) / (2 * half_mm), (P[..., 1] - lo[1]) / (2 * half_mm)], -1)

    front = (V[tri][..., 2] > centre[2] - 8.0).all(1)
    g_tri = tri[front]
    g_fid, g_bary, g_z = tc.rasterize(to_win(V[g_tri]), n, depth=V[g_tri][..., 2])
    st, _ = tc.tile_triangles(d, 1001)
    near = (np.abs(V[st][..., :2] - centre[:2]) < half_mm + 2).all(-1).any(1)
    st = st[near]
    _, _, s_z = tc.rasterize(to_win(V[st]), n, depth=V[st][..., 2])
    vis = (g_fid >= 0) & (g_z > s_z + 0.05)
    uvp = np.einsum("nk,nkc->nc", g_bary[vis], uv_v[g_tri][g_fid[vis]]) - 0.5
    ang = np.degrees(np.arctan2(uvp[:, 1], uvp[:, 0])) % 360
    rad = np.linalg.norm(uvp, axis=1)
    edges = np.arange(bins) * 360 / bins
    radius = []
    for a in edges:
        m = np.abs((ang - a + 180) % 360 - 180) < 360 / bins
        radius.append(round(float(rad[m].max()), 4) if m.any() else 0.0)
    return {"angles_deg": edges.tolist(), "radius": radius}


def load_eye_uv(d=None) -> dict:
    if EYE_UV_JSON.exists():
        return json.loads(EYE_UV_JSON.read_text())
    m = measure(tc.load_base() if d is None else d)
    EYE_UV_JSON.write_text(json.dumps(m, indent=1) + "\n")
    return m


# --------------------------------------------------------------------------- helpers

def lin(rgb):
    return tc.srgb_to_linear(np.asarray(rgb, dtype=np.float64) / 255.0)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def norm01(x):
    x = x - x.mean()
    return x / (x.std() + 1e-9)


def polar_noise(rng, shape, sigma):
    """Gaussian-filtered white noise, periodic along axis 1 (angle), unit variance."""
    return norm01(gaussian_filter(rng.standard_normal(shape), sigma, mode=("nearest", "wrap")))


def lerp(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return a + (b - a) * t


# --------------------------------------------------------------------------- iris

def structure_params(seed: int) -> dict:
    """Shared by both eyes of a set."""
    rng = np.random.default_rng([seed, 0])
    return dict(
        collarette=rng.uniform(0.28, 0.40),
        collarette_jag=rng.uniform(0.035, 0.06),
        fibre_contrast=rng.uniform(0.55, 0.8),
        crypts=int(rng.integers(18, 45)),
        furrows=int(rng.integers(2, 5)),
        limbal=rng.uniform(0.5, 0.75),
        pupillary_mix=rng.uniform(0.55, 0.85),
        veins=int(rng.integers(44, 60)),
        redness=rng.uniform(0.8, 1.2),
        freckle_count=int(rng.integers(0, 5)),
    )


def iris_polar(rng, P, S, nt=420, nth=4096):
    """Iris colour (linear RGB) on a polar grid: rows t in [0, 1] pupil edge -> limbus,
    columns angle in [0, 2pi). Returns (nt, nth, 3)."""
    t = np.linspace(0, 1, nt)[:, None]
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False)[None, :]
    base, fibre, pupillary = lin(P["base"]), lin(P["fibre"]), lin(P["pupillary"])
    coll_c, limbal_c, ruff_c = lin(P["collarette"]), lin(P["limbal"]), lin(P["ruff"])

    # stroma fibres: radial streaks, gently wavy, coarse + fine
    warp = 6.0 * polar_noise(rng, (nt, nth), (40, 60))
    cols = (np.arange(nth)[None, :] + warp) % nth
    rows = np.broadcast_to(np.arange(nt)[:, None], (nt, nth)).astype(np.float64)
    coarse = polar_noise(rng, (nt, nth), (18, 2.2))
    fine = polar_noise(rng, (nt, nth), (7, 0.9))
    f = 0.65 * coarse + 0.45 * fine
    f = map_coordinates(f, [rows, cols], order=1, mode="grid-wrap")
    fib = np.clip(0.5 + 0.28 * f, 0, 1) ** 1.3

    # collarette radius, jagged
    jag = polar_noise(rng, (1, nth), (0, 26))[0] * 0.6 + polar_noise(rng, (1, nth), (0, 6))[0] * 0.4
    tc_th = S["collarette"] + S["collarette_jag"] * jag
    inside = 1.0 - smoothstep(tc_th - 0.02, tc_th + 0.02, t)

    col = lerp(base, fibre, fib * S["fibre_contrast"] + 0.22)
    col = lerp(col, pupillary * (0.7 + 0.6 * fib[..., None]), inside * S["pupillary_mix"])

    # collarette band: brighter, slightly raised
    band = np.exp(-0.5 * ((t - tc_th) / 0.022) ** 2) * (0.6 + 0.4 * np.clip(fib * 1.5, 0, 1))
    col = lerp(col, coll_c, np.clip(band * 0.75, 0, 1))

    # crypts: dark radial lozenges near and outside the collarette, with lighter rims
    dark = np.zeros((nt, nth))
    rim = np.zeros((nt, nth))
    for _ in range(S["crypts"]):
        ct = np.clip(rng.normal(S["collarette"] + 0.12, 0.16), 0.12, 0.85)
        cth = rng.uniform(0, 2 * np.pi)
        lt = rng.uniform(0.025, 0.08)
        r_uv = 0.05 + ct * 0.138
        wth = rng.uniform(0.008, 0.022) / r_uv * 0.6           # angle width ~ arc length
        dth = (th - cth + np.pi) % (2 * np.pi) - np.pi
        q = ((t - ct) / lt) ** 2 + (dth / wth) ** 2
        depth = rng.uniform(0.5, 1.0)
        dark = np.maximum(dark, depth * np.exp(-q * 1.6) * (q < 4))
        rim = np.maximum(rim, depth * np.exp(-((np.sqrt(q) - 1.25) / 0.3) ** 2) * (q < 4))
    col = col * (1 - 0.7 * dark)[..., None]
    col = lerp(col, fibre, 0.25 * rim)

    # contraction furrows: broken concentric dark lines in the outer (ciliary) zone
    for i in range(S["furrows"]):
        ft = 0.55 + 0.38 * (i + rng.uniform(0.2, 0.8)) / S["furrows"]
        ft_th = ft + 0.012 * polar_noise(rng, (1, nth), (0, 40))[0]
        broken = smoothstep(-0.2, 0.6, polar_noise(rng, (1, nth), (0, 80))[0])
        line = np.exp(-0.5 * ((t - ft_th) / 0.006) ** 2) * broken
        col = col * (1 - 0.35 * line)[..., None]

    # iris freckles (Fuchs nevi): a few small dark-brown dots, brown-ish eyes more often
    nfreck = int(round(S["freckle_count"] * P["freckles"]))
    for _ in range(nfreck):
        ct, cth = rng.uniform(0.35, 0.9), rng.uniform(0, 2 * np.pi)
        r_uv = 0.05 + ct * 0.138
        s = rng.uniform(0.004, 0.009)
        dth = (th - cth + np.pi) % (2 * np.pi) - np.pi
        q = ((t - ct) * 0.138 / s) ** 2 + (dth * r_uv / s) ** 2
        col = lerp(col, lin((70, 38, 18)), 0.8 * np.exp(-q))

    # limbal ring: darkening toward the edge
    lim = smoothstep(0.80, 1.0, t) * S["limbal"]
    col = lerp(col, limbal_c, lim)

    # pupil ruff: thin crenellated dark-brown rim at the pupil edge
    ruff_t = np.clip(0.035 + 0.012 * polar_noise(rng, (1, nth), (0, 4))[0], 0.018, 0.06)
    ruff = 1 - smoothstep(ruff_t * 0.6, ruff_t, t)
    col = lerp(col, ruff_c, ruff)

    # low-frequency brightness variation so the iris is not perfectly even
    col = col * (1 + 0.12 * polar_noise(rng, (nt, nth), (60, 200)))[..., None]
    return np.clip(col, 0, 1)


# --------------------------------------------------------------------------- sclera

def draw_vessels(rng, size, count, eye_uv, side, S, layer):
    """Branching vessels in UV, from the back of the globe toward the limbus.

    Returns an (size, size) coverage map in [0, 1]. Angles near the horizontal (the
    canthi, where the conjunctiva is exposed) get most vessels, the nasal side most of all.
    """
    cov = np.zeros((size, size), dtype=np.float64)
    nasal = np.pi if side == "L" else 0.0
    lim = eye_uv["limbus"]

    def seg(p0, p1, w):
        # anti-aliased capsule from p0 to p1 (pixel coords), width w px
        x0, y0 = np.minimum(p0, p1) - w - 2
        x1, y1 = np.maximum(p0, p1) + w + 2
        x0, y0 = max(int(x0), 0), max(int(y0), 0)
        x1, y1 = min(int(x1) + 1, size), min(int(y1) + 1, size)
        if x1 <= x0 or y1 <= y0:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1] + 0.5
        d = p1 - p0
        L2 = max(float(d @ d), 1e-9)
        tt = np.clip(((xs - p0[0]) * d[0] + (ys - p0[1]) * d[1]) / L2, 0, 1)
        dist = np.hypot(xs - (p0[0] + tt * d[0]), ys - (p0[1] + tt * d[1]))
        a = np.clip(w / 2 + 0.5 - dist, 0, 1)
        cov[y0:y1, x0:x1] = np.maximum(cov[y0:y1, x0:x1], a)

    def to_px(r, a):
        return np.array([(0.5 + r * np.cos(a)) * size, (0.5 - r * np.sin(a)) * size])

    def walk(r, a, w, r_end, depth, heading=None):
        # heading is measured in the (radial, tangential) frame; pi = straight toward the limbus.
        # Curvature has momentum, so vessels bend smoothly instead of zigzagging.
        heading = np.pi + rng.normal(0, 0.3) if heading is None else heading
        kappa = 0.0
        p = to_px(r, a)
        step = 0.0035
        wiggle = 0.05 if layer == "fine" else 0.03
        while r > r_end and w > 0.45:
            kappa = 0.75 * kappa + rng.normal(0, wiggle)
            heading += kappa - 0.08 * (heading - np.pi)
            dr = step * np.cos(heading)
            da = step * np.sin(heading) / max(r, 0.05)
            r, a = r + dr, a + da
            q = to_px(r, a)
            seg(p, q, w)
            p = q
            w *= rng.uniform(0.975, 0.995)
            if depth < 3 and rng.random() < (0.05 if layer == "fine" else 0.03):
                side_turn = rng.choice([-1, 1]) * rng.uniform(0.35, 0.8)
                walk(r, a, w * rng.uniform(0.5, 0.75), max(r_end, r - rng.uniform(0.04, 0.12)),
                     depth + 1, heading + side_turn)
                heading -= 0.3 * side_turn

    for _ in range(count):
        # angle density: mostly horizontal, nasal strongest
        while True:
            a = rng.uniform(0, 2 * np.pi)
            dn = np.cos(a - nasal)
            p_acc = 0.18 + 0.82 * (np.abs(np.cos(a)) ** 2) * (0.7 + 0.3 * dn)
            if rng.random() < p_acc:
                break
        r0 = rng.uniform(0.29, 0.47)
        horiz = np.abs(np.cos(a))
        r_end = lim + 0.008 + rng.uniform(0.0, 0.07) + 0.06 * (1 - horiz)
        if layer == "fine":
            w0 = rng.uniform(1.8, 3.8) * (0.6 + 0.4 * horiz)
        else:
            w0 = rng.uniform(4.0, 8.0)
        walk(r0, a, w0, r_end, 0)
    return cov


def sclera(rng, size, eye_uv, side, S, R, TH):
    lim = eye_uv["limbus"]
    nasal = np.pi if side == "L" else 0.0
    base = lin((206, 195, 183))
    yellow = lin((206, 190, 160))
    pink = lin((206, 138, 132))
    rim_tint = np.array([0.80, 0.75, 0.75])

    # gentle mottling
    w = rng.standard_normal((size, size))
    m = 0.6 * norm01(gaussian_filter(w, 24, mode="wrap")) + 0.4 * norm01(gaussian_filter(w, 6, mode="wrap"))
    col = base[None, None, :] * (1 + 0.022 * m)[..., None]

    # warmer and yellower away from the cornea
    col = lerp(col, yellow, 0.22 * smoothstep(lim + 0.05, 0.42, R))

    # pink toward the corners (horizontal), nasal side strongest
    horiz = np.abs(np.cos(TH)) ** 3
    dn = 0.5 + 0.5 * np.cos(TH - nasal)
    corner = horiz * (0.55 + 0.45 * dn) * smoothstep(lim + 0.0, 0.30, R)
    corner = corner * (1 + 0.1 * m)
    col = lerp(col, pink, np.clip(0.7 * corner * S["redness"], 0, 1))

    # darker rim under the lids: beyond the rest-pose opening, ramped so gaze shifts reveal
    # a gradient, never an edge
    lo = eye_uv["lid_opening"]
    ang = np.radians(np.array(lo["angles_deg"] + [360.0]))
    rad = np.array(lo["radius"] + [lo["radius"][0]])
    r_open = np.interp(TH % (2 * np.pi), ang, gaussian_filter(rad, 1.0, mode="wrap"))
    start = np.maximum(r_open, lim + 0.012)
    under = smoothstep(start, start + 0.11, R) * smoothstep(lim, lim + 0.03, R)
    col = col * (1 - (1 - rim_tint) * (0.85 * under)[..., None])

    # vessels: deep blurred episcleral layer first, then sharp conjunctival vessels
    deep = draw_vessels(rng, size, S["veins"] // 3, eye_uv, side, S, "deep")
    deep = gaussian_filter(deep, 3.0)
    col = lerp(col, lin((150, 70, 82)), np.clip(0.22 * deep * S["redness"], 0, 1))
    fine = draw_vessels(rng, size, S["veins"], eye_uv, side, S, "fine")
    halo = gaussian_filter(fine, 2.0)
    fade = smoothstep(lim + 0.004, lim + 0.045, R)               # vessels fade toward the limbus
    col = lerp(col, lin((196, 96, 92)), np.clip(0.25 * halo * fade * S["redness"], 0, 1))
    col = lerp(col, lin((150, 32, 34)), np.clip(0.75 * fine * fade * S["redness"], 0, 1))

    # faint grey-blue band just outside the limbus
    band = np.exp(-0.5 * ((R - (lim + 0.01)) / 0.008) ** 2)
    col = lerp(col, lin((168, 170, 176)), 0.12 * band)
    return col


# --------------------------------------------------------------------------- compose

def make_eye(color: str, seed: int, side: str, eye_uv: dict, size: int = 2048) -> np.ndarray:
    P = PALETTE[color]
    S = structure_params(seed)
    E = eye_uv[side]
    rng = np.random.default_rng([seed, 1 if side == "L" else 2])
    c = (np.arange(size) + 0.5) / size
    U, Vv = np.meshgrid(c, 1.0 - c)
    R = np.hypot(U - 0.5, Vv - 0.5)
    TH = np.arctan2(Vv - 0.5, U - 0.5) % (2 * np.pi)

    rp, rl = E["pupil_edge"], E["limbus"]
    pol = iris_polar(rng, P, S)
    nt, nth = pol.shape[:2]
    t = (R - rp) / (rl - rp)
    rows = np.clip(t, 0, 1) * (nt - 1)
    cols = TH / (2 * np.pi) * nth
    iris = np.stack([map_coordinates(pol[..., k], [rows, cols], order=1, mode="grid-wrap") for k in range(3)], -1)

    scl = sclera(rng, size, E, side, S, R, TH)
    # iris -> sclera blend across the limbus (about 0.15 mm wide on the surface)
    w_iris = 1 - smoothstep(rl - 0.002, rl + 0.006, R)
    col = lerp(scl, iris, w_iris)

    # pupil: near-black inside the measured pupil edge, soft by about one texel
    pupil = 1 - smoothstep(rp - 0.0015, rp + 0.0005, R)
    col = lerp(col, lin((6, 5, 5)), pupil)
    return tc.to_u8(tc.linear_to_srgb(col))


def write_set(color, seed, out: Path, eye_uv, size=2048):
    out.mkdir(parents=True, exist_ok=True)
    imgs = {}
    for side, tile in TILES.items():
        img = make_eye(color, seed, side, eye_uv, size)
        tc.write_png(out / f"eye.{tile}.png", img)
        imgs[side] = img
    (out / "iris.json").write_text(json.dumps(
        {"color": color, "seed": seed, "size": size, "params": structure_params(seed)}, indent=1) + "\n")
    return imgs


def sheet(imgs: list[np.ndarray], crop: float = 0.24, cell: int = 512) -> np.ndarray:
    from PIL import Image
    tiles = []
    for img in imgs:
        s = img.shape[0]
        a, b = int((0.5 - crop) * s), int((0.5 + crop) * s)
        tiles.append(np.asarray(Image.fromarray(img[a:b, a:b]).resize((cell, cell), Image.LANCZOS)))
    return np.concatenate(tiles, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--measure", action="store_true", help="measure eye UV radii into assets/gnm/eye_uv.json")
    ap.add_argument("--color", choices=COLORS, default="brown")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--all", action="store_true", help="all six colours into --out/<colour>/ plus sheet.png")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.measure:
        m = measure(tc.load_base())
        EYE_UV_JSON.write_text(json.dumps(m, indent=1) + "\n")
        for side in TILES:
            e = m[side]
            print(f"[iris] {side}: pupil edge {e['pupil_edge']:.4f} ({e['pupil_edge_mm']} mm), "
                  f"limbus {e['limbus']:.4f} ({e['limbus_mm']} mm), sclera to {e['sclera_outer']:.4f}")
        print(f"[iris] wrote {EYE_UV_JSON.relative_to(REPO)}")
        return

    eye_uv = load_eye_uv()
    if args.all:
        out = args.out or REPO / "outputs/tmp/m2/iris"
        left = []
        for i, color in enumerate(COLORS):
            imgs = write_set(color, args.seed + i, out / color, eye_uv, args.size)
            left.append(imgs["L"])
            print(f"[iris] {color} seed {args.seed + i} -> {(out / color).relative_to(REPO)}")
        tc.write_png(out / "sheet.png", sheet(left))
        print(f"[iris] sheet {(out / 'sheet.png').relative_to(REPO)}")
    else:
        out = args.out or REPO / f"outputs/tmp/m2/iris/{args.color}"
        write_set(args.color, args.seed, out, eye_uv, args.size)
        print(f"[iris] {args.color} seed {args.seed} -> {out}")


if __name__ == "__main__":
    main()
