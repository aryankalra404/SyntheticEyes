"""Render the M1 look-check strips from scene.blend through wrapper/rig.py.

    $BLENDER -b scene.blend -P tools/rig_strips.py -- [--out outputs/tmp/m1] [--camera eyes]
        [--only yaw_-30 yaw_+30 blink_0.66]

Writes, from cam_eyes by default:
    pitch_<deg>.png   lid follow at eye pitch -25, -12, 0, +10, +20 (gaze far away, head still)
    yaw_<deg>.png     eye yaw -30 and +30, to see the cornea under the lids
    blink_<b>.png     blink 0, 0.33, 0.66, 1.0 on both eyes
    brow.png, squint.png, widen.png
and prints the posed shape-key values for each shot.
"""

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import bpy  # noqa: E402

from wrapper import eyes  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "outputs/tmp/m1")
    ap.add_argument("--camera", default="eyes")
    ap.add_argument("--quality", default="final")
    ap.add_argument("--only", nargs="+", default=None, help="render only these shots (names as below)")
    args = ap.parse_args(argv)
    eyes.setup_render(args.quality)
    args.out.mkdir(parents=True, exist_ok=True)
    rig = eyes.static_pose()

    def shot(name, **ch):
        if args.only and name not in args.only:
            return
        c = eyes.neutral_channels()
        c["gaze_dist"] = 1.6
        c.update(ch)
        st = rig.apply(c)
        vals = {k: round(v, 3) for k, v in st["shape"].items() if abs(v) > 1e-3}
        print(f"[strips] {name}: eye pitch L {st['eye_pitch']['L']:+.1f}, shapes {vals}")
        eyes.render(args.out / f"{name}.png", args.camera)

    for p in (-25, -12, 0, 10, 20):
        shot(f"pitch_{p:+d}", gaze_pitch=float(p))
    for y in (-30, 30):
        shot(f"yaw_{y:+d}", gaze_yaw=float(y))
    for b in (0.0, 0.33, 0.66, 1.0):
        shot(f"blink_{b:.2f}", blink_L=b, blink_R=b)
    shot("brow", brow_L=1.0, brow_R=1.0)
    shot("squint", squint=1.0)
    shot("widen", widen=1.0)
    eyes.reset()


main()
