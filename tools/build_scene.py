"""Build scene.blend from assets/gnm/base.npz. Never edit scene.blend by hand; rerun this.

    $BLENDER -b --factory-startup -P tools/build_scene.py
    $BLENDER -b --factory-startup -P tools/build_scene.py -- --out /tmp/test.blend --no-bake

What goes into the file:
- mesh `gnm_head` with `UDIM` (render) and `legacy` UV layers, one material slot per UDIM tile
  (skin, eye_interior.L, cornea.L, eye_interior.R, cornea.R, teeth, tongue)
- armature `gnm_rig`: neck -> head -> eye.L, eye.R from GNM joints and skin weights
- shape keys per eye (.L = subject's left, +X): lid_up, lid_down, lid_open, blink
  (or blink_33 / blink_66 / blink when solved), brow_up, squint; plus `pupil`
- vertex groups pupil_L / pupil_R and custom properties on `gnm_rig` that wrapper/rig.py reads
  (the wrapper never reads assets/ or tools/)
- cam_face (40 cm, 50 mm) and cam_eyes (same spot, 105 mm), 1024x1024
- constant light: the CC0 studio HDRI (packed into the file) plus one soft key; AgX
- the `generate` motion, seed 0, baked as keyframes, so pressing play shows the expression

Lid shapes come from assets/gnm/lids.npz when tools/solve_lids.py has written it. Until then
STAND-IN shapes are built here (see lid_standins). Materials are the grey debug ones from M0
with a procedural pupil/iris/sclera so gaze reads by eye; look development is M3.

GNM is +Y up / +Z forward; Blender is +Z up / -Y forward: (x, y, z) -> (x, -z, y).
"""

import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

BLINK_CLOSE = {"L": 1.40, "R": 1.35}  # M0 spike: scale of the averaged wink that shuts the lid
REST_PUPIL = -1.2                       # GNM pupils_000; about a 3.5 mm pupil
REST_LID_OPEN = 0.5                     # picked by looking at the cam_eyes reset frame
TILE_MATERIALS = ("skin", "eye_interior.L", "cornea.L", "eye_interior.R", "cornea.R",
                  "teeth", "tongue")
BONES = {"neck": "neck", "head": "head", "left_eye": "eye.L", "right_eye": "eye.R"}


def to_blender(p):
    p = np.asarray(p, dtype=np.float64)
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], axis=-1)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", type=Path, default=REPO / "assets/gnm/base.npz")
    ap.add_argument("--lids", type=Path, default=REPO / "assets/gnm/lids.npz")
    ap.add_argument("--hdri", type=Path,
                    default=REPO / "assets/third_party/hdri/brown_photostudio_02_2k.hdr")
    ap.add_argument("--out", type=Path, default=REPO / "scene.blend")
    ap.add_argument("--no-bake", action="store_true", help="skip baking `generate` onto the Timeline")
    return ap.parse_args(argv)


# ---- data -----------------------------------------------------------------------------------

class Data:
    def __init__(self, path):
        d = np.load(path, allow_pickle=False)
        self.d = d
        self.V = d["vertices"].astype(np.float64)
        self.names = [str(n) for n in d["vertex_group_names"]]
        self.masks = d["vertex_group_masks"]
        self.joints = d["joint_positions"].astype(np.float64)

    def mask(self, name):
        return self.masks[self.names.index(name)]

    def pupil(self, side):
        eye = self.mask("left_eye" if side == "L" else "right_eye")
        return self.V[eye & self.mask("pupils")].mean(axis=0)

    def joint(self, side):
        return self.joints[2 if side == "L" else 3]

    def margins(self, side):
        """Upper and lower lid-margin rows in the column through the pupil (gnm_core.lid_margins)."""
        V, p = self.V, self.pupil(side)
        sign = 1.0 if side == "L" else -1.0
        sock = self.mask("eye_sockets") & (np.sign(V[:, 0]) == sign)
        col = sock & (np.abs(V[:, 0] - p[0]) < 0.002)
        out = []
        for half in (V[:, 1] > p[1], V[:, 1] < p[1]):
            idx = np.where(col & half)[0]
            out.append(idx[V[idx, 2] > V[idx, 2].max() - 0.001])
        return out

    def expr_delta(self, coeffs):
        return np.tensordot(coeffs.astype(np.float64), self.d["expression_basis"], axes=1)


def rotate_about_x(P, centre, angle):
    """Rotate points about the GNM x axis through centre; angle > 0 lifts the front (+Z) up (+Y)."""
    c, s = np.cos(angle), np.sin(angle)
    q = P - centre
    y = q[:, 1] * c + q[:, 2] * s
    z = -q[:, 1] * s + q[:, 2] * c
    return np.stack([q[:, 0], y, z], axis=1) + centre


def lid_standins(D, side):
    """STAND-IN lid shapes until tools/solve_lids.py exists. Returns {key: delta (V, 3) GNM}.

    The averaged wink delta, scaled to close the lid, says which skin moves with the lid and
    by how much. Its magnitude, normalised on the margin row, is used as a falloff mask m(v);
    each lid shape then rotates the masked skin about the eye joint's left-right axis by
    angle * m(v). On the margin (m = 1) that is the brief's target exactly: the margin is the
    rest margin rotated about the joint, so it keeps its distance to the globe. Upper and lower
    lid are split by height relative to the pupil. No basis fit and no collision pass yet.
    """
    V = D.V
    J, p = D.joint(side), D.pupil(side)
    blink = D.d[f"delta_blink_{side}"].astype(np.float64) * BLINK_CLOSE[side]
    up_rows, lo_rows = D.margins(side)
    mag = np.linalg.norm(blink, axis=1)
    side_mask = np.sign(V[:, 0]) == (1.0 if side == "L" else -1.0)
    rel = (V[:, 1] - p[1]) * 1000.0
    upper = np.clip((rel + 1.0) / 2.0, 0.0, 1.0) * side_mask   # 1 above the pupil, 0 below
    lower = (1.0 - upper) * side_mask
    m_up = np.clip(mag / np.median(mag[up_rows]), 0.0, 1.0) * upper
    m_lo = np.clip(mag / np.median(mag[lo_rows]), 0.0, 1.0) * lower

    def rot(angle_up_deg, angle_lo_deg):
        out = np.zeros_like(V)
        for m, a in ((m_up, angle_up_deg), (m_lo, angle_lo_deg)):
            sel = m > 1e-4
            if a:
                out[sel] += rotate_about_x(V[sel], J, np.radians(a) * m[sel]) - V[sel]
        return out

    # Upper margin height above the pupil centre, to size lid_open.
    up_h = (V[up_rows, 1].mean() - p[1]) * 1000.0
    r_up = V[up_rows].mean(axis=0) - J
    target = 3.75 + (p[1] - J[1]) * 1000.0            # 3.75 mm above the pupil centre
    radius = math.hypot(r_up[1], r_up[2]) * 1000.0
    open_deg = math.degrees(math.asin(min(target / radius, 1.0)) - math.atan2(r_up[1], r_up[2]))
    print(f"[build] {side} stand-in lids: upper margin {up_h:.2f} mm above pupil, "
          f"lid_open rotates it {open_deg:.2f} deg")

    return {
        f"lid_up.{side}": rot(0.85 * 20.0, 0.35 * 20.0),
        f"lid_down.{side}": rot(-0.90 * 25.0, -0.45 * 25.0),
        f"lid_open.{side}": rot(open_deg, 0.0),
        f"blink.{side}": blink,
    }


def shape_deltas(D, lids_path):
    """All shape-key deltas in GNM coordinates, in creation order."""
    keys = {}
    solved = lids_path.exists()
    if solved:
        L = np.load(lids_path, allow_pickle=False)
        for k in sorted(L.files):
            if k.startswith("delta_"):
                keys[k[len("delta_"):]] = L[k].astype(np.float64)
        print(f"[build] lid shapes from {lids_path.name}: {sorted(keys)}")
    else:
        print(f"[build] {lids_path.name} not found: using STAND-IN lid shapes")
        for side in ("L", "R"):
            keys.update(lid_standins(D, side))
    # Per-side split of the M0 brow_up and squint vectors (0-99 left eye, 100-199 right eye).
    for name in ("brow_up", "squint"):
        c = D.d[f"expr_{name}"]
        for side, sl in (("L", slice(0, 100)), ("R", slice(100, 200))):
            if f"{name}.{side}" in keys:
                continue
            part = np.zeros_like(c)
            part[sl] = c[sl]
            keys[f"{name}.{side}"] = D.expr_delta(part)
    pupil = np.zeros(383, dtype=np.float32)
    pupil[382] = 1.0
    keys.setdefault("pupil", D.expr_delta(pupil))
    return keys, solved


# ---- blender objects ------------------------------------------------------------------------

def build_mesh(D):
    d = D.d
    verts = to_blender(D.V)
    quads = d["quads"]
    me = bpy.data.meshes.new("gnm_head")
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(quads), 4, dtype=np.int32))
    for name, key in (("UDIM", "quad_uvs_udim"), ("legacy", "quad_uvs")):
        uv = me.uv_layers.new(name=name)
        uv.data.foreach_set("uv", d[key].astype(np.float32).ravel())
    me.uv_layers["UDIM"].active_render = True
    me.uv_layers.active = me.uv_layers["UDIM"]
    me.update(calc_edges=True)
    me.validate()
    me.polygons.foreach_set("use_smooth", np.ones(len(quads), dtype=bool))
    me.polygons.foreach_set("material_index", (d["quad_udim_tiles"] - 1001).astype(np.int32))
    ob = bpy.data.objects.new("gnm_head", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build_rig(D, ob):
    d = D.d
    names = [str(n) for n in d["joint_names"]]
    parents = d["joint_parents"]
    joints = to_blender(D.joints)
    arm = bpy.data.armatures.new("gnm_rig")
    rig = bpy.data.objects.new("gnm_rig", arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = {}
    for i, n in enumerate(names):
        b = arm.edit_bones.new(BONES[n])
        b.head = Vector(joints[i])
        eye = "eye" in n
        b.tail = b.head + (Vector((0, -0.012, 0)) if eye else Vector((0, 0, 0.05)))
        b.roll = 0.0
        if parents[i] >= 0:
            b.parent = ebones[names[parents[i]]]
        ebones[n] = b
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    w = d["skinning_weights"]
    for i, n in enumerate(names):
        vg = ob.vertex_groups.new(name=BONES[n])
        nz = np.where(w[i] > 0)[0]
        for wv in np.unique(w[i][nz]):
            vg.add(nz[w[i][nz] == wv].tolist(), float(wv), "REPLACE")
    for side, eye in (("L", "left_eye"), ("R", "right_eye")):
        vg = ob.vertex_groups.new(name=f"pupil_{side}")
        vg.add(np.where(D.mask(eye) & D.mask("pupils"))[0].tolist(), 1.0, "REPLACE")
    mod = ob.modifiers.new("rig", "ARMATURE")
    mod.object = rig
    ob.parent = rig
    return rig


def build_shape_keys(ob, deltas, base):
    ob.shape_key_add(name="Basis", from_mix=False)
    for k, delta in deltas.items():
        sk = ob.shape_key_add(name=k, from_mix=False)
        sk.slider_min = -3.0 if k == "pupil" else 0.0
        sk.slider_max = 3.0 if k == "pupil" else 1.5
        co = base + to_blender(delta)
        sk.data.foreach_set("co", co.astype(np.float32).ravel())


# ---- materials ------------------------------------------------------------------------------

def principled(name, colour, rough=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return mat


def eye_interior(name):
    """Debug eye: pupil / iris / sclera from the measured UV radii (assets/gnm/eye_uv.json)."""
    mat = principled(name, (0.7, 0.7, 0.7), rough=0.6)
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Specular IOR Level"].default_value = 0.1
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UDIM"
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    fu = nt.nodes.new("ShaderNodeMath")
    fu.operation = "FRACT"
    nt.links.new(sep.outputs["X"], fu.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(fu.outputs[0], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = (0.5, 0.5, 0.0)
    nt.links.new(comb.outputs[0], sub.inputs[0])
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    nt.links.new(sub.outputs[0], ln.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.008, 0.008, 0.008, 1)
    els[1].position, els[1].color = 0.0499, (0.13, 0.075, 0.04, 1)
    e = els.new(0.1881)
    e.color = (0.72, 0.68, 0.62, 1)
    nt.links.new(ln.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def cornea(name):
    """Clear shell: Fresnel-weighted gloss for the catchlight, transparent to shadow rays."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    out = nt.nodes["Material Output"]
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.02
    fr = nt.nodes.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.376
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fr.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr2 = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix2 = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], mix2.inputs[0])
    nt.links.new(mix.outputs[0], mix2.inputs[1])
    nt.links.new(tr2.outputs[0], mix2.inputs[2])
    nt.links.new(mix2.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    return mat


def build_materials(ob):
    mats = {
        "skin": principled("skin", (0.5, 0.5, 0.5)),
        "eye_interior.L": eye_interior("eye_interior.L"),
        "cornea.L": cornea("cornea.L"),
        "eye_interior.R": eye_interior("eye_interior.R"),
        "cornea.R": cornea("cornea.R"),
        "teeth": principled("teeth", (0.75, 0.72, 0.66), rough=0.35),
        "tongue": principled("tongue", (0.45, 0.16, 0.16), rough=0.45),
    }
    for name in TILE_MATERIALS:
        ob.data.materials.append(mats[name])


# ---- cameras, light, render settings --------------------------------------------------------

def build_cameras_and_light(mid, hdri):
    scene = bpy.context.scene
    cams = {}
    for name, lens in (("cam_face", 50.0), ("cam_eyes", 105.0)):
        cd = bpy.data.cameras.new(name)
        cd.lens, cd.sensor_width, cd.sensor_fit = lens, 36.0, "HORIZONTAL"
        cd.clip_start, cd.clip_end = 0.01, 10.0
        cam = bpy.data.objects.new(name, cd)
        cam.location = mid + Vector((0, -0.40, 0))
        # Looks along +Y at the face; for cam_eyes this aims exactly at the eye midpoint.
        cam.rotation_euler = (math.pi / 2, 0, 0)
        scene.collection.objects.link(cam)
        cams[name] = cam
    scene.camera = cams["cam_face"]

    ld = bpy.data.lights.new("key", "AREA")
    ld.shape, ld.size, ld.energy = "DISK", 0.35, 5.0
    key = bpy.data.objects.new("key", ld)
    key.location = mid + Vector((-0.30, -0.45, 0.28))
    key.rotation_euler = (mid - key.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(key)

    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = 0.6
    if hdri.exists():
        img = bpy.data.images.load(str(hdri))
        img.pack()  # the HDRI lives in assets/third_party (git-ignored); pack so the .blend stands alone
        img.filepath = "//" + hdri.name
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = img
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value = (0, 0, math.radians(200))
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    else:
        print(f"[build] WARNING: {hdri} missing, grey world instead")
        bg.inputs["Color"].default_value = (0.18, 0.18, 0.18, 1)
    scene.world = world
    return cams


def render_settings(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 128
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.seed = 0
    scene.cycles.use_animated_seed = False
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "None"


# ---- main -----------------------------------------------------------------------------------

def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "SyntheticEyes"
    D = Data(args.npz)
    render_settings(scene)

    ob = build_mesh(D)
    rig = build_rig(D, ob)
    deltas, solved = shape_deltas(D, args.lids)
    build_shape_keys(ob, deltas, to_blender(D.V))
    build_materials(ob)

    eyes = to_blender(D.joints[2:4])
    mid = Vector(eyes.mean(axis=0))
    build_cameras_and_light(mid, args.hdri)

    # Everything wrapper/rig.py needs at run time.
    rig["eye_rest_L"] = list(eyes[0])
    rig["eye_rest_R"] = list(eyes[1])
    rig["eye_mid"] = list(mid)
    rig["forward"] = [0.0, -1.0, 0.0]
    rig["rest_pupil"] = REST_PUPIL
    rig["rest_lid_open"] = REST_LID_OPEN
    rig["lid_shapes"] = "solved" if solved else "standin"
    rig["blink_keys"] = "tent" if "blink_33.L" in deltas else "single"
    rig["camera_px"] = 1024

    if not args.no_bake:
        from wrapper.gaze import generate
        from wrapper.rig import Rig
        track = generate("generate", seed=0)
        n = Rig(rig, ob).bake(track, fps=scene.render.fps)
        print(f"[build] baked `generate` seed 0: {n} frames")
    else:
        scene.frame_start, scene.frame_end = 1, 1

    scene.frame_set(scene.frame_start)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out), compress=True, relative_remap=True)
    print(f"[build] wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB), "
          f"shape keys: {list(deltas)}")


main()
