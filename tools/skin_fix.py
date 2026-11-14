"""Corrections to a baked skin albedo (tile 1001) before the detail layer goes on.

Called by tools/build_textures.py with the set's `fix` recipe; every strength defaults to 0,
so a set without a recipe passes through unchanged. All of it is placed on the surface of the
bare GNM template (vertex groups, 3D positions), not in UV, so nothing here can open a seam.

    scalp    0..1  The MakeHuman skins paint a shaved scalp as a red-orange cap. On a bare head
                   it reads as a painted cap with an edge across the top of the forehead, behind
                   the ears and round the nape, and as soft patches where the cap is uneven.
                   The cap's broad tone is pulled toward the skin tone that surrounds it (the
                   forehead, temples and neck, carried inward over the mesh); stubble dots and
                   anything finer than about 2 mm stay.
    orbital  0..1  Evens out broad tone round the eye (a blotchy or ashy lower lid, an orbit
                   much darker and more orange than the forehead above it).
    delines  0..1  Fades thin dark painted lines round the eye (crow's feet drawn in the
                   colour). The relief belongs in the normal map; drawn in the albedo it does
                   not move with the light and reads as pen strokes.
    lips     0..1  Lip colour: redder and deeper, darker toward the line between the lips,
                   with fine vertical streaks and soft blotches so it is not one flat tone.
    flush    0..1  Redness where a real face has it and a painted skin often does not: the
                   wings of the nose, the lower lid rim and the inner eye corner.
    ears     0..1  The ear's colour where the source has none worth keeping (the head scan of
                   tex_09 does not register on the ears, so they bake as a smeared yellow-orange
                   fill). Its chroma is replaced by a smooth fill from the skin around the ear
                   (harmonic over the mesh, so it meets the head without a border); from about
                   6 mm inside the ear's root on, the fill gives way to the hue of the skin just
                   in front of the ear (median of the parotid and temple), then it is a little
                   redder and more saturated toward the rim of the helix and the lobe. The tone at
                   3 mm and coarser is the fill's (the smear carries the photograph's shadow in the
                   bowl of the ear); anything finer stays. Nothing is shaded in. Over
                   detail_maps.ear_weight (the `ears` group and a feather of about 13 mm); every
                   other texel keeps its bytes.

numpy + scipy only. Same inputs, same pixels.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import spsolve

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tex_core as tc  # noqa: E402
from detail_maps import ear_weight, fbm3, smoothstep  # noqa: E402

TILE = 1001
KEYS = ("scalp", "orbital", "delines", "lips", "flush")


def mesh_edges(d):
    q = d["quads"]
    e = np.concatenate([q[:, [0, 1]], q[:, [1, 2]], q[:, [2, 3]], q[:, [3, 0]]])
    return np.unique(np.sort(e, 1), axis=0)


def vertex_means(T, values, n_vertices):
    """Mean of a per-texel value (N, C) over the texels nearest each vertex; NaN where none."""
    v = T.tri[T.fid, T.bary.argmax(1)]
    count = np.bincount(v, minlength=n_vertices).astype(np.float64)
    out = np.stack([np.bincount(v, weights=values[:, c], minlength=n_vertices) for c in range(values.shape[1])], 1)
    out /= np.maximum(count, 1)[:, None]
    out[count == 0] = np.nan
    return out


def harmonic_fill(edges, values, free):
    """Values on `free` vertices that make each the mean of its neighbours; the rest are kept."""
    n = len(values)
    i, j = np.concatenate([edges[:, 0], edges[:, 1]]), np.concatenate([edges[:, 1], edges[:, 0]])
    A = coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n)).tocsr()
    L = (diags(np.asarray(A.sum(1)).ravel()) - A).tocsr()
    f, b = np.where(free)[0], np.where(~free)[0]
    out = values.copy()
    rhs = -L[f][:, b] @ values[b]
    Lff = L[f][:, f].tocsc()
    for c in range(values.shape[1]):
        out[f, c] = spsolve(Lff, rhs[:, c])
    return out


def region(d, names):
    return np.clip(sum(tc.group(d, n, True).astype(np.float64) for n in names), 0, 1)


def scalp_masks(d):
    """Vertices whose tone is rebuilt from their surroundings (free), and how much (weight)."""
    V = d["template_vertices"] * 1000.0
    names = tc.group_names(d)
    face = region(d, [n for n in names if n.endswith("_region")] + ["upper_lip", "lower_lip", "eye_sockets"]) > 0.5
    ears = tc.group(d, "ears")
    ext = tc.group(d, "skin_exterior")
    eye_y = float(d["joint_positions"][2:4, 1].mean() * 1000)
    ear_low = float(V[ears, 1].min())
    fore = region(d, ["forehead_region"]) > 0.5
    temple = region(d, ["left_temple_region", "right_temple_region"]) > 0.5
    # the cap: skin outside the face regions from 2 cm under the ear lobe up, the top of the
    # forehead region (the painted hairline sits inside it) and the upper temples
    cap = ext & ~face & ~ears & (V[:, 1] > ear_low - 20)
    cap |= fore & (V[:, 1] > eye_y + 36)
    cap |= temple & (V[:, 1] > eye_y - 8)
    weight = np.clip(tc.smooth_vertex_values(d, cap.astype(np.float64), 4), 0, 1)
    weight[ears] = 0
    free = (cap | ears | (weight > 0.02)) & ext
    return free, weight


def blur_log(log_img, sigma):
    return np.stack([gaussian_filter(log_img[..., c], sigma) for c in range(3)], -1)


def fix_albedo(albedo_srgb_u8: np.ndarray, fix: dict | None, seed: int = 0, d=None) -> np.ndarray:
    ears = float((fix or {}).get("ears", 0.0))
    out = fix_regions(albedo_srgb_u8, fix, seed, d)
    if ears > 0:
        out = fix_ears(out, ears, d)
    return out


def fix_regions(albedo_srgb_u8: np.ndarray, fix: dict | None, seed: int = 0, d=None) -> np.ndarray:
    fix = {k: float((fix or {}).get(k, 0.0)) for k in KEYS}
    if not any(fix.values()):
        return albedo_srgb_u8
    d = d or tc.load_base()
    size = albedo_srgb_u8.shape[0]
    T = tc.Texels(d, TILE, size)
    rng = np.random.default_rng([seed, 7])
    lo, hi = T.pos.min(0), T.pos.max(0)
    V = d["template_vertices"] * 1000.0
    lin = tc.srgb_to_linear(albedo_srgb_u8[..., :3] / 255.0).astype(np.float32)
    log = np.log(np.maximum(lin, 1e-4))
    own = None                                              # tone at about 2 mm, in UV
    ys, xs = T.ys, T.xs
    mpp = float(np.median(T.mm_per_px()))

    if fix["scalp"] > 0:
        own = blur_log(log, 2.0 / mpp)
        free, weight = scalp_masks(d)
        vcol = vertex_means(T, own[ys, xs].astype(np.float64), len(V))
        bad = np.isnan(vcol[:, 0])
        vcol[bad] = 0.0
        ref = harmonic_fill(mesh_edges(d), vcol, free | bad)
        w = T.attr(weight).astype(np.float32)[:, None] * fix["scalp"]
        log[ys, xs] += w * (T.attr(ref).astype(np.float32) - own[ys, xs])
        own = None

    orb = region(d, ["left_orbital_region", "right_orbital_region", "left_infraorbital_region",
                     "right_infraorbital_region"])
    orb_w = T.attr(np.clip(tc.smooth_vertex_values(d, orb, 3), 0, 1)).astype(np.float32)
    # the lid margin keeps its painted lash line: nothing within about 2.5 mm of the socket rim
    rim = np.clip(3 * tc.smooth_vertex_values(d, tc.group(d, "eye_sockets", True).astype(np.float64), 3), 0, 1)
    rim_w = T.attr(rim).astype(np.float32)

    if fix["orbital"] > 0:
        own = blur_log(log, 2.0 / mpp)
        wide = blur_log(log, 14.0 / mpp)
        w = (orb_w * fix["orbital"])[:, None]
        log[ys, xs] += w * (wide[ys, xs] - own[ys, xs])

    if fix["delines"] > 0:
        fine = log - blur_log(log, 0.6 / mpp)
        dark = np.minimum(fine, 0)[ys, xs]
        w = (orb_w * (1 - rim_w) * fix["delines"])[:, None]
        log[ys, xs] -= w * dark

    lips_v = np.clip(tc.smooth_vertex_values(d, region(d, ["upper_lip", "lower_lip"]), 2), 0, 1)
    lip_w = smoothstep(0.25, 0.8, T.attr(lips_v)).astype(np.float32)
    if fix["lips"] > 0:
        k = fix["lips"]
        on = lip_w > 1e-3
        pos = T.pos[on]
        # the line between the lips: the mouth sock's rim; darker and redder toward it
        sock = np.clip(4 * tc.smooth_vertex_values(d, tc.group(d, "mouth_sock", True).astype(np.float64), 3), 0, 1)
        inner = T.attr(sock)[on]
        xgrid = np.arange(-45, 45, 0.01)
        n1 = gaussian_filter(rng.standard_normal(len(xgrid)), 30)
        n1 /= n1.std()
        streak = np.interp(pos[:, 0] + 0.3 * fbm3(rng, pos, lo, hi, [1.5], [1.0]), xgrid, n1)
        blotch = fbm3(rng, pos, lo, hi, [2.0, 5.0], [0.7, 1.0])
        lum = 0.035 * streak + 0.06 * blotch - 0.30 * inner
        tint = np.array([0.0, -0.20, -0.17]) * (1.0 + 0.25 * blotch[:, None] + 0.5 * inner[:, None])
        log[ys[on], xs[on]] += (lip_w[on, None] * k * (tint + lum[:, None])).astype(np.float32)

    if fix["flush"] > 0:
        nose = tc.group(d, "nose_region")
        tip_y = float(V[nose, 1].min())
        # wings of the nose: low on the nose region and off the midline
        ala = nose & (V[:, 1] < tip_y + 16) & (np.abs(V[:, 0]) > 9)
        ala_w = np.clip(tc.smooth_vertex_values(d, ala.astype(np.float64), 3), 0, 1)
        # lower lid rim and inner corner: just outside the socket rim, below or nasal of the eye
        eye = d["joint_positions"][2:4] * 1000.0
        side = np.where(V[:, 0] > 0, 0, 1)
        dy = V[:, 1] - eye[side, 1]
        nasal = np.abs(eye[side, 0]) - np.abs(V[:, 0])
        near = np.clip(2.5 * tc.smooth_vertex_values(d, tc.group(d, "eye_sockets", True).astype(np.float64), 5), 0, 1)
        lid = near * np.clip(np.maximum(smoothstep(0.0, 4.0, -dy), smoothstep(9.0, 15.0, nasal)), 0, 1)
        lid *= region(d, ["left_orbital_region", "right_orbital_region", "nose_region"]) > 0.5
        w = T.attr(np.clip(ala_w + 0.8 * lid, 0, 1)) * (0.75 + 0.35 * fbm3(rng, T.pos, lo, hi, [2.5, 6.0], [0.6, 1.0]))
        w = (np.clip(w, 0, 1.3) * (1 - lip_w) * fix["flush"]).astype(np.float32)
        log[ys, xs] += w[:, None] * np.array([0.0, -0.13, -0.11], dtype=np.float32)

    out = albedo_srgb_u8[..., :3].copy()
    out[ys, xs] = tc.to_u8(tc.linear_to_srgb(np.exp(log[ys, xs])))
    # outside the islands: a soft continuation of the corrected borders, as the bake's own fill
    # was (a nearest-texel fill leaves streaks across the padding of the shipped file)
    pad = tc.fill_smooth(out.astype(np.float32) / 255.0, T.mask)
    out[~T.mask] = tc.to_u8(pad)[~T.mask]
    return np.ascontiguousarray(out)


EAR_RED = np.array([0.03, -0.07, -0.06], dtype=np.float32)   # log shift at full rim/lobe weight
EAR_BLUR_MM = 3.0                                              # tone scale that is replaced
EAR_INNER_MM = 6.0                                             # fill -> front hue over this much from the root
EAR_FRONT_MM = 45.0                                            # parotid and temple texels this close to the ear


def ear_masks(d):
    """Per vertex: where the ear's chroma is rebuilt (detail_maps.ear_weight), how far it is
    inside the ear (0 at the root, 1 from EAR_INNER_MM on, over the mesh) and how much redder
    it is (0..1: the helix rim, the part of the ear farthest over the mesh from where it meets
    the head, and the lobe, the lowest quarter of the ear)."""
    from scipy.sparse.csgraph import dijkstra
    V = d["template_vertices"] * 1000.0
    ears = tc.group(d, "ears")
    E = mesh_edges(d)
    cross = E[ears[E[:, 0]] != ears[E[:, 1]]]
    root = np.unique(cross[ears[cross]])
    inner = E[ears[E[:, 0]] & ears[E[:, 1]]]
    length = np.linalg.norm(V[inner[:, 0]] - V[inner[:, 1]], axis=1)
    G = coo_matrix((length, (inner[:, 0], inner[:, 1])), shape=(len(V), len(V))).tocsr()
    dist = dijkstra(G, directed=False, indices=root, min_only=True)
    red = np.zeros(len(V))
    for sign in (1.0, -1.0):
        m = ears & (np.sign(V[:, 0]) == sign)
        rim = smoothstep(0.55, 0.95, dist[m] / dist[m].max())
        y = V[m, 1]
        y0, span = y.min(), y.max() - y.min()
        lobe = 1 - smoothstep(y0 + 0.12 * span, y0 + 0.35 * span, y)
        red[m] = np.maximum(rim, 0.8 * lobe)
    red = np.clip(tc.smooth_vertex_values(d, red, 2), 0, 1) * ears
    inner = np.where(ears, smoothstep(0.0, EAR_INNER_MM, np.nan_to_num(dist, posinf=0.0)), 0.0)
    return ear_weight(d), inner, red


def fix_ears(albedo_srgb_u8: np.ndarray, k: float, d=None) -> np.ndarray:
    d = d or tc.load_base()
    T = tc.Texels(d, TILE, albedo_srgb_u8.shape[0])
    w_v, inner_v, red_v = ear_masks(d)
    tw = T.attr(w_v).astype(np.float32)
    on = tw > 0
    ys, xs = T.ys[on], T.xs[on]
    lin = tc.srgb_to_linear(albedo_srgb_u8[..., :3] / 255.0).astype(np.float32)
    log = np.log(np.maximum(lin, 1e-4))
    own = blur_log(log, EAR_BLUR_MM / float(np.median(T.mm_per_px())))
    vcol = vertex_means(T, own[T.ys, T.xs].astype(np.float64), len(w_v))
    free = w_v > 0
    edges = mesh_edges(d)
    touch = np.isin(edges, np.where(free)[0]).any(1)
    if np.isnan(vcol[edges[touch]].reshape(-1, 3)).any():
        raise RuntimeError("ear fill: a vertex next to the ear has no texels")
    vcol[np.isnan(vcol[:, 0])] = 0.0
    ref = harmonic_fill(edges, vcol, free)                  # log tone, luminance and chroma
    # the hue of the skin in front of each ear: parotid and temple texels near it, own chroma
    V = d["template_vertices"] * 1000.0
    ears = tc.group(d, "ears")
    oc = own[T.ys, T.xs]
    oc = oc - oc.mean(1, keepdims=True)
    for sign, side in ((1.0, "left"), (-1.0, "right")):
        centre = V[ears & (np.sign(V[:, 0]) == sign)].mean(0)
        front = T.attr(region(d, [f"{side}_parotid_region", f"{side}_temple_region"])) > 0.5
        front &= np.linalg.norm(T.pos - centre, axis=1) < EAR_FRONT_MM
        hue = np.median(oc[front], 0)
        m = np.sign(V[:, 0]) == sign
        ref_c = ref[m] - ref[m].mean(1, keepdims=True)
        ref[m] += inner_v[m, None] * (hue - ref_c)
    w = (tw[on] * k)[:, None]
    red = (T.attr(red_v)[on] * k).astype(np.float32)[:, None]
    new = log[ys, xs] + w * (T.attr(ref)[on].astype(np.float32) - own[ys, xs]) + red * EAR_RED
    out = albedo_srgb_u8[..., :3].copy()
    out[ys, xs] = tc.to_u8(tc.linear_to_srgb(np.exp(new)))
    return np.ascontiguousarray(out)

