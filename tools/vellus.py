"""Fine facial hair (vellus, "peach fuzz") grown on GNM's face skin. Pure numpy, no bpy.

tools/build_scene.py calls `grow(...)` on whatever vertices it builds (template or identity) and
gets the same binding arrays tools/lashes.py returns (triangle, barycentrics, offset in the
triangle's frame, radius per point, points per hair), so the fuzz follows shape keys and bones
like the lashes and the carried brow hair do.

What it is for: under the hard raking key of the `eye` look, bare CG skin ends in a clean edge
against the black. Real skin has a fuzz of short, thin, nearly colourless hairs that the light
catches from behind, on the silhouette of the temple, cheek and nose and across the lit cheek.

Numbers (dermatology texts: vellus hair is under 2 mm long and under 30 um thick, a few hundred
per square centimetre on the face; kept sparser and with a share of longer hairs, which is what
reads at 1024 px): about 30 hairs per cm2 on the cheeks and temples, fewer on the nose, forehead
and lids, none on the lips, the lid margins or inside the brows; 1.0 to 3.5 mm long (0.6 to
2.4 until 14 Nov; longer reads as fuzz on the silhouette in the eye close-up); 9 um radius
at the root, 3 um at the tip. Each hair leaves the skin at 20 to 50 degrees, leaning down and
outward (toward the ear) with a wide scatter, and curves back a little toward the skin.
"""

from __future__ import annotations

import numpy as np

DENSITY = 30.0e4            # hairs per m2 where the weight is 1
POINTS = 4                  # per hair
LENGTH = (0.0010, 0.0035)   # m
ROOT_RADIUS = 0.000009      # m
TIP_RADIUS = 0.000003
MARGIN_CLEAR = 0.005        # m around the lid margins left bare (the lashes own that strip)
# weight per region; a triangle takes the mean of its three vertices
REGIONS = {
    "hockey_mask": 1.0,     # the front of the face: the base everything else scales
    "nose_region": 0.6, "forehead_region": 0.6, "left_orbital_region": 0.5, "right_orbital_region": 0.5,
    "upper_lip_region": 0.8, "lower_lip_region": 0.5, "chin_region": 0.6,
    "left_brow_region": 0.0, "right_brow_region": 0.0, "upper_lip": 0.0, "lower_lip": 0.0,
    "eye_sockets": 0.0, "mouth_sock": 0.0,
}


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def frames(A, B, C):
    """Per-triangle orthonormal frame rows (edge, normal x edge, normal); as tools/lashes.py."""
    e1 = unit(B - A)
    n = unit(np.cross(B - A, C - A))
    return np.stack([e1, np.cross(n, e1), n], 1)


def weights(V, names, masks, rims):
    """Per-vertex density weight from the region masks; zero within MARGIN_CLEAR of a lid margin."""
    w = np.zeros(len(V))
    base = masks[names.index("hockey_mask")]
    w[base] = REGIONS["hockey_mask"]
    for name, k in REGIONS.items():
        if name != "hockey_mask" and name in names:
            m = masks[names.index(name)] & base
            w[m] = np.minimum(w[m], k) if k < 1.0 else w[m]
    if len(rims):
        d = np.linalg.norm(V[:, None, :] - V[rims][None], axis=2).min(1)
        w[d < MARGIN_CLEAR] = 0.0
    return w


def grow(V, triangles, names, masks, rims=(), seed=0):
    """Vellus for the whole face on vertices V (GNM coordinates: +Y up, +Z forward, metres).

    triangles: the skin triangles (n, 3). names, masks: GNM's vertex groups. rims: vertex indices
    of the lid margins of both eyes (tools/lashes.py lid_rims), kept bare.
    Returns tri (n, 3), bary (n, 3), off (n, 3), radius (n,), count (hairs,) with every point of a
    hair bound to the triangle under its root, the hair points themselves (n, 3), and for each
    hair the row of `triangles` it grows on (hairs,), for looking up the skin's UV there."""
    rng = np.random.default_rng([seed, 7])
    w = weights(V, list(names), masks, np.asarray(rims, dtype=int))
    T = triangles[(w[triangles] > 0).all(1)]
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(B - A, C - A), axis=1)
    expect = area * w[T].mean(1) * DENSITY
    n = int(rng.poisson(expect.sum()))
    pick = rng.choice(len(T), size=n, p=expect / expect.sum())
    pick.sort()                                   # hairs in triangle order: stable and cache-friendly
    r1, r2 = np.sqrt(rng.random(n)), rng.random(n)
    bary = np.stack([1.0 - r1, r1 * (1.0 - r2), r1 * r2], 1)
    A, B, C = A[pick], B[pick], C[pick]
    root = A * bary[:, :1] + B * bary[:, 1:2] + C * bary[:, 2:3]
    F = frames(A, B, C)
    normal = F[:, 2] * np.sign((F[:, 2] * (root - V.mean(0))).sum(1, keepdims=True))   # outward

    # growth direction on the skin: down and out toward the ear, scattered through +-40 degrees
    lean = np.stack([0.8 * np.sign(root[:, 0]), -np.ones(n), np.zeros(n)], 1)
    lean = unit(lean - (lean * normal).sum(1, keepdims=True) * normal + 1e-9)
    side = np.cross(normal, lean)
    turn = rng.normal(0.0, np.radians(40.0), n)[:, None]
    along = lean * np.cos(turn) + side * np.sin(turn)

    length = rng.uniform(*LENGTH, n) * rng.uniform(0.6, 1.0, n)
    lift0 = np.radians(rng.uniform(20.0, 50.0, n))            # angle off the skin at the root
    lift1 = lift0 * rng.uniform(0.2, 0.7, n)                  # and at the tip: it curves back down
    q = np.linspace(0.0, 1.0, POINTS)
    ang = lift0[:, None] + (lift1 - lift0)[:, None] * q[None, :]
    d = along[:, None, :] * np.cos(ang)[..., None] + normal[:, None, :] * np.sin(ang)[..., None]
    step = (length / (POINTS - 1))[:, None, None]
    pts = root[:, None, :] + np.cumsum(
        np.concatenate([np.zeros((n, 1, 3)), 0.5 * (d[:, 1:] + d[:, :-1]) * step], 1), 1)
    pts[:, 0] -= normal * 0.00003                             # the root starts just under the skin

    radius = (ROOT_RADIUS + (TIP_RADIUS - ROOT_RADIUS) * q)[None, :] * rng.uniform(0.7, 1.2, (n, 1))
    off = np.einsum("nij,npj->npi", F, pts - root[:, None, :])
    return (np.repeat(T[pick], POINTS, 0).astype(np.int32), np.repeat(bary, POINTS, 0),
            off.reshape(-1, 3), radius.reshape(-1).astype(np.float32),
            np.full(n, POINTS, dtype=np.int32), pts.reshape(-1, 3),
            np.where((w[triangles] > 0).all(1))[0][pick])
