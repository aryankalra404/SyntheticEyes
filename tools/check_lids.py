"""Measure the solved lids on the evaluated mesh in scene.blend (M1 section 1, number 2).

    $BLENDER -b scene.blend -P tools/check_lids.py

Poses the rig through wrapper/rig.py over eye pitch -30..+25, yaw -30..+30 and blink 0..1,
reads the evaluated head (shape keys, bones and the globe guard) and reports, per eye, the
deepest the lid skin sits inside the posed globe, how far the margin's back edge is under
or over it, and the deepest any lash point past its root (the evaluated lash carrier: shape
keys, bones and the globe guard; the root starts under the margin skin) sits inside the globe. Writes outputs/lid_check.json.
"""

import json
import sys
from pathlib import Path

import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
import lashes as lash_gen  # noqa: E402
import solve_lids as S  # noqa: E402
from wrapper import eyes  # noqa: E402

PITCH = (-30, -25, -20, -12.5, -6, 0, 5, 10, 15, 20, 25)
YAW = (-30, -15, 0, 15, 30)
BLINK = (0.0, 1 / 6, 1 / 3, 0.5, 2 / 3, 5 / 6, 1.0)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    npz = Path(argv[0]) if argv else REPO / "assets/gnm/base.npz"
    H = S.Head(np.load(npz, allow_pickle=False))
    E = {s: S.Eye(H, s) for s in S.SIDES}
    rig = eyes.static_pose()

    lash = bpy.data.objects.get("lashes_carrier")

    def verts(ob=None):
        ev = (ob or rig.mesh).evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
        co = co.reshape(-1, 3).astype(np.float64)
        return np.stack([co[:, 0], co[:, 2], -co[:, 1]], axis=1)      # Blender -> GNM

    worst = {s: {"skin_inside": [0.0, None], "rim_under": [0.0, None], "rim_over": [0.0, None],
                 "lash_inside": [0.0, None]} for s in S.SIDES}
    if lash is not None:
        L0 = verts(lash)
        root = np.zeros(len(L0), dtype=bool)
        root[::lash_gen.POINTS] = True          # roots start under the margin skin by design
        near = {s: np.where((np.linalg.norm(L0 - e.J, axis=1) < 0.03) & ~root)[0] for s, e in E.items()}
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        for pitch in PITCH:
            for yaw in YAW:
                for blink in BLINK:
                    ch = eyes.neutral_channels()
                    ch.update(gaze_yaw=yaw, gaze_pitch=pitch, gaze_dist=50.0, blink_L=blink, blink_R=blink)
                    rig.apply(ch)
                    P = verts()
                    LP = verts(lash) if lash is not None else None
                    tag = [pitch, yaw, round(blink, 2)]
                    for s, e in E.items():
                        w = worst[s]
                        c = e.clearance(P[e.outer], yaw, pitch)
                        if -c.min() > w["skin_inside"][0]:
                            w["skin_inside"] = [float(-c.min()), tag]
                        c = e.clearance(P[e.rim_all], yaw, pitch)
                        if -c.min() > w["rim_under"][0]:
                            w["rim_under"] = [float(-c.min()), tag]
                        if c.max() > w["rim_over"][0]:
                            w["rim_over"] = [float(c.max()), tag]
                        if LP is not None:
                            c = e.clearance(LP[near[s]], yaw, pitch)
                            if -c.min() > w["lash_inside"][0]:
                                w["lash_inside"] = [float(-c.min()), tag]
    out = {s: {k: {"mm": round(v[0] * 1000, 3), "pitch_yaw_blink": v[1]} for k, v in w.items()}
           for s, w in worst.items()}
    out["poses"] = len(PITCH) * len(YAW) * len(BLINK)
    out["lid_shapes"] = str(rig.arm.get("lid_shapes", "?"))
    path = REPO / "outputs/lid_check.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n")
    for s in S.SIDES:
        print(f"[check_lids] {s}: {json.dumps(out[s])}")
    eyes.reset()


main()
