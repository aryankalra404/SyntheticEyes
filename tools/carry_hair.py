"""Carries MakeHuman strand eyebrows to GNM as a triangle binding (M3 section 3).

Eyelashes are no longer carried: tools/lashes.py grows them on GNM's own lid margin (the five
Mindfront lash sets were tried on 13 Nov; see docs/PROGRESS.md). The per-root binding used for
them is kept below (PER_ROOT) in case a lash set is wanted again: add it to SETS.

    python3 tools/carry_hair.py            # -> assets/gnm/hair_binding.npz (git-ignored, rebuilt here)

numpy + scipy, system python3. tools/build_scene.py rebuilds the hair on whatever GNM vertices it
builds (template or any identity) and on every shape key from this binding.

Source: the Mindfront strand sets are tubes of three-vertex rings, one tube per hair. Each hair
becomes a polyline through its ring centres, with a radius per point (ring size), and is placed in
GNM's frame with the similarity from tools/register_mh.py (wrapped_to_mh.npz).

Binding: GNM's skin wrapped onto the MakeHuman head (`vertices` in wrapped_to_mh.npz) lies on the
surface the hair was modelled on. For a point P the closest point C on a wrapped skin triangle
(tile 1001) is stored as the triangle's three vertex ids and barycentric weights, and P - C in
the triangle's own frame (edge, edge x normal, normal). Rebuilding on other vertices puts C at
the same barycentric spot and turns the offset with the triangle, so hair follows lid and brow
shape keys exactly as the triangle does.
- Eyelashes: every point of a lash is bound to the triangle under its root, so a lash turns
  rigidly with the lid margin and cannot be split between the upper and lower lid.
- Eyebrows: each point is bound to its own closest triangle, so the hair hugs the skin.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gnm_core  # noqa: E402
import mh_core  # noqa: E402

REPO = mh_core.REPO
OUT = REPO / "assets/gnm/hair_binding.npz"
SETS = {
    "brows_01": "eyebrows01/eyebrows/mindfront_eyebrows_01",
    "brows_05": "eyebrows01/eyebrows/mindfront_eyebrows_05",
    "brows_08": "eyebrows01/eyebrows/mindfront_eyebrows_08",
}
PER_ROOT = {"lashes"}   # sets bound per hair root; none in SETS now
ROOT_MAX = 0.0015      # m; lashes rooted further from the wrapped skin are dropped


def strand_rings(V, F):
    """Tubes of three-vertex rings -> list of (centres (k, 3), radii (k,)) in chain order.

    Rings are consecutive vertex triplets, but not stored in chain order (the lash sets keep
    each hair's root ring at the end of the vertex list), so the order is walked through the
    faces: two rings are neighbours when a face spans both. Which end is the root is decided
    later: the end lower along the skin normal (the root ring is under the skin)."""
    ring_of = np.arange(len(V)) // 3
    nbr = {}
    for f in F:
        rs = sorted({int(ring_of[v]) for v in f})
        for a in rs:
            nbr.setdefault(a, set()).update(r for r in rs if r != a)
    seen, out = set(), []
    for start in sorted(nbr):
        if start in seen:
            continue
        comp, stack = [], [start]                     # rings of this tube
        while stack:
            r = stack.pop()
            if r in seen:
                continue
            seen.add(r)
            comp.append(r)
            stack.extend(nbr[r] - seen)
        ends = [r for r in comp if len(nbr[r]) == 1]
        if len(comp) < 3 or len(ends) != 2 or any(len(nbr[r]) > 2 for r in comp):
            continue                                   # not a simple tube
        chain, prev = [ends[0]], None
        while len(chain) < len(comp):
            nxt = [r for r in nbr[chain[-1]] if r != prev][0]
            prev = chain[-1]
            chain.append(nxt)
        rings = V[np.array(chain)[:, None] * 3 + np.arange(3)]
        c = rings.mean(1)
        out.append((c, np.linalg.norm(rings - c[:, None], axis=2).mean(1)))
    return out


def closest_on_triangles(P, A, B, C):
    """Closest point on triangles (A, B, C) to points P, row by row. Returns point, barycentrics."""
    ab, ac, ap = B - A, C - A, P - A
    n = np.cross(ab, ac)
    nn = (n * n).sum(1, keepdims=True)
    # barycentrics of the projection onto the plane
    v = (np.cross(ap, ac) * n).sum(1) / nn[:, 0]
    w = (np.cross(ab, ap) * n).sum(1) / nn[:, 0]
    u = 1 - v - w
    inside = (u >= 0) & (v >= 0) & (w >= 0)
    best = A * u[:, None] + B * v[:, None] + C * w[:, None]
    bary = np.stack([u, v, w], 1)
    if (~inside).any():
        d_best = np.full(len(P), np.inf)
        d_best[inside] = 0
        for (X, Y, ix, iy) in ((A, B, 0, 1), (B, C, 1, 2), (C, A, 2, 0)):
            e = Y - X
            t = np.clip(((P - X) * e).sum(1) / (e * e).sum(1), 0, 1)
            Q = X + t[:, None] * e
            d = ((P - Q) ** 2).sum(1)
            take = ~inside & (d < d_best)
            d_best[take] = d[take]
            best[take] = Q[take]
            b = np.zeros((len(P), 3))
            b[:, ix], b[:, iy] = 1 - t, t
            bary[take] = b[take]
    return best, bary


def frames(A, B, C):
    """Per-triangle orthonormal frame rows: (edge, normal x edge, normal)."""
    e1 = B - A
    e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
    n = np.cross(B - A, C - A)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    e2 = np.cross(n, e1)
    return np.stack([e1, e2, n], 1)          # (N, 3 axes, 3)


def bind(points, V, T, tree, k=24):
    """Closest skin triangle for each point: triangle vertex ids, barycentrics, local offset."""
    _, cand = tree.query(points, k=k)
    best_d = np.full(len(points), np.inf)
    best_t = np.zeros(len(points), dtype=np.int64)
    best_b = np.zeros((len(points), 3))
    best_c = np.zeros((len(points), 3))
    for j in range(k):
        t = cand[:, j]
        A, B, C = V[T[t, 0]], V[T[t, 1]], V[T[t, 2]]
        q, b = closest_on_triangles(points, A, B, C)
        d = np.linalg.norm(points - q, axis=1)
        take = d < best_d
        best_d[take], best_t[take], best_b[take], best_c[take] = d[take], t[take], b[take], q[take]
    tri = T[best_t]
    Fr = frames(V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]])
    off = np.einsum("nij,nj->ni", Fr, points - best_c)
    return tri, best_b, off, best_d


def rebuild(V, tri, bary, off):
    """Hair points on vertices V from a binding (same maths as tools/build_scene.py)."""
    A, B, C = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]
    base = A * bary[:, :1] + B * bary[:, 1:2] + C * bary[:, 2:3]
    return base + np.einsum("nij,ni->nj", frames(A, B, C), off)


def main():
    w = np.load(REPO / "assets/gnm/wrapped_to_mh.npz", allow_pickle=False)
    d = np.load(REPO / "assets/gnm/base.npz", allow_pickle=False)
    s, R, t = float(np.ravel(w["mh_scale"])[0]), w["mh_rotation"], w["mh_translation"]
    Vw = w["vertices"].astype(np.float64)
    T = d["triangles"][d["triangle_udim_tiles"] == 1001]
    tree = cKDTree(Vw[T].mean(1))
    base_V = mh_core.load_obj(mh_core.BASE_OBJ)[0]
    out = {}
    for name, folder in SETS.items():
        pV, _, pF, _ = mh_core.load_proxy(mh_core.MH_DIR / folder, base_V)
        hairs = strand_rings(pV, pF)
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            hairs = [(s * c @ R.T + t, r) for c, r in hairs]
        # root first: the end lower along the skin normal. Both sets model the root ring under
        # the skin; nearest-end would flip lower lashes, whose tips hang close to the cheek.
        d0 = bind(np.array([c[0] for c, _ in hairs]), Vw, T, tree)[2][:, 2]
        d1 = bind(np.array([c[-1] for c, _ in hairs]), Vw, T, tree)[2][:, 2]
        hairs = [(c, r) if a <= b else (c[::-1], r[::-1]) for (c, r), a, b in zip(hairs, d0, d1)]
        pts = np.concatenate([c for c, _ in hairs])
        assert np.isfinite(pts).all()
        rad = np.concatenate([r for _, r in hairs]) * s
        count = np.array([len(c) for c, _ in hairs], dtype=np.int32)
        start = np.concatenate([[0], np.cumsum(count)[:-1]])
        if name in PER_ROOT:
            rtri, rb, _, rd = bind(pts[start], Vw, T, tree)
            keep = rd <= ROOT_MAX
            if (~keep).any():
                # a root far from the skin is a stray in the source set; it renders as a spike
                print(f"[hair] {name}: dropped {int((~keep).sum())} hairs rooted more than "
                      f"{ROOT_MAX * 1e3:.1f} mm from the skin")
                pt_keep = np.repeat(keep, count)
                pts, rad, count, rtri, rb = pts[pt_keep], rad[pt_keep], count[keep], rtri[keep], rb[keep]
                start = np.concatenate([[0], np.cumsum(count)[:-1]])
            tri = np.repeat(rtri, count, axis=0)
            bary = np.repeat(rb, count, axis=0)
            A, B, C = Vw[tri[:, 0]], Vw[tri[:, 1]], Vw[tri[:, 2]]
            Cpt = A * bary[:, :1] + B * bary[:, 1:2] + C * bary[:, 2:3]
            off = np.einsum("nij,nj->ni", frames(A, B, C), pts - Cpt)
            dist = np.linalg.norm(pts[start] - Cpt[start], axis=1)
        else:
            tri, bary, off, dist = bind(pts, Vw, T, tree)
        err = np.abs(rebuild(Vw, tri, bary, off) - pts).max()
        print(f"[hair] {name}: {len(count)} hairs, {len(pts)} points, radius "
              f"{rad.min() * 1e3:.3f}-{rad.max() * 1e3:.3f} mm, binding distance median "
              f"{np.median(dist) * 1e3:.2f} mm max {dist.max() * 1e3:.2f} mm, rebuild error {err * 1e9:.1f} nm")
        out.update({f"{name}_tri": tri.astype(np.int32), f"{name}_bary": bary.astype(np.float64),
                    f"{name}_off": off.astype(np.float64), f"{name}_radius": rad.astype(np.float32),
                    f"{name}_count": count})
    gnm_core.save_npz_deterministic(OUT, out)
    print(f"[hair] wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
