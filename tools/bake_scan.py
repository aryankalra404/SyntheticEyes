"""Bakes the Infinite head scan's displacement map into GNM's skin tile, headless.

    $BLENDER -b --factory-startup -P tools/bake_scan.py [-- --colour]

Needs assets/gnm/base.npz, assets/gnm/wrapped_to_scan.npz (tools/register_scan.py) and the
scan in assets/third_party/lpshead/files/ ("Infinite, 3D Head Scan by Lee Perry-Smith",
CC BY 3.0). Uses only bpy + numpy.

Source: the scan mesh in GNM's frame with bump.png as an emission texture. Target: GNM skin
wrapped onto the scan, GNM's own UVs. Same cage bake as tools/transfer_skin.py, 16 samples so
the denser source map is averaged, not point-sampled. Writes assets/gnm/scan_height.npz:
`height` (float32, raw map value, mid-grey = no displacement) and `hit` (bool), top row first.
--colour also bakes the scan's colour map and renders it on the GNM template from four
angles into outputs/tmp/scan/, to check that features land where they should. That image is
a check only; the scan's colour is not used.
"""

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import mh_core  # noqa: E402
import transfer_skin as ts  # noqa: E402

SCAN = REPO / "assets/third_party/lpshead/files"
OUT = REPO / "assets/gnm/scan_height.npz"


def image_emission(path, colorspace):
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = colorspace

    def build(nt, socket):
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        nt.links.new(tx.outputs["Color"], socket)

    return ts.emission_material(path.stem, build)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--colour", action="store_true", help="also bake the colour map and render a check")
    args = ap.parse_args(argv)

    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    ts.setup_cycles()
    d = np.load(REPO / "assets/gnm/base.npz", allow_pickle=False)
    w = np.load(REPO / "assets/gnm/wrapped_to_scan.npz", allow_pickle=False)
    tile = d["quad_udim_tiles"] == 1001
    target = ts.make_mesh("gnm_wrapped", ts.to_blender(w["vertices"]), list(d["quads"][tile]),
                          d["quad_uvs"][tile].reshape(-1, 2))

    def with_target(nt, socket):
        socket.default_value = (1, 1, 1, 1)
        nt.nodes.new("ShaderNodeTexImage").name = "bake_target"

    ts.set_material(target, ts.emission_material("target", with_target))

    V, VT, F, FT = mh_core.load_obj(SCAN / "head.OBJ")
    s, R, t = float(np.ravel(w["scan_scale"])[0]), w["scan_rotation"], w["scan_translation"]
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        placed = ts.to_blender(s * V @ R.T + t)
    assert np.isfinite(placed).all()
    source = ts.make_mesh("scan", placed, F, np.array([VT[i] for ft in FT for i in ft]))

    ts.set_material(source, image_emission(SCAN / "bump.png", "Non-Color"))
    height = ts.bake(target, [source], ts.new_float_image("height", args.size), "EMIT", args.samples, 0)[..., 0]
    ts.set_material(source, ts.emission_material("white", ts.white))
    hit = ts.bake(target, [source], ts.new_float_image("hit", args.size), "EMIT", 1, 0)[..., 0] > 0.5
    np.savez_compressed(OUT, height=height.astype(np.float32), hit=hit)
    print(f"[scan] {OUT.relative_to(REPO)}: {100 * hit.mean():.1f}% of the tile hit, "
          f"height {height[hit].min():.3f} .. {height[hit].max():.3f}, mean {height[hit].mean():.3f}")

    if args.colour:
        ts.set_material(source, image_emission(SCAN / "lambertian.jpg", "sRGB"))
        colour = ts.bake(target, [source], ts.new_float_image("colour", args.size), "EMIT", 4, 16)
        out = REPO / "outputs/tmp/scan/check"
        png = out / "skin.1001.png"
        ts.write_png(png, ts.linear_to_srgb8(colour))
        for ob in (target, source):
            bpy.data.objects.remove(ob)
        ts.check(argparse.Namespace(out=REPO / "outputs/tmp/scan"), d, png, "check")


if __name__ == "__main__":
    main()
