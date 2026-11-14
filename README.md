# SyntheticEyes

Samsung PRISM XR Hackathon 2026, Track 1: Synthetic Eye Movement & Virtual Camera Rendering.

A Google GNM Head v3 in Blender with calibrated, human-like eye, eyelid and brow motion, and a
set of skin and eye texture sets in GNM's UV layout that can be put on any GNM head.

> TODO: team name, college name and the final zip name (`team_name.zip`).
> TODO: demo video link (≤ 3 min) and deck `CollegeName_TeamName.pdf`.

## Contents

```
scene.blend            GNM head, armature (neck, head, eye.L, eye.R), lid and brow shape keys,
                       materials, lights, two cameras; the `generate` motion on the Timeline
wrapper/eyes.py        public API and command line: move(h, v), reset(), render(), videos
wrapper/rig.py         poses bones and shape keys from the gaze channels
wrapper/gaze/          gaze engine: saccades, fixations, blinks, lids, brows, head (numpy only)
wrapper/camera_move.py when the video camera glides between framings (numpy only)
wrapper/device.py      picks the Cycles GPU backend, or the CPU
renders/               10 clockwise 1024×1024 PNGs (PDF spec)
metadata.json          one record per clockwise render
textures/tex_01 … 09/  nine texture sets in GNM UV space (UDIM tiles and per-region names)
outputs/videos/        left.mp4, right.mp4, generate.mp4 (each ≤ 15 s)
outputs/stills/        one render per texture set; eye/ has one eye close-up per set
tests/                 unit tests: gaze engine, camera move, device choice (no Blender needed)
tools/                 build pipeline and validator (not needed to run the wrapper)
Dockerfile             renders one draft frame on CPU with the pinned Blender
AI_DISCLOSURE.md       which parts were made with AI tools
```

> TODO: `outputs/videos/` is not in the repo yet; the three final videos have not been rendered.

## Setup

- **Blender 4.5.1 LTS** (the version everything was built and tested with). No add-ons.
  Download: https://download.blender.org/release/Blender4.5/
- Everything inside Blender uses only `bpy` and `numpy` (bundled with Blender).
  No `pip install` is needed to render.
- Optional, outside Blender: Python 3.10+ with `numpy` for the tests, and `matplotlib` for the
  motion plots. `tools/validate.py` needs only the standard library.

Paths are relative to the repo root, so the bundle runs from wherever it is unzipped.
In the commands below `blender` is the Blender executable, for example
`/Applications/Blender.app/Contents/MacOS/Blender` on macOS or
`"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"` on Windows.

## Run

All commands are run from the repo root.

```bash
# the three videos (kinematic accuracy): frames → outputs/frames/<input>/, video → outputs/videos/<input>.mp4
blender -b scene.blend -P wrapper/eyes.py -- --input left
blender -b scene.blend -P wrapper/eyes.py -- --input right
blender -b scene.blend -P wrapper/eyes.py -- --input generate --seed 7

# 10 clockwise renders → renders/frame_00.png … frame_09.png, and metadata.json
blender -b scene.blend -P wrapper/eyes.py -- --clockwise

# one still with a texture set
blender -b scene.blend -P wrapper/eyes.py -- --move 0 0 --texture 3 --out outputs/still_03.png

# direction check: pupil pixels for reset, left, right, up, down, reset → outputs/direction_check.json
blender -b scene.blend -P wrapper/eyes.py -- --check-directions --render
```

| Option | Meaning |
|---|---|
| `--input left\|right\|generate` | render that motion and encode an MP4 |
| `--clockwise` | the 10 PDF-spec renders and `metadata.json` |
| `--move H V` | pose with `move(h, v)` and render one still to `--out` |
| `--check-directions` | write pupil positions for the 5-direction check; `--render` also saves PNGs |
| `--seed N` | seed for the motion (default 0); same seed, same frames |
| `--quality final\|draft` | `final`: Cycles, 1024² (default). `draft`: EEVEE, 512², much faster |
| `--texture NN` | use `textures/tex_NN` instead of the built-in materials |
| `--camera face\|eyes\|move` | Stills: `cam_face` (50 mm, whole face, the default) or `cam_eyes` (105 mm, eye region). Videos default to `move`: one level camera (`cam_move`, dark `eye` look) that holds a framing, glides to the next and holds again. It moves only while the eyes hold still: a glide (1.5 s of motion to or from the eye close-up, 1 s otherwise) that does not fit one fixation stops for each saccade or blink and carries on in the next fixation. `left` and `right`: both eyes (the first gaze shift is seen here), then the whole face, then the subject's left eye close up; `generate`: the eye, both eyes, the face. In the eye framing the camera rides on the head. `face` (`cam_video`, 72 mm) or `eyes` (`cam_eyes`) films with one fixed camera |
| `--samples N` | Cycles samples per pixel (default: as saved in `scene.blend`, 128), or EEVEE samples with `--quality draft` |
| `--fps N` | video frame rate (default 30) |
| `--limit N` | render only the first N video frames (for quick looks) |
| `--frames F [F ...]` | videos: render only these Timeline frames, as stills, into `outputs/frames/<input>/<camera>_stills/`; no video is encoded |
| `--cpu` | force Cycles onto the CPU. Without it the first GPU backend that has a device is used, tried in the order OptiX, CUDA, HIP, oneAPI, Metal; with no GPU, the CPU. The log line `[eyes] Blender …` names the one in use. Only Metal on an Apple M4 has been rendered with; use `--cpu` if a GPU backend fails on your machine |

Rough timings on an Apple M4 (Metal): `--clockwise` about 60 s; a draft video about 2 min.
Final Cycles videos take much longer; use `--quality draft` to try things out.

Opening `scene.blend` in the Blender UI and pressing play shows the `generate` motion on the
Timeline (eyes, lids, brows and head, keyframed).

### Python API

From Blender's Python with `scene.blend` open and the repo root on `sys.path`:

```python
from wrapper import eyes
eyes.move(0.5, -1.0)          # h, v in [-1, 1]
eyes.render("out.png")        # 1024×1024 PNG from cam_face; camera="eyes" for the close-up
eyes.reset()                  # back to centre
```

`move` drops the Timeline animation from memory (not from the file) so the static pose is
what renders.

### Checks

```bash
python tools/validate.py                      # bundle layout, metadata, directions, videos, textures, README, Dockerfile
python tools/validate.py --root /path/to/unzipped/bundle
python -m unittest discover tests             # gaze engine against published eye-movement numbers
python -m wrapper.gaze --mode left --seed 0 --plot /tmp/left.png   # the motion as curves
```

`validate.py --blender` also opens `scene.blend` headless and checks the eye bones,
materials, Timeline keyframes and that no file path in it is absolute.

### Docker

The image renders one draft frame on the CPU with Blender 4.5.1 (x86_64 Linux; on Apple
Silicon it runs under emulation). EEVEE gets its OpenGL context from Xvfb and Mesa llvmpipe.

```bash
docker build --platform linux/amd64 -t syntheticeyes .
```

```bash
docker run --rm --platform linux/amd64 -v "$PWD/outputs/docker:/work/outputs/docker" syntheticeyes
```

Output: `outputs/docker/draft.png` (about 40 s under emulation on an Apple M4). Any wrapper
command can be passed after the image name, for example
`blender -b scene.blend -P wrapper/eyes.py -- --input left --quality draft`; the entrypoint
starts the virtual display first. Final quality uses Cycles on the CPU in the container
(`--cpu`) and is slow there.

## Conventions

**Directions are in image space**, as the camera sees the face:

- `h > 0` moves the pupils to **image-right**, `v > 0` moves them **up**. The `left` input
  means image-left.
- `move(h, v)` puts a fixation target on a plane **35 cm** in front of the eye midpoint at
  `(h · 5 cm, v · 5 cm)` and aims both eyes at it, so they converge slightly. At |h| = 1 the
  gaze is atan(5/35) ≈ 8.1° off centre. The head stays still.
- `L` is the subject's left eye, which appears on the **right** of the image.

**Cameras.** Both cameras sit 40 cm in front of the eye midpoint, looking at the face,
1024 × 1024, constant lighting. `cam_face` has a 50 mm lens on a 36 mm sensor.

**Clockwise renders.** Frame k (0…9) has θ = 2πk/10, h = sin θ, v = cos θ, so frame 0 looks
up and the sequence goes clockwise in the image.

**metadata.json**, one record per render:

| Key | Meaning |
|---|---|
| `frame`, `theta`, `input.h`, `input.v` | as above |
| `eye_rotation_L`, `eye_rotation_R` | world-frame rotation of each eye bone from rest, Euler XYZ, radians. Blender world axes: +X image-right, +Y away from the camera, +Z up |
| `pupil_center_2D_L`, `pupil_center_2D_R` | pupil centre in pixels of the 1024² render, **origin top-left, x right, y down** |
| `camera_matrix` | 3×4 `P = K [R | t]`, OpenCV convention (x right, y down, z forward); `P · [X, Y, Z, 1]` divided by its third row gives the pixel |
| `K`, `camera_world_matrix` | intrinsics (3×3) and the camera-to-world matrix (4×4) |
| `image` | path of the render |

**Units and axes.** Metres. GNM is +Y up, +Z forward; in `scene.blend` a GNM point
`(x, y, z)` sits at Blender `(x, −z, y)`, so the face looks along Blender −Y. UVs are unchanged.

## UV layout and texture sets

All textures use **GNM Head v3's own UVs**. GNM has two layouts of the same unwrap:

| UDIM tile | Region | Our file |
|---|---|---|
| 1001 | skin | `skin.1001.png` (albedo, brows baked in), `skin_normal.1001.png`, `skin_rough.1001.png` |
| 1002 | left eye interior: sclera, iris, pupil | `eye.1002.png` |
| 1003 | left cornea | none (clear) |
| 1004 | right eye interior | `eye.1004.png` |
| 1005 | right cornea | none (clear) |
| 1006 | teeth and gums | none |
| 1007 | tongue | none |

- **UDIM** (GNM's `quad_uvs_udim`, the `UDIM` UV map in `scene.blend`): one tile per region.
- **Legacy** (GNM's `quad_uvs`, the `legacy` map): every region in the unit square,
  overlapping. The same pixels ship under per-region names in `legacy/`:
  `skin.png`, `eye_L.png`, `eye_R.png`. Left and right eyes overlap in this layout, so they
  need separate materials.

Each set, `textures/tex_NN/`:

```
skin.1001.png          4096²  albedo, sRGB, eyebrows and fine colour detail baked in
skin_normal.1001.png   4096²  tangent-space normal, OpenGL convention (+G = up in UV), Non-Color
skin_rough.1001.png    2048²  roughness 0…1, Non-Color
eye.1002.png           2048²  left eye interior, sRGB
eye.1004.png           2048²  right eye interior, sRGB (same colour, different iris seed)
legacy/skin.png, legacy/eye_L.png, legacy/eye_R.png    same pixels, per-region names
preview.png            the set on the bare GNM template
```

The pupil is geometry (GNM's pupil coefficient), so the texture keeps the pupil region dark and
the mesh sets its size.

The nine sets. The label, the skin source and the iris colour are in each set's `set.json`:

| Set | Label | Skin source | Iris |
|---|---|---|---|
| `tex_01` | young woman, light skin | MakeHuman `onlytheghosts_young_eurasian_female` | hazel |
| `tex_02` | young woman, South Asian, medium brown skin | MakeHuman `cutoff3d_indian_female_skin` | dark brown |
| `tex_03` | middle-aged man, Black | MakeHuman `mindfront_skin_male_african_middleage` | dark brown |
| `tex_04` | old man, light skin, ash brows | MakeHuman `onlytheghosts_old_eurasian_male` | blue |
| `tex_05` | young man, East Asian | MakeHuman `young_asian_male` | brown |
| `tex_06` | old woman, Black, deep brown skin | MakeHuman `old_african_female` | brown |
| `tex_07` | young man, light freckled skin, auburn brows | MakeHuman `toigo_light_skin_male_freckles` | green |
| `tex_08` | middle-aged woman, light skin | MakeHuman `onlytheghosts_middle_aged_eurasian_female` | grey |
| `tex_09` | man, light skin with stubble, photographed skin | Infinite head scan, colour map (CC BY 3.0) | hazel |

Sets 01 to 08 take their skin colour from MakeHuman CC0 skins and have drawn eyebrows; `tex_09`
takes its colour from the head scan, eyebrows included. On 01 to 08, `tools/refine_skin.py`
rebuilds the drawn brows: a soft layer of pigment under the hairs, uneven strands, fine stray
hairs, a little relief in the normal map and a rougher brow. It also raises the fine skin detail
toward the scan's level. Each `set.json` records what it did under `refine`. All nine share the scan's pore-scale
relief in the normal map. The stills in `outputs/stills/` show each set on its own GNM identity.

### Putting a set on a bare GNM head

1. Give the head one material per region: skin (tile 1001), left eye interior (1002), right
   eye interior (1004), both corneas (1003, 1005), and anything for teeth and tongue.
2. **Skin**: Principled BSDF. `skin.1001.png` → Base Color (sRGB). `skin_rough.1001.png` →
   Roughness (Non-Color). `skin_normal.1001.png` (Non-Color) → Normal Map node (tangent space,
   same UV map) → Normal. Optional for our look: Subsurface Weight 0.25, Radius
   (1.0, 0.35, 0.2), Scale 0.003 (the scene is in metres).
3. **Eye interiors**: Principled BSDF, `eye.1002.png` / `eye.1004.png` → Base Color,
   **Roughness 0.6, Specular IOR Level 0.1**. With Blender's default specular (0.5) and no
   cornea, the irises read grey and washed out at face size; this was measured in our wrap test.
4. **Corneas**: fully transparent (Principled Alpha 0), or glass that is transparent to shadow
   rays (Light Path → Is Shadow Ray mixing in a Transparent BSDF), or the iris renders dark.
5. Image Texture nodes keep their default **Repeat** extension, so with the UDIM map each tile
   reads its own file and no tiled image is needed. With the legacy map use the `legacy/` files.

The same steps as a script, tested on the mesh in `scene.blend` (needs GNM's UDIM UVs on the
mesh; `uv` is the name of that UV map):

```python
import bpy
from pathlib import Path


def apply_set(obj, folder, uv="UDIM"):
    """Put a SyntheticEyes texture set on a GNM head mesh that has GNM's UDIM UVs.

    Faces get one material per UDIM tile (1001 skin, 1002/1004 eye interiors,
    1003/1005 corneas, 1006/1007 mouth). Image lookups use the default Repeat
    extension, so each tile reads its own file without a tiled-image setup.
    """
    folder = Path(folder)

    def img(name, colour):
        im = bpy.data.images.load(str(folder / name), check_existing=True)
        im.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        return im

    def material(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        return m, m.node_tree, m.node_tree.nodes["Principled BSDF"]

    def tex(nt, image, socket):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image, t.interpolation = image, "Cubic"
        u = nt.nodes.new("ShaderNodeUVMap")
        u.uv_map = uv
        nt.links.new(u.outputs["UV"], t.inputs["Vector"])
        nt.links.new(t.outputs["Color"], socket)

    skin, nt, b = material("se_skin")
    tex(nt, img("skin.1001.png", True), b.inputs["Base Color"])
    tex(nt, img("skin_rough.1001.png", False), b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = uv
    tex(nt, img("skin_normal.1001.png", False), nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])

    eyes = {}
    for side, tile in (("L", 1002), ("R", 1004)):
        eyes[side], nt, b = material(f"se_eye_{side}")
        tex(nt, img(f"eye.{tile}.png", True), b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 0.6
        b.inputs["Specular IOR Level"].default_value = 0.1

    cornea, _, b = material("se_cornea")
    b.inputs["Alpha"].default_value = 0.0
    mouth, _, b = material("se_mouth")
    b.inputs["Base Color"].default_value = (0.55, 0.30, 0.28, 1.0)

    me = obj.data
    me.materials.clear()
    for m in (skin, eyes["L"], cornea, eyes["R"], cornea, mouth, mouth):
        me.materials.append(m)
    loops = me.uv_layers[uv].data
    for p in me.polygons:
        p.material_index = min(max(int(loops[p.loop_start].uv[0]), 0), 6)


# apply_set(bpy.context.active_object, "textures/tex_01")
```

## How it works

- **Gaze engine** (`wrapper/gaze/`, numpy only): saccades with amplitude-dependent duration
  and peak velocity, overshoot and corrective saccades, fixation drift and jitter, Poisson
  blinks (closing faster than opening, coupled to large gaze shifts), upper lid following eye
  pitch, brows and a slight squint travelling with the gaze, head joining large shifts with a
  vestibulo-ocular counter-rotation. Numbers from Ruhland et al., *A Review of Eye Gaze in
  Virtual Agents, Social Robotics and HCI*, Computer Graphics Forum 2015.
- **Rig** (`wrapper/rig.py`): GNM's four joints as Blender bones, lid, blink, brow and squint
  shape keys built from GNM expression components, the pupil coefficient as a shape key.
  Motion is baked as keyframes, so it plays on the Timeline.
- **Textures** (`tools/`): MakeHuman CC0 skins baked onto GNM's UVs through a one-off
  registration of the two heads, procedural pore, furrow and roughness maps, and procedural
  irises with a different seed per eye.

`scene.blend` is generated by `tools/build_scene.py`; the tools need their own Python
environment and the downloaded assets, and are not needed to run the wrapper. It is built on
the GNM identity paired with the hero set `tex_09`, so the videos show the same head as the
hero still:

```
$BLENDER -b --factory-startup -P tools/build_scene.py -- --npz assets/gnm/id_male_white_9.npz
```

## Licences and credits

| Asset | Use | Licence |
|---|---|---|
| [Google GNM Head v3](https://github.com/google/GNM) | head mesh, joints, UVs, expression basis | Apache-2.0 |
| [MakeHuman](https://static.makehumancommunity.org/assets/assetpacks.html) Skins 01 and 02, Eyebrows 01, Eyelashes 01, system assets and base mesh | skin colour source, eyebrows, registration target | CC0 |
| [Poly Haven `brown_photostudio_02`](https://polyhaven.com/a/brown_photostudio_02) | lighting (HDRI packed in `scene.blend`) | CC0 |
| "Infinite, 3D Head Scan by Lee Perry-Smith", based on a work at www.triplegangers.com ([download](https://casual-effects.com/g3d/data10/research/model/lpshead/lpshead.zip), McGuire Computer Graphics Archive) | displacement map, filtered to pore scale: skin micro-relief in the normal maps and colour detail of every set; colour map: the skin of `tex_09` only | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| Blender 4.5.1 | renderer (tool only, not redistributed) | GPL |

Irises, sclera, the rest of the detail maps (lips, lids, ears, roughness, colour variation), the
gaze engine and all code were made for this project, with AI coding tools; see
[AI_DISCLOSURE.md](AI_DISCLOSURE.md). The scan's geometry and original files are not
redistributed; each `set.json` names what it takes from the scan.

Code licence: TODO (pick one before submission, e.g. MIT).

## Docs

- [AI_DISCLOSURE.md](AI_DISCLOSURE.md): which parts were made with AI tools
- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md): what the organisers ask for
- [docs/PLAN.md](docs/PLAN.md): plan and architecture
- [docs/TECH_NOTES.md](docs/TECH_NOTES.md): technical notes, reference bar, asset sources
- [docs/PROGRESS.md](docs/PROGRESS.md): work log
