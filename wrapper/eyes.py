"""SyntheticEyes wrapper: calibrated eye control, the 10 clockwise renders, and the three videos.

Run inside Blender on scene.blend (paths are relative to the repo root, wherever it is):

    blender -b scene.blend -P wrapper/eyes.py -- --clockwise
    blender -b scene.blend -P wrapper/eyes.py -- --input left  [--seed 0] [--quality draft]
    blender -b scene.blend -P wrapper/eyes.py -- --input generate --seed 7 --camera face
    blender -b scene.blend -P wrapper/eyes.py -- --input right --samples 64 --limit 10
    blender -b scene.blend -P wrapper/eyes.py -- --input left --samples 64 --frames 40 110 240
    blender -b scene.blend -P wrapper/eyes.py -- --check-directions [--render]

Videos are 1024x1024 at 30 fps, filmed by default with one fixed camera, cam_video (--camera
face: forehead to chin, the `eye` look), so the motion is judged against a frame that holds
still. --camera eyes (cam_eyes) is the other fixed camera. --camera move films with cam_move,
which holds a framing, glides to the next inside a fixation and holds again
(wrapper/camera_move.py): left and right go both eyes, face, one eye; generate goes one eye,
both eyes, face. Watched at playback speed the glides read as zooming for no reason, so it is
no longer the default.

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
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from wrapper import camera_move  # noqa: E402
from wrapper.device import pick_gpu  # noqa: E402
from wrapper.gaze import generate  # noqa: E402
from wrapper.rig import Rig  # noqa: E402

FIX_PLANE = 0.35      # m in front of the eye midpoint
FIX_RANGE = 0.05      # m at |h| or |v| = 1
CAMERAS = {"face": "cam_face", "eyes": "cam_eyes"}
VIDEO_CAMERAS = {"face": "cam_video", "eyes": "cam_eyes",       # face: locked off, forehead to chin
                 "move": "cam_move"}                             # the glide between framings
# cam_move's framings (tools/build_scene.py), named as in wrapper/camera_move.py
MOVE_FRAMINGS = {"eye": "cam_move_eye", "eyes": "cam_move_eyes", "face": "cam_video"}
VIDEO_SIZE = 1024
BULGE = 0.40            # a pulling-back glide backs out this much past its end distance (_blend)

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

    cam_face (the 10 clockwise renders) uses the constant soft light; the video and still
    cameras the `eye` look, one hard raking light on black. Custom properties on the camera:
    look_lights (names, comma separated: lights, and props such as the flag that shades the
    nose, which carry `look_prop`), look_env (HDRI strength), look_backdrop (colour the camera
    sees behind the head), look_view (the AgX look: "AgX - Medium High Contrast" for `eye`,
    "None" for `face`). A camera without them leaves the scene as it is.
    """
    if "look_lights" not in cam:
        return
    scene = bpy.context.scene
    on = set(str(cam["look_lights"]).split(","))
    for ob in scene.objects:
        if ob.type == "LIGHT" or ob.get("look_prop"):
            ob.hide_render = ob.name not in on
    nodes = scene.world.node_tree.nodes if scene.world and scene.world.use_nodes else {}
    if "env_light" in nodes:
        nodes["env_light"].inputs["Strength"].default_value = float(cam["look_env"])
    if "backdrop" in nodes:
        nodes["backdrop"].inputs["Color"].default_value = (*cam["look_backdrop"], 1.0)
    scene.view_settings.look = str(cam.get("look_view", "None"))


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

def draft_materials():
    """EEVEE shows the refracting cornea shell and the tear line as mirrors, hiding the iris. For
    drafts only (in memory, never saved) they become Fresnel gloss over plain transparency, and
    hair renders as flat strips instead of thick strands. Final renders are untouched."""
    for mat in bpy.data.materials:
        if not mat.use_nodes or not (mat.name.startswith("cornea") or mat.name == "tear_line"):
            continue
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        clear = nt.nodes.new("ShaderNodeBsdfTransparent")
        gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
        gloss.inputs["Roughness"].default_value = 0.02
        fresnel = nt.nodes.new("ShaderNodeFresnel")
        fresnel.inputs["IOR"].default_value = 1.376
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(fresnel.outputs[0], mix.inputs[0])
        nt.links.new(clear.outputs[0], mix.inputs[1])
        nt.links.new(gloss.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        mat.surface_render_method = "BLENDED"
    bpy.context.scene.render.hair_type = "STRIP"


def setup_render(quality="final", cpu=False, samples=None):
    """Engine, resolution and samples. samples overrides the draft 32 / the scene's Cycles count."""
    scene = bpy.context.scene
    scene.render.resolution_x = scene.render.resolution_y = 1024
    if quality == "draft":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.resolution_percentage = 50
        scene.eevee.taa_render_samples = samples or 32
        draft_materials()
        return f"EEVEE {scene.eevee.taa_render_samples} spp"
    scene.render.engine = "CYCLES"
    scene.render.resolution_percentage = 100
    if quality == "preview":            # the final look at 768 px and 32 samples, about a quarter of the time
        scene.render.resolution_percentage = 75
        scene.cycles.samples = 32
    if samples:
        scene.cycles.samples = samples
    backend = None                      # OPTIX, CUDA, HIP, ONEAPI or METAL; None renders on the CPU
    if not cpu:
        try:
            backend = pick_gpu(bpy.context.preferences.addons["cycles"].preferences)
        except KeyError:
            pass
    scene.cycles.device = "GPU" if backend else "CPU"
    return f"Cycles {backend or 'CPU'} {scene.cycles.samples} spp"


def use_texture(nn):
    """Load textures/tex_NN into the scene's materials, and show the brow hair that goes with it.

    scene.blend (tools/build_scene.py) has image nodes named tex_albedo, tex_normal, tex_rough on
    the skin material and tex_eye on each eye interior, on the UDIM UVs. This points them at the
    set's files; images are never packed, and paths saved in the .blend are relative.
    The brows grown on the set the scene was built with (`brows_grown`, tools/brows.py) show only
    for that set (`brow_set`); for any other set, set.json names its carried Mindfront brow set and
    colour, which pick the brow hair object.
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
             "vellus_hair": {"tex_albedo": ("skin.1001.png", True)},   # fine hair takes the skin's colour
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
    grown = bpy.data.objects.get("brows_grown")
    own = grown is not None and int(grown.get("brow_set", -1)) == int(nn)
    if grown is not None:
        grown.hide_render = grown.hide_viewport = not own
    if meta_path.exists():
        brows = json.loads(meta_path.read_text()).get("eyebrows", {})
        tag = brows.get("source", "")[-2:]
        for ob in bpy.data.objects:
            if ob.type == "CURVES" and ob.name.startswith("brow_hair_"):
                ob.hide_render = ob.hide_viewport = own or ob.name[-2:] != tag
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


def load_rgb(path):
    """PNG -> (H, W, 3) float array, top row first, display-referred values as stored."""
    img = bpy.data.images.load(str(path))
    try:
        w, h = img.size
        a = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(a)
    finally:
        bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1, :, :3]


def save_rgb(a, path):
    """(H, W, 3) float array, top row first -> 8-bit PNG, written as is (no view transform)."""
    h, w = a.shape[:2]
    img = bpy.data.images.new("_composite", w, h, alpha=False)
    try:
        rgba = np.ones((h, w, 4), np.float32)
        rgba[..., :3] = np.clip(a[::-1], 0.0, 1.0)
        img.pixels.foreach_set(rgba.ravel())
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


def resize(a, w, h):
    """Bilinear resample of an (H, W, C) array to (h, w, C), pixel centres aligned."""
    H, W = a.shape[:2]
    if (W, H) == (w, h):
        return a
    ys = np.clip((np.arange(h) + 0.5) * H / h - 0.5, 0.0, H - 1.0)
    xs = np.clip((np.arange(w) + 0.5) * W / w - 0.5, 0.0, W - 1.0)
    y0, x0 = ys.astype(int), xs.astype(int)
    y1, x1 = np.minimum(y0 + 1, H - 1), np.minimum(x0 + 1, W - 1)
    fy, fx = (ys - y0)[:, None, None], (xs - x0)[None, :, None]
    top = a[y0][:, x0] * (1.0 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1.0 - fx) + a[y1][:, x1] * fx
    return top * (1.0 - fy) + bot * fy


def render_pass(cam, out_dir, crop=None, res=None):
    """Render the Timeline from cam into out_dir/####.png with the camera's look.

    crop (x0, y0, x1, y1 from the top left, fractions) renders only that part of the frame
    (render border, cropped); res sets the square resolution before the quality percentage.
    """
    scene, r = bpy.context.scene, bpy.context.scene.render
    keep = dict(resolution_x=r.resolution_x, resolution_y=r.resolution_y, use_border=r.use_border,
                use_crop_to_border=r.use_crop_to_border, border_min_x=r.border_min_x,
                border_max_x=r.border_max_x, border_min_y=r.border_min_y, border_max_y=r.border_max_y)
    scene.camera = cam
    apply_look(cam)
    out_dir.mkdir(parents=True)
    try:
        if res:
            r.resolution_x = r.resolution_y = res
        if crop:
            x0, y0, x1, y1 = crop
            r.use_border = r.use_crop_to_border = True
            r.border_min_x, r.border_max_x = x0, x1
            r.border_min_y, r.border_max_y = 1.0 - y1, 1.0 - y0   # Blender's border is bottom-up
        r.image_settings.file_format = "PNG"
        r.image_settings.color_mode = "RGB"
        r.filepath = str(out_dir / "####")
        t0 = time.perf_counter()
        bpy.ops.render.render(animation=True)
        sec = time.perf_counter() - t0
    finally:
        for k, v in keep.items():
            setattr(r, k, v)
    frames = sorted(out_dir.glob("*.png"))
    print(f"[eyes] {cam.name}: {len(frames)} frames in {sec:.0f} s "
          f"({sec / max(len(frames), 1):.2f} s/frame)")
    return frames, sec


def upscale(frames, out_dir):
    """Draft frames (rendered at 50 %) brought to VIDEO_SIZE; full-size frames pass through."""
    if not frames or load_rgb(frames[0]).shape[0] == VIDEO_SIZE:
        return frames
    out_dir.mkdir(parents=True)
    out = []
    for i, f in enumerate(frames):
        path = out_dir / f"{i + 1:04d}.png"
        save_rgb(resize(load_rgb(f), VIDEO_SIZE, VIDEO_SIZE), path)
        out.append(path)
    return out


# ---- the camera move ------------------------------------------------------------------------

def _framing(cam, M):
    """A framing from a camera's world matrix M: the point it looks at (move_dist ahead), the
    unit direction from there back to the camera, the distance, lens and stop. Only position
    and look-at are taken from M; the orientation is rebuilt level (_camera_matrix)."""
    back = M.to_3x3().col[2].normalized()
    d = float(cam["move_dist"])
    return dict(T=M.translation - back * d, back=back, d=d, lens=float(cam.data.lens),
                fstop=float(cam["move_fstop"]))


def _phase(s, lo, hi):
    """s remapped so it runs 0 -> 1 between lo and hi, eased at both ends."""
    return float(camera_move.ease((s - lo) / (hi - lo)))


def _blend(A, B, s):
    """Between two framings at progress s (eased piece by piece over the glide).

    The look-at point and the camera position are interpolated separately: the look-at point
    moves straight, the camera moves on a path round it (its direction from the look-at point
    turns on the sphere, its distance, the lens and the stop change geometrically, so the frame
    width does too). The orientation is never interpolated; _camera_matrix builds it from the
    look-at with world up, so the camera stays level. The two parts are staggered so
    the camera never sweeps close past the face: a glide that pulls back moves out first and
    then across (distance, lens and stop over s 0-0.5, point and direction over 0.5-1); it backs
    out past its end distance (BULGE, scaled by the turn) and comes in as it turns. A glide that
    pushes in turns while it is far out and comes in last.
    """
    if s <= 0.0:
        return A
    if s >= 1.0:
        return B
    early, late = _phase(s, 0.0, 0.5), _phase(s, 0.5, 1.0)
    out_first = B["d"] * 36.0 / B["lens"] >= A["d"] * 36.0 / A["lens"]   # frame grows: pull back
    sd, sx = (early, late) if out_first else (late, early)

    def geo(k):
        return math.exp((1.0 - sd) * math.log(A[k]) + sd * math.log(B[k]))

    back = A["back"].slerp(B["back"], sx, A["back"].lerp(B["back"], sx))
    d = geo("d")
    if out_first:
        turn = math.degrees(A["back"].angle(B["back"], 0.0))
        d *= 1.0 + BULGE * sd * (1.0 - sx) * min(1.0, turn / 20.0)
    return dict(T=A["T"].lerp(B["T"], sx), back=back.normalized(), d=d, lens=geo("lens"),
                fstop=geo("fstop"))


def _camera_matrix(F):
    """World matrix of a camera at T + back * d looking at T, level: its x axis is horizontal
    (world up, +Z, defines the roll), so the head is never tilted by the camera."""
    C = F["T"] + F["back"] * F["d"]
    z = (C - F["T"]).normalized()
    x = Vector((0.0, 0.0, 1.0)).cross(z).normalized()
    y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = C
    return M


def key_move(track, mode, fps=30, r=None):
    """Key cam_move on every Timeline frame for this gaze track (already baked on the rig).

    Location, rotation, lens, focus distance and f-stop are keyed with linear in-betweens. Focus
    sits on the subject's left pupil (along the view axis) throughout. In the eye framing the
    camera's position and look-at point ride on the head bone (cam_move_eye's parent); the follow
    is blended in or out over the glide next to it. Returns the glides from camera_move.plan.
    """
    r = r or rig()
    scene = bpy.context.scene
    cam = bpy.data.objects[VIDEO_CAMERAS["move"]]
    cams = {k: bpy.data.objects[v] for k, v in MOVE_FRAMINGS.items()}
    eye_rest = Matrix([cams["eye"]["rest_matrix"][i:i + 4] for i in range(0, 16, 4)])
    fixed = {k: _framing(c, c.matrix_world.copy()) for k, c in cams.items() if k != "eye"}
    fixed["eye_rest"] = _framing(cams["eye"], eye_rest)
    rows, glides = camera_move.frames(track, mode, fps)

    eye_bone = r.arm.pose.bones["eye.L"]
    scene.frame_set(scene.frame_start)
    bone_w = r.arm.matrix_world @ eye_bone.matrix
    pupil_local = bone_w.inverted() @ r.pupil_world()["L"]   # the pupil rides on the eye bone

    for ob in (cam, cam.data):
        ob.animation_data_clear()
    cam.rotation_mode = "QUATERNION"
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    prev = None
    try:
        for row in rows:
            f = scene.frame_start + row["frame"] - 1
            scene.frame_set(f)
            frs = dict(fixed)
            frs["eye"] = _blend(fixed["eye_rest"], _framing(cams["eye"], cams["eye"].matrix_world),
                                row["follow"])
            F = _blend(frs[row["a"]], frs[row["b"]], row["s"])
            M = _camera_matrix(F)
            q = M.to_quaternion()
            if prev is not None and q.dot(prev) < 0.0:
                q.negate()
            prev = q
            cam.location, cam.rotation_quaternion = M.translation, q
            pupil = r.arm.matrix_world @ eye_bone.matrix @ pupil_local
            cam.data.lens = F["lens"]
            cam.data.dof.use_dof = True
            cam.data.dof.focus_distance = (pupil - M.translation).dot(-F["back"])
            cam.data.dof.aperture_fstop = F["fstop"]
            cam.keyframe_insert("location", frame=f)
            cam.keyframe_insert("rotation_quaternion", frame=f)
            for path in ("lens", "dof.focus_distance", "dof.aperture_fstop"):
                cam.data.keyframe_insert(path, frame=f)
    finally:
        prefs.keyframe_new_interpolation_type = old
    scene.frame_set(scene.frame_start)
    print("[eyes] cam_move: " + "; ".join(
        f"{a} -> {b} " + " ".join(f"{p0:.2f}-{p1:.2f}" for p0, p1 in pieces) + " s"
        for _, _, a, b, pieces in glides))
    return glides


def render_frames(cam, frames, out_dir):
    """Render single Timeline frames from cam into out_dir/####.png; seconds for each."""
    scene = bpy.context.scene
    scene.camera = cam
    apply_look(cam)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    out = []
    for f in frames:
        scene.frame_set(f)
        scene.render.filepath = str(out_dir / f"{f:04d}.png")
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        out.append(time.perf_counter() - t0)
        print(f"[eyes] {cam.name} frame {f} ({(f - 1) / scene.render.fps:.2f} s): {out[-1]:.1f} s")
    return out


def video(mode, seed, fps, camera, limit=None, frames=None):
    """Bake the gaze track to the Timeline, film it (the camera move, or face or eyes), encode.
    With frames, only those Timeline frames are rendered, as stills, and nothing is encoded."""
    scene = bpy.context.scene
    track = generate(mode, seed=seed)
    n = rig().bake(track, fps=fps)
    if camera == "move":
        key_move(track, mode, fps)
    if frames:
        out_dir = REPO / "outputs" / "frames" / mode / f"{camera}_stills"
        render_frames(bpy.data.objects[VIDEO_CAMERAS[camera]], [f for f in frames if 1 <= f <= n], out_dir)
        return
    if limit:
        scene.frame_end = scene.frame_start + min(limit, n) - 1
    root = REPO / "outputs" / "frames" / mode
    if root.exists():
        shutil.rmtree(root)
    t0 = time.perf_counter()
    frames, sec = render_pass(bpy.data.objects[VIDEO_CAMERAS[camera]], root / camera)
    frames = upscale(frames, root / "video")
    sec = time.perf_counter() - t0
    print(f"[eyes] `{mode}` seed {seed}, camera {camera}: {len(frames)} frames, {sec:.0f} s in all, "
          f"{sec / max(len(frames), 1):.2f} s/frame")
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
    ap.add_argument("--quality", choices=("final", "preview", "draft"), default="final",
                    help="final: Cycles 1024 px; preview: Cycles 768 px, 32 samples, for judging a "
                         "video before the long render; draft: EEVEE 512 px, motion only")
    ap.add_argument("--camera", choices=(*CAMERAS, "move"), default=None,
                    help="videos: face (default; one fixed camera, forehead to chin), eyes, or move "
                         "(glides between one eye, both eyes and the face); stills: face (default) or eyes")
    ap.add_argument("--samples", type=int, default=None,
                    help="render samples (Cycles; EEVEE with --quality draft)")
    ap.add_argument("--texture", type=int, default=None, help="use textures/tex_NN")
    ap.add_argument("--render", action="store_true", help="with --check-directions, also render PNGs")
    ap.add_argument("--limit", type=int, default=None, help="render only the first N video frames")
    ap.add_argument("--frames", type=int, nargs="+", default=None,
                    help="videos: render only these Timeline frames, as stills, into "
                         "outputs/frames/<input>/<camera>_stills/ (no video is encoded)")
    ap.add_argument("--out", type=Path, default=None, help="output PNG for --move")
    ap.add_argument("--cpu", action="store_true")
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    if args.camera == "move" and not args.input:
        raise SystemExit("eyes.py: --camera move is for videos (--input)")
    engine = setup_render(args.quality, args.cpu, args.samples)
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
        video(args.input, args.seed, args.fps, args.camera or "face", args.limit, args.frames)


if __name__ == "__main__" and "--" in sys.argv:
    main(sys.argv[sys.argv.index("--") + 1:])
