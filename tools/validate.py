"""Check the bundle without Blender: layout, metadata.json, direction signs, videos, textures.

    python tools/validate.py            # everything; exit code 1 if anything fails
    python tools/validate.py --skip videos textures

Direction signs come from outputs/direction_check.json, written by
    blender -b scene.blend -P wrapper/eyes.py -- --check-directions
Image space: x right, y down, so left = -x, right = +x, up = -y, down = +y.
"""

import argparse
import json
import math
import struct
import sys
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


SECTIONS = {"layout": check_layout, "metadata": check_metadata, "directions": check_directions,
            "videos": check_videos, "textures": check_textures}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", nargs="*", default=[], choices=tuple(SECTIONS))
    args = ap.parse_args()
    r = Report()
    for name, fn in SECTIONS.items():
        if name in args.skip:
            print(f"SKIP  {name}")
            continue
        fn(r)
    print(f"\n{'OK' if not r.fails else f'{r.fails} check(s) failed'}")
    sys.exit(1 if r.fails else 0)


if __name__ == "__main__":
    main()
