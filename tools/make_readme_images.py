"""Make the pictures in README.md, into docs/img/.

    python3 tools/make_readme_images.py [--ui DIR]

Reads the stills, the texture tiles, the direction-check renders and the rendered video frames in
outputs/frames/<input>/ (left behind by the final `--input` runs, git-ignored). --ui is a folder
of Blender window screenshots from tools/capture_blender_ui.py (its `quick` mode is enough);
the third one (the Cycles viewport at Timeline frame 81) becomes blender_timeline.jpg.
Needs Pillow and numpy only.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"


def font(size):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNS.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def label(im, text, size=20, pad=10):
    d = ImageDraw.Draw(im)
    f = font(size)
    x0, y0, x1, y1 = d.textbbox((0, 0), text, font=f)
    w, h = x1 - x0, y1 - y0
    d.rectangle((pad - 6, im.height - pad - h - 10, pad + w + 6, im.height - pad + 2), fill=(0, 0, 0))
    d.text((pad, im.height - pad - h - 6 - y0), text, fill=(235, 235, 235), font=f)
    return im


def rgb(p, size=None):
    im = Image.open(p).convert("RGB")
    return im.resize(size, Image.LANCZOS) if size else im


def save_jpg(im, name):
    im.save(OUT / name, quality=86, optimize=True, progressive=True)
    print(name, im.size, f"{(OUT / name).stat().st_size / 1e6:.2f} MB")


def anim(frames, name, fps, quality=72):
    """Animated WebP: a fraction of a GIF's size for noisy Cycles frames, and full colour."""
    frames[0].save(OUT / name, save_all=True, append_images=frames[1:], duration=round(1000 / fps),
                   loop=0, quality=quality, method=6)
    print(name, frames[0].size, len(frames), f"{(OUT / name).stat().st_size / 1e6:.2f} MB")


def video_frames(mode, cam, size, step):
    files = sorted((ROOT / "outputs" / "frames" / mode / cam).glob("*.png"))
    if not files:
        raise SystemExit(f"no frames in outputs/frames/{mode}/{cam}: render the videos first")
    return [rgb(p, size) for p in files[::step]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ui", type=Path)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # motion: the split video of `generate` as the hero, the face pane of each input below it
    anim(video_frames("generate", "video", (960, 480), 2), "hero_generate.webp", 15)
    for mode in ("left", "right", "generate"):
        anim(video_frames(mode, "face", (360, 360), 2), f"{mode}.webp", 15)

    # the nine heads
    t = 400
    g = Image.new("RGB", (3 * t, 3 * t))
    for k in range(9):
        im = label(rgb(ROOT / f"outputs/stills/tex_{k + 1:02d}.png", (t, t)), f"tex_{k + 1:02d}", 18)
        g.paste(im, ((k % 3) * t, (k // 3) * t))
    save_jpg(g, "faces.jpg")

    # eye close-ups, the bottom row of the eye sheet
    sheet = rgb(ROOT / "outputs/stills/eye/sheet.png")
    w = 1800
    save_jpg(sheet.resize((w, round(sheet.height * w / sheet.width)), Image.LANCZOS), "eyes.jpg")

    # what a texture set is: the UV-space maps of tex_09
    tex = ROOT / "textures/tex_09"
    tiles = [("skin.1001.png", "albedo (tile 1001)"), ("skin_normal.1001.png", "normal"),
             ("skin_rough.1001.png", "roughness"), ("eye.1002.png", "left eye (1002)"),
             ("eye.1004.png", "right eye (1004)")]
    s = 360
    row = Image.new("RGB", (len(tiles) * s, s))
    for i, (f, txt) in enumerate(tiles):
        row.paste(label(rgb(tex / f, (s, s)), txt, 16), (i * s, 0))
    save_jpg(row, "uv_maps.jpg")

    # direction check as a plus: up, left, reset, right, down
    box = (150, 420, 880, 620)
    cw, ch = (box[2] - box[0]) // 2, (box[3] - box[1]) // 2
    plus = Image.new("RGB", (3 * cw, 3 * ch), (13, 17, 23))
    for name, (cx, cy) in {"up": (1, 0), "left": (0, 1), "reset": (1, 1), "right": (2, 1),
                           "down": (1, 2)}.items():
        im = rgb(ROOT / f"outputs/direction_check/{name}.png").crop(box).resize((cw, ch), Image.LANCZOS)
        plus.paste(label(im, name, 15, 6), (cx * cw, cy * ch))
    save_jpg(plus, "directions.jpg")

    # the 10 clockwise renders, cropped to the eyes
    box = (300, 430, 724, 590)
    tiles = []
    for k in range(10):
        im = rgb(ROOT / f"renders/frame_{k:02d}.png").crop(box)
        tiles.append(label(im.resize((im.width, im.height)), f"k={k}", 15, 6))
    cw, ch = tiles[0].size
    grid = Image.new("RGB", (5 * cw, 2 * ch))
    for k, im in enumerate(tiles):
        grid.paste(im, ((k % 5) * cw, (k // 5) * ch))
    save_jpg(grid, "clockwise.jpg")

    if a.ui:
        shots = sorted(a.ui.glob("*.png"))
        im = rgb(shots[2])
        save_jpg(im.resize((1400, round(im.height * 1400 / im.width)), Image.LANCZOS),
                 "blender_timeline.jpg")


if __name__ == "__main__":
    main()
