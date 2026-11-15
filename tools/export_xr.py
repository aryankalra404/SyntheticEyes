"""Export the hero head for the WebXR page (xr/). Reads scene.blend, never saves it.

    $BLENDER -b scene.blend -P tools/export_xr.py                 # head.glb, rig.json, textures
    $BLENDER -b --factory-startup -P tools/export_xr.py -- --check   # reload head.glb and count

What it writes to xr/assets/:
- head.glb: gnm_head skinned to gnm_rig (neck -> head -> eye.L, eye.R) at rest, the 21 shape keys
  as named morph targets with morph normals, UV layers UDIM (folded into 0..1 per material, as
  TEXCOORD_0) and legacy (TEXCOORD_1), one primitive per material slot named after the slot.
  No animation, no modifier applied (the globe guard shrinkwraps cannot be exported), plain
  placeholder materials: xr/js/app.js builds the real ones.
  Also (stage F of docs/BRIEF_M14.md): `lashes`, a ribbon per lash built from lashes_carrier
  (430 polylines of 7 points: the same points the scene's curves are made from, with their
  skin weights and the 21 shape keys, so they follow the lids), widened LASH_WIDTH times
  because a lash at its real 0.1 mm is a fraction of a headset pixel at 0.7 m; and the two
  tear_line strips as they are in the scene (skinned, their side's keys).
- rig.json: what xr/js/rig.js needs, in the glTF frame (see "axes" in the file): eye centres,
  bone heads, the rig constants read from wrapper/rig.py and the motion numbers from
  wrapper/gaze/engine.py GazeParams.
- textures from textures/tex_09: skin albedo and normal at 2048, roughness and eyes at 1024.

Everything is changed in memory only (animation cleared, pose at rest, keys at 0, UVs folded,
materials flattened); the script never calls save, so scene.blend on disk is untouched.
"""

import dataclasses
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "xr" / "assets"
TEX = REPO / "textures" / "tex_09"
sys.path.insert(0, str(REPO))

# (source, output, size, format, quality)
TEXTURES = (
    ("skin.1001.png", "skin_albedo.jpg", 2048, "JPEG", 90),
    ("skin_normal.1001.png", "skin_normal.png", 2048, "PNG", 0),
    ("skin_rough.1001.png", "skin_rough.jpg", 1024, "JPEG", 92),
    ("eye.1002.png", "eye_L.jpg", 1024, "JPEG", 92),
    ("eye.1004.png", "eye_R.jpg", 1024, "JPEG", 92),
)
LASH_WIDTH = 1.5        # ribbon width = this x the carrier's hair_radius x 2 (2.5 read as mascara)
AXES = ("glTF frame, metres, Y up. glTF +X = Blender +X = image-right (the subject's left); "
        "glTF +Y = Blender +Z = up; glTF +Z = Blender -Y = toward the viewer (the face looks "
        "along +Z). Point map: (x, y, z)_gltf = (x, z, -y)_blender.")


def to_gltf(v):
    return [float(v[0]), float(v[2]), -float(v[1])]


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return set(argv)


# ---- export ---------------------------------------------------------------------------------

def prepare():
    """Rest pose, keys at 0, no animation, UDIM folded, flat materials. In memory only."""
    arm = bpy.data.objects["gnm_rig"]
    head = bpy.data.objects["gnm_head"]
    for idb in (arm, head.data.shape_keys):
        if idb.animation_data:
            idb.animation_data_clear()
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    for kb in head.data.shape_keys.key_blocks:
        kb.value = 0.0
    head.data.shape_keys.key_blocks[0].value = 0.0

    # Fold the UDIM layer per face: tile 100N sits at u in [N-1, N]; take the face's mean tile so
    # a face touching a tile edge keeps all its corners on one side.
    me = head.data
    uv = np.zeros(len(me.loops) * 2)
    me.uv_layers["UDIM"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    ls = np.zeros(len(me.polygons), int)
    lt = np.zeros(len(me.polygons), int)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    face_of_loop = np.repeat(np.arange(len(me.polygons)), lt)
    mean_u = np.bincount(face_of_loop, weights=uv[:, 0]) / lt
    uv[:, 0] -= np.floor(mean_u)[face_of_loop]
    me.uv_layers["UDIM"].data.foreach_set("uv", uv.ravel())
    me.uv_layers.active = me.uv_layers["UDIM"]
    for i, layer in enumerate(me.uv_layers):
        layer.active_render = layer.name == "UDIM"

    for slot in head.material_slots:
        if slot.material:
            slot.material.use_nodes = False
    bpy.context.view_layer.update()
    return arm, head


def lash_ribbons(arm):
    """A mesh `lashes`: two vertices per carrier point, offset along the lid's tangent (round the
    eye in the frontal plane), quads between neighbours; skin weights and key offsets copied."""
    car = bpy.data.objects["lashes_carrier"]
    me = car.data
    n = len(me.vertices)
    co = np.zeros(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    rad = np.zeros(n)
    me.attributes["hair_radius"].data.foreach_get("value", rad)
    adj = [[] for _ in range(n)]
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)
    seen = np.zeros(n, bool)
    chains = []
    for v in range(n):
        if len(adj[v]) != 1 or seen[v]:
            continue
        chain, prev, cur = [v], -1, v
        seen[v] = True
        while True:
            nxt = [w for w in adj[cur] if w != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            chain.append(cur)
            seen[cur] = True
        if rad[chain[-1]] > rad[chain[0]]:      # roots are the thick end
            chain.reverse()
        chains.append(chain)
    eye = {s: np.array(arm[f"eye_rest_{s}"]) for s in ("L", "R")}
    fwd = np.array([0.0, -1.0, 0.0])
    verts, faces, src, along = [], [], [], []
    for chain in chains:
        root = co[chain[0]]
        c = eye["L"] if root[0] > 0 else eye["R"]
        base = len(verts)
        for i, v in enumerate(chain):
            w = np.cross(fwd, co[v] - c)
            w /= max(np.linalg.norm(w), 1e-9)
            half = rad[v] * LASH_WIDTH
            verts += [co[v] - w * half, co[v] + w * half]
            src += [v, v]
            along += [i / (len(chain) - 1)] * 2
            if i:
                a = base + 2 * (i - 1)
                faces.append((a, a + 1, a + 3, a + 2))
    src = np.array(src)
    rib = bpy.data.meshes.new("lashes")
    rib.from_pydata([tuple(p) for p in verts], [], faces)
    rib.shade_smooth()                          # no split vertices: half the morph data
    # UV: u across the ribbon (0, 1), v from root (0) to tip (1). The page fades the ribbon's
    # edges and its tip with an alpha map over this, so a lash reads as a soft strand and not
    # as a flat black wedge. One UV per vertex, so nothing splits.
    uv = rib.uv_layers.new(name="UVMap")
    for poly in rib.polygons:
        for li in poly.loop_indices:
            vi = rib.loops[li].vertex_index
            uv.data[li].uv = (vi % 2, along[vi])
    mat = bpy.data.materials.new("lashes")
    rib.materials.append(mat)
    ob = bpy.data.objects.new("lashes_xr", rib)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = arm
    mod = ob.modifiers.new("rig", "ARMATURE")
    mod.object = arm
    for g in car.vertex_groups:
        if g.name.startswith("lid_guard"):
            continue
        ng = ob.vertex_groups.new(name=g.name)
        for i, v in enumerate(src):
            try:
                wgt = g.weight(int(v))
            except RuntimeError:
                continue
            ng.add([i], wgt, "REPLACE")
    keys = me.shape_keys.key_blocks
    basis = np.zeros(n * 3)
    keys[0].data.foreach_get("co", basis)
    basis = basis.reshape(-1, 3)
    ob.shape_key_add(name="Basis")
    rco = np.array(verts)
    for kb in keys[1:]:
        k = np.zeros(n * 3)
        kb.data.foreach_get("co", k)
        off = k.reshape(-1, 3) - basis
        nk = ob.shape_key_add(name=kb.name, from_mix=False)
        nk.slider_min, nk.slider_max = kb.slider_min, kb.slider_max
        nk.data.foreach_set("co", (rco + off[src]).ravel())
        nk.value = 0.0
    print(f"[export_xr] lashes: {len(chains)} ribbons, {len(verts)} vertices, "
          f"{len(keys) - 1} keys, width x{LASH_WIDTH}")
    return ob


def tear_lines():
    out = []
    for s in ("L", "R"):
        ob = bpy.data.objects.get(f"tear_line.{s}")
        if ob is None:
            continue
        sk = ob.data.shape_keys
        if sk:
            if sk.animation_data:
                sk.animation_data_clear()        # drivers from the head keys; in memory only
            for kb in sk.key_blocks:
                kb.value = 0.0
        for slot in ob.material_slots:
            if slot.material:
                slot.material.use_nodes = False
        out.append(ob)
    return out


def export_glb(arm, head, extra=()):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for ob in (arm, head, *extra):
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.select_set(True)
    bpy.context.view_layer.objects.active = head
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / "head.glb"), export_format="GLB", use_selection=True,
        export_yup=True, export_apply=False, export_texcoords=True, export_normals=True,
        export_tangents=False, export_materials="EXPORT", export_image_format="NONE",
        export_skins=True, export_def_bones=False, export_all_influences=False,
        export_morph=True, export_morph_normal=True, export_morph_tangent=False,
        export_animations=False, export_cameras=False, export_lights=False, export_extras=False,
        export_try_sparse_sk=True)
    print(f"[export_xr] head.glb {(OUT / 'head.glb').stat().st_size / 1e6:.2f} MB")


def write_rig(arm, head):
    import wrapper.rig as rig   # constants only; importing it poses nothing
    from wrapper.gaze.engine import GazeParams

    def vg_centre(name):
        gi = head.vertex_groups[name].index
        pts = [v.co for v in head.data.vertices if any(g.group == gi for g in v.groups)]
        c = sum(pts, pts[0] * 0) / len(pts)
        return to_gltf(c)

    bones = {}
    for b in arm.data.bones:
        bones[b.name] = dict(parent=b.parent.name if b.parent else None,
                             head=to_gltf(b.head_local))
    data = dict(
        axes=AXES,
        source="scene.blend (gnm_rig, gnm_head) via tools/export_xr.py",
        eye_rest_L=to_gltf(arm["eye_rest_L"]), eye_rest_R=to_gltf(arm["eye_rest_R"]),
        eye_mid=to_gltf(arm["eye_mid"]),
        pupil_rest_L=vg_centre("pupil_L"), pupil_rest_R=vg_centre("pupil_R"),
        rest_pupil=float(arm["rest_pupil"]), rest_lid_open=float(arm.get("rest_lid_open", 0.0)),
        blink_keys=str(arm.get("blink_keys", "single")),
        bones=bones,
        shape_keys=[k.name for k in head.data.shape_keys.key_blocks[1:]],
        constants=dict(NECK_SHARE=rig.NECK_SHARE, LID_UP_FULL=rig.LID_UP_FULL,
                       LID_DOWN_FULL=rig.LID_DOWN_FULL, LID_SIDE_FULL=rig.LID_SIDE_FULL,
                       LID_FOLLOW_MAX=rig.LID_FOLLOW_MAX, WIDEN_GAIN=rig.WIDEN_GAIN,
                       BLINK_BROW_DIP=rig.BLINK_BROW_DIP),
        gaze_params={k: (list(v) if isinstance(v, tuple) else v)
                     for k, v in dataclasses.asdict(GazeParams()).items()},
    )
    (OUT / "rig.json").write_text(json.dumps(data, indent=1) + "\n")
    print("[export_xr] rig.json written")


def write_textures():
    for src, dst, size, fmt, q in TEXTURES:
        img = bpy.data.images.load(str(TEX / src), check_existing=False)
        img.colorspace_settings.name = "Non-Color"     # pass the bytes through untouched
        if img.size[0] != size:
            img.scale(size, size)
        img.file_format = fmt
        path = OUT / dst
        if fmt == "JPEG":
            img.save(filepath=str(path), quality=q)
        else:
            img.save(filepath=str(path))
        bpy.data.images.remove(img)
        print(f"[export_xr] {dst} {size}px {path.stat().st_size / 1e6:.2f} MB")


# ---- check ----------------------------------------------------------------------------------

def check():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(OUT / "head.glb"), merge_vertices=True)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    # the importer makes an icosphere as the bones' display shape; it is not in the file
    shapes = {pb.custom_shape for a in arms for pb in a.pose.bones if pb.custom_shape}
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o not in shapes]
    others = {o.name: (len(o.data.vertices), len(o.data.shape_keys.key_blocks) - 1 if o.data.shape_keys else 0)
              for o in meshes if o.name != "gnm_head"}
    print(f"[export_xr check] other meshes (vertices, keys): {others}")
    meshes = [o for o in meshes if o.name == "gnm_head"]
    nv = sum(len(o.data.vertices) for o in meshes)
    keys = [k.name for o in meshes if o.data.shape_keys for k in o.data.shape_keys.key_blocks[1:]]
    bones = [b.name for a in arms for b in a.data.bones]
    rig = json.loads((OUT / "rig.json").read_text())
    ok = (nv == 17821 and len(bones) == 4 and keys == rig["shape_keys"] and len(keys) == 21)
    print(f"[export_xr check] meshes={[o.name for o in meshes]} vertices={nv} bones={bones} "
          f"morph targets={len(keys)} names match rig.json={keys == rig['shape_keys']} "
          f"uv={[u.name for o in meshes for u in o.data.uv_layers]}")
    print("[export_xr check]", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)


def main():
    a = args()
    if "--check" in a:
        check()
        return
    arm, head = prepare()
    extra = [] if "--no-lashes" in a else [lash_ribbons(arm), *tear_lines()]
    bpy.context.view_layer.update()
    export_glb(arm, head, extra)
    write_rig(arm, head)
    if "--no-textures" not in a:
        write_textures()


main()
