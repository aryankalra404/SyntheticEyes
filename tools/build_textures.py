"""Assembles the shipped texture sets, textures/tex_01 ... tex_09 (M2 section 5).

    python3 tools/build_textures.py                 # all sets
    python3 tools/build_textures.py --sets 03 07    # some
    python3 tools/build_textures.py --sets 03 --skip-bake --skip-check
    python3 tools/build_textures.py --sheet-only    # outputs/stills/texture_sheet.png

Per set, from the recipe table below:
  1. tools/transfer_skin.py (Blender) bakes the MakeHuman skin + strand eyebrows into tile 1001
     -> outputs/tmp/m2/sets/tex_NN/skin.1001.png (raw bake, not shipped). A set with scan=True
     takes its colour from the Infinite head scan instead (tools/bake_scan.py --albedo; needs
     tools/register_scan.py to have run) and keeps the scan's own eyebrows.
  2. tools/detail_maps.py --seed S -> normal, roughness, albedo-detail maps
  3. tools/make_iris.py --color C --seed S -> eye.1002.png (left), eye.1004.png (right)
  4. optional tone adjustment of the bake (saturation, hue shift, gain, in linear light),
     then albedo x detail in linear light (detail_maps.apply_albedo_detail) -> skin.1001.png
  5. legacy/ copies under per-region names, set.json
  6. tools/check_detail.py --wrap on the shipped files (the judges' view): front,
     three-quarter, profile, back -> outputs/tmp/m2/sets/tex_NN/wrap_*.png; the front
     becomes preview.png

The wrap test reads skin.1001.png with the detail already in it, so it is given a flat
skin_detail (128 = x1) next to the set's normal and roughness maps. Same arguments, same
bytes for every texture file (renders are Cycles and may differ in noise).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tex_core as tc  # noqa: E402
import detail_maps  # noqa: E402

REPO = tc.REPO
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
MH = "assets/third_party/makehuman"
WORK = REPO / "outputs/tmp/m2/sets"
TEX = REPO / "textures"

# Brow colours are linear RGB. Detail flags are multipliers on detail_maps.py's defaults.
# tone (optional): saturation about each texel's luminance (1 = unchanged), hue rotation in
# degrees about the grey axis (+ turns red toward yellow), gain; applied to the bake in linear
# light before the detail layer, so brows and lips shift with the skin.
# identity: the GNM IdentitySampler settings these textures are paired with for stills
# (ethnicity is the sampler's class name; South Asian has no class of its own, closest is
# MIDDLE_EASTERN).
SETS = {
    "01": dict(
        label="young woman, light skin, hazel eyes",
        skin="skins01/skins/onlytheghosts_young_eurasian_female",
        eyebrows="eyebrows01/eyebrows/mindfront_eyebrows_01",
        brow=dict(color=[0.060, 0.038, 0.024], opacity=0.85, width=0.12, density=1.4, shadow=0.40),
        iris="hazel", seed=1,
        detail={},
        identity=dict(gender="female", ethnicity="white", seed=1)),
    "02": dict(
        label="young woman, South Asian, medium brown skin, dark brown eyes",
        skin="skins01/skins/cutoff3d_indian_female_skin",
        eyebrows="eyebrows01/eyebrows/mindfront_eyebrows_05",
        brow=dict(color=[0.022, 0.015, 0.011], opacity=0.8, width=0.11, density=1.3, shadow=0.35),
        iris="dark_brown", seed=2,
        detail={"redness": 0.8},
        # the source bakes light-medium (cheek Y 0.34); taken to medium brown, Y 0.15
        tone=dict(saturation=1.3, hue=0.0, gain=0.44),
        identity=dict(gender="female", ethnicity="middle_eastern", seed=2)),
    "03": dict(
        label="middle-aged man, Black, dark brown eyes",
        skin="skins02/skins/mindfront_skin_male_african_middleage",
        eyebrows="eyebrows01/eyebrows/mindfront_eyebrows_08",
        brow=dict(color=[0.012, 0.009, 0.007], opacity=0.9, width=0.14, density=1.6, shadow=0.45),
        iris="dark_brown", seed=3,
        detail={"redness": 0.5, "pore_strength": 1.15, "lid_lines": 1.3, "micro_strength": 1.15},
        identity=dict(gender="male", ethnicity="black", seed=3)),
    "04": dict(
        label="old man, light skin, blue eyes, ash brows",
        skin="skins02/skins/onlytheghosts_old_eurasian_male",
        eyebrows="eyebrows01/eyebrows/mindfront_eyebrows_05",
        brow=dict(color=[0.075, 0.062, 0.050], opacity=0.7, width=0.12, density=1.3, shadow=0.25),
        iris="blue", seed=4,
        detail={"pore_strength": 1.15, "lid_lines": 1.6, "micro_strength": 1.3},
        identity=dict(gender="male", ethnicity="white", seed=4)),
    "05": dict(
        label="young man, East Asian, brown eyes",
        skin=f"makehuman_system_assets/skins/young_asian_male",
        eyebrows="eyebrows01/eyebrows/mindfront_eyebrows_08",
        brow=dict(color=[0.014, 0.011, 0.009], opacity=0.75, width=0.12, density=1.2, shadow=0.35),
        iris="brown", seed=5,
        detail={"pore_strength": 1.1, "freckles": 0.5},
        identity=dict(gender="male", ethnicity="asian", seed=5)),
    "06": dict(
        label="old woman, Black, deep brown skin, brown eyes",
        skin="makehuman_system_assets/skins/old_african_female",
        eyebrows="eyebrows01/eyebrows/mindfront_eyebrows_01",
        brow=dict(color=[0.010, 0.007, 0.006], opacity=0.9, width=0.13, density=1.5, shadow=0.45),
        iris="brown", seed=6,
        detail={"redness": 0.5, "lid_lines": 1.6, "micro_strength": 1.3},
        # the source is a saturated red-brown (cheek sRGB 96/39/20); to deep brown, about 86/53/37
        tone=dict(saturation=0.6, hue=6.0, gain=1.1),
        identity=dict(gender="female", ethnicity="black", seed=6)),
    "07": dict(
        label="young man, light freckled skin, auburn brows, green eyes",
        # the ginger variant of this skin smears a freckle along the inner corner of the left lid
        skin="skins02/skins/toigo_light_skin_male_freckles",
        eyebrows="eyebrows01/eyebrows/mindfront_eyebrows_05",
        brow=dict(color=[0.13, 0.055, 0.025], opacity=0.7, width=0.11, density=1.2, shadow=0.25),
        iris="green", seed=7,
        detail={"freckles": 1.6},
        identity=dict(gender="male", ethnicity="white", seed=7)),
    "08": dict(
        label="middle-aged woman, light skin, grey eyes",
        skin="skins01/skins/onlytheghosts_middle_aged_eurasian_female",
        eyebrows="eyebrows01/eyebrows/mindfront_eyebrows_01",
        brow=dict(color=[0.075, 0.052, 0.036], opacity=0.85, width=0.12, density=1.4, shadow=0.40),
        iris="grey", seed=8,
        detail={"lid_lines": 1.3, "micro_strength": 1.15},
        identity=dict(gender="female", ethnicity="white", seed=8)),
    "09": dict(
        label="man, light skin with stubble, photographed skin, hazel eyes",
        # colour from the scan's photographs, so no generated colour detail on top of it, and
        # the scan's relief stays under its own brows
        scan=True,
        iris="hazel", seed=9,
        detail={"mottle_strength": 0, "redness": 0, "freckles": 0, "moles": 0, "veins": 0,
                "pore_tint": 0, "variation": 0, "scan_brows": True},
        identity=dict(gender="male", ethnicity="white", seed=9)),
}
SCAN_CREDIT = "Infinite, 3D Head Scan by Lee Perry-Smith, based on a work at www.triplegangers.com"


def run(cmd):
    print("[build]", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=REPO)


def bake(nn, r):
    if r.get("scan"):
        run([BLENDER, "-b", "--factory-startup", "-P", "tools/bake_scan.py", "--",
             "--albedo", WORK / f"tex_{nn}/skin.1001.png"])
        return
    b = r["brow"]
    run([BLENDER, "-b", "--factory-startup", "-P", "tools/transfer_skin.py", "--",
         "--skin", r["skin"], "--eyebrows", r["eyebrows"], "--name", f"tex_{nn}", "--out", WORK,
         "--brow-color", *b["color"], "--brow-opacity", b["opacity"], "--brow-width", b["width"],
         "--brow-density", b["density"], "--brow-shadow", b["shadow"], "--brow-seed", r["seed"]])


def details(nn, r):
    flags = []
    for k, v in r["detail"].items():
        flags += [f"--{k.replace('_', '-')}"] + ([] if v is True else [v])
    run([sys.executable, "tools/detail_maps.py", "--seed", r["seed"], "--out", WORK / f"tex_{nn}/detail", *flags])
    run([sys.executable, "tools/make_iris.py", "--color", r["iris"], "--seed", r["seed"],
         "--out", WORK / f"tex_{nn}/iris"])


LUMA = np.array([0.2126, 0.7152, 0.0722])


def tone_matrix(saturation=1.0, hue=0.0, gain=1.0):
    """3x3 matrix on linear RGB: saturation about luminance, hue rotation about grey, gain."""
    k = np.ones(3) / np.sqrt(3.0)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    t = np.radians(hue)
    rot = np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K
    sat = np.outer(np.ones(3), LUMA) * (1 - saturation) + saturation * np.eye(3)
    return gain * rot @ sat


def apply_tone(albedo_srgb_u8, tone):
    lin = tc.srgb_to_linear(albedo_srgb_u8[..., :3] / 255.0)
    m = tone_matrix(**tone)
    # per-channel sums, not matmul: numpy's matmul on Apple silicon raises spurious warnings here
    lin = np.clip(sum(lin[..., j:j + 1] * m[:, j] for j in range(3)), 0.0, 1.0)
    return tc.to_u8(tc.linear_to_srgb(lin))


def assemble(nn, r):
    w, out = WORK / f"tex_{nn}", TEX / f"tex_{nn}"
    out.mkdir(parents=True, exist_ok=True)
    alb = tc.read_png(w / "skin.1001.png")
    if r.get("tone"):
        alb = apply_tone(alb, r["tone"])
    det = tc.read_png(w / "detail/skin_detail.1001.png")
    skin = detail_maps.apply_albedo_detail(alb, det)
    tc.write_png(out / "skin.1001.png", skin)
    for f in ("skin_normal.1001.png", "skin_rough.1001.png"):
        shutil.copyfile(w / "detail" / f, out / f)
    for f in ("eye.1002.png", "eye.1004.png"):
        shutil.copyfile(w / "iris" / f, out / f)
    leg = out / "legacy"
    leg.mkdir(exist_ok=True)
    for src, dst in (("skin.1001.png", "skin.png"), ("eye.1002.png", "eye_L.png"), ("eye.1004.png", "eye_R.png")):
        shutil.copyfile(out / src, leg / dst)
    iris = json.loads((w / "iris/iris.json").read_text())
    meta = {
        "set": f"tex_{nn}",
        "label": r["label"],
        "skin": ({"source": f"{SCAN_CREDIT} (colour map)", "licence": "CC BY 3.0"} if r.get("scan") else
                 {"source": f"{MH}/{r['skin']}", "licence": "CC0 (MakeHuman)"}),
        "eyebrows": ({"source": "in the scan's colour map"} if r.get("scan") else
                     {"source": f"{MH}/{r['eyebrows']}", "licence": "CC0 (MakeHuman)",
                      "color_linear": r["brow"]["color"], "opacity": r["brow"]["opacity"],
                      "width_mm": r["brow"]["width"], "density": r["brow"]["density"],
                      "shadow": r["brow"]["shadow"], "seed": r["seed"]}),
        "micro_relief": {"source": f"{SCAN_CREDIT} (displacement map, filtered to pore scale)",
                         "licence": "CC BY 3.0", "in": "skin_normal.1001.png and the pore tint in skin.1001.png"},
        "iris": {"color": r["iris"], "seed": r["seed"], "params": iris},
        "tone": r.get("tone"),
        "detail_maps": {"seed": r["seed"], "flags": r["detail"]},
        "gnm_identity": {"sampler": "IdentitySampler", **r["identity"]},
        "files": {
            "skin.1001.png": "albedo 4096², sRGB, brows and detail layer baked in",
            "skin_normal.1001.png": "tangent-space normal 4096², OpenGL (+G up), non-colour",
            "skin_rough.1001.png": "roughness 2048², non-colour",
            "eye.1002.png": "left eye interior (subject's left, +X) 2048², sRGB",
            "eye.1004.png": "right eye interior 2048², sRGB",
            "legacy/": "same pixels under per-region names for the legacy UV layer",
        },
        "command": f"python3 tools/build_textures.py --sets {nn}",
    }
    (out / "set.json").write_text(json.dumps(meta, indent=1) + "\n")


def check(nn):
    w, out = WORK / f"tex_{nn}", TEX / f"tex_{nn}"
    cd = w / "wrapcheck"
    cd.mkdir(exist_ok=True)
    for f in ("skin_normal.1001.png", "skin_rough.1001.png"):
        shutil.copyfile(out / f, cd / f)
    flat = cd / "skin_detail.1001.png"
    if not flat.exists():
        tc.write_png(flat, np.full((64, 64, 3), 128, np.uint8))
    run([BLENDER, "-b", "--factory-startup", "-P", "tools/check_detail.py", "--",
         "--detail", cd, "--iris", out, "--skin", out / "skin.1001.png", "--wrap",
         "--shots", "wrap_front,wrap_three_quarter,profile,back", "--out", w])
    shutil.copyfile(w / "wrap_front.png", out / "preview.png")


def sheet():
    from PIL import Image, ImageDraw
    tiles = []
    for nn in sorted(SETS):
        w = WORK / f"tex_{nn}"
        row = [Image.open(w / f).convert("RGB") for f in ("wrap_front.png", "wrap_three_quarter.png")]
        tiles.append((nn, row))
    s = 512
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    img = Image.new("RGB", (cols * 2 * s, rows * (s + 28)), (24, 24, 24))
    d = ImageDraw.Draw(img)
    for i, (nn, row) in enumerate(tiles):
        x, y = (i % cols) * 2 * s, (i // cols) * (s + 28)
        for j, im in enumerate(row):
            img.paste(im.resize((s, s), Image.LANCZOS), (x + j * s, y + 28))
        d.text((x + 8, y + 7), f"tex_{nn}  {SETS[nn]['label']}", fill=(230, 230, 230))
    path = REPO / "outputs/stills/texture_sheet.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)
    print("[build] sheet", path.relative_to(REPO))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sets", nargs="*", default=sorted(SETS))
    ap.add_argument("--skip-bake", action="store_true", help="reuse outputs/tmp/m2/sets/tex_NN/skin.1001.png")
    ap.add_argument("--skip-maps", action="store_true", help="reuse the detail maps and irises")
    ap.add_argument("--skip-check", action="store_true")
    ap.add_argument("--sheet-only", action="store_true")
    args = ap.parse_args()
    if not args.sheet_only:
        for nn in args.sets:
            r = SETS[nn]
            if not args.skip_bake:
                bake(nn, r)
            if not args.skip_maps:
                details(nn, r)
            assemble(nn, r)
            if not args.skip_check:
                check(nn)
    if args.sheet_only or set(args.sets) == set(SETS):
        sheet()


if __name__ == "__main__":
    main()
