#!/usr/bin/env python3
"""Cut the demo video from finished outputs. No voice-over: short captions in a band under
the picture, plain cuts with short fades.

    python3 tools/make_demo.py --ffmpeg /path/to/ffmpeg --capture outputs/tmp/demo/blender_ui \
        [--xr headset.mp4 [--xr-pip phone.mp4 --xr-offset S] --xr-start S --xr-dur S] \
        [--out outputs/demo/demo.mp4]

Reads outputs/videos/*.mp4, outputs/stills (faces and eye close-ups), textures/tex_NN,
renders/, metadata.json, the final render log outputs/tmp/finals/right.log (terminal
segment) and the Blender window capture from tools/capture_blender_ui.py. Needs Pillow and
numpy and an ffmpeg binary (the one in imageio-ffmpeg works).
"""
import argparse, json, math, re, subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
W, H, FPS = 1920, 1080, 30
BG = (9, 9, 9)
BOX = (80, 40, 1760, 880)            # picture area: x, y, w, h; captions live below it
BAND_Y = 932
FADE = 8                             # frames of fade at each segment edge
FG, DIM, FAINT = (238, 238, 236), (140, 140, 138), (92, 92, 90)

FONT_DIR = Path("/System/Library/Fonts")


def font(kind, size):
    if kind == "mono":
        return ImageFont.truetype(str(FONT_DIR / "Menlo.ttc"), size, index=0)
    want = {"regular": "Regular", "medium": "Medium", "light": "Light"}[kind]
    for i in range(16):
        try:
            f = ImageFont.truetype(str(FONT_DIR / "HelveticaNeue.ttc"), size, index=i)
        except OSError:
            break
        if f.getname()[1] == want:
            return f
    return ImageFont.truetype(str(FONT_DIR / "HelveticaNeue.ttc"), size, index=0)


F_LABEL = font("mono", 21)
F_CAP = font("regular", 33)
F_CMD = font("mono", 31)


def canvas():
    return Image.new("RGB", (W, H), BG)


def fit(im, w, h, cover=False):
    s = (max if cover else min)(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    if cover:
        x, y = (im.width - w) // 2, (im.height - h) // 2
        im = im.crop((x, y, x + w, y + h))
    return im


def paste_center(dst, im, box):
    x, y, w, h = box
    dst.paste(im, (x + (w - im.width) // 2, y + (h - im.height) // 2))


# ---------------------------------------------------------------- captions

def caption_layer(label, text):
    """RGBA band image for one caption: a mono label over one line of text."""
    band = Image.new("RGBA", (W, H - BAND_Y), (0, 0, 0, 0))
    d = ImageDraw.Draw(band)
    x = BOX[0]
    if label:
        d.text((x, 6), label, font=F_LABEL, fill=DIM + (255,))
    if text:
        mono = text.startswith("--") or text.startswith("tex_")
        d.text((x, 42 if label else 24), text, font=F_CMD if mono else F_CAP, fill=FG + (255,))
    a = np.asarray(band).astype(np.float32) / 255.0
    return a[..., :3] * 255.0, a[..., 3:4]


class Segment:
    """frames: list-like or generator of HxWx3 uint8; caps: [(label, text, t0, t1)] in seconds."""

    def __init__(self, n, frames, caps=(), fade_in=False, fade_out=False):
        self.n, self.frames, self.caps = n, frames, list(caps)
        self.fade_in, self.fade_out = fade_in, fade_out


def composite(seg):
    layers = [(caption_layer(l, t), t0, t1) for l, t, t0, t1 in seg.caps]
    for i, fr in enumerate(seg.frames):
        if i >= seg.n:
            break
        f = fr.astype(np.float32)
        t = i / FPS
        for (rgb, a), t0, t1 in layers:
            k = min(1.0, max(0.0, (t - t0) * 8), max(0.0, (t1 - t) * 8))
            if k > 0:
                band = f[BAND_Y:]
                f[BAND_Y:] = band * (1 - a * k) + rgb * a * k
        g = 1.0
        if seg.fade_in and i < FADE:
            g = min(g, (i + 1) / FADE)
        if seg.fade_out and i >= seg.n - FADE:
            g = min(g, (seg.n - i) / FADE)
        if g < 1:
            f = f * g + np.array(BG, np.float32) * (1 - g)
        yield f.clip(0, 255).astype(np.uint8)


# ---------------------------------------------------------------- sources

def decode(ffmpeg, path, w, h, start=0.0, dur=None):
    seek = ["-ss", f"{start:.3f}"] if start else []
    span = ["-t", f"{dur:.3f}"] if dur else []
    p = subprocess.Popen([ffmpeg, "-v", "error", *seek, "-i", str(path), *span, "-r", str(FPS), "-vf",
                          f"scale={w}:{h}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    size = w * h * 3
    while True:
        b = p.stdout.read(size)
        if len(b) < size:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
    p.wait()


def probe_frames(ffmpeg, path):
    out = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    fps = float(re.search(r"([\d.]+) fps", out).group(1))
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return int(round(dur * fps)), (int(x) for x in re.search(r", (\d+)x(\d+)", out).groups())


def seg_video(ffmpeg, path, caps, size=None):
    n, (vw, vh) = probe_frames(ffmpeg, path)
    bw, bh = BOX[2], BOX[3]
    s = min(bw / vw, bh / vh)
    w, h = size or (int(vw * s) // 2 * 2, int(vh * s) // 2 * 2)
    x, y = BOX[0] + (bw - w) // 2, BOX[1] + (bh - h) // 2

    def gen():
        base = np.asarray(canvas()).copy()
        for fr in decode(ffmpeg, path, w, h):
            base[y:y + h, x:x + w] = fr
            yield base

    return Segment(n, gen(), caps)


def still_frames(img, n):
    a = np.asarray(img)
    return Segment(n, (a for _ in range(n)))


# ---------------------------------------------------------------- segments

def seg_xr(ffmpeg, main, pip, start, dur, offset, caps, pip_side=280, pip_top=0.18):
    """The headset recording full frame, with the phone recording of the wearer in a small
    square box in the bottom-left corner. offset: pip time minus main time for the same moment
    (found from the audio and checked on the arm raise). pip_top: where the square is cut from
    the portrait phone frame, as a share of its height."""
    n = int(dur * FPS)
    _, (vw, vh) = probe_frames(ffmpeg, main)
    s = max(W / vw, H / vh)                                    # fill the frame, crop the rest
    w, h = int(round(vw * s)) // 2 * 2, int(round(vh * s)) // 2 * 2
    cx, cy = (w - W) // 2, (h - H) // 2
    gens = [decode(ffmpeg, main, w, h, start, dur)]
    side = pip_side
    if pip:
        _, (pw, ph) = probe_frames(ffmpeg, pip)
        k = side / min(pw, ph)
        pw2, ph2 = int(round(pw * k)) // 2 * 2, int(round(ph * k)) // 2 * 2
        oy = min(int(ph2 * pip_top), ph2 - side)
        ox = (pw2 - side) // 2
        px, py = 36, H - side - 36
        mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=14, fill=255)
        m = (np.asarray(mask, np.float32) / 255.0)[..., None]
        ring = Image.new("L", (side + 4, side + 4), 0)
        ImageDraw.Draw(ring).rounded_rectangle((0, 0, side + 3, side + 3), radius=16, fill=255)
        r = (np.asarray(ring, np.float32) / 255.0)[..., None]
        gens.append(decode(ffmpeg, pip, pw2, ph2, start + offset, dur))

    def gen():
        pg = gens[1] if pip else None
        for fr in gens[0]:
            base = fr[cy:cy + H, cx:cx + W].copy()
            if pg is not None:
                q = next(pg, None)
                if q is not None:
                    q = q[oy:oy + side, ox:ox + side].astype(np.float32)
                    sl = base[py - 2:py + side + 2, px - 2:px + side + 2].astype(np.float32)
                    sl = sl * (1 - r * 0.6) + 15 * r * 0.6              # a thin dark edge
                    sl[2:-2, 2:-2] = sl[2:-2, 2:-2] * (1 - m) + q * m
                    base[py - 2:py + side + 2, px - 2:px + side + 2] = sl.astype(np.uint8)
            yield base

    return Segment(n, gen(), caps)


def terminal_lines(log):
    raw = log.read_text(errors="replace").splitlines()
    clean = lambda s: s.replace(str(REPO) + "/", "").replace(str(REPO), ".")
    head = [clean(l) for l in raw[:2]]
    fra, seen, cam, last = [], set(), 0, 0
    for l in raw:
        m = re.match(r"Fra:(\d+) .*\| Sample (\d+)/128", l)
        if not m:
            continue
        f, s = int(m.group(1)), int(m.group(2))
        if f < last:
            cam += 1                     # the second camera pass starts again at frame 1
        last = f
        keep = (f <= 2 and s % 16 == 0) or (f > 2 and s in (64, 128))
        if keep and (cam, f, s) not in seen:
            seen.add((cam, f, s))
            fra.append(clean(re.sub(r"\s+", " ", l)))
    tail = [clean(l) for l in raw if l.startswith("[eyes]") or l == "Blender quit"]
    return head, fra, tail


def seg_terminal(log, cmd, secs, caps):
    head, fra, tail = terminal_lines(log)
    mono = font("mono", 19)
    cw = mono.getlength("M")
    x0, y0, bw, bh = BOX
    bar = 40
    lh = 25
    cols = int((bw - 48) // cw)
    rows = int((bh - bar - 36) // lh)
    prompt = "samsung-prism % "
    n = int(secs * FPS)
    t_type0, t_type1 = 0.5, 0.5 + len(cmd) / 42
    t_run, t_fra1 = t_type1 + 0.35, secs - 2.6

    win = canvas()
    d = ImageDraw.Draw(win)
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=12, fill=(22, 22, 22), outline=(48, 48, 48))
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bar), radius=12, fill=(38, 38, 38))
    d.rectangle((x0, y0 + bar - 12, x0 + bw, y0 + bar), fill=(38, 38, 38))
    for k, c in enumerate([(236, 95, 87), (244, 190, 79), (98, 197, 84)]):
        cx, cy = x0 + 22 + k * 22, y0 + bar // 2
        d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=c)
    title = "samsung-prism — zsh"
    tf = font("regular", 19)
    d.text((x0 + (bw - d.textlength(title, font=tf)) / 2, y0 + 9), title, font=tf, fill=(170, 170, 168))
    base = np.asarray(win)

    def frame(i):
        t = i / FPS
        lines = []
        typed = cmd[:max(0, int((t - t_type0) * 42))] if t >= t_type0 else ""
        lines.append(prompt + (cmd if t >= t_type1 else typed))
        if t >= t_run:
            lines += head
            u = min(1.0, (t - t_run) / (t_fra1 - t_run))
            k = int(len(fra) * (u ** 2.2))
            lines += fra[:k]
            if t >= t_fra1:
                m = min(len(tail), int((t - t_fra1) / 0.18) + 1)
                lines += tail[:m]
                if m == len(tail) and t > t_fra1 + 0.18 * len(tail) + 0.3:
                    lines.append(prompt)
        lines = lines[-rows:]
        im = Image.fromarray(base.copy())
        dd = ImageDraw.Draw(im)
        y = y0 + bar + 18
        for l in lines:
            col = FG if l.startswith(prompt) else ((214, 214, 212) if l.startswith("[eyes]") else (150, 150, 148))
            dd.text((x0 + 24, y), l[:cols], font=mono, fill=col)
            y += lh
        last = lines[-1][:cols]
        if (int(t * 2) % 2 == 0) or (t_type0 <= t < t_type1):
            cx = x0 + 24 + mono.getlength(last)
            dd.rectangle((cx + 2, y - lh + 2, cx + cw, y - 3), fill=(200, 200, 198))
        return np.asarray(im)

    return Segment(n, (frame(i) for i in range(n)), caps)


def seg_grid(images, labels, secs, caps, cell=(336, 420), gap=(20, 40)):
    """5 over 4 grid, cells cropped to fill, staggered fade-in."""
    cw, ch = cell
    tiles = [fit(im, cw, ch, cover=True) for im in images]
    lab = font("mono", 17)
    x0, y0, bw, bh = BOX
    pos = []
    for r, row in enumerate([range(0, 5), range(5, 9)]):
        cnt = len(row)
        tw = cnt * cw + (cnt - 1) * gap[0]
        ty = y0 + (bh - (2 * ch + gap[1])) // 2 + r * (ch + gap[1])
        for j, k in enumerate(row):
            pos.append((x0 + (bw - tw) // 2 + j * (cw + gap[0]), ty))
    layers = []
    for (x, y), tile, l in zip(pos, tiles, labels):
        im = tile.copy()
        if l:
            dd = ImageDraw.Draw(im)
            dd.text((12, ch - 30), l, font=lab, fill=(200, 200, 198))
        layers.append((x, y, np.asarray(im).astype(np.float32)))
    n = int(secs * FPS)

    def gen():
        for i in range(n):
            f = np.full((H, W, 3), BG, np.float32)
            for k, (x, y, a) in enumerate(layers):
                g = 1.0
                if g > 0:
                    f[y:y + a.shape[0], x:x + a.shape[1]] = a * g + np.array(BG) * (1 - g)
            yield f.astype(np.uint8)

    return Segment(n, gen(), caps)


def seg_sets(sets, per, caps_fn):
    """Each set: face render | eye close-up | skin map in GNM UV, with labels under."""
    side, gap = 560, 40
    x0, y0, bw, bh = BOX
    y = y0 + (bh - side) // 2 - 10
    xs = [x0 + k * (side + gap) for k in range(3)]
    lab = font("mono", 18)
    frames_per = int(per * FPS)
    xf = 7
    pics = []
    for s in sets:
        im = canvas()
        d = ImageDraw.Draw(im)
        for x, src, l in zip(xs, s["imgs"], s["names"]):
            im.paste(fit(src, side, side, cover=True), (x, y))
            d.text((x, y + side + 14), l, font=lab, fill=DIM)
        pics.append(np.asarray(im).astype(np.float32))
    n = frames_per * len(sets)
    caps = []
    for k, s in enumerate(sets):
        caps.append(caps_fn(s, k * per + 0.1, (k + 1) * per - 0.1))

    def gen():
        for i in range(n):
            k, j = divmod(i, frames_per)
            a = pics[k]
            if j >= frames_per - xf and k + 1 < len(pics):
                u = (j - (frames_per - xf) + 1) / (xf + 1)
                a = a * (1 - u) + pics[k + 1] * u
            yield a.astype(np.uint8)

    return Segment(n, gen(), caps)


def seg_capture(cap_dir, phases_caps):
    shots = json.load(open(cap_dir / "shots.json"))
    files = sorted(cap_dir.glob("[0-9][0-9][0-9][0-9].png"))
    first = Image.open(files[0])
    bw, bh = BOX[2], BOX[3]
    s = min(bw / first.width, bh / first.height)
    w, h = int(first.width * s), int(first.height * s)
    x, y = BOX[0] + (bw - w) // 2, BOX[1] + (bh - h) // 2
    caps, start = [], 0
    for name in dict.fromkeys(p for p, _ in shots):
        cnt = sum(1 for p, _ in shots if p == name)
        if name in phases_caps:
            l, t = phases_caps[name]
            caps.append((l, t, start / FPS + 0.15, (start + cnt) / FPS - 0.1))
        start += cnt
    # merge consecutive captions with the same text so they do not blink
    merged = []
    for c in caps:
        if merged and merged[-1][:2] == c[:2]:
            merged[-1] = (c[0], c[1], merged[-1][2], c[3])
        else:
            merged.append(c)

    def gen():
        base = np.asarray(canvas()).copy()
        for f in files:
            im = Image.open(f).convert("RGB").resize((w, h), Image.LANCZOS)
            base[y:y + h, x:x + w] = np.asarray(im)
            yield base

    return Segment(len(files), gen(), merged)


def seg_clockwise(per, caps):
    meta = json.load(open(REPO / "metadata.json"))
    side = 880
    x0, y0 = BOX[0], BOX[1]
    full = [Image.open(REPO / r["image"]).convert("RGB") for r in meta]
    renders = [fit(im, side, side) for im in full]
    mono = font("mono", 22)
    small = font("mono", 18)
    px = x0 + side + 90
    zw = BOX[0] + BOX[2] - px                          # eye strip, cut from the same render
    zh = round(zw / 2.8)
    pl = np.mean([r["pupil_center_2D_L"] for r in meta] + [r["pupil_center_2D_R"] for r in meta], axis=0)
    cw_ = 400
    ch_ = round(cw_ / 2.8)
    crop = (int(pl[0] - cw_ / 2), int(pl[1] - ch_ / 2), int(pl[0] + cw_ / 2), int(pl[1] + ch_ / 2))
    strips = [im.crop(crop).resize((zw, zh), Image.LANCZOS) for im in full]
    cx, cy, R = px + zw - 120, y0 + zh + 230, 100
    n_per = int(per * FPS)
    hold = int(0.8 * FPS)
    n = n_per * len(meta) + hold

    def fmt(v):
        return "[" + ", ".join(f"{x:.3f}" for x in v) + "]"

    pages = []
    for k, r in enumerate(meta):
        im = canvas()
        im.paste(renders[k], (x0, y0))
        im.paste(strips[k], (px, y0))
        d = ImageDraw.Draw(im)
        d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(70, 70, 68), width=2)
        for j, rr in enumerate(meta):
            th = rr["theta"]
            px_, py_ = cx + R * math.sin(th), cy - R * math.cos(th)
            r_ = 9 if j == k else 5
            col = FG if j == k else ((120, 120, 118) if j < k else (60, 60, 58))
            d.ellipse((px_ - r_, py_ - r_, px_ + r_, py_ + r_), fill=col)
        d.text((cx - 8, cy - R - 42), "v", font=small, fill=DIM)
        d.text((cx + R + 16, cy - 12), "h", font=small, fill=DIM)
        rows = [
            ("frame", f"{r['frame']}"),
            ("theta", f"{r['theta']:.4f}"),
            ("h, v", f"{r['input']['h']:+.3f}, {r['input']['v']:+.3f}"),
            ("eye_rotation_L", fmt(r["eye_rotation_L"])),
            ("eye_rotation_R", fmt(r["eye_rotation_R"])),
            ("pupil_center_2D_L", fmt(r["pupil_center_2D_L"])),
            ("pupil_center_2D_R", fmt(r["pupil_center_2D_R"])),
        ]
        ty = y0 + zh + 74
        d.text((px, ty), "metadata.json", font=small, fill=DIM)
        ty += 40
        for key, val in rows:
            d.text((px, ty), key, font=small, fill=DIM)
            d.text((px, ty + 22), val, font=mono, fill=FG)
            ty += 56
        pages.append(np.asarray(im))

    def gen():
        for i in range(n):
            yield pages[min(i // n_per, len(pages) - 1)]

    return Segment(n, gen(), caps)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ffmpeg", required=True)
    ap.add_argument("--capture", type=Path, required=True)
    ap.add_argument("--xr", type=Path, help="headset recording")
    ap.add_argument("--xr-pip", type=Path, help="phone recording of the wearer, shown small")
    ap.add_argument("--xr-offset", type=float, default=0.0, help="pip time minus headset time, s")
    ap.add_argument("--xr-start", type=float, default=0.0)
    ap.add_argument("--xr-dur", type=float)
    ap.add_argument("--out", type=Path, default=REPO / "outputs/demo/demo.mp4")
    ap.add_argument("--only", help="comma list of segment names, for previews")
    args = ap.parse_args()
    ff = args.ffmpeg
    V = REPO / "outputs/videos"

    sets = []
    for i in range(1, 10):
        tid = f"tex_{i:02d}"
        meta = json.load(open(REPO / "textures" / tid / "set.json"))
        sets.append({
            "id": tid, "label": meta["label"],
            "imgs": [Image.open(REPO / f"outputs/stills/{tid}.png").convert("RGB"),
                     Image.open(REPO / f"outputs/stills/eye/{tid}_eye.png").convert("RGB"),
                     Image.open(REPO / f"textures/{tid}/skin.1001.png").convert("RGB")],
            "names": ["render", "eye", "UV map"],
        })

    segs = {
        "open": lambda: seg_video(ff, V / "generate.mp4", [("command", "--input generate", 0.5, 8.1)]),
        "terminal": lambda: seg_terminal(
            REPO / "outputs/tmp/finals/right.log",
            "blender -b scene.blend -P wrapper/eyes.py -- --input right", 9.5, [
                ("", "rendering right.mp4", 2.4, 5.0),
                ("", "7\u00bd hours on an M4, sped up", 5.1, 9.3)]),
        "right": lambda: seg_video(ff, V / "right.mp4", [("command", "--input right", 0.3, 8.8)]),
        "left": lambda: seg_video(ff, V / "left.mp4", [("command", "--input left", 0.3, 8.8)]),
        "grid": lambda: seg_grid([s["imgs"][0] for s in sets], [s["id"] for s in sets], 4.0, [
            ("", "9 skin textures", 0.3, 3.8)]),
        "sets": lambda: seg_sets(sets, 2.2, lambda s, t0, t1: ("", s["id"], t0, t1)),
        "eyes": lambda: seg_grid([s["imgs"][1] for s in sets], [s["id"] for s in sets], 4.0, [
            ("", "irises", 0.3, 3.8)], cell=(336, 336)),
        "blender": lambda: seg_capture(args.capture, {
            "render": ("", "scene.blend, playing on the timeline")}),
        "clockwise": lambda: seg_clockwise(0.6, [
            ("command", "--clockwise", 0.3, 6.6)]),
    }
    order = ["open", "terminal", "right", "left", "grid", "sets", "eyes", "blender", "clockwise"]
    if args.xr:
        dur = args.xr_dur or (probe_frames(ff, args.xr)[0] / FPS - args.xr_start)
        segs["xr"] = lambda: seg_xr(ff, args.xr, args.xr_pip, args.xr_start, dur, args.xr_offset,
                                    [])
        order.append("xr")
    if args.only:
        order = [o for o in order if o in args.only.split(",")]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen([ff, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(args.out)],
                           stdin=subprocess.PIPE)
    total = 0
    for idx, name in enumerate(order):
        seg = segs[name]()
        seg.fade_in = idx == 0
        seg.fade_out = idx == len(order) - 1
        k = 0
        for fr in composite(seg):
            enc.stdin.write(np.ascontiguousarray(fr).tobytes())
            k += 1
        total += k
        print(f"[demo] {name:10s} {k / FPS:5.1f} s   (at {total / FPS:6.1f} s)", flush=True)
    enc.stdin.close()
    enc.wait()
    print(f"[demo] wrote {args.out}  {total / FPS:.1f} s")


if __name__ == "__main__":
    main()
