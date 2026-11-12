"""Check renders for the M2 detail maps and eye textures on the bare GNM template.

    $BLENDER -b --factory-startup -P tools/check_detail.py -- \
        --detail outputs/tmp/m2/detail/seed_0 --iris outputs/tmp/m2/iris/brown \
        --out outputs/tmp/m2/check_detail [--skin outputs/tmp/m2/<name>/skin.1001.png]

Grey mode (default): plain grey skin with only the normal and roughness maps, one hard-ish
key light, so relief has to stand on its own (the "Flexpressions" bar). Shots: front,
three-quarter, close on the left eye, close on the lips. With --skin the same shots are
rendered textured (albedo x skin_detail) and a 1024² face shot shows the iris at the size it
has in a face render.

Uses the legacy UV layer: tile 1001 is the legacy skin square, and the eye-interior legacy
UVs equal the UDIM ones minus the tile offset. bpy + numpy only.
"""

import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

REPO = Path(__file__).resolve().parents[1]


def to_blender(p):
    p = np.asarray(p, dtype=np.float64)
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], axis=-1)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", type=Path, required=True)
    ap.add_argument("--iris", type=Path, required=True)
    ap.add_argument("--skin", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=REPO / "outputs/tmp/m2/check_detail")
    ap.add_argument("--samples", type=int, default=192)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--shots", default="front,three_quarter,eye,lips")
    ap.add_argument("--cpu", action="store_true")
    return ap.parse_args(argv)


def setup(args):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    device = "CPU"
    if not args.cpu:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for dev in prefs.devices:
            dev.use = dev.type == "METAL"
        if any(dev.type == "METAL" for dev in prefs.devices):
            device = "GPU"
    scene.cycles.device = device
    scene.cycles.samples = args.samples
    scene.cycles.seed = 0
    scene.cycles.use_denoising = False          # the denoiser smears pores
    scene.render.resolution_x = scene.render.resolution_y = args.size
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("dim")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.12
    scene.world = world
    return scene


def image(path, non_color):
    img = bpy.data.images.load(str(Path(path).resolve()))
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def tex_node(nt, img):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = img
    n.interpolation = "Cubic"
    return n


def skin_material(args):
    mat = bpy.data.materials.new("skin")
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    rough = tex_node(nt, image(args.detail / "skin_rough.1001.png", True))
    nt.links.new(rough.outputs["Color"], b.inputs["Roughness"])
    nrm = tex_node(nt, image(args.detail / "skin_normal.1001.png", True))
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "legacy"
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Specular IOR Level"].default_value = 0.5
    if args.skin is None:
        b.inputs["Base Color"].default_value = (0.30, 0.30, 0.30, 1)
    else:
        alb = tex_node(nt, image(args.skin, False))
        det = tex_node(nt, image(args.detail / "skin_detail.1001.png", True))
        scale = nt.nodes.new("ShaderNodeVectorMath")
        scale.operation = "SCALE"
        scale.inputs["Scale"].default_value = 255.0 / 128.0
        nt.links.new(det.outputs["Color"], scale.inputs[0])
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY"
        nt.links.new(alb.outputs["Color"], mul.inputs[0])
        nt.links.new(scale.outputs[0], mul.inputs[1])
        nt.links.new(mul.outputs[0], b.inputs["Base Color"])
        b.inputs["Subsurface Weight"].default_value = 0.25
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
        b.inputs["Subsurface Scale"].default_value = 0.003
    return mat


def eye_material(name, png):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    t = tex_node(nt, image(png, False))
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    b.inputs["Specular IOR Level"].default_value = 0.1     # under the cornea: nearly diffuse
    return mat


def cornea_material():
    mat = bpy.data.materials.new("cornea")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    glass = nt.nodes.new("ShaderNodeBsdfGlossy")
    glass.inputs["Roughness"].default_value = 0.02
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    fres = nt.nodes.new("ShaderNodeFresnel")
    fres.inputs["IOR"].default_value = 1.376
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fres.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(glass.outputs[0], mix.inputs[2])
    # shadow rays pass straight through, or the cornea shades the iris (TECH_NOTES)
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr2 = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix2 = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], mix2.inputs[0])
    nt.links.new(mix.outputs[0], mix2.inputs[1])
    nt.links.new(tr2.outputs[0], mix2.inputs[2])
    nt.links.new(mix2.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return mat


def flat(name, rgb, rough=0.4):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return mat


def build_head(d, args):
    quads, tiles = d["quads"], d["quad_udim_tiles"]
    V = to_blender(d["template_vertices"])
    me = bpy.data.meshes.new("gnm_template")
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(quads), 4, dtype=np.int32))
    uv = me.uv_layers.new(name="legacy")
    uv.data.foreach_set("uv", d["quad_uvs"].astype(np.float32).ravel())
    me.update(calc_edges=True)
    me.polygons.foreach_set("use_smooth", np.ones(len(quads), dtype=bool))
    ob = bpy.data.objects.new("gnm_template", me)
    bpy.context.collection.objects.link(ob)
    mats = [skin_material(args), cornea_material(),
            eye_material("eye_L", args.iris / "eye.1002.png"), eye_material("eye_R", args.iris / "eye.1004.png"),
            flat("mouth", (0.35, 0.16, 0.14), 0.3)]
    for m in mats:
        me.materials.append(m)
    idx = np.zeros(len(quads), dtype=np.int32)
    idx[np.isin(tiles, (1003, 1005))] = 1
    idx[tiles == 1002] = 2
    idx[tiles == 1004] = 3
    idx[np.isin(tiles, (1006, 1007))] = 4
    me.polygons.foreach_set("material_index", idx)
    return ob


def main():
    args = parse_args()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    scene = setup(args)
    d = np.load(REPO / "assets/gnm/base.npz", allow_pickle=False)
    build_head(d, args)
    names = [str(n) for n in d["vertex_group_names"]]
    masks = d["vertex_group_masks"]
    V = to_blender(d["template_vertices"])
    eyeL = Vector(to_blender(d["joint_positions"][2]))
    eyes = Vector(to_blender(d["joint_positions"][2:4]).mean(0))
    lips = masks[names.index("upper_lip")] | masks[names.index("lower_lip")]
    mouth = Vector(V[lips].mean(0))

    cam_data = bpy.data.cameras.new("cam")
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.01
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    key_data = bpy.data.lights.new("key", "AREA")
    key_data.size = 0.05
    key = bpy.data.objects.new("key", key_data)
    scene.collection.objects.link(key)

    face = eyes + Vector((0, 0, -0.035))
    # name: (target, azimuth deg, elevation deg, distance m, lens mm, light azimuth, light elevation, light W)
    shots = {
        "front": (face, 0, 0, 0.60, 85, -50, 35, 14),
        "three_quarter": (face, 40, 0, 0.60, 85, -30, 35, 14),
        "eye": (eyeL + Vector((0, -0.012, 0.002)), 25, 5, 0.13, 85, -45, 25, 7),
        "lips": (mouth, 15, -5, 0.13, 85, -55, 30, 7),
        "face": (face, 0, 0, 0.42, 50, -35, 30, 10),
        "eye_front": (eyeL + Vector((0, -0.012, 0.0)), 0, 0, 0.11, 85, 20, 30, 6),
        "profile": (face + Vector((0.03, 0.03, 0)), 90, 0, 0.60, 85, 60, 35, 14),
        "back": (face + Vector((0, 0.06, 0.03)), 180, 10, 0.60, 85, 150, 35, 14),
    }
    tag = "grey" if args.skin is None else "tex"
    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.shots.split(","):
        target, az, el, dist, lens, laz, lel, watts = shots[name]
        cam_data.lens = lens

        def direction(a, e):
            a, e = math.radians(a), math.radians(e)
            return Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))

        cam.location = target + dist * direction(az, el)
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        key.location = target + 0.5 * direction(laz, lel)
        key.rotation_euler = (target - key.location).to_track_quat("-Z", "Y").to_euler()
        key_data.energy = watts
        scene.render.filepath = str(args.out / f"{tag}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[check] {scene.render.filepath}")


main()
