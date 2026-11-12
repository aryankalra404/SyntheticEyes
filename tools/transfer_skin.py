"""Bakes a MakeHuman skin (and one eyebrow set) onto GNM's skin tile, headless.

    $BLENDER -b --factory-startup -P tools/transfer_skin.py -- \
        --skin skins01/skins/onlytheghosts_young_eurasian_female \
        --eyebrows eyebrows01/eyebrows/mindfront_eyebrows_01 --name eurasian_f_young

Needs assets/gnm/base.npz (tools/export_gnm.py) and assets/gnm/wrapped_to_mh.npz
(tools/register_mh.py). Uses only bpy + numpy.

Source: MakeHuman head with the skin texture, placed in GNM's frame. Its hidden inner
sheets (eye pockets, mouth cavity) are removed first so no ray can land on them.
Target: GNM skin wrapped onto the MakeHuman head, GNM's own UVs.
Cycles bake, Selected to Active with a cage, into 32-bit float images:
  skin colour (diffuse colour only), a hit mask, brow colour and brow coverage.
Brows are composited in linear light, texels with no trustworthy source (inside of the
lids, mouth rim, misses) are filled from their neighbours by push-pull, and the result is
written as an 8-bit sRGB PNG. --check renders it on the unwrapped GNM template from front,
three-quarter, profile and back.
"""

import argparse
import math
import struct
import sys
import zlib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import mh_core  # noqa: E402

CAGE = 0.003        # m, how far the cage sits outside the wrapped GNM skin
RAY = 0.008         # m, how far a bake ray may travel from the cage


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--skin", required=True, help="skin folder or PNG, relative to assets/third_party/makehuman")
    ap.add_argument("--eyebrows", default="eyebrows01/eyebrows/mindfront_eyebrows_01",
                    help="eyebrow folder relative to assets/third_party/makehuman, or 'none'")
    ap.add_argument("--brow-color", type=float, nargs=3, default=[0.045, 0.028, 0.018],
                    help="linear RGB for strand eyebrows, which have no texture")
    ap.add_argument("--brow-opacity", type=float, default=0.9)
    ap.add_argument("--brow-shadow", type=float, default=1.2, help="strength of the soft shadow under the brow hair")
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", type=Path, default=REPO / "outputs/tmp/m2")
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--margin", type=int, default=16)
    ap.add_argument("--check", action="store_true", help="render four views on the GNM template")
    ap.add_argument("--check-only", action="store_true", help="skip the bake, render an existing PNG")
    return ap.parse_args(argv)


def to_blender(p):
    p = np.asarray(p, dtype=np.float64)
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], axis=-1)


def make_mesh(name, verts, faces, loop_uvs=None, smooth=True):
    """faces: list of index lists (any arity). loop_uvs: (n_loops, 2) in face order."""
    me = bpy.data.meshes.new(name)
    counts = np.array([len(f) for f in faces], dtype=np.int32)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", np.asarray(verts, dtype=np.float32).ravel())
    me.loops.add(int(counts.sum()))
    me.loops.foreach_set("vertex_index", np.concatenate([np.asarray(f, dtype=np.int32) for f in faces]))
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.concatenate([[0], np.cumsum(counts)[:-1]]).astype(np.int32))
    me.polygons.foreach_set("loop_total", counts)
    if loop_uvs is not None:
        uv = me.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", np.asarray(loop_uvs, dtype=np.float32).ravel())
    me.update(calc_edges=True)
    me.polygons.foreach_set("use_smooth", np.full(len(faces), smooth))
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def exterior_faces(V, quads, occluders):
    """True for MakeHuman faces that can be seen from outside the head.

    A face is hidden when rays leaving it along its normal, and tilted around it, all hit
    something within 4 cm. Eyeballs, teeth and tongue are included as occluders, which is
    what closes the eye pockets and the mouth.
    """
    polys = [list(q) for q in quads] + occluders
    tree = BVHTree.FromPolygons([Vector(v) for v in V], polys)
    P = V[quads]
    centre = P.mean(1)
    n = np.cross(P[:, 2] - P[:, 0], P[:, 3] - P[:, 1])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)
    t1 = P[:, 1] - P[:, 0]
    t1 /= np.maximum(np.linalg.norm(t1, axis=1, keepdims=True), 1e-20)
    t2 = np.cross(n, t1)
    out = np.zeros(len(quads), dtype=bool)
    tilt = math.tan(math.radians(40))
    for i in range(len(quads)):
        o = Vector(centre[i] + 0.005 * n[i])
        for a, b in ((0, 0), (tilt, 0), (-tilt, 0), (0, tilt), (0, -tilt)):
            d = Vector(n[i] + a * t1[i] + b * t2[i]).normalized()
            if tree.ray_cast(o, d, 0.4)[0] is None:
                out[i] = True
                break
    return out


def emission_material(name, color_socket_builder):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    color_socket_builder(nt, em.inputs["Color"])
    return mat


def white(nt, socket):
    socket.default_value = (1, 1, 1, 1)


def set_material(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def new_float_image(name, size):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    return img


def pixels(img):
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)[::-1, :, :3]      # top row first


def bake(target, sources, img, kind, samples, margin, selected_to_active=True):
    scene = bpy.context.scene
    scene.cycles.samples = samples
    node = target.data.materials[0].node_tree.nodes["bake_target"]
    node.image = img
    target.data.materials[0].node_tree.nodes.active = node
    bpy.ops.object.select_all(action="DESELECT")
    for s in sources:
        s.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    kw = dict(type=kind, margin=margin, margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES",
              use_selected_to_active=selected_to_active)
    if selected_to_active:
        kw.update(use_cage=True, cage_extrusion=CAGE, max_ray_distance=RAY)
    if kind == "DIFFUSE":
        kw["pass_filter"] = {"COLOR"}
    bpy.ops.object.bake(**kw)
    return pixels(img)


def push_pull(img, valid):
    """Fills invalid texels from their neighbours: average down until full, then pull back up."""
    levels = [(img * valid[..., None], valid.astype(np.float32))]
    while levels[-1][1].shape[0] > 1:
        c, w = levels[-1]
        h, wd = w.shape
        levels.append((c.reshape(h // 2, 2, wd // 2, 2, 3).sum((1, 3)), w.reshape(h // 2, 2, wd // 2, 2).sum((1, 3))))
    c, w = levels[-1]
    filled = c / np.maximum(w, 1e-8)[..., None]
    for c, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(filled, 2, 0), 2, 1)
        # binomial blur so the 2x2 blocks of the coarser level leave no visible grid
        for axis in (0, 1):
            pad = np.pad(up, [(1, 1) if a == axis else (0, 0) for a in range(3)], mode="edge")
            lo = pad[:-2] if axis == 0 else pad[:, :-2]
            hi = pad[2:] if axis == 0 else pad[:, 2:]
            up = 0.25 * lo + 0.5 * up + 0.25 * hi
        own = c / np.maximum(w, 1e-8)[..., None]
        # full weight keeps the texel, partial weight blends toward the fill
        k = np.clip(w, 0, 1)[..., None]
        filled = k * own + (1 - k) * up
    return filled


def box_blur(x, radius, passes=3):
    """Separable box blur, repeated so it is close to a Gaussian."""
    for _ in range(passes):
        for axis in (0, 1):
            pad = np.pad(x, [(radius + 1, radius) if a == axis else (0, 0) for a in range(x.ndim)], mode="edge")
            c = np.cumsum(pad, axis=axis, dtype=np.float64)
            n = x.shape[axis]
            hi = np.take(c, np.arange(2 * radius + 1, 2 * radius + 1 + n), axis=axis)
            lo = np.take(c, np.arange(0, n), axis=axis)
            x = ((hi - lo) / (2 * radius + 1)).astype(np.float32)
    return x


def linear_to_srgb8(x):
    x = np.clip(x, 0, 1)
    s = np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)
    return (s * 255 + 0.5).astype(np.uint8)


def write_png(path, rgb):
    """8-bit RGB PNG with the Sub filter; same bytes for the same pixels."""
    h, w, _ = rgb.shape
    flat = rgb.reshape(h, w * 3)
    raw = np.empty((h, 1 + w * 3), dtype=np.uint8)
    raw[:, 0] = 1
    raw[:, 1:4] = flat[:, :3]
    raw[:, 4:] = flat[:, 3:] - flat[:, :-3]

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"sRGB", b"\x00") + chunk(b"IDAT", zlib.compress(raw.tobytes(), 6)) + chunk(b"IEND", b""))


def find_texture(folder):
    if folder.suffix.lower() == ".png":
        return folder
    for line in next(folder.glob("*.mhmat")).read_text().splitlines():
        if line.startswith("diffuseTexture"):
            return folder / line.split(None, 1)[1].strip()
    return None


def setup_cycles():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"      # bakes are deterministic and quick on the CPU
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.seed = 0
    return scene


def transfer(args, d, name):
    w = np.load(REPO / "assets/gnm/wrapped_to_mh.npz", allow_pickle=False)
    names = [str(n) for n in d["vertex_group_names"]]
    masks = d["vertex_group_masks"]
    size = args.size

    # target: GNM skin tile on the wrapped vertices
    tile = d["quad_udim_tiles"] == 1001
    quads = d["quads"][tile]
    target = make_mesh("gnm_wrapped", to_blender(w["vertices"]), list(quads), d["quad_uvs"][tile].reshape(-1, 2))
    # no source for the lid pockets, the mouth sock and the two rings of inner lip next to it,
    # where rays would land on MakeHuman's painted mouth interior
    sock_v = masks[names.index("mouth_sock")].copy()
    for _ in range(2):
        sock_v[quads[sock_v[quads].any(1)].ravel()] = True
    trust_v = ~(masks[names.index("eye_sockets")] | sock_v)
    # red = trusted source, green = mouth sock and inner lip, blue = lips
    lips_v = masks[names.index("upper_lip")] | masks[names.index("lower_lip")]
    rgba = np.stack([trust_v, sock_v, lips_v, np.ones(len(trust_v))], 1)
    attr = target.data.color_attributes.new("trust", "FLOAT_COLOR", "POINT")
    attr.data.foreach_set("color", rgba.astype(np.float32).ravel())

    def trust_color(nt, socket):
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_name = "trust"
        nt.links.new(a.outputs["Color"], socket)
        t = nt.nodes.new("ShaderNodeTexImage")
        t.name = "bake_target"

    set_material(target, emission_material("target", trust_color))

    # source: MakeHuman head in GNM's frame, hidden sheets removed
    V, VT, F, FT = mh_core.load_head()
    occluders = []
    for g in ("helper-l-eye", "helper-r-eye", "helper-upper-teeth", "helper-lower-teeth", "helper-tongue"):
        occluders += mh_core.load_obj(mh_core.BASE_OBJ, g)[2]
    seen = exterior_faces(V, F, occluders)
    print(f"[transfer] MakeHuman head: {len(F)} quads, {int((~seen).sum())} hidden ones removed")
    s, R, t = float(np.ravel(w["mh_scale"])[0]), w["mh_rotation"], w["mh_translation"]

    def place(p):
        return to_blender(s * p @ R.T + t)

    source = make_mesh("mh_head", place(V), list(F[seen]), VT[FT[seen]].reshape(-1, 2))
    tex_path = find_texture(mh_core.MH_DIR / args.skin)
    skin_img = bpy.data.images.load(str(tex_path))
    skin_mat = bpy.data.materials.new("mh_skin")
    skin_mat.use_nodes = True
    nt = skin_mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = skin_img
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    set_material(source, skin_mat)

    m = args.margin
    colour = bake(target, [source], new_float_image("skin", size), "DIFFUSE", 4, m)
    set_material(source, emission_material("white", white))
    hit = bake(target, [source], new_float_image("hit", size), "EMIT", 1, m)[..., 0]
    regions = bake(target, [], new_float_image("trust", size), "EMIT", 1, m, selected_to_active=False)
    trust, sock, lips = regions[..., 0], regions[..., 1], regions[..., 2]
    source.hide_render = True

    if args.eyebrows != "none":
        folder = mh_core.MH_DIR / args.eyebrows
        bV, bVT, bF, bFT = mh_core.load_proxy(folder, V)
        uvs = np.array([bVT[i] for f in bFT for i in f]) if len(bVT) else None
        brows = make_mesh("brows", place(bV), bF, uvs, smooth=False)
        btex = find_texture(folder)
        if btex is not None and btex.exists():
            bimg = bpy.data.images.load(str(btex))

            def premultiplied(nt, socket):
                tx = nt.nodes.new("ShaderNodeTexImage")
                tx.image = bimg
                mix = nt.nodes.new("ShaderNodeMix")
                mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
                mix.inputs["Factor"].default_value = 1.0
                nt.links.new(tx.outputs["Color"], mix.inputs["A"])
                nt.links.new(tx.outputs["Alpha"], mix.inputs["B"])
                nt.links.new(mix.outputs["Result"], socket)

            def alpha(nt, socket):
                tx = nt.nodes.new("ShaderNodeTexImage")
                tx.image = bimg
                nt.links.new(tx.outputs["Alpha"], socket)

            set_material(brows, emission_material("brow_colour", premultiplied))
            brow_rgb = bake(target, [brows], new_float_image("brow", size), "EMIT", 16, 0)
            set_material(brows, emission_material("brow_alpha", alpha))
            cover = bake(target, [brows], new_float_image("cover", size), "EMIT", 16, 0)[..., 0]
        else:
            set_material(brows, emission_material("brow_white", white))
            cover = bake(target, [brows], new_float_image("cover", size), "EMIT", 16, 0)[..., 0]
            brow_rgb = cover[..., None] * np.array(args.brow_color, dtype=np.float32)
        cover = np.clip(cover, 0, 1) * args.brow_opacity
        # skin under a brow is darker than bare skin: a soft shadow of the hair density
        shade = np.clip(box_blur(cover, max(2, round(size / 4096 * 7))) * args.brow_shadow, 0, 0.6)
        colour = colour * (1 - shade[..., None]) + shade[..., None] * np.array(args.brow_color, dtype=np.float32)
        colour = colour * (1 - cover[..., None]) + brow_rgb * args.brow_opacity
        print(f"[transfer] brows cover {100 * (cover > 0.05).mean():.2f}% of the tile")

    # any texel the inner lip touches is dropped, so no painted teeth leak onto the lip edge
    valid = (hit > 0.5) & (trust > 0.5) & (sock < 0.01)
    # the mouth sock shows when the jaw opens: give it a darkened lip colour, not skin;
    # the band between it and the lips is filled, which grades from lip colour to dark
    lip_colour = colour[valid & (lips > 0.9)].mean(0)
    inside = sock > 0.99
    colour[inside] = 0.45 * lip_colour
    albedo = push_pull(colour, valid | inside)
    out = args.out / name / "skin.1001.png"
    write_png(out, linear_to_srgb8(albedo))
    rgb = linear_to_srgb8(albedo)
    print(f"[transfer] {out.relative_to(REPO)}: {100 * valid.mean():.1f}% of texels from the source, "
          f"rest filled; darkest texel {int(rgb.max(2).min())}, {out.stat().st_size / 1e6:.1f} MB")
    for ob in (target, source):
        bpy.data.objects.remove(ob)
    if args.eyebrows != "none":
        bpy.data.objects.remove(brows)
    return out


def check(args, d, png, name):
    """Four views of the texture on the unwrapped GNM template, plain light, Standard view."""
    scene = bpy.context.scene
    names = [str(n) for n in d["vertex_group_names"]]
    masks = d["vertex_group_masks"]
    quads, tiles = d["quads"], d["quad_udim_tiles"]
    head = make_mesh("gnm_template", to_blender(d["template_vertices"]), list(quads), d["quad_uvs"].reshape(-1, 2))

    skin = bpy.data.materials.new("skin")
    skin.use_nodes = True
    nt = skin.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(png))
    bsdf = nt.nodes["Principled BSDF"]
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6

    def flat(mat_name, rgb, rough=0.4):
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        b = mat.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*rgb, 1)
        b.inputs["Roughness"].default_value = rough
        return mat

    clear = bpy.data.materials.new("cornea")
    clear.use_nodes = True
    cn = clear.node_tree
    cn.nodes.remove(cn.nodes["Principled BSDF"])
    cn.links.new(cn.nodes.new("ShaderNodeBsdfTransparent").outputs[0], cn.nodes["Material Output"].inputs["Surface"])
    for mat in (skin, clear, flat("sclera", (0.80, 0.77, 0.74)), flat("iris", (0.10, 0.06, 0.04)),
                flat("pupil", (0.005, 0.005, 0.005)), flat("mouth", (0.45, 0.25, 0.22))):
        head.data.materials.append(mat)
    idx = np.zeros(len(quads), dtype=np.int32)
    idx[np.isin(tiles, (1003, 1005))] = 1
    interior = np.isin(tiles, (1002, 1004))
    idx[interior] = 2
    idx[interior & masks[names.index("irises")][quads].all(1)] = 3
    idx[interior & masks[names.index("pupils")][quads].all(1)] = 4
    idx[np.isin(tiles, (1006, 1007))] = 5
    head.data.polygons.foreach_set("material_index", idx)

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.seed = 0
    scene.render.resolution_x = scene.render.resolution_y = 900
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("plain")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.75, 0.75, 0.75, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    scene.world = world
    cam_data = bpy.data.cameras.new("check_cam")
    cam_data.lens, cam_data.sensor_width = 85.0, 36.0
    cam = bpy.data.objects.new("check_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    sun_data = bpy.data.lights.new("check_sun", "SUN")
    sun_data.energy, sun_data.angle = 1.6, math.radians(20)
    sun = bpy.data.objects.new("check_sun", sun_data)
    scene.collection.objects.link(sun)

    centre = Vector((0.0, -0.02, 0.255))
    shots = []
    for label, az in (("front", 0), ("three_quarter", 40), ("profile", 90), ("back", 180)):
        a = math.radians(az)
        direction = Vector((math.sin(a), -math.cos(a), 0.0))
        cam.location = centre + 0.92 * direction
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        light_dir = (direction + Vector((-0.35 * math.cos(a), -0.35 * math.sin(a), 0.5))).normalized()
        sun.rotation_euler = (-light_dir).to_track_quat("-Z", "Y").to_euler()
        path = args.out / name / f"check_{label}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(path))
        a8 = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
        img.pixels.foreach_get(a8)
        shots.append((a8.reshape(img.size[1], img.size[0], 4)[::-1, :, :3] * 255 + 0.5).astype(np.uint8))
    sheet = np.concatenate([np.concatenate(shots[:2], 1), np.concatenate(shots[2:], 1)], 0)
    out = args.out / name / "check_sheet.png"
    write_png(out, sheet)
    print(f"[transfer] check sheet {out.relative_to(REPO)}")
    bpy.data.objects.remove(head)


def main():
    args = parse_args()
    name = args.name or Path(args.skin).stem
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    setup_cycles()
    d = np.load(REPO / "assets/gnm/base.npz", allow_pickle=False)
    png = args.out / name / "skin.1001.png" if args.check_only else transfer(args, d, name)
    if args.check or args.check_only:
        check(args, d, png, name)


main()
