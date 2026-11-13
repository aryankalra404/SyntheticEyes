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
- materials load a texture set from textures/tex_NN by path (made relative on save, never
  packed): albedo, normal and roughness on the skin tile, the eye image on each eye-interior tile.
  `--texture NN` picks the set; wrapper/eyes.py `use_texture` switches it in an open file.
- M3 extras, all rebuilt from this identity's vertices and following every shape key (each hair
  or strip shape key is driven by the head key of the same name, so rig.py stays unchanged):
  eyelashes grown on the lid margin (tools/lashes.py); eyebrow hair carried from MakeHuman
  (assets/gnm/hair_binding.npz, tools/carry_hair.py), one object per Mindfront set with only the
  texture set's one shown, all rendered as Cycles hair curves; a tear meniscus along each lower
  lid; per-vertex masks wet / pink / lips / lids on the head for the skin shader
- look: skin with subsurface, wet lid margins and pink inner corners; a refracting cornea shell
  over a matte iris and scattering sclera (see the material functions)
- cam_face (40 cm, 50 mm) and cam_eyes (same spot, 105 mm), 1024x1024; M3 test cameras
  cam_test_face (whole face, forehead to chin) and cam_test_eye (subject's left eye, three-quarter);
  video cameras cam_video (the face, a little looser) and cam_inset (the eye close-up, on the head bone)
- two looks, chosen by the camera that renders (LOOKS, wrapper/eyes.py apply_look): `face`, the
  constant light (CC0 studio HDRI packed into the file plus one soft key, plain dark backdrop) for
  cam_face, cam_test_face and the 10 clockwise renders; `eye`, a dark background, one small side
  key and a shallow depth of field, for cam_eyes and cam_test_eye. AgX.
- the `generate` motion, seed 0, baked as keyframes, so pressing play shows the expression

Lid shapes come from assets/gnm/lids.npz (tools/solve_lids.py). A head other than the one that
file was solved on (--npz with an identity) has its lids solved here, in the same way. Without
the file STAND-IN shapes are built (see lid_standins).
- the globe guard: a Shrinkwrap modifier per eye that keeps lid skin, lashes and the tear line
  outside the eyeball in poses no lid key was solved for (see build_globe_guard)

GNM is +Y up / +Z forward; Blender is +Z up / -Y forward: (x, y, z) -> (x, -z, y).
"""

import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
import lashes as lash_gen  # noqa: E402  (pure numpy)
import solve_lids  # noqa: E402  (pure numpy)

BLINK_CLOSE = {"L": 1.40, "R": 1.35}  # M0 spike: scale of the averaged wink that shuts the lid
REST_PUPIL = -1.2                       # GNM pupils_000; about a 3.5 mm pupil
REST_LID_OPEN = 1.0                     # cam_eyes reset frame: lid 4.0 mm above the pupil centre, top of the iris just under it
TILE_MATERIALS = ("skin", "eye_interior.L", "cornea.L", "eye_interior.R", "cornea.R",
                  "teeth", "tongue")
SKIN_SSS = 0.0025                         # skin subsurface scale in metres (--sss), 0 = off
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
    ap.add_argument("--texture", type=int, default=9, help="texture set textures/tex_NN loaded by default (09 is the hero set)")
    ap.add_argument("--hair", type=Path, default=REPO / "assets/gnm/hair_binding.npz")
    ap.add_argument("--no-guard", action="store_true", help="leave out the globe guard (to compare)")
    ap.add_argument("--sss", type=float, default=SKIN_SSS, help="skin subsurface scale in metres, 0 = off")
    return ap.parse_args(argv)


# ---- data -----------------------------------------------------------------------------------

class Data:
    def __init__(self, path):
        d = np.load(path, allow_pickle=False)
        self.d = d
        self.path = Path(path)
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
    # The wink also moves brow and forehead a little. A lid shape must not: it would drag each
    # half of the forehead with the gaze and leave a step down the midline (seen in the M3 stills).
    # Fade the mask out past the orbit: full within 18 mm of the pupil, none beyond 30 mm.
    reach = np.clip((0.030 - np.hypot(V[:, 0] - p[0], V[:, 1] - p[1])) / 0.012, 0.0, 1.0)
    reach = reach * reach * (3.0 - 2.0 * reach)
    m_up = np.clip(mag / np.median(mag[up_rows]), 0.0, 1.0) * upper * reach
    m_lo = np.clip(mag / np.median(mag[lo_rows]), 0.0, 1.0) * lower * reach

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
        sha = solve_lids.Head(D.d).sha()
        if "source_sha" in L.files and str(L["source_sha"][0]) != sha:
            # the file was solved on another head (the template); lids must fit this one's globe
            print(f"[build] {lids_path.name} is for another head: solving lids for {D.path.name}")
            keys, _ = solve_lids.solve(D.d, REST_LID_OPEN, verbose=False)
        else:
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
    """The eye's outer shell: clear, refracting, mirror-smooth (the tear film), so the iris sits
    at depth behind a bulge and the catchlight is sharp. Shadow rays pass straight through, or the
    iris and sclera under it would render black."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    out = nt.nodes["Material Output"]
    gl = nt.nodes.new("ShaderNodeBsdfGlass")
    gl.inputs["IOR"].default_value = 1.376
    gl.inputs["Roughness"].default_value = 0.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], mix.inputs[0])
    nt.links.new(gl.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def image_node(nt, name, uv, colour=True):
    """Empty image texture node on the UDIM UV map; wrapper/eyes.py use_texture fills it.

    Each material covers one UDIM tile and the image repeats, so tile 100N's UVs (u in [N-1, N])
    read a plain single-tile image without a tile offset."""
    n = nt.nodes.new("ShaderNodeTexImage")
    n.name = n.label = name
    n.interpolation = "Cubic" if name == "tex_normal" else "Linear"
    nt.links.new(uv.outputs["UV"], n.inputs["Vector"])
    return n


def attr(nt, name):
    n = nt.nodes.new("ShaderNodeAttribute")
    n.attribute_type = "GEOMETRY"
    n.attribute_name = name
    return n.outputs["Fac"]


def mnode(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


PINK = (0.50, 0.16, 0.13)        # wet tissue inside the lids and at the inner corner (linear)


def skin_textured(sss_scale=None):
    """Skin: the set's albedo, tangent normal (OpenGL) and roughness maps on a Principled BSDF
    with subsurface, plus four per-vertex masks written by build_masks():
      wet   lid margin and the pocket behind the lids: low roughness under a clear coat
      pink  the same pocket and the inner corner: wet red tissue instead of the albedo's skin fill
      lips  smoother, with a thin coat
      lids  thin skin round the eye: a touch more subsurface
    """
    mat = principled("skin", (0.5, 0.5, 0.5))
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UDIM"
    wet, pink, lips, lids = (attr(nt, k) for k in ("wet", "pink", "lips", "lids"))

    alb = image_node(nt, "tex_albedo", uv)
    col = nt.nodes.new("ShaderNodeMix")
    col.data_type = "RGBA"
    nt.links.new(mnode(nt, "MULTIPLY", pink, 0.85), col.inputs["Factor"])
    nt.links.new(alb.outputs["Color"], col.inputs["A"])
    col.inputs["B"].default_value = (*PINK, 1.0)
    nt.links.new(col.outputs["Result"], bsdf.inputs["Base Color"])

    nrm = image_node(nt, "tex_normal", uv, colour=False)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UDIM"
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    rough = image_node(nt, "tex_rough", uv, colour=False)
    r = mnode(nt, "MULTIPLY", rough.outputs["Color"], mnode(nt, "SUBTRACT", 1.0, mnode(nt, "MULTIPLY", lips, 0.3)))
    r = mnode(nt, "MULTIPLY", r, mnode(nt, "SUBTRACT", 1.0, mnode(nt, "MULTIPLY", wet, 0.75)))
    nt.links.new(r, bsdf.inputs["Roughness"])
    coat = mnode(nt, "ADD", wet, mnode(nt, "MULTIPLY", lips, 0.25), clamp=True)
    nt.links.new(coat, bsdf.inputs["Coat Weight"])
    nt.links.new(mnode(nt, "SUBTRACT", 0.28, mnode(nt, "MULTIPLY", wet, 0.25)), bsdf.inputs["Coat Roughness"])
    bsdf.inputs["Coat IOR"].default_value = 1.38
    # the wet film is not flat: a fine ripple on the coat alone breaks the highlight into glints
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2200.0       # object space is metres: about 0.5 mm features
    noise.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ripple = nt.nodes.new("ShaderNodeBump")
    ripple.inputs["Distance"].default_value = 0.0002
    nt.links.new(wet, ripple.inputs["Strength"])
    nt.links.new(noise.outputs["Fac"], ripple.inputs["Height"])
    nt.links.new(nm.outputs["Normal"], ripple.inputs["Normal"])
    nt.links.new(ripple.outputs["Normal"], bsdf.inputs["Coat Normal"])

    scale = SKIN_SSS if sss_scale is None else sss_scale
    if scale > 0:
        bsdf.subsurface_method = "RANDOM_WALK_SKIN"
        bsdf.inputs["Subsurface Weight"].default_value = 1.0
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.18)
        bsdf.inputs["Subsurface IOR"].default_value = 1.4
        bsdf.inputs["Subsurface Anisotropy"].default_value = 0.8
        nt.links.new(mnode(nt, "MULTIPLY", mnode(nt, "ADD", 1.0, mnode(nt, "MULTIPLY", lids, 0.5)), scale),
                     bsdf.inputs["Subsurface Scale"])
    return mat


def build_masks(D, ob):
    """Per-vertex float attributes wet, pink, lips, lids on the head mesh (see skin_textured).
    They are topology, not UV: the same on every identity, and they follow the lids."""
    V, n = D.V, len(D.V)
    sock, skin, eye = D.mask("eye_sockets"), D.mask("skin"), D.mask("eyes")
    nbr = [[] for _ in range(n)]
    for q in D.d["quads"]:
        for i in range(4):
            nbr[int(q[i])].append(int(q[(i + 1) % 4]))
            nbr[int(q[(i + 1) % 4])].append(int(q[i]))

    def soften(w, steps):
        for _ in range(steps):
            w = np.array([0.5 * w[i] + 0.5 * np.mean(w[nbr[i]]) if nbr[i] else w[i] for i in range(n)])
        return w

    wet, pink = sock.astype(np.float64), sock.astype(np.float64)
    for side in ("L", "R"):
        rims = lash_gen.lid_rims(V, D.d["quads"], sock, skin, eye, side)
        inner = V[rims["upper"][0][0]]
        for rim, _, o1 in rims.values():
            k = np.clip(1.0 - np.linalg.norm(V[rim] - inner, axis=1) / 0.0045, 0.0, 1.0)   # caruncle
            wet[o1] = 0.9
            pink[rim] = 0.5 + 0.5 * k
            pink[o1] = np.maximum(pink[o1], 0.08 + 0.55 * k)
    lips = soften((D.mask("upper_lip") | D.mask("lower_lip")).astype(np.float64), 1)
    lids = soften((D.mask("left_orbital_region") | D.mask("right_orbital_region")).astype(np.float64), 2)
    for name, w in (("wet", wet), ("pink", pink), ("lips", lips), ("lids", lids)):
        a = ob.data.attributes.new(name, "FLOAT", "POINT")
        a.data.foreach_set("value", w.astype(np.float32))


def eye_textured(name):
    """Eye interior under the clear shell: the set's eye tile as base colour, matte (the shell
    carries the gloss). The sclera scatters a little (it is not paper); the iris gets relief from
    its own fibres so the side light catches them."""
    mat = principled(name, (0.7, 0.7, 0.7), rough=0.55)
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Specular IOR Level"].default_value = 0.15
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UDIM"
    tex = image_node(nt, "tex_eye", uv)
    # radius from the tile centre: iris inside the limbus (0.188, assets/gnm/eye_uv.json), sclera outside
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    fu = nt.nodes.new("ShaderNodeMath")
    fu.operation = "FRACT"
    nt.links.new(sep.outputs["X"], fu.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(fu.outputs[0], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    dist = nt.nodes.new("ShaderNodeVectorMath")
    dist.operation = "DISTANCE"
    dist.inputs[1].default_value = (0.5, 0.5, 0.0)
    nt.links.new(comb.outputs[0], dist.inputs[0])
    sclera = nt.nodes.new("ShaderNodeMapRange")
    sclera.interpolation_type = "SMOOTHSTEP"
    sclera.inputs["From Min"].default_value = 0.175
    sclera.inputs["From Max"].default_value = 0.205
    nt.links.new(dist.outputs["Value"], sclera.inputs["Value"])
    # The tile carries its own tone, limbal ring and fornix falloff (tools/make_iris.py), so the
    # colour goes in as it is: the scene shows what the judges get when they wrap the tile.
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    sss = nt.nodes.new("ShaderNodeMath")
    sss.operation = "MULTIPLY"
    sss.inputs[1].default_value = 0.6
    nt.links.new(sclera.outputs["Result"], sss.inputs[0])
    nt.links.new(sss.outputs[0], bsdf.inputs["Subsurface Weight"])
    bsdf.subsurface_method = "RANDOM_WALK"
    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.3)
    bsdf.inputs["Subsurface Scale"].default_value = 0.0015
    iris = nt.nodes.new("ShaderNodeMath")
    iris.operation = "SUBTRACT"
    iris.inputs[0].default_value = 1.0
    nt.links.new(sclera.outputs["Result"], iris.inputs[1])
    amt = nt.nodes.new("ShaderNodeMath")
    amt.operation = "MULTIPLY"
    amt.inputs[1].default_value = 0.6
    nt.links.new(iris.outputs[0], amt.inputs[0])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.00025
    nt.links.new(amt.outputs[0], bump.inputs["Strength"])
    nt.links.new(tex.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def build_materials(ob, sss=None):
    mats = {
        "skin": skin_textured(sss),
        "eye_interior.L": eye_textured("eye_interior.L"),
        "cornea.L": cornea("cornea.L"),
        "eye_interior.R": eye_textured("eye_interior.R"),
        "cornea.R": cornea("cornea.R"),
        "teeth": principled("teeth", (0.75, 0.72, 0.66), rough=0.35),
        "tongue": principled("tongue", (0.45, 0.16, 0.16), rough=0.45),
    }
    for name in TILE_MATERIALS:
        ob.data.materials.append(mats[name])


# ---- M3 extras: hair and tear line -----------------------------------------------------------

def tri_frames(A, B, C):
    """Per-triangle orthonormal frame rows (edge, normal x edge, normal); as tools/carry_hair.py."""
    e1 = B - A
    e1 = e1 / np.linalg.norm(e1, axis=1, keepdims=True)
    n = np.cross(B - A, C - A)
    n = n / np.linalg.norm(n, axis=1, keepdims=True)
    return np.stack([e1, np.cross(n, e1), n], 1)


def hair_points(V, tri, bary, off):
    A, B, C = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]
    base = A * bary[:, :1] + B * bary[:, 1:2] + C * bary[:, 2:3]
    return base + np.einsum("nij,ni->nj", tri_frames(A, B, C), off)


def drive_keys(ob, head):
    """Drive each shape key of ob by the head shape key of the same name (single-property SUM
    drivers, so no Python runs). Head keys are what rig.py writes and keyframes."""
    for kb in ob.data.shape_keys.key_blocks[1:]:
        fc = kb.driver_add("value")
        drv = fc.driver
        drv.type = "SUM"
        var = drv.variables.new()
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "KEY"
        var.targets[0].id = head.data.shape_keys
        var.targets[0].data_path = f'key_blocks["{kb.name}"].value'


def follower(name, verts, edges, faces, shapes, weights, head, rig):
    """Mesh object that moves like the head: same shape keys (driven), same bones (armature)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], edges, faces)
    me.update(calc_edges=True)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.shape_key_add(name="Basis", from_mix=False)
    for k, co in shapes.items():
        sk = ob.shape_key_add(name=k, from_mix=False)
        src = head.data.shape_keys.key_blocks[k]
        sk.slider_min, sk.slider_max = src.slider_min, src.slider_max
        sk.data.foreach_set("co", co.astype(np.float32).ravel())
    if len(shapes):
        drive_keys(ob, head)
    for bone, w in weights.items():
        vg = ob.vertex_groups.new(name=bone)
        nz = np.where(w > 1e-6)[0]
        for i in nz:
            vg.add([int(i)], float(w[i]), "REPLACE")
    mod = ob.modifiers.new("rig", "ARMATURE")
    mod.object = rig
    ob.parent = rig
    return ob


def follower_shapes(points_fn, base_pts, D, deltas):
    """Shape-key positions (Blender coords) for every head key that moves these points."""
    out = {}
    for k, delta in deltas.items():
        P = to_blender(points_fn(D.V + delta))
        if np.abs(P - base_pts).max() > 1e-7:
            out[k] = P
    return out


def bone_weights(D, vids, w):
    """Skinning weights of points interpolated from head vertices vids (n, m) with weights w (n, m)."""
    sw = D.d["skinning_weights"]
    names = [BONES[str(n)] for n in D.d["joint_names"]]
    return {names[j]: (sw[j][vids] * w).sum(1) for j in range(len(names)) if (sw[j][vids] * w).sum() > 0}


def hair_node_group():
    """Carrier mesh edges -> Catmull-Rom hair curves with the per-point radius.

    Lives on a Curves object and reads the carrier through Object Info: Cycles 4.5 renders curves
    on a Curves object as hair, but drops curves that a mesh object's modifier makes."""
    ng = bpy.data.node_groups.new("hair_curves", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Carrier", in_out="INPUT", socket_type="NodeSocketObject")
    ng.interface.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    info = n.new("GeometryNodeObjectInfo")
    info.transform_space = "RELATIVE"
    m2c = n.new("GeometryNodeMeshToCurve")
    spl = n.new("GeometryNodeCurveSplineType")
    spl.spline_type = "CATMULL_ROM"
    rad = n.new("GeometryNodeSetCurveRadius")
    attr = n.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "FLOAT"
    attr.inputs["Name"].default_value = "hair_radius"
    mat = n.new("GeometryNodeSetMaterial")
    L = ng.links
    L.new(gi.outputs[1], info.inputs["Object"])
    L.new(info.outputs["Geometry"], m2c.inputs["Mesh"])
    L.new(m2c.outputs["Curve"], spl.inputs["Curve"])
    L.new(spl.outputs["Curve"], rad.inputs["Curve"])
    L.new(attr.outputs["Attribute"], rad.inputs["Radius"])
    L.new(rad.outputs["Curve"], mat.inputs["Geometry"])
    L.new(gi.outputs[2], mat.inputs["Material"])
    L.new(mat.outputs["Geometry"], go.inputs[0])
    return ng


def hair_material(name, colour):
    """Principled Hair BSDF, direct colouring: fine dark hair with a soft sheen, not wire."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    h = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    h.parametrization = "COLOR"
    h.inputs["Color"].default_value = (*colour, 1.0)
    h.inputs["Roughness"].default_value = 0.35
    h.inputs["Radial Roughness"].default_value = 0.55
    h.inputs["Random Roughness"].default_value = 0.3
    nt.links.new(h.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return mat


def grow_lashes(D):
    """Lashes for both eyes on this head's own lid margins (tools/lashes.py), as binding arrays."""
    T = D.d["triangles"][D.d["triangle_udim_tiles"] == 1001]
    parts = [lash_gen.grow(D.V, D.d["quads"], T, D.mask("eye_sockets"), D.mask("skin"), D.mask("eyes"),
                           D.joint(side), side)[:5] for side in ("L", "R")]
    keys = ("tri", "bary", "off", "radius", "count")
    return {f"lashes_{k}": np.concatenate([p[i] for p in parts]) for i, k in enumerate(keys)}


# The carried Mindfront brows render as a dark slab at eye close-up range: too many, too thick and
# standing off the skin. Thin them so single hairs separate and the brow painted in the albedo
# shows between them.
BROW_KEEP = 0.6         # fraction of strands kept (fixed seed, per brow set)
BROW_RADIUS = 0.5       # x the carried strand radius (48 um at the root before)
BROW_LIFT = 0.5         # x the height above the skin of each point past the first two
BROW_SEED = 2026


def thin_brows(H, name):
    """Drop strands, halve radius and lay the strands down nearer the skin, all deterministic."""
    count = H[f"{name}_count"]
    keep = np.random.default_rng([BROW_SEED, int(name[-2:])]).random(len(count)) < BROW_KEEP
    start = np.concatenate([[0], np.cumsum(count)[:-1]])
    pts = np.concatenate([np.arange(s, s + c) for s, c in zip(start[keep], count[keep])])
    off = H[f"{name}_off"][pts].copy()
    up = off[:, 2] > 0              # root and the point at the skin stay where they are
    off[up, 2] *= BROW_LIFT
    H[f"{name}_off"] = off
    H[f"{name}_tri"] = H[f"{name}_tri"][pts]
    H[f"{name}_bary"] = H[f"{name}_bary"][pts]
    H[f"{name}_radius"] = H[f"{name}_radius"][pts] * BROW_RADIUS
    H[f"{name}_count"] = count[keep]


def build_hair(D, deltas, head, rig, path):
    """Eyelashes (grown here) and the three carried Mindfront brow sets as driven hair objects."""
    H = grow_lashes(D)
    names = ["lashes"]
    if path.exists():
        B = np.load(path, allow_pickle=False)
        H.update({k: B[k] for k in B.files if k.startswith("brows_")})
        names += ["brows_01", "brows_05", "brows_08"]
        for name in names[1:]:
            thin_brows(H, name)
    else:
        print(f"[build] {path.name} not found (run tools/carry_hair.py): no brow hair")
    ng = hair_node_group()
    mats = {"lashes": hair_material("lash_hair", (0.016, 0.011, 0.008)),
            "brows": hair_material("brow_hair", (0.045, 0.028, 0.018))}
    made = []
    for name in names:
        tri, bary, off = H[f"{name}_tri"], H[f"{name}_bary"], H[f"{name}_off"]
        count = H[f"{name}_count"]
        pts_fn = lambda V, tri=tri, bary=bary, off=off: hair_points(V, tri, bary, off)
        base = to_blender(pts_fn(D.V))
        start = np.concatenate([[0], np.cumsum(count)[:-1]])
        edges = [(int(s0 + i), int(s0 + i + 1)) for s0, c in zip(start, count) for i in range(c - 1)]
        shapes = follower_shapes(pts_fn, base, D, deltas)
        label = name if name == "lashes" else f"brow_hair_{name[-2:]}"
        carrier = follower(f"{label}_carrier", base, edges, [], shapes, bone_weights(D, tri, bary), head, rig)
        a = carrier.data.attributes.new("hair_radius", "FLOAT", "POINT")
        a.data.foreach_set("value", H[f"{name}_radius"].astype(np.float32))
        carrier.hide_render = True
        carrier.display_type = "WIRE"
        ob = bpy.data.objects.new(label, bpy.data.hair_curves.new(label))
        bpy.context.scene.collection.objects.link(ob)
        mat = mats["lashes" if name == "lashes" else "brows"]
        ob.data.materials.append(mat)
        mod = ob.modifiers.new("hair", "NODES")
        mod.node_group = ng
        ids = {it.socket_type: it.identifier for it in ng.interface.items_tree
               if getattr(it, "in_out", "") == "INPUT"}
        mod[ids["NodeSocketObject"]] = carrier
        mod[ids["NodeSocketMaterial"]] = mat
        if name != "lashes":
            ob.hide_render = ob.hide_viewport = name != "brows_01"
        print(f"[build] {ob.name}: {len(count)} hairs, {len(base)} points, {len(shapes)} driven keys")
        made.append(ob)
    return made


TEAR_RISE = 0.00075     # m the meniscus climbs the globe above the lid contact line
TEAR_LID = 0.75         # how far across the lid margin (back edge 0, lash edge 1) it starts
TEAR_ROWS = 5


def tear_material():
    """Clear water: refraction at IOR 1.34, a mirror-sharp reflection, no shadow of its own.
    A tenth of plain mirror is mixed in: the meniscus is a millimetre wide, and with Fresnel
    alone its reflection of the room is too faint to read as a wet line at 1024 px."""
    mat = bpy.data.materials.new("tear_line")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    gl = nt.nodes.new("ShaderNodeBsdfGlass")
    gl.inputs["IOR"].default_value = 1.34
    gl.inputs["Roughness"].default_value = 0.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = 0.0
    wetmix = nt.nodes.new("ShaderNodeMixShader")
    wetmix.inputs[0].default_value = 0.10
    nt.links.new(gl.outputs[0], wetmix.inputs[1])
    nt.links.new(gloss.outputs[0], wetmix.inputs[2])
    nt.links.new(lp.outputs["Is Shadow Ray"], mix.inputs[0])
    nt.links.new(wetmix.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return mat


def build_tear_lines(D, deltas, head, rig):
    """The tear meniscus: a concave fillet of water in the angle between the lower lid margin and
    the globe, inner corner to outer corner. Row 0 lies part-way across the lid margin, the last
    row on the eye's outer shell TEAR_RISE above the contact line; rows between follow a curve
    pulled into the corner. Rebuilt on every head key, so it follows the lid."""
    made = []
    sock, skin, eye = D.mask("eye_sockets"), D.mask("skin"), D.mask("eyes")
    for side in ("L", "R"):
        rim, _, o1 = lash_gen.lid_rims(D.V, D.d["quads"], sock, skin, eye, side)["lower"]
        J = D.joint(side)
        shell = D.mask("left_eye" if side == "L" else "right_eye") & D.mask("eye_exteriors")
        R = float(np.median(np.linalg.norm(D.V[shell] - J, axis=1))) + 0.00002
        n = len(rim)
        taper = np.sqrt(np.sin(np.linspace(0, np.pi, n)))[:, None]

        def rows(V, rim=rim, o1=o1, J=J, R=R, taper=taper):
            lid = V[rim] + TEAR_LID * taper * (V[o1] - V[rim])
            u = V[rim] - J
            u /= np.linalg.norm(u, axis=1, keepdims=True)
            up = np.array([0.0, 1.0, 0.0]) - u[:, 1:2] * u            # GNM up, tangent to the globe
            up /= np.linalg.norm(up, axis=1, keepdims=True)
            g = u * R + up * TEAR_RISE * taper
            glob = J + g / np.linalg.norm(g, axis=1, keepdims=True) * R
            corner = J + u * R                                        # where lid and globe meet
            out = []
            for t in np.linspace(0.0, 1.0, TEAR_ROWS):
                out.append((1 - t) ** 2 * lid + 2 * t * (1 - t) * (0.6 * corner + 0.2 * (lid + glob))
                           + t ** 2 * glob)
            return np.concatenate(out)

        base = to_blender(rows(D.V))
        faces = [(r * n + i, r * n + i + 1, (r + 1) * n + i + 1, (r + 1) * n + i)
                 for r in range(TEAR_ROWS - 1) for i in range(n - 1)]
        shapes = follower_shapes(rows, base, D, deltas)
        vids = np.concatenate([np.stack([rim, o1], 1)] * TEAR_ROWS)
        w = np.full(vids.shape, 0.5)
        ob = follower(f"tear_line.{side}", base, [], faces, shapes, bone_weights(D, vids, w), head, rig)
        ob.data.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))
        ob.data.materials.append(bpy.data.materials.get("tear_line") or tear_material())
        print(f"[build] tear_line.{side}: {n} margin points, shell radius {R * 1000:.2f} mm, "
              f"{len(shapes)} driven keys")
        made.append(ob)
    return made


GUARD_OFFSET = 0.00012  # m of skin kept over the globe
GUARD_REACH = 0.030     # m from the eye joint


def build_globe_guard(D, head, rig, followers):
    """Keep lid skin outside the globe in every pose, not only the ones a lid key was solved for.

    A shape key is solved for one eye direction, and keys add up in straight lines; the cornea
    bulge travels under the lid with yaw, and under a closing lid with pitch, where no key knows
    about it (0.9 mm through the template's own lid at 30 deg yaw). So each eye gets a hidden copy
    of its outer shell on the eye bone, and the head a Shrinkwrap modifier per eye (nearest
    surface point, "outside" mode) on the lid skin and the lid margin: a vertex is moved only
    while it is inside the globe, and then to GUARD_OFFSET above it. No Python runs; it evaluates
    on the Timeline like the armature does. The pocket behind the margin is left alone (it lies
    under the shell by design). The lash carrier and the tear lines get the same modifier, so a
    lash or the meniscus cannot end up inside the cornea either."""
    made = []
    sock = D.mask("eye_sockets")
    for side, eye in (("L", "left_eye"), ("R", "right_eye")):
        shell = D.mask(eye) & D.mask("eye_exteriors")
        idx = np.where(shell)[0]
        slot = -np.ones(len(D.V), dtype=int)
        slot[idx] = np.arange(len(idx))
        faces = [tuple(int(slot[v]) for v in q) for q in D.d["quads"] if shell[q].all()]
        ob = follower(f"globe_guard.{side}", to_blender(D.V[idx]), [], faces, {},
                      {f"eye.{side}": np.ones(len(idx))}, head, rig)
        ob.hide_render = True
        ob.display_type = "WIRE"
        J = D.joint(side)
        sign = 1.0 if side == "L" else -1.0
        lid = (D.mask("skin") & ~sock & (np.sign(D.V[:, 0]) == sign)
               & (np.linalg.norm(D.V - J, axis=1) < GUARD_REACH))
        rims = lash_gen.lid_rims(D.V, D.d["quads"], sock, D.mask("skin"), D.mask("eyes"), side)
        for rim, _, _ in rims.values():
            lid[rim] = True
        vg = head.vertex_groups.new(name=f"lid_guard.{side}")
        vg.add(np.where(lid)[0].tolist(), 1.0, "REPLACE")
        targets = [(head, vg.name)]
        for f in followers:
            co = np.array([v.co for v in f.data.vertices])
            near = np.where(np.linalg.norm(co - to_blender(J), axis=1) < GUARD_REACH)[0]
            if len(near):
                fg = f.vertex_groups.new(name=f"lid_guard.{side}")
                fg.add(near.tolist(), 1.0, "REPLACE")
                targets.append((f, fg.name))
        for target, group in targets:
            mod = target.modifiers.new(f"globe_guard.{side}", "SHRINKWRAP")
            mod.target = ob
            mod.wrap_method = "NEAREST_SURFACEPOINT"
            mod.wrap_mode = "OUTSIDE"
            mod.offset = GUARD_OFFSET
            mod.vertex_group = group
        print(f"[build] globe_guard.{side}: {len(idx)} shell vertices, {int(lid.sum())} lid vertices, "
              f"on {[t.name for t, _ in targets]}")
        made.append(ob)
    return made


# ---- cameras, light, render settings --------------------------------------------------------

# A camera carries its own look as custom properties; wrapper/eyes.py apply_look() switches the
# lights and the world when that camera renders. `face`: the constant light for whole-face shots
# and the 10 clockwise renders. `eye`: dark background and one small key from the side, for the
# eye close-up and the eye inset in the videos (those cameras also have a shallow depth of field).
LOOKS = {
    "face": dict(lights="key", env=0.24, backdrop=(0.028, 0.028, 0.030)),
    "eye": dict(lights="key_eye", env=0.14, backdrop=(0.0, 0.0, 0.0)),
}


def set_look(cam, look, focus=None, fstop=None):
    cam["look"] = look
    cam["look_lights"] = LOOKS[look]["lights"]
    cam["look_env"] = LOOKS[look]["env"]
    cam["look_backdrop"] = list(LOOKS[look]["backdrop"])
    if focus:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = focus
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.aperture_blades = 0


def aim(ob, target):
    ob.rotation_euler = (target - ob.location).to_track_quat("-Z", "Y").to_euler()


def offset(az, el, dist):
    """Blender-space offset from a point on the face: az > 0 toward the subject's left (+X,
    image right), el up, dist metres out in front (-Y)."""
    a, e = math.radians(az), math.radians(el)
    return dist * Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


def build_cameras_and_light(mid, eye_l, hdri):
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
    set_look(cams["cam_face"], "face")
    set_look(cams["cam_eyes"], "eye", focus=0.40 - 0.0125, fstop=11.0)
    scene.camera = cams["cam_face"]

    # face key: a large soft source up and to image left, so a window-shaped catchlight sits in
    # the upper left of each cornea
    ld = bpy.data.lights.new("key", "AREA")
    ld.shape, ld.size, ld.size_y, ld.energy = "RECTANGLE", 0.45, 0.60, 17.0
    key = bpy.data.objects.new("key", ld)
    key.location = mid + offset(-38.0, 32.0, 0.80)
    aim(key, mid)
    scene.collection.objects.link(key)

    # eye key: small and hard enough that every wet surface glints, from the nose side
    ld = bpy.data.lights.new("key_eye", "AREA")
    ld.shape, ld.size, ld.size_y, ld.energy = "RECTANGLE", 0.10, 0.15, 1.3
    key = bpy.data.objects.new("key_eye", ld)
    key.location = eye_l + offset(-22.0, 18.0, 0.45)
    aim(key, eye_l)
    key.hide_render = True
    scene.collection.objects.link(key)

    # world: the HDRI lights the scene and shows in reflections; the camera sees a plain backdrop
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    bg.name = "env_light"
    bg.inputs["Strength"].default_value = LOOKS["face"]["env"]
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
    back = nt.nodes.new("ShaderNodeBackground")
    back.name = "backdrop"
    back.inputs["Color"].default_value = (*LOOKS["face"]["backdrop"], 1.0)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(back.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs["Surface"])
    scene.world = world
    return cams


INSET_DIST = 0.125      # m from the pupil to cam_inset: a 45 mm wide view


def build_test_cameras(D, rig):
    """The two fixed M3 test shots. face: forehead to chin, straight on. eye: the subject's left
    eye (+X, image right) from 30 deg to that side and 5 deg up, about the "Eye Piece" crop."""
    eyeL = Vector(to_blender(D.pupil("L")))
    mid = Vector(to_blender(D.joints[2:4]).mean(axis=0))
    scene = bpy.context.scene
    out = {}
    for name, target, lens, dist, az, el in (
            ("cam_test_face", mid + Vector((0, -0.01, -0.04)), 85.0, 0.56, 0.0, 0.0),
            ("cam_video", mid + Vector((0, -0.01, -0.04)), 72.0, 0.56, 0.0, 0.0),
            ("cam_test_eye", eyeL, 100.0, 0.11, 30.0, 5.0)):
        cd = bpy.data.cameras.new(name)
        cd.lens, cd.sensor_width, cd.sensor_fit = lens, 36.0, "HORIZONTAL"
        cd.clip_start, cd.clip_end = 0.005, 10.0
        cam = bpy.data.objects.new(name, cd)
        cam.location = target + offset(az, el, dist)
        aim(cam, target)
        scene.collection.objects.link(cam)
        out[name] = cam
    set_look(out["cam_test_face"], "face")
    set_look(out["cam_video"], "face")   # the videos' face: looser, so a turning head stays clear of the inset
    set_look(out["cam_test_eye"], "eye", focus=0.11 + 0.0005, fstop=40.0)

    # cam_inset: the eye close-up that wrapper/eyes.py pastes into the videos. The same view as
    # cam_test_eye from a little further back (room for the lids and lashes to move), riding on
    # the head bone, so the eye stays in frame when the head turns and what shows is the eye
    # moving in the head.
    cd = bpy.data.cameras.new("cam_inset")
    cd.lens, cd.sensor_width, cd.sensor_fit = 100.0, 36.0, "HORIZONTAL"
    cd.clip_start, cd.clip_end = 0.005, 10.0
    cam = bpy.data.objects.new("cam_inset", cd)
    cam.location = eyeL + offset(30.0, 5.0, INSET_DIST)
    aim(cam, eyeL)
    scene.collection.objects.link(cam)
    bone = rig.data.bones["head"]
    cam.parent, cam.parent_type, cam.parent_bone = rig, "BONE", "head"
    # a bone parent is the bone's tail frame; cancel it at rest so the transform above stays world
    cam.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local
                                 @ Matrix.Translation((0.0, bone.length, 0.0))).inverted()
    set_look(cam, "eye", focus=INSET_DIST + 0.0005, fstop=40.0)
    out["cam_inset"] = cam
    return out


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
    build_masks(D, ob)
    build_materials(ob, args.sss)

    eyes = to_blender(D.joints[2:4])
    mid = Vector(eyes.mean(axis=0))
    build_cameras_and_light(mid, Vector(to_blender(D.pupil("L"))), args.hdri)
    build_test_cameras(D, rig)
    build_hair(D, deltas, ob, rig, args.hair)
    tears = build_tear_lines(D, deltas, ob, rig)
    if not args.no_guard:
        build_globe_guard(D, ob, rig, [bpy.data.objects["lashes_carrier"]] + tears)
    scene.cycles_curves.shape = "THICK"     # hair curves as round tubes

    from wrapper.eyes import apply_look, use_texture
    use_texture(args.texture)
    apply_look(scene.camera)

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
