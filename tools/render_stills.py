"""Per-set stills on each set's paired GNM identity (M3 section 6).

    python3 tools/render_stills.py                  # every textures/tex_NN
    python3 tools/render_stills.py --sets 03 09     # some
    python3 tools/render_stills.py --sheet-only

For each set, from `gnm_identity` in its set.json (gender, ethnicity, seed):
  1. tools/export_gnm.py in .venv-gnm (the GNM package never runs inside Blender) samples the
     identity -> assets/gnm/id_<gender>_<ethnicity>_<seed>.npz (git-ignored, cached)
  2. tools/build_scene.py --npz builds a scene for that head, --no-bake, the set loaded
     -> outputs/tmp/m3/scenes/<same name>.blend. Lashes, brow hair, tear line, cameras and lid
     shapes are all rebuilt from that identity's vertices.
  3. tools/look_shots.py --still renders, gaze centre, the two still cameras in the `eye` look:
     outputs/stills/tex_NN.png (the face, no scalp) and outputs/stills/eye/tex_NN_eye.png
Then outputs/stills/eye/sheet.png puts all of them side by side.
Scenes are rebuilt when tools/build_scene.py, tools/lashes.py, tools/vellus.py, tools/brows.py or tools/carry_hair.py's
output is newer.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
GNM_PY = REPO / ".venv-gnm/bin/python"
IDS = REPO / "assets/gnm"      # export_gnm.py reads expr_*.npy from the output folder
SCENES = REPO / "outputs/tmp/m3/scenes"
STILLS = REPO / "outputs/stills"


def run(cmd):
    print("[stills]", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=REPO)


def sets():
    return sorted(p.parent.name[4:] for p in (REPO / "textures").glob("tex_*/set.json"))


def still(nn):
    meta = json.loads((REPO / f"textures/tex_{nn}/set.json").read_text())
    ident = meta["gnm_identity"]
    tag = f"{ident['gender']}_{ident['ethnicity']}_{ident['seed']}"
    npz = IDS / f"id_{tag}.npz"
    if not npz.exists():
        run([GNM_PY, "tools/export_gnm.py", "--identity-seed", ident["seed"], "--gender", ident["gender"],
             "--ethnicity", ident["ethnicity"], "--out", npz])
    blend = SCENES / f"{tag}.blend"
    deps = [REPO / "tools/build_scene.py", REPO / "tools/lashes.py", REPO / "tools/vellus.py", REPO / "tools/brows.py",
            REPO / "assets/gnm/hair_binding.npz", npz]
    if not blend.exists() or blend.stat().st_mtime < max(p.stat().st_mtime for p in deps):
        run([BLENDER, "-b", "--factory-startup", "-P", "tools/build_scene.py", "--",
             "--npz", npz, "--out", blend, "--no-bake", "--texture", int(nn)])
        if not blend.exists():
            raise SystemExit(f"[stills] build_scene.py did not write {blend}")
    run([BLENDER, "-b", blend, "-P", "tools/look_shots.py", "--", "--texture", int(nn), "--still"])


def sheet():
    from PIL import Image, ImageDraw
    nns = [n for n in sets() if (STILLS / f"tex_{n}.png").exists()]
    s = 512
    img = Image.new("RGB", (len(nns) * s, 2 * s + 28), (24, 24, 24))
    d = ImageDraw.Draw(img)
    for i, nn in enumerate(nns):
        img.paste(Image.open(STILLS / f"tex_{nn}.png").convert("RGB").resize((s, s), Image.LANCZOS), (i * s, 28))
        img.paste(Image.open(STILLS / f"eye/tex_{nn}_eye.png").convert("RGB").resize((s, s), Image.LANCZOS),
                  (i * s, 28 + s))
        d.text((i * s + 8, 8), f"tex_{nn}", fill=(230, 230, 230))
    out = STILLS / "eye/sheet.png"
    img.save(out, optimize=True)
    print("[stills] sheet", out.relative_to(REPO))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sets", nargs="*", default=None)
    ap.add_argument("--sheet-only", action="store_true")
    args = ap.parse_args()
    if not args.sheet_only:
        for nn in args.sets or sets():
            still(nn)
    sheet()


if __name__ == "__main__":
    sys.exit(main())
