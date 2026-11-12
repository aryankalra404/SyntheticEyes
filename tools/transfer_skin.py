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
  skin colour (diffuse colour only) and a hit mask.
Strand eyebrows are not baked: each hair's centreline is projected onto the wrapped skin,
taken to UV and drawn there as a tapered, anti-aliased stroke, with extra hairs seeded
around the modelled ones and a soft shadow underneath. A hair is under a texel wide, so a
ray bake of the strand tubes gives broken, hatched strokes. Card eyebrows (textured) are
still baked. Brows are composited in linear light, texels with no trustworthy source
(inside of the lids, mouth rim, misses) are filled from their neighbours by push-pull, and
the result is written as an 8-bit sRGB PNG. --check renders it on the unwrapped GNM template from front,
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
    ap.add_argument("--brow-shadow", type=float, default=0.45, help="strength of the soft shadow under the brow hair")
    ap.add_argument("--brow-width", type=float, default=0.13, help="strand hair width at the root, mm")
    ap.add_argument("--brow-density", type=float, default=1.4, help="hairs drawn per modelled strand")
    ap.add_argument("--brow-seed", type=int, default=0)
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


def strand_centrelines(V, F):
    """Strand eyebrows are tubes of three-vertex rings; returns one (rings, 3) centreline per hair."""
    parent = list(range(len(V)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for f in F:
        for v in f[1:]:
            ra, rb = find(f[0]), find(v)
            if ra != rb:
                parent[ra] = rb
    groups = {}
    for i in range(len(V)):
        groups.setdefault(find(i), []).append(i)
    lines = []
    for idx in groups.values():
        if len(idx) < 9 or len(idx) % 3:
            continue
        rings = V[np.array(sorted(idx))].reshape(-1, 3, 3)
        if np.abs(rings - rings.mean(1, keepdims=True)).max() > 0.02:     # dm; not a ring layout
            continue
        lines.append(rings.mean(1)[1:])      # the first ring is the root under the skin
    return lines


def surface_uv(co, tris, tri_uv, points):
    """UV of the closest point on a triangle mesh for each point (Blender coordinates)."""
    tree = BVHTree.FromPolygons([Vector(v) for v in co], [tuple(int(i) for i in t) for t in tris])
    out = np.zeros((len(points), 2))
    for i, p in enumerate(points):
        loc, _, k, _ = tree.find_nearest(Vector(p))
        a, b, c = co[tris[k]]
        v0, v1, v2 = b - a, c - a, np.array(loc) - a
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01
        wb, wc = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
        out[i] = (1 - wb - wc) * tri_uv[k, 0] + wb * tri_uv[k, 1] + wc * tri_uv[k, 2]
    return out


def smooth_curve(P, steps=6):
    """Catmull-Rom through the points, so three or four rings become a curved hair."""
    Q = np.concatenate([2 * P[:1] - P[1:2], P, 2 * P[-1:] - P[-2:-1]])
    s = np.linspace(0, 1, steps, endpoint=False)[:, None]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = Q[i], Q[i + 1], Q[i + 2], Q[i + 3]
        out.append(0.5 * (2 * p1 + (p2 - p0) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s ** 2
                          + (3 * p1 - p0 - 3 * p2 + p3) * s ** 3))
    return np.concatenate(out + [P[-1:]])


def draw_hairs(size, hairs):
    """Composites tapered anti-aliased strokes. hairs: (points px (n, 2), root width px, opacity, rgb).

    Returns the transmittance left for the skin and the premultiplied hair colour.
    """
    T = np.ones((size, size), dtype=np.float32)
    C = np.zeros((size, size, 3), dtype=np.float32)
    for P, width, opacity, rgb in hairs:
        pad = 0.5 * width + 2
        x0, y0 = np.maximum(np.floor(P.min(0) - pad).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(P.max(0) + pad).astype(int), size)
        if x1 <= x0 or y1 <= y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        q = np.stack([gx.ravel(), gy.ravel()], 1)
        a, ab = P[:-1], P[1:] - P[:-1]
        seg = np.maximum(np.linalg.norm(ab, axis=1), 1e-9)
        u = np.clip(((q[:, None] - a[None]) * ab[None]).sum(2) / seg[None] ** 2, 0, 1)
        dist = np.linalg.norm(q[:, None] - (a[None] + u[..., None] * ab[None]), axis=2)
        k = dist.argmin(1)
        rows = np.arange(len(q))
        along = (np.concatenate([[0], np.cumsum(seg)[:-1]])[k] + u[rows, k] * seg[k]) / seg.sum()
        half = 0.5 * width * (1 - 0.7 * along ** 2)                 # thinner toward the tip
        alpha = opacity * (1 - 0.5 * along ** 3) * np.clip(half - dist[rows, k] + 0.5, 0, 1)
        alpha = alpha.reshape(gx.shape).astype(np.float32)
        T[y0:y1, x0:x1] *= 1 - alpha
        C[y0:y1, x0:x1] = C[y0:y1, x0:x1] * (1 - alpha[..., None]) + alpha[..., None] * np.asarray(rgb, np.float32)
    return T, C


def strand_brows(args, lines_bl, co, tris, tri_uv, size):
    """Draws strand eyebrows in UV. lines_bl: hair centrelines in Blender coordinates (m)."""
    rng = np.random.default_rng(args.brow_seed)
    counts = [len(p) for p in lines_bl]
    uv = surface_uv(co, tris, tri_uv, np.concatenate(lines_bl))
    px = np.stack([uv[:, 0] * size, (1 - uv[:, 1]) * size], 1)
    base = np.array(args.brow_color, dtype=np.float64)
    hairs, start = [], 0
    for n, P3 in zip(counts, lines_bl):
        P = px[start:start + n]
        start += n
        length_px = np.linalg.norm(np.diff(P, axis=0), axis=1).sum()
        length_m = np.linalg.norm(np.diff(P3, axis=0), axis=1).sum()
        if length_px > 0.2 * size or length_px < 2 or length_m <= 0:      # crosses a UV seam, or degenerate
            continue
        scale = length_px / (length_m * 1000)                             # texels per mm at this hair
        copies = 1 + int(args.brow_density - 1) + (rng.random() < (args.brow_density - 1) % 1)
        stray = rng.random() < 0.3                                        # a short fine hair off the edge
        for c in range(copies + stray):
            Q, thin = P.copy(), 1.0
            if c:                                                         # a neighbour of the modelled hair
                fine = stray and c == copies
                root = Q[0] + rng.normal(0, (1.0 if fine else 0.35) * scale, 2)
                ang = rng.normal(0, math.radians(9 if fine else 5))
                rot = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
                Q = root + (Q - Q[0]) @ rot.T * (rng.uniform(0.4, 0.7) if fine else rng.uniform(0.7, 1.1))
                thin = 0.5 if fine else 1.0
            width = args.brow_width * scale * rng.uniform(0.8, 1.15) * (0.5 + 0.5 * thin)
            tone = base * rng.lognormal(0, 0.3) * (1 + rng.normal(0, 0.05, 3))
            opacity = args.brow_opacity * rng.uniform(0.55, 0.95) * thin
            hairs.append((smooth_curve(Q), width, opacity, np.clip(tone, 0, 1)))
    order = rng.permutation(len(hairs))
    T, C = draw_hairs(size, [hairs[i] for i in order])
    print(f"[transfer] brows: {len(lines_bl)} modelled hairs, {len(hairs)} drawn")
    return T, C


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
        # numpy on Apple silicon raises spurious matmul warnings here; the result is checked instead
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            out = to_blender(s * p @ R.T + t)
        assert np.isfinite(out).all()
        return out

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

    brows = None
    if args.eyebrows != "none":
        folder = mh_core.MH_DIR / args.eyebrows
        bV, bVT, bF, bFT = mh_core.load_proxy(folder, V)
        btex = find_texture(folder)
        if btex is not None and btex.exists():
            # card eyebrows: textured planes, baked
            uvs = np.array([bVT[i] for f in bFT for i in f])
            brows = make_mesh("brows", place(bV), bF, uvs, smooth=False)
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
            hair = bake(target, [brows], new_float_image("brow", size), "EMIT", 16, 0) * args.brow_opacity
            set_material(brows, emission_material("brow_alpha", alpha))
            cover = bake(target, [brows], new_float_image("cover", size), "EMIT", 16, 0)[..., 0]
            through = 1 - np.clip(cover, 0, 1) * args.brow_opacity
        else:
            # strand eyebrows: drawn in UV from the hair centrelines
            co = to_blender(w["vertices"])
            tris = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
            quv = d["quad_uvs"][tile]
            tri_uv = np.concatenate([quv[:, [0, 1, 2]], quv[:, [0, 2, 3]]])
            lines = [place(p) for p in strand_centrelines(bV, bF)]
            through, hair = strand_brows(args, lines, co, tris, tri_uv, size)
        cover = 1 - through
        # skin under a brow is darker than bare skin: a tight and a wide soft shadow of the hair density
        k = size / 4096
        shade = 0.8 * box_blur(cover, max(2, round(6 * k))) + 0.35 * box_blur(cover, max(4, round(20 * k)))
        shade = np.clip(shade * args.brow_shadow, 0, 0.6)
        colour = colour * (1 - shade[..., None]) + shade[..., None] * np.array(args.brow_color, dtype=np.float32)
        colour = colour * through[..., None] + hair
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
    if brows is not None:
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
