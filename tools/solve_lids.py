"""Solve the eyelid shape keys for a GNM head (M1 section 1). Pure numpy, no bpy, no GNM package.

    python3 tools/solve_lids.py                      # assets/gnm/base.npz -> assets/gnm/lids.npz
    python3 tools/solve_lids.py --npz assets/gnm/id_male_white_9.npz --out /tmp/lids_id.npz
    python3 tools/solve_lids.py --report-only        # the three section-1 numbers, nothing written

Writes `delta_<key>` arrays, (V, 3) float32, GNM coordinates (metres, +Y up, +Z forward), for
lid_up, lid_down, lid_in, lid_out, lid_open, blink_33, blink_66, blink (.L = subject's left, +X), plus
`source_sha` (hash of the vertices solved on) and `report` (json). tools/build_scene.py reads the
file; for a head whose vertices do not match `source_sha` it calls `solve()` here instead.

The model. A lid is a sheet lying on the globe, hinged at the two corners:
  1. Transport. Every margin and pocket vertex is rotated about the eye joint's left-right axis
     by its column's angle (zero at the corners), which keeps it at its distance from the joint.
  2. Seat. Its distance from the joint is then reset so it sits on the *posed* globe (sclera
     sphere plus the cornea bulge, read from the eyeball mesh) with the clearance it has at rest.
  3. Skin. The 100 eye-region expression coefficients are fitted to those targets (far ring held
     still, |c|^2 prior), so the skin behind the margin moves the way GNM's data says lid skin
     moves. What the basis cannot reach is added as a direct correction, spread over neighbours.
     That is right for a closing lid, whose skin unfolds. A lid that retracts (upper lid going
     up, lower lid going down) is different: the fitted skin stays put and the margin slides in
     behind it, burying the lashes. There the lid's own skin is rotated with the margin instead,
     fading out over RETRACT mm of skin, so it gathers evenly toward the brow or the cheek.
  4. Drape. Skin that rides on the globe keeps its rest clearance over the posed globe (the lid
     bulges where the cornea is under it), and nothing ends up inside the globe.
  5. Reach. The result is faded out between 18 and 30 mm from the pupil, so no lid shape moves
     the brow or forehead.

Targets (pitch > 0 = eye up):
  lid_up     eye +20 deg: upper margin +0.85 x 20, lower +0.35 x 20
  lid_down   eye -25 deg: upper margin -0.90 x 25, lower -0.45 x 25
  lid_open   upper margin up until it is OPEN_MM above the pupil centre
  blink_33 / blink_66 / blink   upper margin 33 / 66 / 100 % of the way down to the lower margin,
             which rises 12 % of the gap; rig.py blends the three with tent weights
  lid_in / lid_out   eye turned SIDE_YAW deg toward the nose / the temple, pitch 0: the lid apex
             follows the cornea (columns over its new place open, the ones it left close: upper
             margin APEX_MM[0] at the peak, lower APEX_MM[1], zero at both corners) and the lid
             is seated and draped on the yawed globe, so the cornea bulge travels under it
A shape key is a straight line and the lid travels an arc, so lid_up and lid_down are the
least-squares line through the arc at FRACTIONS of the way instead of its end point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lashes as lash_gen  # noqa: E402  (pure numpy; lid_rims)

REPO = Path(__file__).resolve().parents[1]
SIDES = ("L", "R")

UP_PITCH, UP_UPPER, UP_LOWER = 20.0, 0.85, 0.35
DOWN_PITCH, DOWN_UPPER, DOWN_LOWER = -25.0, 0.90, 0.45
OPEN_MM = 4.0                 # upper margin above the pupil centre at lid_open = 1
LOWER_RISE = 0.12             # share of the gap the lower lid closes in a blink
CLOSED_GAP = 0.00008          # m left between the margins at blink = 1
FRACTIONS = (0.25, 0.5, 0.75, 1.0, 1.2)
REACH_IN, REACH_OUT = 0.018, 0.030      # m from the pupil (front view): full effect, none
CORNER_TAPER = 0.7            # lid-follow angle ~ sin(pi s)^CORNER_TAPER along the lid
BLINK_CORNER = 0.0025         # m from a corner over which the blink angle fades in
RIM_CLEAR = (-0.00015, 0.00006)   # m, clearance range a moved margin back edge is seated at
SKIN_CLEAR = 0.00003          # m, least clearance of outer skin over the globe
RIDE = (0.0010, 0.0035)       # m rest clearance: rides the globe fully below, not at all above
W_RIM, W_FRONT, W_POCKET = 1.0, 1.0, 0.25
LAMBDA_FIX, LAMBDA_PRIOR = 1.0, 0.02
SPREAD_MM = 3.0               # decay length of the direct margin correction over the skin
RETRACT = {"upper": 0.020, "lower": 0.012}   # m of lid skin that gathers when that lid retracts
SIDE_YAW = 25.0               # deg of eye yaw for lid_in / lid_out = 1
APEX_MM = (0.5, 0.3)          # upper, lower margin travel at the peak of the apex shift, mm


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def rot_x(P, centre, angle):
    """Rotate points about the GNM x axis through centre; angle (per point) > 0 lifts the front up."""
    c, s = np.cos(angle), np.sin(angle)
    q = P - centre
    return np.stack([q[:, 0], q[:, 1] * c + q[:, 2] * s, -q[:, 1] * s + q[:, 2] * c], 1) + centre


def eye_matrix(yaw, pitch):
    """Eye rotation, degrees: yaw > 0 toward +X (subject's left), pitch > 0 up; yaw applied last."""
    y, p = np.radians(yaw), np.radians(pitch)
    Ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(p), np.sin(p)], [0, -np.sin(p), np.cos(p)]])
    return Ry @ Rx


class Head:
    """The arrays of a base.npz the solve needs."""

    def __init__(self, d):
        self.V = d["vertices"].astype(np.float64)
        self.names = [str(n) for n in d["vertex_group_names"]]
        self.masks = d["vertex_group_masks"]
        self.joints = d["joint_positions"].astype(np.float64)
        self.quads = d["quads"]
        self.basis = d["expression_basis"]
        n = len(self.V)
        e = np.concatenate([self.quads[:, [i, (i + 1) % 4]] for i in range(4)])
        e = np.unique(np.sort(e, axis=1), axis=0)
        self.edges = e
        self.nbr = [[] for _ in range(n)]
        for a, b in e:
            self.nbr[a].append(int(b))
            self.nbr[b].append(int(a))

    def mask(self, name):
        return self.masks[self.names.index(name)]

    def sha(self):
        return hashlib.sha256(np.ascontiguousarray(self.V.astype(np.float32)).tobytes()).hexdigest()


class Eye:
    """One eye: its globe as a radius profile about the optical axis, its lid rows, its skin."""

    def __init__(self, H, side):
        self.H, self.side = H, side
        V = H.V
        sign = 1.0 if side == "L" else -1.0
        eye = H.mask("left_eye" if side == "L" else "right_eye")
        self.J = H.joints[2 if side == "L" else 3]
        self.pupil = V[eye & H.mask("pupils")].mean(axis=0)
        self.axis = (self.pupil - self.J) / np.linalg.norm(self.pupil - self.J)

        # Globe: the eye's outer shell is a surface of revolution about the optical axis.
        q = V[eye & H.mask("eye_exteriors")] - self.J
        r = np.linalg.norm(q, axis=1)
        th = np.arccos(np.clip(q @ self.axis / r, -1.0, 1.0))
        o = np.argsort(th)
        th, r = th[o], r[o]
        cut = np.where(np.diff(th) > np.radians(0.6))[0] + 1
        self.prof_t = np.array([a.mean() for a in np.split(th, cut)])
        self.prof_r = np.array([a.max() for a in np.split(r, cut)])

        side_ok = np.sign(V[:, 0]) == sign
        sock = H.mask("eye_sockets") & side_ok
        skin = H.mask("skin") & side_ok
        dist = np.hypot(V[:, 0] - self.pupil[0], V[:, 1] - self.pupil[1])
        self.reach = np.where(skin, smooth((REACH_OUT - dist) / (REACH_OUT - REACH_IN)), 0.0)
        self.region = np.where(self.reach > 0)[0]              # every vertex a lid shape may move
        support = (np.abs(H.basis[self.coeffs()]).max(axis=(0, 2)) > 1e-9)
        self.far = np.where(support & (self.reach == 0) & H.mask("skin"))[0]

        rims = lash_gen.lid_rims(V, H.quads, H.mask("eye_sockets"), H.mask("skin"), H.mask("eyes"), side)
        # label[v] = (lid, index into that lid's rim) for margin and pocket vertices
        self.rims = {}
        lid_of, col_of = {}, {}
        for lid in ("upper", "lower"):
            rim, _, o1 = rims[lid]
            seg = np.linalg.norm(np.diff(V[rim], axis=0), axis=1)
            arc = np.concatenate([[0.0], np.cumsum(seg)])
            self.rims[lid] = dict(rim=rim, o1=o1, arc=arc, s=arc / arc[-1])
        for lid in ("upper", "lower"):
            for i, v in enumerate(self.rims[lid]["rim"]):
                if int(v) not in lid_of:                       # corners belong to both; angle is 0 there
                    lid_of[int(v)], col_of[int(v)] = lid, i
        frontier = list(lid_of)
        while frontier:                                        # pocket: nearest rim vertex by hops
            nxt = []
            for v in frontier:
                for u in H.nbr[v]:
                    if sock[u] and u not in lid_of:
                        lid_of[u], col_of[u] = lid_of[v], col_of[v]
                        nxt.append(u)
            frontier = nxt
        self.kind = {}                                         # vertex -> "rim" | "pocket" | "front"
        for v in lid_of:
            self.kind[v] = "pocket"
        for lid in ("upper", "lower"):
            for i, (v, o) in enumerate(zip(self.rims[lid]["rim"], self.rims[lid]["o1"])):
                self.kind[int(v)] = "rim"
                if int(o) not in lid_of:
                    lid_of[int(o)], col_of[int(o)] = lid, i
                    self.kind[int(o)] = "front"
        self.con = np.array(sorted(lid_of))                    # constrained vertices
        self.con_lid = np.array([lid_of[v] == "upper" for v in self.con])
        self.con_col = np.array([col_of[v] for v in self.con])
        self.con_kind = np.array([self.kind[v] for v in self.con])
        self.con_rimv = np.array([self.rims["upper" if u else "lower"]["rim"][c]
                                  for u, c in zip(self.con_lid, self.con_col)])
        self.rim_all = np.unique(np.concatenate([self.rims["upper"]["rim"], self.rims["lower"]["rim"]]))
        con_set = set(self.con.tolist())
        self.free = np.array([v for v in self.region if v not in con_set])   # outer skin in reach
        self.outer = np.where(skin & ~sock & (np.linalg.norm(V - self.J, axis=1) < 0.035))[0]

        self.rest_clear = self.clearance(V)                    # every vertex, eye at rest

        # skin distance from the lid margin, and which rim vertex is nearest, for the free skin
        import heapq
        ok = np.zeros(len(V), dtype=bool)
        ok[self.free] = True
        dist_to = {}
        heap = []
        for lid in ("upper", "lower"):
            for i, (v, o) in enumerate(zip(self.rims[lid]["rim"], self.rims[lid]["o1"])):
                for src in (int(v), int(o)):
                    heapq.heappush(heap, (0.0, src, lid == "upper", i))
        owner = {}
        while heap:
            dd, v, is_up, i = heapq.heappop(heap)
            if v in dist_to:
                continue
            dist_to[v], owner[v] = dd, (is_up, i)
            for u in H.nbr[v]:
                if ok[u] and u not in dist_to:
                    heapq.heappush(heap, (dd + float(np.linalg.norm(V[u] - V[v])), u, is_up, i))
        self.free_arc = np.array([dist_to.get(int(v), np.inf) for v in self.free])
        self.free_up = np.array([owner.get(int(v), (True, 0))[0] for v in self.free])
        self.free_col = np.array([owner.get(int(v), (True, 0))[1] for v in self.free])

        # column through the pupil, as gnm_core.lid_margins
        col = sock & (np.abs(V[:, 0] - self.pupil[0]) < 0.002)
        self.column = []
        for half in (V[:, 1] > self.pupil[1], V[:, 1] < self.pupil[1]):
            idx = np.where(col & half)[0]
            self.column.append(idx[V[idx, 2] > V[idx, 2].max() - 0.001])

        self._spread = None

    def coeffs(self):
        return slice(0, 100) if self.side == "L" else slice(100, 200)

    # ---- globe ------------------------------------------------------------------------------

    def shell_radius(self, P, yaw=0.0, pitch=0.0):
        a = eye_matrix(yaw, pitch) @ self.axis if (yaw or pitch) else self.axis
        q = P - self.J
        r = np.linalg.norm(q, axis=1)
        t = np.arccos(np.clip(q @ a / np.maximum(r, 1e-12), -1.0, 1.0))
        return np.interp(t, self.prof_t, self.prof_r), r

    def clearance(self, P, yaw=0.0, pitch=0.0):
        """Distance from the joint minus the globe's radius in that direction; < 0 is inside."""
        rs, r = self.shell_radius(P, yaw, pitch)
        return r - rs

    def set_clearance(self, P, clear, yaw=0.0, pitch=0.0):
        rs, r = self.shell_radius(P, yaw, pitch)
        return self.J + (P - self.J) * ((rs + clear) / r)[:, None]

    # ---- targets ----------------------------------------------------------------------------

    def phi(self, P):
        return np.arctan2(P[:, 1] - self.J[1], P[:, 2] - self.J[2])

    def follow_angles(self, upper_deg, lower_deg):
        """Angle per rim vertex of each lid for a lid-follow pose: full mid-lid, zero at the corners."""
        return {lid: np.radians(deg) * np.sin(np.pi * self.rims[lid]["s"]) ** CORNER_TAPER
                for lid, deg in (("upper", upper_deg), ("lower", lower_deg))}

    def gap_angles(self):
        """Per rim vertex of each lid: angle about the joint's x axis to the other lid at the same x."""
        V = self.H.V
        up, lo = self.rims["upper"]["rim"], self.rims["lower"]["rim"]
        sign = 1.0 if self.side == "L" else -1.0
        xu, xl = sign * V[up, 0], sign * V[lo, 0]
        ou, ol = np.argsort(xu), np.argsort(xl)
        gap_up = self.phi(V[up]) - np.interp(xu, xl[ol], self.phi(V[lo])[ol])
        gap_lo = np.interp(xl, xu[ou], self.phi(V[up])[ou]) - self.phi(V[lo])
        return np.maximum(gap_up, 0.0), np.maximum(gap_lo, 0.0)

    def blink_angles(self, b):
        gap_up, gap_lo = self.gap_angles()
        out = {}
        left = CLOSED_GAP / 0.0147                              # radians kept open
        for lid, gap, share in (("upper", gap_up, -(1.0 - LOWER_RISE)), ("lower", gap_lo, LOWER_RISE)):
            rr = self.rims[lid]
            d = np.minimum(rr["arc"], rr["arc"][-1] - rr["arc"])
            out[lid] = (share * b * np.maximum(gap - (left if lid == "upper" else 0.0), 0.0)
                        * smooth(d / BLINK_CORNER))
        return out

    def apex_angles(self, nasal):
        """Per rim vertex of each lid: the lid apex follows the cornea sideways. nasal = +1 for
        the eye turned toward the nose (lid_in), -1 toward the temple (lid_out). Along each lid a
        half sine from the nasal corner to the pupil column and one from there to the temporal
        corner, opposite in sign: over the side the cornea went to, the upper margin rises and
        the lower drops; over the side it left, the reverse. Zero at both corners and under the
        pupil. Angles are margin travel over the rim's distance from the joint's x axis."""
        V = self.H.V
        sign = 1.0 if self.side == "L" else -1.0              # sign * x grows toward the temple
        xp = sign * self.pupil[0]
        out = {}
        for lid, mm, up in (("upper", APEX_MM[0], 1.0), ("lower", APEX_MM[1], -1.0)):
            rim = self.rims[lid]["rim"]
            x = sign * V[rim, 0]
            xn, xt = min(x[0], x[-1]), max(x[0], x[-1])
            w = np.where(x < xp, np.sin(np.pi * np.clip((x - xn) / (xp - xn), 0.0, 1.0)),
                         -np.sin(np.pi * np.clip((x - xp) / (xt - xp), 0.0, 1.0)))
            r = np.hypot(V[rim, 1] - self.J[1], V[rim, 2] - self.J[2])
            out[lid] = up * nasal * w * (mm / 1000.0) / r
        return out

    def side_yaw(self, nasal):
        """Eye yaw (deg, + toward +X) for an eye turned SIDE_YAW toward the nose (nasal = +1)."""
        return -nasal * SIDE_YAW if self.side == "L" else nasal * SIDE_YAW

    def open_angles(self):
        V, up = self.H.V, self.rims["upper"]["rim"]
        rows = self.column[0]
        q = V[rows].mean(axis=0) - self.J
        radius = np.hypot(q[1], q[2])
        want = OPEN_MM / 1000.0 + self.pupil[1] - self.J[1]
        deg = np.degrees(np.arcsin(min(want / radius, 1.0)) - np.arctan2(q[1], q[2]))
        return self.follow_angles(max(deg, 0.0), 0.0), deg

    def targets(self, rim_angles, pitch, yaw=0.0):
        """Target displacement of the constrained vertices: rotate, then seat on the posed globe."""
        V = self.H.V
        angles = np.where(self.con_lid, rim_angles["upper"][np.minimum(self.con_col, len(rim_angles["upper"]) - 1)],
                          rim_angles["lower"][np.minimum(self.con_col, len(rim_angles["lower"]) - 1)])
        P = rot_x(V[self.con], self.J, angles)
        moved = smooth(np.abs(angles) * 0.0147 / 0.0005)        # 0 where the vertex does not travel
        rest = self.rest_clear[self.con]
        want = rest.copy()
        rim = self.con_kind == "rim"
        want[rim] = rest[rim] + moved[rim] * (np.clip(rest[rim], *RIM_CLEAR) - rest[rim])
        front = self.con_kind == "front"
        want[front] = rest[front] + moved[front] * (np.maximum(rest[front], SKIN_CLEAR) - rest[front])
        seat = rim | front
        P[seat] = self.set_clearance(P[seat], want[seat], yaw, pitch)
        # pocket vertices follow their rim vertex's change of radius
        idx = {int(v): i for i, v in enumerate(self.con)}
        rim_i = np.array([idx[int(v)] for v in self.con_rimv])
        dr = np.linalg.norm(P - self.J, axis=1) - np.linalg.norm(V[self.con] - self.J, axis=1)
        pocket = self.con_kind == "pocket"
        u = P[pocket] - self.J
        rr = np.linalg.norm(u, axis=1, keepdims=True)
        P[pocket] = self.J + u / rr * (rr + dr[rim_i[pocket]][:, None])
        return P - V[self.con]

    # ---- skin -------------------------------------------------------------------------------

    def fit(self, target):
        """Eye-region coefficients for the constrained targets; returns (c, basis field on all V)."""
        B = self.H.basis[self.coeffs()].astype(np.float64)       # (100, V, 3)
        w = np.where(self.con_kind == "rim", W_RIM, np.where(self.con_kind == "front", W_FRONT, W_POCKET))
        A = np.concatenate([
            (B[:, self.con] * np.sqrt(w)[None, :, None]).reshape(100, -1).T,
            np.sqrt(LAMBDA_FIX) * B[:, self.far].reshape(100, -1).T,
        ])
        y = np.concatenate([(target * np.sqrt(w)[:, None]).ravel(), np.zeros(len(self.far) * 3)])
        lam = LAMBDA_PRIOR * (A * A).sum() / 100.0                # relative to the data term
        c = np.linalg.solve(A.T @ A + lam * np.eye(100), A.T @ y)
        return c, np.tensordot(c, B, axes=1)

    def spread(self, values):
        """Extend per-vertex 3-vectors on the constrained set over the free skin: harmonic with decay."""
        if self._spread is None:
            V = self.H.V
            idx = -np.ones(len(V), dtype=int)
            idx[self.free] = np.arange(len(self.free))
            cidx = -np.ones(len(V), dtype=int)
            cidx[self.con] = np.arange(len(self.con))
            n = len(self.free)
            L = np.zeros((n, n))
            R = np.zeros((n, len(self.con)))
            for a, b in self.H.edges:
                wgt = 1.0 / max(np.sum((V[a] - V[b]) ** 2), 1e-12)
                for p, q in ((a, b), (b, a)):
                    if idx[p] < 0:
                        continue
                    L[idx[p], idx[p]] += wgt
                    if idx[q] >= 0:
                        L[idx[p], idx[q]] -= wgt
                    elif cidx[q] >= 0:
                        R[idx[p], cidx[q]] += wgt
            L[np.arange(n), np.arange(n)] += 1.0 / (SPREAD_MM / 1000.0) ** 2
            self._spread = np.linalg.solve(L, R)                   # (free, con)
        return self._spread @ values

    def pose(self, rim_angles, pitch, retract=(), yaw=0.0):
        """Displacement of every vertex for one lid pose; also (coefficients, margin residual).
        retract names the lids ("upper", "lower") whose own skin is rotated with the margin.
        yaw, pitch: the posed globe the lid is seated and draped on."""
        H, V = self.H, self.H.V
        target = self.targets(rim_angles, pitch, yaw)
        c, field = self.fit(target)
        resid = target - field[self.con]
        d = np.zeros_like(V)
        fitted = field[self.free] + self.spread(resid)
        for lid in retract:
            m = (self.free_up == (lid == "upper")) & (self.free_arc < RETRACT[lid])
            f = smooth(1.0 - self.free_arc[m] / RETRACT[lid])
            v = self.free[m]
            direct = rot_x(V[v], self.J, rim_angles[lid][self.free_col[m]] * f) - V[v]
            k = smooth(f / 0.3)[:, None]                          # hand over to the fit at the far end
            fitted[m] = k * direct + (1.0 - k) * fitted[m]
        d[self.free] = fitted * self.reach[self.free][:, None]
        d[self.con] = target
        self.drape(d, pitch, yaw)
        rim = self.con_kind == "rim"
        return d, c, np.linalg.norm(resid[rim], axis=1)

    def drape(self, d, pitch, yaw=0.0):
        """Free skin that rides the globe keeps its rest clearance over the posed globe; none inside."""
        V, f = self.H.V, self.free
        rest = self.rest_clear[f]
        ride = 1.0 - smooth((rest - RIDE[0]) / (RIDE[1] - RIDE[0]))
        floor = np.minimum(rest, SKIN_CLEAR)
        P = V[f] + d[f]
        now = self.clearance(P, yaw, pitch)
        lift = ride * (rest - now) * self.reach[f]
        slot = -np.ones(len(V), dtype=int)
        slot[f] = np.arange(len(f))
        nb = [[slot[u] for u in self.H.nbr[v] if slot[u] >= 0] for v in f]
        for _ in range(2):                                         # soften, then never below the floor
            lift = np.array([0.5 * lift[i] + 0.5 * np.mean(lift[n]) if n else lift[i]
                             for i, n in enumerate(nb)])
            lift = np.maximum(lift, floor - now)
        u = P - self.J
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        d[f] += u * lift[:, None]

    # ---- keys -------------------------------------------------------------------------------

    def solve(self):
        keys, info = {}, {}
        s = self.side

        def line(make):
            """Least-squares straight line through the poses at FRACTIONS of the way."""
            acc, last = 0.0, None
            for f in FRACTIONS:
                last = make(f)
                acc = acc + f * last[0]
            return acc / sum(f * f for f in FRACTIONS), last

        d, (_, c, r) = line(lambda f: self.pose(self.follow_angles(f * UP_UPPER * UP_PITCH,
                                                                     f * UP_LOWER * UP_PITCH), f * UP_PITCH,
                                                 retract=("upper",)))
        keys[f"lid_up.{s}"], info["lid_up"] = d, r
        d, (_, c, r) = line(lambda f: self.pose(self.follow_angles(f * DOWN_UPPER * DOWN_PITCH,
                                                                     f * DOWN_LOWER * DOWN_PITCH), f * DOWN_PITCH,
                                                 retract=("lower",)))
        keys[f"lid_down.{s}"], info["lid_down"] = d, r
        for name, nasal in (("lid_in", 1.0), ("lid_out", -1.0)):
            ang, yaw = self.apex_angles(nasal), self.side_yaw(nasal)
            d, (_, c, r) = line(lambda f: self.pose({k: f * v for k, v in ang.items()}, 0.0,
                                                    yaw=f * yaw))
            keys[f"{name}.{s}"], info[name] = d, r
        ang, deg = self.open_angles()
        d, c, r = self.pose(ang, 0.0, retract=("upper",))
        keys[f"lid_open.{s}"], info["lid_open"] = d, r
        self.open_deg = deg
        for name, b in (("blink_33", 1 / 3), ("blink_66", 2 / 3), ("blink", 1.0)):
            d, c, r = self.pose(self.blink_angles(b), 0.0)
            keys[f"{name}.{s}"], info[name] = d, r
        self.fit_residual = {k: (float(v.mean() * 1000), float(v.max() * 1000)) for k, v in info.items()}
        return keys

    # ---- measuring --------------------------------------------------------------------------

    def posed(self, keys, pitch=0.0, blink=0.0, rest_open=0.0, widen=0.0, yaw=0.0):
        """Vertices with the shape-key weights wrapper/rig.py would set (tent blink keys)."""
        s = self.side
        up = min(max(pitch / 20.0, 0.0), 1.2)
        down = min(max(-pitch / 25.0, 0.0), 1.2)
        nasal = -yaw if s == "L" else yaw
        tent = lambda c: max(0.0, 1.0 - abs(blink - c) * 3.0)
        w = {f"lid_up.{s}": (up + 0.25 * widen) * (1 - blink), f"lid_down.{s}": down * (1 - blink),
             f"lid_in.{s}": min(max(nasal / SIDE_YAW, 0.0), 1.2) * (1 - blink),
             f"lid_out.{s}": min(max(-nasal / SIDE_YAW, 0.0), 1.2) * (1 - blink),
             f"lid_open.{s}": rest_open * (1 - blink), f"blink_33.{s}": tent(1 / 3),
             f"blink_66.{s}": tent(2 / 3), f"blink.{s}": tent(1.0)}
        P = self.H.V.copy()
        for k, wk in w.items():
            if wk and k in keys:
                P += wk * keys[k]
        return P

    def gap_mm(self, P):
        return float((P[self.column[0], 1].min() - P[self.column[1], 1].max()) * 1000)

    def report(self, keys, rest_open):
        V = self.H.V
        out = {"fit_residual_mm_mean_max": {k: [round(x, 3) for x in v] for k, v in self.fit_residual.items()},
               "lid_open_deg": round(float(self.open_deg), 2)}
        out["gap_mm"] = {f"{b:.2f}": round(self.gap_mm(self.posed(keys, blink=b, rest_open=rest_open)), 3)
                         for b in (0.0, 1 / 3, 2 / 3, 1.0)}
        up = self.rims["upper"]["rim"]
        mid = (self.rims["upper"]["s"] > 0.15) & (self.rims["upper"]["s"] < 0.85)
        P = self.posed(keys, blink=1.0)
        lo = self.rims["lower"]["rim"]
        sign = 1.0 if self.side == "L" else -1.0
        o = np.argsort(sign * P[lo, 0])
        low_y = np.interp(sign * P[up, 0], sign * P[lo, 0][o], P[lo, 1][o])
        out["closed_gap_along_lid_mm_max"] = round(float(((P[up, 1] - low_y)[mid]).max() * 1000), 3)

        # 2. deepest penetration over the gaze and blink grid, from the keys alone. In the scene
        # the globe guard (tools/build_scene.py) then pushes out whatever is still inside;
        # tools/check_lids.py measures that on the evaluated mesh.
        grid = [(p, b) for p in (-30, -25, -20, -12.5, -6, 0, 5, 10, 15, 20, 25)
                for b in (0.0, 1 / 6, 1 / 3, 0.5, 2 / 3, 5 / 6, 1.0)]
        pen = {"skin_yaw0": 0.0, "skin_all_yaw": 0.0, "rim_under": 0.0, "rim_over": 0.0}
        for pitch, blink in grid:
            for yaw in (-30, -15, 0, 15, 30):
                P = self.posed(keys, pitch=pitch, blink=blink, rest_open=rest_open, yaw=yaw)
                c = float(-self.clearance(P[self.outer], yaw, pitch).min())
                pen["skin_all_yaw"] = max(pen["skin_all_yaw"], c)
                if yaw == 0:
                    pen["skin_yaw0"] = max(pen["skin_yaw0"], c)
                c = self.clearance(P[self.rim_all], yaw, pitch)
                pen["rim_under"] = max(pen["rim_under"], float(-c.min()))
                pen["rim_over"] = max(pen["rim_over"], float(c.max()))
        out["keys_only_mm"] = {k: round(v * 1000, 3) for k, v in pen.items()}
        out["design_poses_skin_mm"] = round(max(
            float(-self.clearance(self.posed(keys, pitch=p, blink=b, rest_open=0.0)[self.outer], 0, p).min())
            for p, b in ((0, 0), (20, 0), (-25, 0), (0, 1 / 3), (0, 2 / 3), (0, 1.0))) * 1000, 3)
        out["template_skin_yaw30_mm"] = round(max(
            float(-self.clearance(V[self.outer], yaw, 0.0).min()) for yaw in (-30, 30)) * 1000, 3)

        # 3. upper margin above the (rotating) pupil centre
        rows = self.column[0]
        rest_h = (self.posed(keys, rest_open=rest_open)[rows, 1].mean() - self.pupil[1]) * 1000
        hs = {}
        for pitch in (-25, -20, -12, -6, 0, 5, 10, 15, 20):
            P = self.posed(keys, pitch=pitch, rest_open=rest_open)
            pup = self.J + eye_matrix(0.0, pitch) @ (self.pupil - self.J)
            hs[str(pitch)] = round(float((P[rows, 1].mean() - pup[1]) * 1000), 2)
        out["upper_margin_above_pupil_mm"] = hs
        out["upper_margin_rest_mm"] = round(float(rest_h), 2)
        out["template_upper_margin_mm"] = round(float((V[rows, 1].mean() - self.pupil[1]) * 1000), 2)
        return out


def solve(d, rest_open=1.0, verbose=True):
    """All lid keys for the head in an opened base.npz; returns ({key: (V, 3) delta}, report)."""
    H = Head(d)
    keys, report = {}, {}
    # numpy's Accelerate matmul raises spurious floating-point flags on Apple silicon
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        for side in SIDES:
            eye = Eye(H, side)
            k = eye.solve()
            keys.update(k)
            report[side] = eye.report(k, rest_open)
            if verbose:
                print(f"[lids] {side}: {json.dumps(report[side])}")
    reach = max(float(np.abs(v[H.mask('forehead_region')]).max()) for v in keys.values())
    report["forehead_max_mm"] = round(reach * 1000, 4)
    report["source_sha"] = H.sha()
    return keys, report


def save(path, keys, report):
    import gnm_core
    arrays = {f"delta_{k}": v.astype(np.float32) for k, v in keys.items()}
    arrays["source_sha"] = np.array([report["source_sha"]])
    arrays["report"] = np.array([json.dumps(report)])
    gnm_core.save_npz_deterministic(path, arrays)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npz", type=Path, default=REPO / "assets/gnm/base.npz")
    ap.add_argument("--out", type=Path, default=REPO / "assets/gnm/lids.npz")
    ap.add_argument("--rest-open", type=float, default=1.0, help="rest_lid_open used for the report")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    d = np.load(args.npz, allow_pickle=False)
    keys, report = solve(d, args.rest_open)
    print(f"[lids] forehead moves at most {report['forehead_max_mm']} mm")
    if not args.report_only:
        save(args.out, keys, report)
        print(f"[lids] wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB), keys {sorted(keys)}")


if __name__ == "__main__":
    main()
