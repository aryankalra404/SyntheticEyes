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
# These are final colours: they include the tone the eye shader used to add on top
# (linear-light HSV, saturation x 0.72, value x 0.80; M3), and the pupillary and collarette
# hues are kept within 15 degrees of the fibre hue so the inner zone reads as part of the same
# iris, not a painted patch. Brown and dark brown are set by hand, darker and warmer than the
# toned originals (which read grey-brown at face distance).
# radial (brown and dark brown only, M11): on a bare head under plain light, with a clear cornea
# that lays a grey reflection over the whole eye, the M3 browns went to flat grey-brown discs.
# These add chroma and radial structure only, all functions of the radius and the fibre noise,
# never of the angle (the tile turns with the eye): stroma contrast x contrast, a lighter warm
# zone `mid` round the collarette (gaussian at mid_t, width mid_w), a deeper limbal ring (colour
# weight `limbal`, brightness at the limbus limbal_gain instead of LIMBAL_GAIN) and darker stroma
# out to pupil_ring_t round the pupil. Mean iris luminance rises 26-34 % (linear), its spread
# about 75 %. Palettes without `radial` are unchanged, byte for byte.
PALETTE = {
    "dark_brown": dict(base=(22, 12, 6), fibre=(72, 41, 19), pupillary=(32, 17, 8),
                       collarette=(84, 50, 23), limbal=(8, 5, 3), ruff=(10, 6, 4), freckles=0.5,
                       radial=dict(contrast=1.3, mid=(104, 64, 30), mid_t=0.40, mid_w=0.13, mid_amt=0.4,
                                   limbal=0.95, limbal_gain=0.32, pupil_ring=0.35, pupil_ring_t=0.16)),
    "brown": dict(base=(40, 22, 11), fibre=(106, 66, 34), pupillary=(50, 28, 13),
                  collarette=(118, 76, 38), limbal=(14, 8, 5), ruff=(16, 9, 5), freckles=0.7,
                  radial=dict(contrast=1.3, mid=(138, 92, 46), mid_t=0.40, mid_w=0.13, mid_amt=0.4,
                              limbal=0.95, limbal_gain=0.32, pupil_ring=0.35, pupil_ring_t=0.16)),
    "hazel": dict(base=(70, 66, 47), fibre=(132, 124, 93), pupillary=(110, 89, 63),
                  collarette=(152, 125, 92), limbal=(32, 32, 23), ruff=(30, 21, 16), freckles=0.5),
    "green": dict(base=(58, 73, 55), fibre=(118, 135, 103), pupillary=(112, 125, 77),
                  collarette=(124, 135, 96), limbal=(27, 35, 29), ruff=(30, 22, 17), freckles=0.3),
    "blue": dict(base=(79, 95, 123), fibre=(154, 172, 192), pupillary=(97, 104, 106),
                 collarette=(164, 172, 183), limbal=(36, 43, 57), ruff=(32, 25, 22), freckles=0.15),
    "grey": dict(base=(88, 94, 99), fibre=(159, 164, 166), pupillary=(99, 106, 106),
                 collarette=(166, 168, 168), limbal=(41, 45, 50), ruff=(32, 26, 23), freckles=0.15),
}
COLORS = list(PALETTE)
FRECKLE = (63, 44, 35)

# Shading the eye shader used to apply and that is now in the tile (M3 numbers; the shader's
# IRIS_SATURATION / IRIS_VALUE go to 1, LIMBAL_DARK to 0 and its fornix falloff goes away).
LIMBAL_START = 0.72      # limbal ring starts darkening at this fraction of the limbus radius
LIMBAL_GAIN = 0.45       # brightness factor at the limbus
LIMBAL_FADE = 0.03       # UV distance over which it fades out into the sclera
FORNIX = (0.20, 0.40, 0.30)   # sclera darkens from UV radius 0.20 to 0.40, by 30 %


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
        fibre_contrast=rng.uniform(0.8, 1.0),
        crypts=int(rng.integers(40, 80)),
        furrows=int(rng.integers(1, 4)),
        limbal=rng.uniform(0.5, 0.75),
        pupillary_mix=rng.uniform(0.55, 0.85),
        veins=int(rng.integers(44, 60)),
        redness=rng.uniform(0.8, 1.2),
        freckle_count=int(rng.integers(0, 5)),
        streaks=rng.uniform(0.22, 0.32),
        collarette_gaps=rng.uniform(0.15, 0.35),
        collarette_reach=rng.uniform(0.08, 0.16),
        crypt_scale=rng.uniform(0.85, 1.2),
    )


def iris_polar(rng, P, S, nt=420, nth=4096):
    """Iris colour (linear RGB) on a polar grid: rows t in [0, 1] pupil edge -> limbus,
    columns angle in [0, 2pi). Returns (nt, nth, 3)."""
    t = np.linspace(0, 1, nt)[:, None]
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False)[None, :]
    base, fibre, pupillary = lin(P["base"]), lin(P["fibre"]), lin(P["pupillary"])
    coll_c, limbal_c, ruff_c = lin(P["collarette"]), lin(P["limbal"]), lin(P["ruff"])

    # stroma fibres: radial streaks, gently wavy, coarse + fine
    warp = 6.0 * polar_noise(rng, (nt, nth), (40, 60)) + 6.0 * polar_noise(rng, (nt, nth), (25, 90))
    cols = (np.arange(nth)[None, :] + warp) % nth
    rows = np.broadcast_to(np.arange(nt)[:, None], (nt, nth)).astype(np.float64)
    coarse = polar_noise(rng, (nt, nth), (18, 2.2))
    fine = polar_noise(rng, (nt, nth), (7, 0.9))
    f = 0.65 * coarse + 0.45 * fine
    f = map_coordinates(f, [rows, cols], order=1, mode="grid-wrap")
    fib = np.clip(0.5 + 0.36 * f, 0, 1) ** 1.3

    # radial streaks a few fibres wide, light and dark, long along the radius. At render size
    # (iris ~60 px across, ~20 polar columns per pixel) single fibres average out; these do not.
    st = 0.6 * polar_noise(rng, (nt, nth), (60, 12)) + 0.6 * polar_noise(rng, (nt, nth), (90, 26))
    st = map_coordinates(norm01(st), [rows, cols], order=1, mode="grid-wrap")

    # collarette radius, gently jagged
    jag = polar_noise(rng, (1, nth), (0, 26))[0] * 0.6 + polar_noise(rng, (1, nth), (0, 6))[0] * 0.4
    tc_th = S["collarette"] + 0.6 * S["collarette_jag"] * jag
    # the pupillary zone reaches outward along radial spokes (a few fibres wide) instead of
    # stopping at a line, and blends into the ciliary zone over +-0.08 of the iris width
    spokes = norm01(0.6 * polar_noise(rng, (1, nth), (0, 10))[0] + 0.5 * polar_noise(rng, (1, nth), (0, 30))[0])
    edge = tc_th + S["collarette_reach"] * smoothstep(0.0, 2.0, spokes)
    inside = 1.0 - smoothstep(edge - 0.08, edge + 0.08, t)
    inside = inside * np.clip(0.55 + 0.9 * fib, 0, 1) ** (1.0 - inside)   # ragged along the fibres

    R_ = P.get("radial")                      # optional, brown palettes only (M11); None = as before
    mix = fib * S["fibre_contrast"] + 0.18 + 0.12 * st
    if R_:
        mix = 0.5 + (mix - 0.5) * R_["contrast"]
    col = lerp(base, fibre, np.clip(mix, 0, 1))
    col = lerp(col, pupillary * (0.7 + 0.6 * fib[..., None]), inside * S["pupillary_mix"])
    col = col * (1 + S["streaks"] * np.clip(st, -2.2, 2.2))[..., None]
    if R_:
        # a lighter, warmer zone round the collarette, following the fibres; a function of the
        # radius and the fibre noise only, so it has no side and turns with the eye unnoticed
        zone = np.exp(-0.5 * ((t - R_["mid_t"]) / R_["mid_w"]) ** 2)
        col = lerp(col, lin(R_["mid"]) * (0.7 + 0.6 * fib[..., None]),
                   np.clip(R_["mid_amt"] * zone * (0.5 + 0.7 * fib), 0, 1))

    # collarette: a low broken ridge, not a ring. Width and brightness vary around the iris and
    # it has gaps; it follows the fibres so it reads as raised stroma, not a painted line.
    width = 0.035 * np.clip(0.75 + 0.45 * polar_noise(rng, (1, nth), (0, 30))[0], 0.3, 1.6)
    bright = np.clip(0.6 + 0.4 * polar_noise(rng, (1, nth), (0, 45))[0], 0.1, 1.0)
    gap_n = polar_noise(rng, (1, nth), (0, 60))[0]
    gaps = smoothstep(np.quantile(gap_n, S["collarette_gaps"]) - 0.3,
                      np.quantile(gap_n, S["collarette_gaps"]) + 0.3, gap_n)
    band = np.exp(-0.5 * ((t - tc_th) / width) ** 2) * np.clip(fib * 1.4, 0, 1)
    col = lerp(col, coll_c * (0.8 + 0.4 * fib[..., None]), np.clip(0.85 * band * bright * gaps, 0, 1))

    # crypts: dark lozenges stretched along the radius, pointed at both ends, varied in size,
    # densest just outside the collarette and thinning toward the limbus, with lighter rims of
    # trabeculae. Drawn on a local window each (the full grid per crypt is slow).
    dark = np.zeros((nt, nth))
    rim = np.zeros((nt, nth))
    span = 0.138                                            # iris width in UV (pupil edge -> limbus)
    for _ in range(S["crypts"]):
        if rng.random() < 0.7:
            ct = S["collarette"] + 0.03 + rng.exponential(0.1)
        else:
            ct = rng.uniform(0.1, 0.85)
        ct = float(np.clip(ct, 0.08, 0.88))
        cth = rng.uniform(0, 2 * np.pi)
        r_uv = 0.05 + ct * span
        # half-width across the radius (UV); bigger and deeper near the collarette
        near = np.exp(-max(ct - S["collarette"], 0) / 0.2)
        w = S["crypt_scale"] * rng.lognormal(np.log(0.0042), 0.45) * (0.7 + 0.5 * near)
        L = w * rng.uniform(1.8, 3.2)                       # half-length along the radius
        L_out = L * rng.uniform(1.0, 1.5)                   # a little longer outward (teardrop)
        depth = rng.uniform(0.45, 1.0) * (0.7 + 0.3 * near)
        r0, r1 = int((ct - 1.6 * L / span) * (nt - 1)) - 1, int((ct + 1.6 * L_out / span) * (nt - 1)) + 2
        r0, r1 = max(r0, 0), min(r1, nt)
        half = int(1.6 * w / r_uv / (2 * np.pi) * nth) + 2
        c_mid = int(round(cth / (2 * np.pi) * nth))
        ci = np.arange(c_mid - half, c_mid + half + 1) % nth
        if r1 <= r0:
            continue
        tt = t[r0:r1]
        dth = (th[0, ci][None, :] - cth + np.pi) % (2 * np.pi) - np.pi
        dr = (tt - ct) * span
        a = np.where(dr > 0, dr / L_out, dr / L)
        b = dth * r_uv / w
        q = (np.abs(a) ** 1.25 + np.abs(b) ** 1.25) ** (1 / 1.25)   # rounded diamond
        d_in = depth * (1 - smoothstep(0.55, 1.0, q)) * (0.65 + 0.35 * np.clip(1 - q, 0, 1))
        d_rim = depth * np.exp(-((q - 1.12) / 0.16) ** 2)
        dark[r0:r1, ci] = np.maximum(dark[r0:r1, ci], d_in)
        rim[r0:r1, ci] = np.maximum(rim[r0:r1, ci], d_rim)
    col = col * (1 - 0.7 * dark * (0.75 + 0.5 * (1 - fib)))[..., None]
    col = lerp(col, fibre * (0.85 + 0.3 * fib[..., None]), 0.3 * rim)

    # contraction furrows: a few short, faint arcs in the outer (ciliary) zone
    for i in range(S["furrows"]):
        ft = 0.6 + 0.32 * (i + rng.uniform(0.2, 0.8)) / S["furrows"]
        ft_th = ft + 0.012 * polar_noise(rng, (1, nth), (0, 40))[0]
        broken = smoothstep(0.9, 1.6, polar_noise(rng, (1, nth), (0, 50))[0])
        line = np.exp(-0.5 * ((t - ft_th) / 0.005) ** 2) * broken
        col = col * (1 - 0.15 * line)[..., None]

    # iris freckles (Fuchs nevi): a few small dark-brown dots, brown-ish eyes more often
    nfreck = int(round(S["freckle_count"] * P["freckles"]))
    for _ in range(nfreck):
        ct, cth = rng.uniform(0.35, 0.9), rng.uniform(0, 2 * np.pi)
        r_uv = 0.05 + ct * 0.138
        s = rng.uniform(0.004, 0.009)
        dth = (th - cth + np.pi) % (2 * np.pi) - np.pi
        q = ((t - ct) * 0.138 / s) ** 2 + (dth * r_uv / s) ** 2
        col = lerp(col, lin(FRECKLE), 0.8 * np.exp(-q))

    # limbal colour toward the edge; the wide brightness falloff across the limbus is applied
    # in make_eye, in UV, so it carries on into the sclera
    lim = smoothstep(0.75, 1.0, t) * S["limbal"] * (R_["limbal"] if R_ else 0.7)
    col = lerp(col, limbal_c, lim)

    # pupil ruff: thin crenellated dark-brown rim at the pupil edge
    ruff_t = np.clip(0.035 + 0.012 * polar_noise(rng, (1, nth), (0, 4))[0], 0.018, 0.06)
    ruff = 1 - smoothstep(ruff_t * 0.6, ruff_t, t)
    col = lerp(col, ruff_c, ruff)
    if R_:
        # darker stroma close round the pupil
        col = col * (1 - R_["pupil_ring"] * (1 - smoothstep(0.02, R_["pupil_ring_t"], t)))[..., None]

    # low-frequency brightness variation so the iris is not perfectly even
    col = col * (1 + 0.12 * polar_noise(rng, (nt, nth), (60, 200)))[..., None]
    return np.clip(col, 0, 1)


# --------------------------------------------------------------------------- sclera

BLOOD = np.array([0.15, 1.0, 0.80])     # absorbance of a blood column in linear R, G, B (green = 1)
VESSEL_TAU = 3.3                        # green optical depth through a vessel 6 texels wide


def draw_vessels(rng, size, count, eye_uv, side, kind):
    """Vessels in UV as an optical-depth map (how much blood the light crosses at each texel).

    kind: "tree" (conjunctival trunks that rise from behind the lids, run toward the limbus and
    fork into finer, more winding twigs), "fine" (small vessels that surface part-way, with a
    few twigs of their own) or "deep" (anterior ciliary vessels over the four rectus muscles:
    wide, nearly straight, blurred by the caller because they lie under the episclera).

    A vessel is a blood-filled tube, so depth follows a round cross-section and grows with
    width: wide vessels come out dark, twigs pale. One texel is about 14 um on the globe.
    Forks start solid at the parent (width split by Murray's law) and every tip thins and
    fades out, so nothing starts or ends as a cut line. Angles near the horizontal (the canthi,
    where the conjunctiva is exposed) get most vessels, the nasal side most of all.
    """
    od = np.zeros((size, size), dtype=np.float64)
    nasal = np.pi if side == "L" else 0.0
    lim = eye_uv["limbus"]
    centre = np.array([size / 2, size / 2])
    step = 2.5 * size / 2048                                   # texels per segment
    max_depth = {"tree": 4, "fine": 2, "deep": 1}[kind]
    tort = {"tree": 1.0, "fine": 1.15, "deep": 0.35}[kind]

    def seg(p0, p1, w, alpha):
        if alpha <= 0.01:
            return
        ww = max(w, 1.0)                       # under a texel wide: thinner means fainter
        tau = alpha * min(w, 1.0) * VESSEL_TAU * (ww / 6.0) ** 0.85
        rad = ww / 2 + 0.5
        x0, y0 = np.minimum(p0, p1) - rad - 1
        x1, y1 = np.maximum(p0, p1) + rad + 1
        x0, y0 = max(int(x0), 0), max(int(y0), 0)
        x1, y1 = min(int(x1) + 1, size), min(int(y1) + 1, size)
        if x1 <= x0 or y1 <= y0:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1] + 0.5
        d = p1 - p0
        L2 = max(float(d @ d), 1e-9)
        tt = np.clip(((xs - p0[0]) * d[0] + (ys - p0[1]) * d[1]) / L2, 0, 1)
        dist = np.hypot(xs - (p0[0] + tt * d[0]), ys - (p0[1] + tt * d[1]))
        a = np.sqrt(np.clip(1 - (dist / rad) ** 2, 0, 1)) * tau      # chord through a round tube
        od[y0:y1, x0:x1] = np.maximum(od[y0:y1, x0:x1], a)

    def grow(p, base, w, depth, bias, r_stop, life, root):
        """One vessel from p (texels). base: its heading; bias: how far it splays off the radial
        (relaxes along the way, so a branch leaves at an angle and then turns toward the limbus);
        life: longest length in texels; root: fade in (a vessel surfacing, not a fork)."""
        pts, ws = [p.copy()], [w]
        kids = []
        phase = rng.uniform(0, 2 * np.pi)
        thin = 1.0 / max(w, 0.8)
        # lazy bends of uneven length, never a regular wave: the wavelength is redrawn every
        # half turn and the swing with it
        wavelen = rng.uniform(70, 190) * (0.5 + 0.5 * min(w, 5.0) / 5.0) * size / 2048
        amp = tort * rng.uniform(0.14, 0.5) * (1.0 + 0.45 * thin)      # heading swing, radians
        half = int(phase / np.pi)
        taper = rng.uniform(0.9945, 0.9975) if depth == 0 else rng.uniform(0.990, 0.996)
        next_fork = rng.uniform(40, 150) * (0.45 + 0.55 * min(w, 6.0) / 6.0) * size / 2048
        run = travelled = 0.0
        kappa = 0.0
        while w > 0.4 and travelled < life:
            v = centre - p
            r = np.hypot(v[0], v[1]) / size
            if r <= r_stop or r > 0.72:
                break
            aim = np.arctan2(v[1], v[0]) + bias
            bias *= 0.985
            kappa = 0.85 * kappa + rng.normal(0, 0.012 * tort * (1 + 0.8 * thin))
            base += kappa + 0.10 * ((aim - base + np.pi) % (2 * np.pi) - np.pi)
            phase += 2 * np.pi * step / wavelen
            if int(phase / np.pi) != half:
                half = int(phase / np.pi)
                wavelen = rng.uniform(70, 190) * (0.5 + 0.5 * min(w, 5.0) / 5.0) * size / 2048
                amp = tort * rng.uniform(0.14, 0.5) * (1.0 + 0.45 * thin)
            h = base + amp * np.sin(phase)
            p = p + step * np.array([np.cos(h), np.sin(h)])
            w *= taper
            run += step
            travelled += step
            pts.append(p.copy())
            ws.append(w)
            if depth < max_depth and run > next_fork and w > 0.7:
                run = 0.0
                next_fork = rng.uniform(40, 150) * (0.45 + 0.55 * min(w, 6.0) / 6.0) * size / 2048
                turn = rng.choice([-1, 1]) * rng.uniform(0.4, 0.95)
                cw = w * rng.uniform(0.45, 0.78)
                w = (w ** 3 - cw ** 3) ** (1 / 3)                        # Murray's law
                kids.append((p.copy(), h + turn, cw, depth + 1, 0.9 * turn,
                             max(r_stop, lim + rng.uniform(0.006, 0.07)),
                             rng.uniform(70, 260) * (0.4 + 0.6 * min(cw, 3.0) / 3.0) * size / 2048, False))
                base -= 0.2 * turn
        n = len(pts)
        fill = rng.uniform(0.75, 1.0)
        tail = max(4, int(0.3 * n))
        for i in range(n - 1):
            a = fill * min(1.0, (n - 1 - i) / tail)
            if root:
                a *= min(1.0, (i + 1) / 14.0)
            seg(pts[i], pts[i + 1], 0.5 * (ws[i] + ws[i + 1]), a)
        for k in kids:
            grow(*k)

    def start(r, a, w, r_stop, life):
        p = centre + size * r * np.array([np.cos(a), -np.sin(a)])
        v = centre - p
        grow(p, np.arctan2(v[1], v[0]) + rng.normal(0, 0.25), w, 0, rng.normal(0, 0.12), r_stop, life, True)

    for i in range(count):
        if kind == "deep":
            a = (i % 4) * np.pi / 2 + rng.normal(0, 0.2)
            start(rng.uniform(0.36, 0.45), a, rng.uniform(4.5, 7.5), lim + rng.uniform(0.03, 0.08), 1e9)
            continue
        while True:
            a = rng.uniform(0, 2 * np.pi)
            dn = np.cos(a - nasal)
            if rng.random() < 0.12 + 0.88 * (np.abs(np.cos(a)) ** 3) * (0.65 + 0.35 * dn):
                break
        horiz = np.abs(np.cos(a))
        r_stop = lim + 0.004 + rng.uniform(0.0, 0.05) + 0.05 * (1 - horiz)
        if kind == "tree":
            # roots lie beyond the mapped sclera, so a trunk is already running where it comes into view
            w0 = (3.2 + 6.0 * rng.uniform() ** 1.8) * (0.6 + 0.4 * horiz)   # few wide, more narrow
            start(rng.uniform(0.47, 0.52), a, w0, r_stop, 1e9)
        else:
            start(lim + 0.05 + (0.46 - lim) * rng.uniform() ** 0.8, a, rng.uniform(1.2, 2.6), r_stop,
                  rng.uniform(90, 300) * size / 2048)
    return od


def sclera(rng, vrng, size, eye_uv, side, S, R, TH):
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

    # vessels, on their own generator so the iris does not change when they do. They are blood
    # seen through a clear membrane, so they absorb (mostly green and blue) instead of being
    # painted on: wide ones come out dark crimson, twigs a pale orange-pink. The conjunctiva
    # scatters a little, which softens every edge and leaves a faint flush beside the big ones.
    red = S["redness"]
    fade = smoothstep(lim + 0.004, lim + 0.04, R)                # vessels thin out at the limbus
    deep = gaussian_filter(draw_vessels(vrng, size, 8, eye_uv, side, "deep"), 4.0 * size / 2048)
    tree = draw_vessels(vrng, size, max(10, S["veins"] // 3), eye_uv, side, "tree")
    fine = draw_vessels(vrng, size, S["veins"], eye_uv, side, "fine")
    tau = gaussian_filter(np.maximum(tree, fine), 0.75 * size / 2048)
    tau = tau + 0.3 * gaussian_filter(tau, 5.0 * size / 2048)
    col = col * np.exp(-(tau * fade * red)[..., None] * BLOOD)
    col = col * np.exp(-(0.28 * deep * fade * red)[..., None] * np.array([0.5, 1.0, 0.7]))

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

    scl = sclera(rng, np.random.default_rng([seed, 1 if side == "L" else 2, 11]), size, E, side, S, R, TH)
    # iris -> sclera blend across the limbus (about 0.15 mm wide on the surface)
    w_iris = 1 - smoothstep(rl - 0.002, rl + 0.006, R)
    col = lerp(scl, iris, w_iris)

    # limbal ring: a wide, soft shadow from 72 % of the limbus radius, darkest at the limbus,
    # fading 0.03 UV into the sclera; its strength wanders a little around the eye
    wander = 1 + 0.08 * polar_noise(rng, (1, 1024), (0, 40))[0]
    wander = np.interp(TH / (2 * np.pi) * 1024, np.arange(1025), np.append(wander, wander[0]))
    ring = smoothstep(LIMBAL_START * rl, rl, R) * (1 - smoothstep(rl, rl + LIMBAL_FADE, R))
    gain = P["radial"]["limbal_gain"] if P.get("radial") else LIMBAL_GAIN
    col = col * (1 - (1 - gain) * np.clip(ring * wander, 0, 1))[..., None]

    # sclera: darker toward the fornix, away from the lit front
    f0, f1, fk = FORNIX
    col = col * (1 - fk * smoothstep(f0, f1, R))[..., None]

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


def sheet(imgs: list[np.ndarray], limbus: float, crop: float = 0.24, cell: int = 512,
          small_iris_px: int = 60) -> np.ndarray:
    """Top row: each iris cropped and downsized to `cell`. Bottom row: the same crop at the
    size it has in a face render (iris `small_iris_px` across), blown up with nearest
    neighbour so each render pixel is visible."""
    from PIL import Image
    top, bottom = [], []
    for img in imgs:
        s = img.shape[0]
        a, b = int((0.5 - crop) * s), int((0.5 + crop) * s)
        im = Image.fromarray(img[a:b, a:b])
        top.append(np.asarray(im.resize((cell, cell), Image.LANCZOS)))
        n = max(8, int(round((b - a) * small_iris_px / (2 * limbus * s))))
        bottom.append(np.asarray(im.resize((n, n), Image.LANCZOS).resize((cell, cell), Image.NEAREST)))
    return np.concatenate([np.concatenate(top, 1), np.concatenate(bottom, 1)], 0)


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
        tc.write_png(out / "sheet.png", sheet(left, eye_uv["L"]["limbus"]))
        print(f"[iris] sheet {(out / 'sheet.png').relative_to(REPO)}")
    else:
        out = args.out or REPO / f"outputs/tmp/m2/iris/{args.color}"
        write_set(args.color, args.seed, out, eye_uv, args.size)
        print(f"[iris] {args.color} seed {args.seed} -> {out}")


if __name__ == "__main__":
    main()
