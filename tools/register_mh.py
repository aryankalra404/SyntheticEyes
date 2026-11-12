"""Registers the MakeHuman base head to GNM, once, so skins can be baked across.

    python3 tools/register_mh.py            (numpy + scipy; no GNM package, no Blender)

1. Similarity (scale, rotation, translation) MakeHuman -> GNM from the landmark pairs in
   assets/mh_landmarks.json.
2. Fits GNM's 170 head identity coefficients to the MakeHuman head: closest points with
   agreeing normals, linear least squares, landmarks weighted high, a prior on the norm.
   The similarity is re-estimated every round.
3. Final snap: a smooth displacement field pulls each GNM skin vertex onto the MakeHuman
   surface. Lid pockets, the mouth sock and vertices whose closest point faces the wrong
   way get no pull of their own and follow their neighbours, so they cannot jump to the
   inner sheets of the MakeHuman mesh.

Writes assets/gnm/wrapped_to_mh.npz (GNM frame, metres) and prints the residual over the
face (GNM's hockey_mask group).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

import gnm_core
import mh_core

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "assets/gnm/wrapped_to_mh.npz"


def similarity(src, dst, w=None):
    """Weighted Umeyama: dst ~ s * R @ src + t."""
    w = np.ones(len(src)) if w is None else w
    w = w / w.sum()
    mu_s, mu_d = (w[:, None] * src).sum(0), (w[:, None] * dst).sum(0)
    a, b = src - mu_s, dst - mu_d
    U, S, Vt = np.linalg.svd((w[:, None] * b).T @ a)
    D = np.diag([1.0, 1.0, np.sign(np.linalg.det(U @ Vt))])
    R = U @ D @ Vt
    s = (S * np.diag(D)).sum() / (w * (a ** 2).sum(1)).sum()
    return s, R, mu_d - s * R @ mu_s


def closest_on_triangles(p, a, b, c):
    """Closest point on each triangle (a, b, c) to p; all arrays broadcast to (..., 3)."""
    ab, ac, ap = b - a, c - a, p - a
    d00, d01, d11 = (ab * ab).sum(-1), (ab * ac).sum(-1), (ac * ac).sum(-1)
    d20, d21 = (ap * ab).sum(-1), (ap * ac).sum(-1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    inside = (v >= 0) & (w >= 0) & (v + w <= 1)
    best = a + v[..., None] * ab + w[..., None] * ac
    best_d = np.where(inside, ((best - p) ** 2).sum(-1), np.inf)
    for x, y in ((a, b), (b, c), (c, a)):
        e = y - x
        t = np.clip(((p - x) * e).sum(-1) / np.maximum((e * e).sum(-1), 1e-30), 0, 1)
        q = x + t[..., None] * e
        d = ((q - p) ** 2).sum(-1)
        take = d < best_d
        best = np.where(take[..., None], q, best)
        best_d = np.where(take, d, best_d)
    return best, np.sqrt(best_d)


class Surface:
    """Triangle mesh with closest-point queries that can require agreeing normals."""

    def __init__(self, V, T, spacing):
        self.V, self.T = V, T
        P = V[T]
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        self.normals = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)
        # Sample each triangle densely enough that the nearest samples name the nearest triangles.
        edge = np.linalg.norm(P - np.roll(P, 1, axis=1), axis=2).max(1)
        pts, tri = [], []
        for k in np.unique(np.ceil(edge / spacing).astype(int)):
            sel = np.where(np.ceil(edge / spacing).astype(int) == k)[0]
            k = max(int(k), 1)
            i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1))
            m = i + j <= k
            u, v = i[m] / k, j[m] / k
            bary = np.stack([1 - u - v, u, v], 1)
            pts.append(np.einsum("sb,tbc->tsc", bary, P[sel]).reshape(-1, 3))
            tri.append(np.repeat(sel, len(bary)))
        self.sample_tri = np.concatenate(tri)
        self.tree = cKDTree(np.concatenate(pts))

    def closest(self, X, normals=None, min_dot=0.0, k=24):
        """Closest surface point per query. With normals, only triangles facing the same way count.

        Returns points, distances (inf when nothing qualifies), triangle normals.
        """
        _, idx = self.tree.query(X, k=k)
        tri = self.sample_tri[idx]                       # (n, k)
        P = self.V[self.T[tri]]                          # (n, k, 3, 3)
        q, d = closest_on_triangles(X[:, None, :], P[:, :, 0], P[:, :, 1], P[:, :, 2])
        if normals is not None:
            dot = (self.normals[tri] * normals[:, None, :]).sum(-1)
            d = np.where(dot >= min_dot, d, np.inf)
        best = d.argmin(1)
        rows = np.arange(len(X))
        return q[rows, best], d[rows, best], self.normals[tri[rows, best]]


def vertex_normals(V, T):
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    out = np.zeros_like(V)
    for k in range(3):
        np.add.at(out, T[:, k], n)
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-20)


def grow(mask, quads, rings):
    for _ in range(rings):
        mask = mask.copy()
        mask[quads[mask[quads].any(1)].ravel()] = True
    return mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=16)
    ap.add_argument("--prior", type=float, default=2e-7, help="weight on |identity|^2")
    ap.add_argument("--landmark-weight", type=float, default=60.0)
    ap.add_argument("--snap-landmark-weight", type=float, default=40.0)
    ap.add_argument("--stiffness", type=float, nargs="+", default=[3000, 1000, 300, 100, 30, 10, 3, 1])
    args = ap.parse_args()

    # numpy on Apple silicon raises spurious matmul warnings; results are checked for finiteness
    np.seterr(divide="ignore", over="ignore", invalid="ignore")
    model = gnm_core.load_model()
    groups = gnm_core.Groups(model)
    template = model["template_vertex_positions"].astype(np.float64)
    basis = model["vertex_identity_basis"][:170].astype(np.float64)        # (170, V, 3)
    quads, tris = model["quads"], model["triangles"]
    skin = groups.mask("skin")
    exterior = groups.mask("skin_exterior")
    skin_quads = quads[skin[quads].all(1)]
    skin_tris = tris[skin[tris].all(1)]
    pockets = groups.mask("eye_sockets", "mouth_sock")
    protected = grow(pockets, skin_quads, 1) | ~exterior
    ears = groups.mask("ears")
    face = groups.mask("hockey_mask") & exterior & ~protected

    lm_idx, lm_w = gnm_core.load_landmarks()
    picks = json.loads(mh_core.LANDMARKS_JSON.read_text())["landmarks"]
    ids = np.array([p["gnm"] for p in picks])
    mh_V, _, mh_F, _ = mh_core.load_head()
    mh_T = mh_core.triangulate(mh_F)
    mh_lm = np.array([(mh_V[p["verts"]] * np.array(p["weights"])[:, None]).sum(0) for p in picks])
    lm_idx, lm_w = lm_idx[ids], lm_w[ids].astype(np.float64)

    def gnm_landmarks(X):
        return (X[lm_idx] * lm_w[..., None]).sum(1)

    # 1. similarity from landmarks
    s, R, t = similarity(mh_lm, gnm_landmarks(template))
    print(f"[register] landmark similarity: scale {s:.5f}, "
          f"rms {np.sqrt(((s * mh_lm @ R.T + t - gnm_landmarks(template)) ** 2).sum(1).mean()) * 1000:.2f} mm")

    # 2. identity fit
    fit_idx = np.where(exterior & ~protected)[0]
    fit_w = np.where(ears[fit_idx], 0.3, 1.0)
    B_fit = basis[:, fit_idx, :]                                           # (170, n, 3)
    B_lm = (basis[:, lm_idx, :] * lm_w[None, :, :, None]).sum(2)           # (170, L, 3)
    c = np.zeros(170)
    X = template.copy()
    for it in range(args.rounds):
        surf = Surface(s * mh_V @ R.T + t, mh_T, spacing=0.0015)
        N = vertex_normals(X, skin_tris)
        q, d, qn = surf.closest(X[fit_idx], N[fit_idx], min_dot=0.3)
        reach = 0.03 * (0.5 ** (it / 4)) + 0.004
        ok = d < reach
        w = fit_w * ok
        # point-to-plane with a little point-to-point so the fit cannot slide freely
        A_plane = np.einsum("knc,nc->nk", B_fit, qn) * np.sqrt(w)[:, None]
        r_plane = ((q - template[fit_idx]) * qn).sum(1) * np.sqrt(w)
        A_pt = (B_fit * np.sqrt(0.1 * w)[None, :, None]).transpose(1, 2, 0).reshape(-1, 170)
        r_pt = ((q - template[fit_idx]) * np.sqrt(0.1 * w)[:, None]).ravel()
        wl = np.sqrt(args.landmark_weight * ok.sum() / len(ids))
        A_lm = wl * B_lm.transpose(1, 2, 0).reshape(-1, 170)
        r_lm = wl * (s * mh_lm @ R.T + t - gnm_landmarks(template)).ravel()
        A = np.concatenate([A_plane, A_pt, A_lm])
        r = np.concatenate([r_plane, r_pt, r_lm])
        lam = args.prior * ok.sum()
        c = np.linalg.solve(A.T @ A + lam * np.eye(170), A.T @ r)
        X = template + np.einsum("k,kvc->vc", c, basis)
        # re-estimate the similarity against the new shape
        src = np.concatenate([(q[ok] - t) @ R / s, mh_lm])
        dst = np.concatenate([X[fit_idx][ok], gnm_landmarks(X)])
        ww = np.concatenate([w[ok], np.full(len(ids), args.landmark_weight * ok.sum() / len(ids))])
        s, R, t = similarity(src, dst, ww)
        if it % 3 == 0 or it == args.rounds - 1:
            lm_err = np.linalg.norm(s * mh_lm @ R.T + t - gnm_landmarks(X), axis=1) * 1000
            print(f"[register] round {it:2d}: {ok.mean() * 100:5.1f}% matched, mean {d[ok].mean() * 1000:.2f} mm, "
                  f"landmarks {lm_err.mean():.2f} mm (max {lm_err.max():.2f}), |c| {np.linalg.norm(c):.1f}")
    fit = X.copy()
    print(f"[register] final similarity scale {s:.5f}")
    mh_in_gnm = s * mh_V @ R.T + t
    surf = Surface(mh_in_gnm, mh_T, spacing=0.0015)
    target_lm = s * mh_lm @ R.T + t

    # 3. smooth snap of the skin
    sidx = np.where(skin)[0]
    local = np.full(len(template), -1)
    local[sidx] = np.arange(len(sidx))
    n = len(sidx)
    e = np.unique(np.sort(np.concatenate([skin_quads[:, [i, (i + 1) % 4]] for i in range(4)]), 1), axis=0)
    e = local[e]
    Adj = sp.coo_matrix((np.ones(2 * len(e)), (np.concatenate([e[:, 0], e[:, 1]]), np.concatenate([e[:, 1], e[:, 0]]))),
                        shape=(n, n)).tocsr()
    Lap = sp.eye(n) - sp.diags(1.0 / np.asarray(Adj.sum(1)).ravel()) @ Adj      # uniform Laplacian
    # thin-plate energy keeps the pull of a landmark smooth; a little membrane keeps pockets tame
    smooth = sp.kron(Lap.T @ Lap + 0.05 * Lap.T @ sp.diags(np.asarray(Adj.sum(1)).ravel()) @ Lap, sp.eye(3), format="csr")
    rows = np.repeat(np.arange(len(ids)), 3)
    Lm = sp.coo_matrix((lm_w.ravel(), (rows, local[lm_idx].ravel())), shape=(len(ids), n)).tocsr()
    Lm3 = sp.kron(Lm, sp.eye(3), format="csr")
    free = ~protected[sidx]
    ear_s = ears[sidx]
    X = fit.copy()
    for it, stiff in enumerate(args.stiffness):
        N = vertex_normals(X, skin_tris)
        q, d, qn = surf.closest(X[sidx], N[sidx], min_dot=0.5)
        ok = free & (d < 0.012) & ~(ear_s & (d > 0.006))
        w = np.where(ok, np.where(ear_s, 0.5, 1.0), 0.0)
        # data: point-to-plane plus a tenth point-to-point, per vertex 3x3 block
        blocks = w[:, None, None] * (qn[:, :, None] * qn[:, None, :] + 0.1 * np.eye(3)[None])
        ii = (3 * np.arange(n)[:, None, None] + np.arange(3)[None, :, None]).repeat(3, axis=2)
        jj = (3 * np.arange(n)[:, None, None] + np.arange(3)[None, None, :]).repeat(3, axis=1)
        Wd = sp.coo_matrix((blocks.ravel(), (ii.ravel(), jj.ravel())), shape=(3 * n, 3 * n)).tocsr()
        target = np.where(ok[:, None], q, X[sidx])
        wl = args.snap_landmark_weight
        A = Wd + stiff * smooth + wl * (Lm3.T @ Lm3)
        # unknown: new positions; smoothness acts on the displacement from the identity fit
        b = Wd @ target.ravel() + stiff * (smooth @ fit[sidx].ravel()) + wl * (Lm3.T @ target_lm.ravel())
        X[sidx] = spsolve(A.tocsc(), b).reshape(-1, 3)
        _, dd, _ = surf.closest(X[np.where(face)[0]])
        lm_err = np.linalg.norm(target_lm - gnm_landmarks(X), axis=1) * 1000
        print(f"[register] snap {it}: stiffness {stiff:7.1f}, {ok.mean() * 100:5.1f}% pulled, "
              f"face mean {dd.mean() * 1000:.3f} mm, p95 {np.percentile(dd, 95) * 1000:.3f} mm, "
              f"landmarks {lm_err.mean():.2f} mm")
    assert np.isfinite(X).all()

    face_idx = np.where(face)[0]
    _, dd, _ = surf.closest(X[face_idx])
    _, d_all, _ = surf.closest(X[np.where(exterior & ~protected)[0]])
    lm_err = np.linalg.norm(target_lm - gnm_landmarks(X), axis=1) * 1000
    move = np.linalg.norm(X - fit, axis=1)[sidx] * 1000
    print(f"[register] face ({len(face_idx)} vertices): mean {dd.mean() * 1000:.3f} mm, "
          f"p95 {np.percentile(dd, 95) * 1000:.3f} mm, max {dd.max() * 1000:.2f} mm")
    print(f"[register] all exterior skin: mean {d_all.mean() * 1000:.3f} mm, p95 {np.percentile(d_all, 95) * 1000:.3f} mm")
    print(f"[register] landmarks: mean {lm_err.mean():.2f} mm, max {lm_err.max():.2f} mm; "
          f"snap moved skin by mean {move.mean():.2f} mm, max {move.max():.2f} mm")

    gnm_core.save_npz_deterministic(OUT, {
        "vertices": X.astype(np.float32),
        "fit_vertices": fit.astype(np.float32),
        "identity": c.astype(np.float32),
        "mh_scale": np.array(s), "mh_rotation": R, "mh_translation": t,
        "face_distance_mm": np.array([dd.mean() * 1000, np.percentile(dd, 95) * 1000]),
        "pulled": np.isin(np.arange(len(template)), sidx[ok]),
    })
    print(f"[register] wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
