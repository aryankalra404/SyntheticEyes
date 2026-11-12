"""M0 smoke render: untextured GNM head from assets/gnm/base.npz, headless.

    $BLENDER -b --factory-startup -P tools/smoke_render.py
    $BLENDER -b --factory-startup -P tools/smoke_render.py -- --bench

Builds the mesh (UDIM + legacy UV layers), a 4-bone armature from GNM joints and
skin weights, and blink shape keys when base.npz has delta_blink_L/R. Grey material,
one area light, camera 40 cm in front of the eye midpoint, 1024x1024, Cycles on the
Metal GPU. Writes to outputs/spike/:

    neutral.png  blink_L.png  blink_R.png  gaze_left15.png  gaze_up15.png

and prints the projected pupil centres so the gaze direction can be checked in
numbers as well as by eye. --bench times a neutral frame at 64/128/256 samples.

GNM is +Y up / +Z forward; Blender is +Z up / -Y forward: (x, y, z) -> (x, -z, y).
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[1]


def to_blender(p):
    p = np.asarray(p, dtype=np.float64)
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], axis=-1)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", type=Path, default=REPO / "assets/gnm/base.npz")
    ap.add_argument("--out", type=Path, default=REPO / "outputs/spike")
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--cpu", action="store_true")
    return ap.parse_args(argv)


def setup_cycles(scene, samples, cpu):
    scene.render.engine = "CYCLES"
    device = "CPU"
    if not cpu:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == "METAL"]
        for d in prefs.devices:
            d.use = d.type == "METAL"
        if gpus:
            device = "GPU"
    scene.cycles.device = device
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    return device


def build_mesh(d):
    verts = to_blender(d["vertices"])
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
    me.update(calc_edges=True)
    me.validate()
    me.polygons.foreach_set("use_smooth", np.ones(len(quads), dtype=bool))
    ob = bpy.data.objects.new("gnm_head", me)
    bpy.context.collection.objects.link(ob)
    return ob


def build_rig(d, ob):
    names = [str(n) for n in d["joint_names"]]
    parents = d["joint_parents"]
    joints = to_blender(d["joint_positions"])
    arm = bpy.data.armatures.new("gnm_rig")
    rig = bpy.data.objects.new("gnm_rig", arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = {}
    for i, n in enumerate(names):
        b = arm.edit_bones.new(n)
        b.head = Vector(joints[i])
        length = 0.012 if "eye" in n else 0.05
        # eyes point forward (-Y), neck/head point up (+Z)
        b.tail = b.head + (Vector((0, -length, 0)) if "eye" in n else Vector((0, 0, length)))
        b.roll = 0.0
        if parents[i] >= 0:
            b.parent = ebones[names[parents[i]]]
        ebones[n] = b
    bpy.ops.object.mode_set(mode="OBJECT")
    w = d["skinning_weights"]
    for i, n in enumerate(names):
        vg = ob.vertex_groups.new(name=n)
        nz = np.where(w[i] > 0)[0]
        for wv in np.unique(w[i][nz]):
            vg.add(nz[w[i][nz] == wv].tolist(), float(wv), "REPLACE")
    mod = ob.modifiers.new("rig", "ARMATURE")
    mod.object = rig
    ob.parent = rig
    return rig


def build_shape_keys(d, ob):
    keys = [k[len("delta_"):] for k in d.files if k.startswith("delta_")]
    if not keys:
        return []
    ob.shape_key_add(name="Basis", from_mix=False)
    base = to_blender(d["vertices"])
    for k in keys:
        sk = ob.shape_key_add(name=k, from_mix=False)
        sk.slider_max = 3.0
        co = base + to_blender(d[f"delta_{k}"])
        sk.data.foreach_set("co", co.astype(np.float32).ravel())
    return keys


def build_scene(d):
    scene = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    ob = build_mesh(d)
    rig = build_rig(d, ob)
    keys = build_shape_keys(d, ob)

    # Plain greys, plus a see-through cornea and darker iris/pupil so gaze reads by eye.
    def grey(name, v):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (v, v, v, 1)
        bsdf.inputs["Roughness"].default_value = 0.5
        ob.data.materials.append(mat)

    def clear(name):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.remove(nt.nodes["Principled BSDF"])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        nt.links.new(tr.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
        ob.data.materials.append(mat)

    grey("grey", 0.5)       # 0
    clear("cornea")         # 1
    grey("iris", 0.15)      # 2
    grey("pupil", 0.01)     # 3
    names = [str(n) for n in d["vertex_group_names"]]
    masks = d["vertex_group_masks"]
    q = d["quads"]
    idx = np.zeros(len(q), dtype=np.int32)
    tiles = d["quad_udim_tiles"]
    idx[np.isin(tiles, (1003, 1005))] = 1
    interior = np.isin(tiles, (1002, 1004))
    idx[interior & masks[names.index("irises")][q].all(1)] = 2
    idx[interior & masks[names.index("pupils")][q].all(1)] = 3
    ob.data.polygons.foreach_set("material_index", idx)

    eyes = to_blender(d["joint_positions"][2:4])
    mid = Vector(eyes.mean(axis=0))

    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = 50.0, 36.0, "HORIZONTAL"
    cam_data.clip_start = 0.01
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = mid + Vector((0, -0.40, 0))
    cam.rotation_euler = (math.pi / 2, 0, 0)  # looks along +Y at the face
    scene.collection.objects.link(cam)
    scene.camera = cam

    light_data = bpy.data.lights.new("key", "AREA")
    light_data.size, light_data.energy = 0.3, 6.0
    light = bpy.data.objects.new("key", light_data)
    light.location = mid + Vector((-0.25, -0.40, 0.25))
    light.rotation_euler = (mid - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(light)

    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)
    scene.world = world
    return ob, rig, keys, cam


def set_gaze(rig, yaw_deg, pitch_deg):
    """Rotate both eye bones about their heads. yaw>0 = image-right, pitch>0 = up."""
    rot = (Matrix.Rotation(math.radians(yaw_deg), 4, "Z")
           @ Matrix.Rotation(math.radians(-pitch_deg), 4, "X"))
    for n in ("left_eye", "right_eye"):
        pb = rig.pose.bones[n]
        head = pb.bone.head_local
        pb.matrix = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ pb.bone.matrix_local
    bpy.context.view_layer.update()


def pupil_centres_px(ob, cam, d):
    names = [str(n) for n in d["vertex_group_names"]]
    masks = d["vertex_group_masks"]
    pupils = masks[names.index("pupils")]
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    ob.evaluated_get(dg).to_mesh_clear()
    out = {}
    scene = bpy.context.scene
    for side in ("left_eye", "right_eye"):
        p = co[pupils & masks[names.index(side)]].mean(axis=0)
        v = world_to_camera_view(scene, cam, ob.matrix_world @ Vector(p))
        out[side] = (round(v.x * 1024, 2), round((1 - v.y) * 1024, 2))  # origin top-left
    return out


def render(path):
    bpy.context.scene.render.filepath = str(path)
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    return time.perf_counter() - t


def main():
    args = parse_args()
    d = np.load(args.npz, allow_pickle=False)
    scene = bpy.context.scene
    device = setup_cycles(scene, args.samples, args.cpu)
    ob, rig, keys, cam = build_scene(d)
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"[smoke] Blender {bpy.app.version_string}, device {device}, shape keys {keys}")

    if args.bench:
        render(args.out / "bench_warmup.png")  # kernel load / BVH build
        for s in (64, 128, 256):
            scene.cycles.samples = s
            times = [render(args.out / f"bench_{s}.png") for _ in range(2)]
            print(f"[bench] {s} samples: {min(times):.2f} s (runs {', '.join(f'{x:.2f}' for x in times)})")
        return

    spike = args.npz.parent / "blink_spike.json"
    close = json.loads(spike.read_text()) if spike.exists() else {}
    shots = [("neutral", None, 1.0, (0, 0))]
    for k in ("blink_L", "blink_R"):
        if k in keys:
            shots.append((k, k, 1.0, (0, 0)))
            s = (close.get(k) or {}).get("scale_to_close")
            if s and s != 1.0:  # weight that actually closes the lid
                shots.append((f"{k}_x{s}", k, s, (0, 0)))
        else:
            print(f"[smoke] skip {k}: no delta_{k} in {args.npz.name} (blink spike not run)")
    shots += [("gaze_left15", None, 1.0, (-15, 0)), ("gaze_up15", None, 1.0, (0, 15))]

    base_px = None
    for name, key, weight, (yaw, pitch) in shots:
        for kb in (ob.data.shape_keys.key_blocks if ob.data.shape_keys else []):
            kb.value = weight if kb.name == key else 0.0
        set_gaze(rig, yaw, pitch)
        px = pupil_centres_px(ob, cam, d)
        base_px = base_px or px
        shift = {s: (round(px[s][0] - base_px[s][0], 2), round(px[s][1] - base_px[s][1], 2)) for s in px}
        sec = render(args.out / f"{name}.png")
        print(f"[smoke] {name}: {sec:.2f} s, pupil px {px}, shift vs neutral {shift}")


main()
