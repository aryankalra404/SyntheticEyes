"""Eyelashes grown on GNM's own lid margin (M3 section 3). Pure numpy, no bpy.

tools/build_scene.py calls `grow(...)` on whatever vertices it builds (template or identity) and
gets the same binding arrays tools/carry_hair.py writes (triangle, barycentrics, offset in the
triangle's frame, radius per point, points per hair), so lashes follow lid shape keys and bones
like the carried brow hair does.

Why not the MakeHuman lashes: all five Mindfront sets were looked at on 13 Nov. They are modelled
as mascara clumps for MakeHuman's lid, and carried through the registration they root up to a
millimetre off GNM's lid edge, stand off the upper lid and leave a tuft at the outer corner.
Here each lash is rooted on the front edge of the lid margin of the head being built.

Lash shape (numbers from anatomy texts: about 100-150 upper lashes of 8-12 mm, 50-75 lower of
6-8 mm, base diameter about 0.1 mm; 14 Nov: longer and thicker than at first, after the
reference, where the lashes read as dark clumped strands with a pale highlight): a planar arc
that leaves the margin along the globe's outward direction and curls away from the eye, fanned
toward the outer corner, with jittered length and direction, a share of short lashes still
growing, and neighbours gathered into clumps of three to five whose tips are pulled most of the
way together; one lash in ten stays out of any clump.
"""

from __future__ import annotations

import numpy as np

LIDS = {
    #          count  s0    s1    length m  curl deg (root, tip)  fan deg (inner, outer)
    "upper": dict(n=135, s0=0.14, s1=0.97, length=0.0100, curl=(-8.0, 58.0), fan=(-4.0, 36.0)),
    "lower": dict(n=80, s0=0.22, s1=0.95, length=0.0065, curl=(-10.0, 30.0), fan=(-6.0, 30.0)),
}
POINTS = 7                 # per lash
ROOT_RADIUS = 0.000060     # m
TIP_RADIUS = 0.000006
CLUMP = (3, 5)             # lashes per clump, inclusive
CLUMP_PULL = (0.6, 0.8)    # share of the way each tip is pulled to the clump's mean tip
CLUMP_ALONE = 0.1          # share of lashes left out of any clump
ROOT_SINK = 0.00015        # m the root starts under the skin


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def lid_rims(V, quads, sock, skin, eye, side):
    """Ordered lid-margin rows of one eye, inner corner to outer corner, for both lids.

    Returns {"upper": (rim, r1, o1), "lower": (rim, r1, o1)}. rim is the socket's front edge: the
    back edge of the lid margin, which rides on the globe. r1 is the next ring into the pocket
    behind the lid. o1 is the first ring of outer skin, 0.6-0.9 mm further from the eye centre:
    the front edge of the margin, where lashes root. The band rim-o1 is the lid margin.
    """
    sign = 1.0 if side == "L" else -1.0
    sock = sock & (np.sign(V[:, 0]) == sign)
    nbr = [set() for _ in range(len(V))]
    for q in quads:
        for i in range(4):
            a, b = int(q[i]), int(q[(i + 1) % 4])
            nbr[a].add(b)
            nbr[b].add(a)
    S = np.where(sock)[0]
    rim = [v for v in S if any(not sock[u] and skin[u] and not eye[u] for u in nbr[v])]
    rim_set = set(rim)
    r1 = []
    for v in rim:
        c = [u for u in nbr[v] if sock[u] and u not in rim_set]
        r1.append(min(c, key=lambda u: np.linalg.norm(V[u] - V[v])))
    o1 = [min((u for u in nbr[v] if not sock[u] and skin[u] and not eye[u]),
              key=lambda u: np.linalg.norm(V[u] - V[v])) for v in rim]
    rim, r1, o1 = np.array(rim), np.array(r1), np.array(o1)
    inner, outer = rim[np.argmin(np.abs(V[rim, 0]))], rim[np.argmax(np.abs(V[rim, 0]))]
    a, b = V[inner], V[outer]
    line_y = a[1] + (V[rim, 0] - a[0]) / (b[0] - a[0]) * (b[1] - a[1])
    ends = np.isin(rim, [inner, outer])
    out = {}
    for name, half in (("upper", V[rim, 1] >= line_y - 1e-9), ("lower", V[rim, 1] <= line_y + 1e-9)):
        sel = half | ends
        order = np.argsort(np.abs(V[rim[sel], 0] - V[inner, 0]))
        out[name] = (rim[sel][order], r1[sel][order], o1[sel][order])
    return out


def edge_triangle(a, b, triangles, sock):
    """A skin triangle holding edge (a, b), the one on the lid's outer skin when there is a choice."""
    has = (triangles == a).any(1) & (triangles == b).any(1)
    cand = triangles[has]
    if not len(cand):
        return None
    third = np.array([[v for v in t if v != a and v != b][0] for t in cand])
    pick = np.where(~sock[third])[0]
    return cand[pick[0] if len(pick) else 0]


def crosses(P0, P1, A, B, C):
    """For segments P0->P1 (m, 3) and triangles A, B, C (k, 3): (m,) bool, True where the segment
    passes through any triangle (Moller-Trumbore, every pair at once)."""
    d = (P1 - P0)[:, None, :]
    e1, e2 = (B - A)[None], (C - A)[None]
    h = np.cross(d, e2)
    det = (e1 * h).sum(-1)
    ok = np.abs(det) > 1e-18
    inv = 1.0 / np.where(ok, det, 1.0)
    sv = P0[:, None, :] - A[None]
    u = (sv * h).sum(-1) * inv
    qv = np.cross(sv, e1)
    v = (d * qv).sum(-1) * inv
    tt = (e2 * qv).sum(-1) * inv
    return (ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (tt >= 0) & (tt <= 1)).any(1)


def frames(A, B, C):
    e1 = unit(B - A)
    n = unit(np.cross(B - A, C - A))
    return np.stack([e1, np.cross(n, e1), n], 1)


def grow(V, quads, triangles, sock, skin, eye, joint, side, seed=0):
    """Lashes of one eye on vertices V (GNM coordinates, metres).

    Returns tri (n, 3), bary (n, 3), off (n, 3), radius (n,), count (hairs,) with every point of a
    lash bound to the triangle under its root, and the lash points themselves (n, 3)."""
    rng = np.random.default_rng(seed * 2 + (side == "R"))
    rims = lid_rims(V, quads, sock, skin, eye, side)
    close = triangles[(np.linalg.norm(V[triangles].mean(1) - joint, axis=1) < 0.035)]
    lid_tris = (V[close[:, 0]], V[close[:, 1]], V[close[:, 2]])       # skin round this eye
    uncurled = unclumped = 0
    tri_o, bary_o, off_o, rad_o, cnt_o, pts_o = [], [], [], [], [], []
    for li, (lid, spec) in enumerate(LIDS.items()):
        back, _, rim = rims[lid]              # lashes root on the margin's front edge
        P, Q = V[rim], V[back]
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg)]) / seg.sum()
        n = spec["n"]
        s = spec["s0"] + (np.arange(n) + rng.uniform(0.15, 0.85, n)) / n * (spec["s1"] - spec["s0"])
        i = np.clip(np.searchsorted(cum, s) - 1, 0, len(rim) - 2)
        f = (s - cum[i]) / (cum[i + 1] - cum[i])
        root = P[i] * (1 - f[:, None]) + P[i + 1] * f[:, None]
        inward = (Q[i] * (1 - f[:, None]) + Q[i + 1] * f[:, None]) - root      # toward the globe edge
        root = root + inward * rng.uniform(-0.05, 0.3, (n, 1))                # two or three loose rows
        t = unit(P[i + 1] - P[i])
        out = root - joint
        out = unit(out - (out * t).sum(1, keepdims=True) * t)                  # away from the eye centre
        c = np.cross(t, out)
        c *= np.sign(c[:, 1:2])                                                # GNM up
        if lid == "lower":
            c = -c
        u = np.clip((s - spec["s0"]) / (spec["s1"] - spec["s0"]), 0, 1)
        # length: longest past the middle toward the outer third, short at both ends
        prof = np.interp(u, [0.0, 0.15, 0.4, 0.65, 0.85, 1.0], [0.3, 0.55, 0.9, 1.0, 0.85, 0.5])
        length = spec["length"] * prof * rng.uniform(0.78, 1.05, n)
        growing = rng.random(n) < 0.22
        length[growing] *= rng.uniform(0.45, 0.7, int(growing.sum()))
        fan = np.radians(spec["fan"][0] + (spec["fan"][1] - spec["fan"][0]) * u + rng.normal(0, 7.0, n))
        c0 = np.radians(spec["curl"][0] + rng.normal(0, 5.0, n))
        c1 = np.radians(spec["curl"][1] + rng.normal(0, 7.0, n))
        q = np.linspace(0.0, 1.0, POINTS)
        step = (length / (POINTS - 1))[:, None, None]

        def shape(c0, c1):
            ang = c0[:, None] + (c1 - c0)[:, None] * q[None, :]
            d = out[:, None, :] * np.cos(ang)[..., None] + c[:, None, :] * np.sin(ang)[..., None]
            d = unit(d + t[:, None, :] * np.tan(fan)[:, None, None])
            return root[:, None, :] - d[:, :1] * ROOT_SINK + np.cumsum(
                np.concatenate([np.zeros((n, 1, 3)), 0.5 * (d[:, 1:] + d[:, :-1]) * step], 1), 1)

        # A hooded lid overhangs its own margin; a lash curled up into the fold would come out
        # through the skin. Uncurl any lash that passes through skin (past its first segment, which
        # starts under the surface) until it runs clear under the fold.
        for _ in range(18):
            pts = shape(c0, c1)
            hit = crosses(pts[:, 1:-1].reshape(-1, 3), pts[:, 2:].reshape(-1, 3),
                          *lid_tris).reshape(n, POINTS - 2).any(1)
            if not hit.any():
                break
            c1[hit] -= np.radians(5.0)
            c0[hit] -= np.radians(1.5)
        uncurled += int((c1 < np.radians(spec["curl"][1] - 25.0)).sum())
        # clumps: runs of CLUMP neighbours whose tips are pulled together; a lash that the pull
        # would push through the lid skin keeps its own shape
        alone = rng.random(n) < CLUMP_ALONE
        g, cur, left = np.empty(n, dtype=int), -1, 0
        for k in range(n):
            if alone[k]:
                cur, left = cur + 1, 0
            elif left == 0:
                cur, left = cur + 1, int(rng.integers(CLUMP[0], CLUMP[1] + 1)) - 1
            else:
                left -= 1
            g[k] = cur
        free = pts.copy()
        for k in np.unique(g):
            m = g == k
            if m.sum() > 1:
                tip = pts[m, -1].mean(0)
                pull = rng.uniform(*CLUMP_PULL)
                pts[m] += (tip - pts[m, -1])[:, None, :] * pull * (q ** 2)[None, :, None]
        hit = crosses(pts[:, 1:-1].reshape(-1, 3), pts[:, 2:].reshape(-1, 3),
                      *lid_tris).reshape(n, POINTS - 2).any(1)
        pts[hit] = free[hit]
        unclumped += int(hit.sum())
        radius = ROOT_RADIUS + (TIP_RADIUS - ROOT_RADIUS) * q ** 1.4
        radius = radius[None, :] * rng.uniform(0.8, 1.1, (n, 1))
        for k in range(n):
            a, b = int(rim[i[k]]), int(rim[i[k] + 1])
            tri = edge_triangle(a, b, triangles, sock)
            if tri is None:                       # corner fan: any skin triangle on the nearer vertex
                near = a if f[k] < 0.5 else b
                cand = triangles[(triangles == near).any(1)]
                if not len(cand):
                    continue
                tri = cand[0]
            A, B, C = V[tri[0]], V[tri[1]], V[tri[2]]
            # barycentrics of the root's projection, clamped to the triangle
            T = np.stack([B - A, C - A], 1)
            vw = np.linalg.lstsq(T, pts[k, 0] - A, rcond=None)[0]
            bc = np.clip(np.array([1 - vw.sum(), vw[0], vw[1]]), 0, 1)
            bc /= bc.sum()
            base = A * bc[0] + B * bc[1] + C * bc[2]
            F = frames(A[None], B[None], C[None])[0]
            tri_o.append(np.repeat(tri[None], POINTS, 0))
            bary_o.append(np.repeat(bc[None], POINTS, 0))
            off_o.append((pts[k] - base) @ F.T)
            rad_o.append(radius[k])
            cnt_o.append(POINTS)
            pts_o.append(pts[k])
    if uncurled:
        print(f"[lashes] {side}: {uncurled} lashes uncurled to clear the lid fold")
    if unclumped:
        print(f"[lashes] {side}: {unclumped} lashes left out of their clump to clear the lid skin")
    return (np.concatenate(tri_o).astype(np.int32), np.concatenate(bary_o), np.concatenate(off_o),
            np.concatenate(rad_o).astype(np.float32), np.array(cnt_o, dtype=np.int32),
            np.concatenate(pts_o))
