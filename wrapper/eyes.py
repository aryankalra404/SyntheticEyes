"""SyntheticEyes wrapper: calibrated eye control, the 10 clockwise renders, and the three videos.

Run inside Blender on scene.blend (paths are relative to the repo root, wherever it is):

    blender -b scene.blend -P wrapper/eyes.py -- --clockwise
    blender -b scene.blend -P wrapper/eyes.py -- --input left  [--seed 0] [--quality draft]
    blender -b scene.blend -P wrapper/eyes.py -- --input generate --seed 7 --camera face
    blender -b scene.blend -P wrapper/eyes.py -- --check-directions [--render]

Or as a module from Blender's Python, with the repo root on sys.path:

    from wrapper import eyes
    eyes.move(0.5, -1.0); eyes.render("out.png"); eyes.reset()

Conventions (also in README):
- h, v in [-1, 1] are image space as the camera sees the face: h > 0 moves the pupils to
  image-right, v > 0 up. The fixation target sits on a plane 35 cm in front of the eye
  midpoint at (h * 5 cm, v * 5 cm); both eyes aim at it, so they converge slightly.
- Pupil centres are pixels in the 1024x1024 render, origin top-left, x right, y down.
- eye_rotation_L/R: world-frame rotation of each eye bone relative to rest, Euler XYZ, radians
  (Blender world: +X image-right, +Y away from the camera, +Z up). L is the subject's left eye,
  which appears on the image right.
- camera_matrix: 3x4 P = K [R | t] in the OpenCV convention (x right, y down, z forward), so
  P @ [X, Y, Z, 1] gives the pupil pixel after dividing by the third row.
"""

import argparse
import json
import math
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import bpy  # noqa: E402
from mathutils import Matrix  # noqa: E402

from wrapper.gaze import generate  # noqa: E402
from wrapper.rig import Rig  # noqa: E402

FIX_PLANE = 0.35      # m in front of the eye midpoint
FIX_RANGE = 0.05      # m at |h| or |v| = 1
CAMERAS = {"face": "cam_face", "eyes": "cam_eyes"}

_rig = None


def rig():
    global _rig
    if _rig is None:
        _rig = Rig()
    return _rig


# ---- public API -----------------------------------------------------------------------------

def static_pose():
    """Drop the Timeline animation baked into scene.blend so a static pose is what renders.

    The render re-evaluates F-curves at the current frame, which would override move().
    Only the copy in memory changes; scene.blend on disk keeps its animation.
    """
    r = rig()
    if r.arm.animation_data or r.mesh.data.shape_keys.animation_data:
        r.clear_animation()
    return r


def neutral_channels():
    return dict(gaze_yaw=0.0, gaze_pitch=0.0, gaze_dist=FIX_PLANE, head_yaw=0.0, head_pitch=0.0,
                head_roll=0.0, eye_yaw=0.0, eye_pitch=0.0, blink_L=0.0, blink_R=0.0,
                brow_L=0.0, brow_R=0.0, widen=0.0, squint=0.0, pupil=0.0)


def move(h, v):
    """Aim both eyes at (h * 5 cm, v * 5 cm) on the plane 35 cm ahead. Head still. h, v in [-1, 1]."""
    if not (-1.0 <= h <= 1.0 and -1.0 <= v <= 1.0):
        raise ValueError("h and v must be in [-1, 1]")
    x, z = h * FIX_RANGE, v * FIX_RANGE
    ch = neutral_channels()
    ch["gaze_yaw"] = math.degrees(math.atan2(x, FIX_PLANE))
    ch["gaze_pitch"] = math.degrees(math.atan2(z, math.hypot(x, FIX_PLANE)))
    ch["gaze_dist"] = math.sqrt(x * x + z * z + FIX_PLANE * FIX_PLANE)
    return static_pose().apply(ch)


def reset():
    """Eyes back to the centre of the fixation plane."""
    return move(0.0, 0.0)


def render(path, camera="face"):
    """Render a still to path (PNG) from cam_face (default) or cam_eyes."""
    scene = bpy.context.scene
    scene.camera = bpy.data.objects[CAMERAS.get(camera, camera)]
    apply_look(scene.camera)
    scene.render.filepath = str(Path(path).resolve())
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    return path


def apply_look(cam):
    """Switch lights and world to the look the camera carries (set by tools/build_scene.py).

    Whole-face cameras use the constant soft light; eye cameras a dark background and a small
    side key. Custom properties on the camera: look_lights (names, comma separated), look_env
    (HDRI strength), look_backdrop (colour the camera sees behind the head). A camera without
    them leaves the scene as it is.
    """
    if "look_lights" not in cam:
        return
    scene = bpy.context.scene
    on = set(str(cam["look_lights"]).split(","))
    for ob in scene.objects:
        if ob.type == "LIGHT":
            ob.hide_render = ob.name not in on
    nodes = scene.world.node_tree.nodes if scene.world and scene.world.use_nodes else {}
    if "env_light" in nodes:
        nodes["env_light"].inputs["Strength"].default_value = float(cam["look_env"])
    if "backdrop" in nodes:
        nodes["backdrop"].inputs["Color"].default_value = (*cam["look_backdrop"], 1.0)


# ---- camera ---------------------------------------------------------------------------------

def camera_matrices(cam):
    """K (3x3), P = K [R | t] (3x4) in OpenCV convention, and the 4x4 camera-to-world matrix."""
    scene = bpy.context.scene
    w, h = scene.render.resolution_x, scene.render.resolution_y
    cd = cam.data
    f = cd.lens / cd.sensor_width * w            # sensor_fit HORIZONTAL, square pixels
    K = Matrix(((f, 0.0, w / 2.0), (0.0, f, h / 2.0), (0.0, 0.0, 1.0)))
    cv = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))   # Blender camera axes -> OpenCV axes
    W = cam.matrix_world
    R = cv @ W.to_3x3().transposed()
    t = -(R @ W.translation)
    Rt = Matrix(([*R[0], t[0]], [*R[1], t[1]], [*R[2], t[2]]))
    P = [[sum(K[i][k] * Rt[k][j] for k in range(3)) for j in range(4)] for i in range(3)]
    return [list(r) for r in K], P, [list(r) for r in W]


def project(P, p):
    x = [sum(P[i][j] * c for j, c in enumerate((p.x, p.y, p.z, 1.0))) for i in range(3)]
    return x[0] / x[2], x[1] / x[2]


# ---- render setup ---------------------------------------------------------------------------

def setup_render(quality="final", cpu=False):
    scene = bpy.context.scene
    scene.render.resolution_x = scene.render.resolution_y = 1024
    if quality == "draft":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.resolution_percentage = 50
        scene.eevee.taa_render_samples = 32
        return "EEVEE"
    scene.render.engine = "CYCLES"
    scene.render.resolution_percentage = 100
    device = "CPU"
    if not cpu:
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "METAL"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type == "METAL"
            if any(d.type == "METAL" for d in prefs.devices):
                device = "GPU"
        except (KeyError, TypeError, ValueError):
            pass
    scene.cycles.device = device
    return f"Cycles {device}"


def use_texture(nn):
    """Load textures/tex_NN into the scene's materials, and show the brow hair that goes with it.

    scene.blend (tools/build_scene.py) has image nodes named tex_albedo, tex_normal, tex_rough on
    the skin material and tex_eye on each eye interior, on the UDIM UVs. This points them at the
    set's files; images are never packed, and paths saved in the .blend are relative.
    set.json names the set's Mindfront brow set and colour, which pick the brow hair object.
    """
    folder = REPO / "textures" / f"tex_{int(nn):02d}"
    if not folder.is_dir():
        print(f"[eyes] --texture {nn}: textures/tex_{int(nn):02d} not found, keeping the current set")
        return False

    def image(name, colour=True):
        img = bpy.data.images.load(str(folder / name), check_existing=True)
        img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        return img

    slots = {"skin": {"tex_albedo": ("skin.1001.png", True), "tex_normal": ("skin_normal.1001.png", False),
                      "tex_rough": ("skin_rough.1001.png", False)},
             "eye_interior.L": {"tex_eye": ("eye.1002.png", True)},
             "eye_interior.R": {"tex_eye": ("eye.1004.png", True)}}
    for mat_name, nodes in slots.items():
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            continue
        for node_name, (fname, colour) in nodes.items():
            node = mat.node_tree.nodes.get(node_name)
            if node is not None:
                node.image = image(fname, colour)

    meta_path = folder / "set.json"
    if meta_path.exists():
        brows = json.loads(meta_path.read_text()).get("eyebrows", {})
        tag = brows.get("source", "")[-2:]
        for ob in bpy.data.objects:
            if ob.type == "CURVES" and ob.name.startswith("brow_hair_"):
                ob.hide_render = ob.hide_viewport = ob.name[-2:] != tag
        mat = bpy.data.materials.get("brow_hair")
        if mat is not None and "color_linear" in brows:
            for node in mat.node_tree.nodes:
                if node.bl_idname == "ShaderNodeBsdfHairPrincipled":
                    node.inputs["Color"].default_value = (*brows["color_linear"], 1.0)
    print(f"[eyes] texture set textures/tex_{int(nn):02d}")
    return True


# ---- jobs -----------------------------------------------------------------------------------

def clockwise(out_dir, meta_path, camera="face"):
    scene = bpy.context.scene
    cam = bpy.data.objects[CAMERAS[camera]]
    scene.camera = cam
    K, P, W = camera_matrices(cam)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for k in range(10):
        theta = 2.0 * math.pi * k / 10.0
        h, v = math.sin(theta), math.cos(theta)
        move(h, v)
        px = rig().pupil_px(cam)
        pw = rig().pupil_world()
        for s in ("L", "R"):    # P must reproduce the projection used for the pupils
            q = project(P, pw[s])
            assert abs(q[0] - px[s][0]) < 0.05 and abs(q[1] - px[s][1]) < 0.05, (q, px[s])
        rot = rig().eye_rotations()
        path = out_dir / f"frame_{k:02d}.png"
        t0 = time.perf_counter()
        render(path, camera)
        print(f"[eyes] {path.name}: h {h:+.3f} v {v:+.3f} pupils L {px['L'][0]:.2f},{px['L'][1]:.2f} "
              f"R {px['R'][0]:.2f},{px['R'][1]:.2f} ({time.perf_counter() - t0:.1f} s)")
        records.append({
            "frame": k,
            "theta": round(theta, 6),
            "input": {"h": round(h, 6), "v": round(v, 6)},
            "eye_rotation_L": [round(a, 6) for a in rot["L"]],
            "eye_rotation_R": [round(a, 6) for a in rot["R"]],
            "pupil_center_2D_L": [round(c, 3) for c in px["L"]],
            "pupil_center_2D_R": [round(c, 3) for c in px["R"]],
            "camera_matrix": [[round(c, 6) for c in r] for r in P],
            "K": [[round(c, 6) for c in r] for r in K],
            "camera_world_matrix": [[round(c, 6) for c in r] for r in W],
            "image": f"renders/{path.name}",
        })
    reset()
    meta_path.write_text(json.dumps(records, indent=2) + "\n")
    print(f"[eyes] wrote {meta_path.relative_to(REPO)} ({len(records)} records)")


def check_directions(out_json, render_dir=None, camera="eyes"):
    """Pupil pixels for reset, left, right, up, down and reset again; optionally renders them."""
    scene = bpy.context.scene
    cam = bpy.data.objects[CAMERAS[camera]]
    scene.camera = cam
    shots = [("reset", 0, 0), ("left", -1, 0), ("right", 1, 0), ("up", 0, 1), ("down", 0, -1),
             ("reset_again", 0, 0)]
    out = {"camera": cam.name, "convention": "pixels, origin top-left, y down", "shots": {}}
    face = bpy.data.objects["cam_face"]
    for name, h, v in shots:
        move(h, v)
        out["shots"][name] = {"h": h, "v": v,
                              "pupil_px": {s: list(p) for s, p in rig().pupil_px(cam).items()},
                              "pupil_px_cam_face": {s: list(p) for s, p in rig().pupil_px(face).items()}}
        if render_dir is not None:
            render_dir.mkdir(parents=True, exist_ok=True)
            render(render_dir / f"{name}.png", camera)
    reset()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out, indent=2) + "\n")
    print(f"[eyes] wrote {out_json.relative_to(REPO)}")
    for name in ("left", "right", "up", "down"):
        a, b = out["shots"]["reset"]["pupil_px"], out["shots"][name]["pupil_px"]
        print(f"[eyes] {name:5s} shift L {b['L'][0] - a['L'][0]:+.2f},{b['L'][1] - a['L'][1]:+.2f}  "
              f"R {b['R'][0] - a['R'][0]:+.2f},{b['R'][1] - a['R'][1]:+.2f} px")


def encode_mp4(frames, fps, out):
    """Encode PNG frames to H.264 MP4 with Blender's own FFmpeg (no external tool)."""
    src = bpy.context.scene
    sc = bpy.data.scenes.new("encode")
    try:
        sc.sequence_editor_create()
        ed = sc.sequence_editor
        coll = getattr(ed, "strips", None) or ed.sequences
        strip = coll.new_image(name="frames", filepath=str(frames[0]), channel=1, frame_start=1)
        for f in frames[1:]:
            strip.elements.append(f.name)
        img = bpy.data.images.load(str(frames[0]))
        w, h = img.size
        bpy.data.images.remove(img)
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.resolution_percentage = 100
        sc.render.fps = fps
        sc.frame_start, sc.frame_end = 1, len(frames)
        sc.view_settings.view_transform = "Standard"   # frames are already display-referred
        sc.render.image_settings.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"
        sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.constant_rate_factor = "HIGH"
        sc.render.ffmpeg.gopsize = fps
        sc.render.ffmpeg.audio_codec = "NONE"
        tmp = out.parent / f".{out.stem}_encode_"
        sc.render.filepath = str(tmp)
        sc.render.use_file_extension = True
        bpy.ops.render.render(animation=True, scene=sc.name)
        made = sorted(out.parent.glob(f".{out.stem}_encode_*"))
        if not made:
            raise RuntimeError("FFmpeg output not found")
        shutil.move(str(made[-1]), str(out))
    finally:
        bpy.data.scenes.remove(sc)
        if bpy.context.window is not None:
            bpy.context.window.scene = src


def video(mode, seed, fps, camera, limit=None):
    scene = bpy.context.scene
    track = generate(mode, seed=seed)
    n = rig().bake(track, fps=fps)
    if limit:
        scene.frame_end = scene.frame_start + min(limit, n) - 1
    scene.camera = bpy.data.objects[CAMERAS[camera]]
    apply_look(scene.camera)
    frames_dir = REPO / "outputs" / "frames" / mode
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(frames_dir / "####")
    t0 = time.perf_counter()
    bpy.ops.render.render(animation=True)
    frames = sorted(frames_dir.glob("*.png"))
    sec = time.perf_counter() - t0
    print(f"[eyes] rendered {len(frames)} frames of `{mode}` seed {seed} in {sec:.0f} s "
          f"({sec / max(len(frames), 1):.2f} s/frame)")
    out = REPO / "outputs" / "videos" / f"{mode}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    encode_mp4(frames, fps, out)
    print(f"[eyes] wrote {out.relative_to(REPO)} ({len(frames) / fps:.2f} s, "
          f"saccades {len(track.meta['saccades'])}, blinks {len(track.meta['blinks'])})")


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="eyes.py", description=__doc__.split("\n\n")[0])
    job = ap.add_mutually_exclusive_group(required=True)
    job.add_argument("--input", choices=("left", "right", "generate"))
    job.add_argument("--clockwise", action="store_true", help="10 renders + metadata.json")
    job.add_argument("--check-directions", action="store_true")
    job.add_argument("--move", nargs=2, type=float, metavar=("H", "V"),
                     help="pose with move(h, v) and render one still to --out")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--quality", choices=("final", "draft"), default="final")
    ap.add_argument("--camera", choices=tuple(CAMERAS), default=None)
    ap.add_argument("--texture", type=int, default=None, help="use textures/tex_NN")
    ap.add_argument("--render", action="store_true", help="with --check-directions, also render PNGs")
    ap.add_argument("--limit", type=int, default=None, help="render only the first N video frames")
    ap.add_argument("--out", type=Path, default=None, help="output PNG for --move")
    ap.add_argument("--cpu", action="store_true")
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    engine = setup_render(args.quality, args.cpu)
    if args.texture is not None:
        use_texture(args.texture)
    print(f"[eyes] Blender {bpy.app.version_string}, {engine}, lid shapes "
          f"{rig().arm.get('lid_shapes', '?')}")
    if args.clockwise:
        clockwise(REPO / "renders", REPO / "metadata.json", args.camera or "face")
    elif args.check_directions:
        check_directions(REPO / "outputs" / "direction_check.json",
                         REPO / "outputs" / "direction_check" if args.render else None,
                         args.camera or "eyes")
    elif args.move:
        move(*args.move)
        render(args.out or REPO / "outputs" / "move.png", args.camera or "face")
    else:
        video(args.input, args.seed, args.fps, args.camera or "eyes", args.limit)


if __name__ == "__main__" and "--" in sys.argv:
    main(sys.argv[sys.argv.index("--") + 1:])
