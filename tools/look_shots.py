"""The two fixed M3 test shots, and the per-set stills (M3 sections 1 and 6). Blender, headless.

    $BLENDER -b scene.blend -P tools/look_shots.py -- [--texture 01]
        -> outputs/tmp/m3/current/{face,eye}_{centre,side20}.png; the run before is moved to
           outputs/tmp/m3/previous/ and outputs/tmp/m3/pairs/ shows previous | current
    $BLENDER -b scene.blend -P tools/look_shots.py -- --blink
        -> outputs/tmp/m3/blink/eye_blink_{000,050,100}.png, lashes and tear line through a blink
    $BLENDER -b <identity scene>.blend -P tools/look_shots.py -- --texture 03 --still
        -> outputs/stills/tex_03.png (whole face) and outputs/stills/eye/tex_03_eye.png
           (tools/render_stills.py runs this for every set on its paired identity)

Shots come from the scene's cameras (tools/build_scene.py), both in the `eye` look (one hard
raking light on black): cam_test_face, mid forehead to chin, straight on, the bare scalp out of
frame; cam_test_eye, the subject's left eye in the videos' eye framing (from the nose side, the
temple against black).
Gaze: centre is the fixation point 35 cm ahead (as eyes.reset()); side20 turns both eyes 20 deg
toward image right, head still. Lids follow the gaze through rig.py as in the videos.
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from wrapper import eyes  # noqa: E402

GAZES = {"centre": 0.0, "side20": 20.0}
SHOTS = {"face": "cam_test_face", "eye": "cam_test_eye"}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--texture", type=int, default=None, help="textures/tex_NN (default: as saved)")
    ap.add_argument("--out", type=Path, default=REPO / "outputs/tmp/m3")
    ap.add_argument("--still", action="store_true", help="per-set stills into outputs/stills/")
    ap.add_argument("--blink", action="store_true", help="eye shot at blink 0, 0.5, 1.0")
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--cpu", action="store_true")
    return ap.parse_args(argv)


def pose(yaw, blink=0.0):
    ch = eyes.neutral_channels()
    ch["gaze_yaw"] = yaw
    ch["blink_L"] = ch["blink_R"] = blink
    eyes.static_pose().apply(ch)


def render(cam, path):
    t0 = time.perf_counter()
    eyes.render(path, cam)
    dt = time.perf_counter() - t0
    print(f"[look] {Path(path).relative_to(REPO)} ({dt:.1f} s)")
    return dt


def pair_sheet(prev, cur, out):
    """previous | current side by side, half size, for each shot present in both runs."""
    out.mkdir(parents=True, exist_ok=True)
    for p in sorted(cur.glob("*.png")):
        q = prev / p.name
        if not q.exists():
            continue
        a, b = bpy.data.images.load(str(q)), bpy.data.images.load(str(p))
        w, h = a.size
        pa = np.array(a.pixels[:], dtype=np.float32).reshape(h, w, 4)
        pb = np.array(b.pixels[:], dtype=np.float32).reshape(h, w, 4)
        both = np.concatenate([pa, pb], axis=1)[::2, ::2]
        img = bpy.data.images.new(f"pair_{p.stem}", both.shape[1], both.shape[0], alpha=False)
        img.pixels.foreach_set(both.ravel())
        img.filepath_raw = str(out / p.name)
        img.file_format = "PNG"
        img.save()
        for i in (a, b, img):
            bpy.data.images.remove(i)


def main():
    args = parse_args()
    args.out = args.out.resolve()
    engine = eyes.setup_render("final", args.cpu)
    scene = bpy.context.scene
    if args.samples:
        scene.cycles.samples = args.samples
    if args.texture is not None:
        eyes.use_texture(args.texture)
    imgs = sorted({n.image.filepath for m in bpy.data.materials if m.use_nodes
                   for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})
    print(f"[look] {engine}, {scene.cycles.samples} spp, images: {imgs}")

    if args.still:
        nn = f"{args.texture:02d}" if args.texture is not None else "xx"
        pose(0.0)
        render("cam_test_face", REPO / f"outputs/stills/tex_{nn}.png")
        render("cam_test_eye", REPO / f"outputs/stills/eye/tex_{nn}_eye.png")
        return

    if args.blink:
        for b in (0.0, 0.5, 1.0):
            pose(0.0, b)
            render("cam_test_eye", args.out / "blink" / f"eye_blink_{int(b * 100):03d}.png")
        return

    cur, prev = args.out / "current", args.out / "previous"
    if cur.exists():
        if prev.exists():
            shutil.rmtree(prev)
        cur.rename(prev)
    cur.mkdir(parents=True)
    times = []
    for gname, yaw in GAZES.items():
        pose(yaw)
        for sname, cam in SHOTS.items():
            times.append(render(cam, cur / f"{sname}_{gname}.png"))
    print(f"[look] {np.mean(times):.1f} s per 1024² frame")
    if prev.exists():
        pair_sheet(prev, cur, args.out / "pairs")


main()
