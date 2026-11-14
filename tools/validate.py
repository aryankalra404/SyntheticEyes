"""Check the bundle: layout, metadata.json, direction signs, videos, textures, wrapper API,
README and Dockerfile. Standard library only; the scene check also needs Blender.

    python tools/validate.py            # everything; exit code 1 if anything fails
    python tools/validate.py --skip videos textures
    python tools/validate.py --root /path/to/unzipped/bundle
    python tools/validate.py --zip team_name.zip        # unzip to a temp folder and check that
    python tools/validate.py --blender /path/to/blender # also open scene.blend headless

The scene section runs when --blender is given or $BLENDER is set, and is skipped otherwise.

Direction signs come from outputs/direction_check.json, written by
    blender -b scene.blend -P wrapper/eyes.py -- --check-directions
Image space: x right, y down, so left = -x, right = +x, up = -y, down = +y.
"""

import argparse
import ast
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MIN_SHIFT_PX = 2.0          # a direction must move each pupil at least this far
RESET_TOL_PX = 0.1
MAX_VIDEO_S = 15.0
VIDEOS = ("left", "right", "generate")
RECORD_KEYS = ("frame", "theta", "input", "eye_rotation_L", "eye_rotation_R",
               "pupil_center_2D_L", "pupil_center_2D_R", "camera_matrix")
TEXTURE_FILES = ("skin.1001.png", "eye.1002.png", "eye.1004.png", "skin_normal.1001.png",
                 "skin_rough.1001.png", "legacy/skin.png", "legacy/eye_L.png",
                 "legacy/eye_R.png", "preview.png")


class Report:
    def __init__(self):
        self.fails = 0

    def check(self, ok, what, detail=""):
        print(f"{'PASS' if ok else 'FAIL'}  {what}" + (f"  ({detail})" if detail else ""))
        self.fails += not ok
        return ok


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def mp4_duration(path):
    """Seconds from the moov/mvhd box; no ffprobe needed."""
    data = Path(path).read_bytes()

    def boxes(buf, start, end):
        i = start
        while i + 8 <= end:
            size, kind = struct.unpack(">I4s", buf[i:i + 8])
            hdr = 8
            if size == 1:
                size = struct.unpack(">Q", buf[i + 8:i + 16])[0]
                hdr = 16
            elif size == 0:
                size = end - i
            yield kind, i + hdr, i + size
            i += size

    for kind, s, e in boxes(data, 0, len(data)):
        if kind == b"moov":
            for k2, s2, _ in boxes(data, s, e):
                if k2 == b"mvhd":
                    version = data[s2]
                    if version == 1:
                        scale, dur = struct.unpack(">IQ", data[s2 + 20:s2 + 32])
                    else:
                        scale, dur = struct.unpack(">II", data[s2 + 12:s2 + 20])
                    return dur / scale
    return None


def check_layout(r):
    for p in ("scene.blend", "wrapper/eyes.py", "wrapper/rig.py", "README.md", "metadata.json",
              "renders"):
        r.check((REPO / p).exists(), f"layout: {p}")
    frames = sorted((REPO / "renders").glob("frame_*.png")) if (REPO / "renders").exists() else []
    r.check(len(frames) == 10, "renders: 10 frames", f"found {len(frames)}")
    bad = [f.name for f in frames if png_size(f) != (1024, 1024)]
    r.check(frames and not bad, "renders: 1024x1024 PNG", ", ".join(bad))
    blend = REPO / "scene.blend"
    if blend.exists():
        mb = blend.stat().st_size / 1e6
        r.check(mb < 50, "scene.blend under 50 MB", f"{mb:.1f} MB")


def check_metadata(r):
    path = REPO / "metadata.json"
    if not path.exists():
        r.check(False, "metadata.json exists")
        return
    recs = json.loads(path.read_text())
    r.check(isinstance(recs, list) and len(recs) == 10, "metadata: 10 records")
    for k, rec in enumerate(recs if isinstance(recs, list) else []):
        missing = [key for key in RECORD_KEYS if key not in rec]
        if not r.check(not missing, f"metadata[{k}]: schema", ", ".join(missing)):
            continue
        theta = 2 * math.pi * k / 10
        ok = (rec["frame"] == k and abs(rec["theta"] - theta) < 1e-4
              and abs(rec["input"]["h"] - math.sin(theta)) < 1e-4
              and abs(rec["input"]["v"] - math.cos(theta)) < 1e-4)
        r.check(ok, f"metadata[{k}]: frame, theta, h = sin, v = cos",
                f"theta {rec['theta']}, h {rec['input']['h']}, v {rec['input']['v']}")
        P = rec["camera_matrix"]
        shapes = (len(rec["eye_rotation_L"]) == 3 and len(rec["eye_rotation_R"]) == 3
                  and len(rec["pupil_center_2D_L"]) == 2 and len(rec["pupil_center_2D_R"]) == 2
                  and len(P) == 3 and all(len(row) == 4 for row in P))
        r.check(shapes, f"metadata[{k}]: array shapes")
        inside = all(0 <= c <= 1024 for c in rec["pupil_center_2D_L"] + rec["pupil_center_2D_R"])
        r.check(inside, f"metadata[{k}]: pupils inside the image")
    # The 10 targets go round clockwise in the image: pupils follow h (x) and v (-y).
    if isinstance(recs, list) and len(recs) == 10 and all("input" in x for x in recs):
        for s in ("L", "R"):
            xs = [x[f"pupil_center_2D_{s}"][0] for x in recs]
            ys = [x[f"pupil_center_2D_{s}"][1] for x in recs]
            hs = [x["input"]["h"] for x in recs]
            vs = [x["input"]["v"] for x in recs]
            cx, cy = sum(xs) / 10, sum(ys) / 10
            corr_x = sum((a - cx) * h for a, h in zip(xs, hs))
            corr_y = sum((b - cy) * v for b, v in zip(ys, vs))
            r.check(corr_x > 0 and corr_y < 0, f"metadata: pupil {s} follows h right and v up",
                    f"x.h {corr_x:+.1f}, y.v {corr_y:+.1f}")


def check_directions(r):
    path = REPO / "outputs" / "direction_check.json"
    if not r.check(path.exists(), "direction check: outputs/direction_check.json exists"):
        return
    shots = json.loads(path.read_text())["shots"]
    base = shots["reset"]["pupil_px"]
    want = {"left": (0, -1), "right": (0, +1), "up": (1, -1), "down": (1, +1)}
    for name, (axis, sign) in want.items():
        p = shots[name]["pupil_px"]
        for s in ("L", "R"):
            d = p[s][axis] - base[s][axis]
            off = p[s][1 - axis] - base[s][1 - axis]
            r.check(d * sign >= MIN_SHIFT_PX and abs(off) < abs(d) / 3,
                    f"direction {name}: pupil {s}", f"{'xy'[axis]} {d:+.2f} px, other {off:+.2f} px")
    again = shots["reset_again"]["pupil_px"]
    err = max(abs(again[s][i] - base[s][i]) for s in ("L", "R") for i in (0, 1))
    r.check(err <= RESET_TOL_PX, "direction reset: back to centre", f"{err:.3f} px")


def check_videos(r):
    for mode in VIDEOS:
        p = REPO / "outputs" / "videos" / f"{mode}.mp4"
        if not r.check(p.exists(), f"video {mode}.mp4 exists"):
            continue
        dur = mp4_duration(p)
        r.check(dur is not None and 0 < dur <= MAX_VIDEO_S, f"video {mode}.mp4 <= 15 s",
                f"{dur:.2f} s" if dur else "no mvhd")
        mb = p.stat().st_size / 1e6
        r.check(mb < 50, f"video {mode}.mp4 under 50 MB", f"{mb:.1f} MB")


def check_textures(r):
    sets = sorted((REPO / "textures").glob("tex_*")) if (REPO / "textures").exists() else []
    r.check(5 <= len(sets) <= 10, "textures: 5 to 10 sets", f"found {len(sets)}")
    for s in sets:
        missing = [f for f in TEXTURE_FILES if not (s / f).exists()]
        r.check(not missing, f"textures: {s.name} complete", ", ".join(missing))
        big = [f.name for f in s.rglob("*.png") if f.stat().st_size > 50e6]
        r.check(not big, f"textures: {s.name} files under 50 MB", ", ".join(big))
    stills = sorted((REPO / "outputs" / "stills").glob("*.png")) if (REPO / "outputs/stills").exists() else []
    r.check(len(stills) >= len(sets) and stills, "stills: one per texture set", f"found {len(stills)}")


WRAPPER_FUNCS = ("move", "reset", "render")
WRAPPER_FLAGS = ("--input", "--texture", "--clockwise", "--seed", "--quality")
README_TOPICS = {  # section D: setup, run, conventions, licences
    "setup": r"blender\s+4\.\d",
    "run commands": r"wrapper/eyes\.py\s+--\s+--input",
    "direction convention": r"image[- ]right",
    "UV convention": r"\b1001\b.*\b1002\b",
    "licences": r"licen[cs]e",
}


def check_wrapper(r):
    path = REPO / "wrapper" / "eyes.py"
    if not r.check(path.exists(), "wrapper: wrapper/eyes.py exists"):
        return
    src = path.read_text()
    funcs = {n.name: n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    for name in WRAPPER_FUNCS:
        r.check(name in funcs, f"wrapper: eyes.{name}() defined")
    if "move" in funcs:
        args = [a.arg for a in funcs["move"].args.args]
        r.check(args[:2] == ["h", "v"], "wrapper: move(h, v) signature", ", ".join(args))
    for flag in WRAPPER_FLAGS:
        r.check(f'"{flag}"' in src, f"wrapper: CLI flag {flag}")
    m = re.search(r'"--input",\s*choices=\(([^)]*)\)', src)
    choices = set(re.findall(r'"(\w+)"', m.group(1))) if m else set()
    r.check(choices >= {"left", "right", "generate"}, "wrapper: --input left|right|generate",
            ", ".join(sorted(choices)))


def check_docs(r):
    readme = REPO / "README.md"
    if r.check(readme.exists(), "README.md exists"):
        text = readme.read_text()
        for topic, pat in README_TOPICS.items():
            r.check(re.search(pat, text, re.I | re.S) is not None, f"README: {topic}")
        todos = [ln.strip() for ln in text.splitlines() if "TODO" in ln]
        r.check(not todos, "README: no TODO left", f"{len(todos)} line(s)")
    disclosure = REPO / "AI_DISCLOSURE.md"       # on the organisers' GitHub checklist
    if r.check(disclosure.exists(), "AI_DISCLOSURE.md exists"):
        todos = [ln for ln in disclosure.read_text().splitlines() if "TODO" in ln]
        r.check(not todos, "AI_DISCLOSURE: no TODO left", f"{len(todos)} line(s)")
    docker = REPO / "Dockerfile"
    if r.check(docker.exists(), "Dockerfile exists"):
        text = docker.read_text()
        ver = re.search(r"BLENDER_VERSION=(\d+\.\d+\.\d+)", text)
        r.check(ver is not None, "Dockerfile: pins an exact Blender version",
                ver.group(1) if ver else "")
        r.check(re.search(r"sha256", text, re.I) is not None, "Dockerfile: checks the download hash")


SCENE_PROBE = r"""
import bpy, json, os
rig = bpy.data.objects.get("gnm_rig")
head = bpy.data.objects.get("gnm_head")
out = {"version": bpy.app.version_string,
       "bones": sorted(b.name for b in rig.data.bones) if rig else [],
       "uv_layers": sorted(u.name for u in head.data.uv_layers) if head else [],
       "materials": sorted(m.name for m in head.data.materials if m) if head else [],
       "frame_range": [bpy.context.scene.frame_start, bpy.context.scene.frame_end],
       "fcurves": {}, "absolute_paths": []}
for name, owner in (("armature", rig), ("shape_keys", head.data.shape_keys if head else None)):
    ad = owner.animation_data if owner else None
    act = ad.action if ad else None
    out["fcurves"][name] = sum(1 for fc in act.fcurves if len(fc.keyframe_points) > 1) if act else 0
for coll in (bpy.data.images, bpy.data.libraries, bpy.data.sounds, bpy.data.movieclips):
    for d in coll:
        fp = getattr(d, "filepath", "")
        packed = getattr(d, "packed_file", None) is not None
        if fp and not fp.startswith("//") and not packed and os.path.isabs(fp):
            out["absolute_paths"].append(fp)
print("VALIDATE_SCENE " + json.dumps(out))
"""


def check_scene(r, blender):
    blend = REPO / "scene.blend"
    if not r.check(blend.exists(), "scene: scene.blend exists"):
        return
    try:
        proc = subprocess.run([blender, "-b", str(blend), "--python-expr", SCENE_PROBE],
                              capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        r.check(False, "scene: Blender runs", str(e))
        return
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("VALIDATE_SCENE ")), None)
    if not r.check(line is not None, "scene: Blender opened scene.blend", proc.stderr.strip()[-200:]):
        return
    s = json.loads(line.split(" ", 1)[1])
    r.check(s["version"].startswith("4.5"), "scene: Blender 4.5 (pinned)", s["version"])
    r.check({"eye.L", "eye.R"} <= set(s["bones"]), "scene: eye bones eye.L and eye.R",
            ", ".join(s["bones"]))
    r.check({"UDIM", "legacy"} <= set(s["uv_layers"]), "scene: UDIM and legacy UV maps",
            ", ".join(s["uv_layers"]))
    r.check(len(s["materials"]) > 0, "scene: head has materials", f"{len(s['materials'])}")
    f0, f1 = s["frame_range"]
    r.check(f1 > f0, "scene: Timeline has a frame range", f"{f0}..{f1}")
    r.check(s["fcurves"]["armature"] > 0, "scene: eye/head bones keyframed on the Timeline",
            f"{s['fcurves']['armature']} animated F-curves")
    r.check(s["fcurves"]["shape_keys"] > 0, "scene: lid/brow shape keys keyframed",
            f"{s['fcurves']['shape_keys']} animated F-curves")
    r.check(not s["absolute_paths"], "scene: no absolute file paths", ", ".join(s["absolute_paths"]))


SECTIONS = {"layout": check_layout, "metadata": check_metadata, "directions": check_directions,
            "videos": check_videos, "textures": check_textures, "wrapper": check_wrapper,
            "docs": check_docs, "scene": check_scene}


def unzip(path, into):
    """Extract a bundle zip; the root is the folder holding scene.blend."""
    with zipfile.ZipFile(path) as z:
        z.extractall(into)
    hits = sorted(Path(into).rglob("scene.blend"), key=lambda p: len(p.parts))
    return hits[0].parent if hits else Path(into)


def main():
    global REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", nargs="*", default=[], choices=tuple(SECTIONS))
    where = ap.add_mutually_exclusive_group()
    where.add_argument("--root", type=Path, help="check this folder instead of the repo")
    where.add_argument("--zip", type=Path, help="unzip to a temp folder and check that")
    ap.add_argument("--blender", default=os.environ.get("BLENDER"),
                    help="Blender executable for the scene check (default $BLENDER)")
    args = ap.parse_args()
    tmp = None
    if args.zip:
        tmp = tempfile.TemporaryDirectory()
        REPO = unzip(args.zip, tmp.name)
        print(f"checking {args.zip.name}, unzipped to {REPO}")
    elif args.root:
        REPO = args.root.resolve()
    r = Report()
    for name, fn in SECTIONS.items():
        if name in args.skip:
            print(f"SKIP  {name}")
            continue
        if name == "scene":
            if not args.blender:
                print("SKIP  scene  (no --blender and no $BLENDER)")
                continue
            fn(r, args.blender)
            continue
        fn(r)
    if tmp:
        tmp.cleanup()
    print(f"\n{'OK' if not r.fails else f'{r.fails} check(s) failed'}")
    sys.exit(1 if r.fails else 0)


if __name__ == "__main__":
    main()
