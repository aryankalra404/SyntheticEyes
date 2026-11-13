# Progress

Newest entry first. One entry per working session: what changed, what was measured,
what the next session needs to know.

## Status

| Milestone | State |
|---|---|
| M0 Setup and spikes | done |
| M1 Rig and calibrated wrapper | done (13 Nov): lids solved (`tools/solve_lids.py`), globe guard, rig reviewed; `scene.blend` rebuilt with `lid_shapes = "solved"` |
| M2 Texture pipeline | done (13 Nov): 9 sets in `textures/`, all with scanned skin micro-relief; `tex_09` (photographed skin) is the hero set; contact sheet in `outputs/stills/texture_sheet.png` |
| M3 Look | done on stand-in lids (Fable, 13 Nov): lashes, wet eye, skin, two lighting looks, nine stills; open items listed in the M3 entry (iris texture, brow hair weight, recheck after the lid solve) |
| M4 Motion | gaze engine done and tested; rig adapter and Timeline bake done (M1 plumbing); draft videos render with the face + eye inset framing (Opus, 13 Nov; inset size, lens and head follow are Fable's); final videos pending |
| M5 Compliance and packaging | README, Dockerfile (built and run) and validator done (Opus, 13 Nov); clean-clone and zip test of the real bundle and the final renders wait for M1–M4; TODOs listed in the M5 entry |
| M6 Ship | not started |

## Open questions

- College and team name for the zip and deck (`CollegeName_TeamName`)

## Log

### Fri 13 Nov 2026, late — M4 video framing: face with an eye inset (Opus)
`wrapper/eyes.py` only. Videos now default to `--camera both`: each Timeline frame is rendered
from `cam_test_face` (85 mm, forehead to chin, `face` look) and from `cam_eyes` (`eye` look),
the eye band is pasted into the face frame with numpy, and the 1024² frames go to Blender's own
FFmpeg at 30 fps as before. `apply_look()` runs per camera. `--camera face` / `eyes` still render
one camera alone (`face` for videos is now `cam_test_face`; stills and `--clockwise` keep
`cam_face`). New `--samples N` (Cycles, or EEVEE with `--quality draft`). `--camera both` is
refused for stills.

How it renders: two passes over the Timeline (face, then eyes), then a composite pass. The eye
pass uses a render border cropped to `INSET["crop"]`, at the resolution where the crop comes out
at inset size, so only the band costs time. Frames land in `outputs/frames/<mode>/{face,eyes,video}/`
(git-ignored). Draft renders at 50 % and is scaled up to 1024² in the composite. Composite keeps
the rendered 8-bit values (means within 0.2/255 of the source PNGs).

**Inset now** (`INSET` at the top of `eyes.py`): crop of cam_eyes x 0.10-0.90, y 0.31-0.62 (brows
to below the lower lids), 573 × 222 px, centred, 14 px from the top, 2 px grey border, over the
scalp. At that size the eyes are only **1.24 ×** their size in the face frame (interpupil 258 px
in the face, 321 px in the inset), so it reads as a second lighting more than a close-up.

**Timing** (M4 Metal, 1024², `--input left --samples 64 --limit 10`, includes Blender's
start-up on frame 1): face 14.7 s/frame, eye inset 3.2 s/frame, composite 0.08 s/frame;
**18.0 s per composited frame**. The three videos are 861 frames: about **4.3 h at 64 spp**.
Draft (EEVEE 32): 0.52 s per composited frame, 2.5 min for `left`.

**Looked at**: four frames from each draft video (`left`, `right`, `generate` seed 0; 9.0, 9.0,
10.7 s; decode as 1024², 30 fps), and the Cycles frame 10 of `left`. Draft EEVEE corneas look
like mirrored glass; that is EEVEE refraction, Cycles is right. `outputs/videos/*.mp4` are
these drafts; not committed. Final videos not rendered. Unit tests pass (18); `tools/validate.py`
passes except the README TODO lines it already flagged.

**For Fable** (yours to judge; all in `INSET` and in `tools/build_scene.py`, which I did not touch):
- **An eye leaves the inset when the head turns.** cam_eyes is fixed in the world and the crop is
  fixed in its frame, so in `right` (frames 60-120) and `left` (around 120) one eye is cut by the
  inset edge. Fix in `build_scene.py`: make cam_eyes follow the head (child of the head bone, or a
  Copy Transforms on it), so the inset holds the eyes still and shows eye-in-head motion. The other
  way is to centre the crop on the projected eye midpoint every frame in `eyes.py`, but the crop
  has only ±0.10 of the frame to move in.
- **Size and position.** 1.24 × is weak. A real close-up needs a longer lens on cam_eyes (about
  180-200 mm frames both eyes at roughly 2 ×) or one eye in the inset. Over the scalp is the only
  place that hides no face texture; the bottom of the inset sits about 10 px above the face's
  brows, so a brow raise can touch it.
- **Lens and stop.** cam_eyes is 105 mm at f/11. A longer lens at the same stop also gives
  shallower depth of field; check the lashes and the far eye corner stay sharp.
- Inset border 2 px, grey 0.55: keep, change or drop.

### Fri 13 Nov 2026, late — M3 iris: the five make_iris items, eye tiles rebuilt (Opus)
Did the five items from "Iris: what `tools/make_iris.py` needs" in the M3 entry and rebuilt the
eye files of all nine sets with the new `python3 tools/build_textures.py --eyes-only`
(eye.1002/1004, legacy eye_L/eye_R, set.json, preview.png; the texture sheet too). The skin
maps were not touched: no `skin*` file shows in `git status`.

1. **Collarette** blends over ±0.08 of the iris width and reaches outward along radial spokes
   (`collarette_reach` 0.08-0.16 of the width), ragged along the fibres; the ridge is low and
   follows the fibres. Pupillary and collarette hues are within 15° of the fibre hue.
2. **Tone in the palettes.** All palettes are now final colours: the shader's linear-HSV
   saturation × 0.72 and value × 0.80 are applied to the old values, and brown and dark brown are
   set by hand darker and warmer (brown fibre 98,62,36, was 119,90,73 after the shader tone).
   Fibres also wander a little (a second, longer warp), which took away the zoom-blur look.
3. **Limbal ring** in UV in `make_eye`: from 72 % of the limbus radius to × 0.45 at the limbus,
   fading 0.03 UV into the sclera, strength ±8 % around the eye. The palette's limbal colour
   pull is softer (from t 0.75, × 0.7).
4. **Crypts**: 40-80 rounded-diamond lozenges, 1.8-3.6 times longer along the radius than
   across, a little longer outward, lognormal size; 70 % sit just outside the collarette
   (exponential falloff), bigger and deeper there; lighter trabecular rims.
5. **Sclera** × (1 − 0.3 · smoothstep(0.20, 0.40, R)), the shader's fornix falloff.

**Looked at**: the six colours flat and at face size (`outputs/tmp/m2/iris_v4/sheet.png`), all
nine sets' L and R tiles flat, and every set in the bare-head wrap test with two extra close
shots (`outputs/tmp/m2/sets/tex_NN/wrap_eye_front.png`, `wrap_eye.png`). Hazel and green show a
warmer / lighter inner zone that streaks out instead of an orange patch; crypts read as lozenges.
In the wrap test the plain Principled (specular 0.5, no cornea) lays a grey sheen on dark
irises (the pupil, albedo 6,5,5, renders mid-grey), so browns look lighter there than in the
scene.

**For Fable** (`tools/build_scene.py`, not edited here): the tile now carries the tone, the
limbal ring and the fornix falloff, so in `eye_textured` set `IRIS_SATURATION = 1`,
`IRIS_VALUE = 1`, `LIMBAL_DARK = 0`, **and drop the `far` × 0.3 term** (it is hard-coded in the
`gain` expression, not behind a constant; leaving it darkens the sclera twice). Then rebuild
`scene.blend` and rerun `tools/render_stills.py`, and check the eye stills against the M3 ones:
browns should read darker and warmer, the rest about the same tone.

### Fri 13 Nov 2026 — M1 lid solve, globe guard, rig review (Fable)
The five items left in `docs/BRIEF_M1.md`. New: `tools/solve_lids.py`, `tools/check_lids.py`.
Changed: `tools/build_scene.py`, `wrapper/rig.py` (one line). `scene.blend` rebuilt (9.9 MB,
`lid_shapes = "solved"`, `blink_keys = "tent"`).

**The solve** (`python3 tools/solve_lids.py`, numpy only, 0.8 s, byte-identical across runs;
`assets/gnm/lids.npz` is git-ignored like `base.npz`, so run it before `build_scene.py`).
Per eye: the globe is read from the eyeball mesh as a radius profile about the optical axis
(sclera 14.60 mm, cornea apex 16.22 mm). Every margin and pocket vertex is rotated about the
joint's left-right axis by its column's angle (zero at both corners), then reseated on the
globe as posed for that key. The 100 eye-region coefficients are fitted to those targets with
the far ring held still; what the basis misses is added directly and spread over 3 mm of skin.
Skin that rides the globe keeps its rest clearance over the posed globe. Everything fades out
between 18 and 30 mm from the pupil.

What differs from the brief, and why:
- **Targets run along the whole lid**, not one column: lid follow tapers as sin(pi s)^0.7 to the
  corners; a blink rotates each margin vertex to the other lid at the same x.
- **`lid_up` and `lid_down` are the least-squares line through the arc** (at 0.25 to 1.2 of the
  way). A key is a straight line; the end point alone put the margin 0.28 mm inside the globe
  at half weight.
- **A retracting lid carries its own skin.** With the basis fit alone, an upper lid going up slid
  in behind the lid skin above it and the lashes came out through the skin (seen at +20 deg).
  For the upper lid in `lid_up` / `lid_open` and the lower lid in `lid_down`, the lid's skin is
  rotated with the margin, fading over 20 mm (upper) or 12 mm (lower) of skin.
- **Globe guard** (`build_globe_guard` in `tools/build_scene.py`). Lid keys cannot meet
  number 2 below by themselves: the cornea bulge moves with yaw, and under a closing lid with
  pitch, and no key knows. The template alone, lids untouched, has the cornea 0.86 mm (L) and
  0.91 mm (R) through the lid skin at 30 deg yaw; keys alone leave 1.2 to 1.3 mm in the worst
  combined pose (closed lids, eye down 20 deg). So each eye has a hidden copy of its shell on
  the eye bone, and the head, the lash carrier and the tear lines each have a Shrinkwrap
  modifier (nearest surface point, outside mode, 0.12 mm): a vertex moves only while it is
  inside the globe. This bends M1's "no drivers, no constraints": it is a modifier, evaluated
  by Blender with the armature, no Python, and the eyes and pupils (so `metadata.json`) are
  untouched. `--no-guard` builds without it.
- **Identity heads** (`--npz`): `lids.npz` records the hash of the vertices it was solved on;
  for any other head `build_scene.py` runs the same solve in-process. Checked on the ten cached
  identities: closed gap 0.00 to 0.13 mm, rest lid 2.3 to 4.1 mm above the pupil brought to 4.0.

**The three section-1 numbers** (template; `tools/solve_lids.py` prints them, number 2 is from
`$BLENDER -b scene.blend -P tools/check_lids.py`, the evaluated mesh over 385 poses)

| | Left | Right | Brief |
|---|---|---|---|
| 1. Lid gap at blink 1.0, column through the pupil | 0.04 mm | 0.04 mm | <= 0.2 |
| largest gap along the middle 70 % of the lid | 0.13 mm | 0.09 mm | |
| gap at blink 0, 0.33, 0.67 | 9.15, 6.13, 2.95 | 9.09, 6.13, 2.95 | |
| basis-fit residual on the margin, mean / max: `blink` | 0.35 / 1.20 mm | 0.36 / 1.23 mm | (0.3: correct directly) |
| `blink_33`, `blink_66` | 0.19 / 0.66, 0.28 / 0.90 | 0.20 / 0.68, 0.29 / 0.92 | |
| `lid_up`, `lid_down`, `lid_open` | 0.41 / 1.08, 0.47 / 1.35, 0.05 / 0.12 | 0.41 / 1.08, 0.48 / 1.34, 0.05 / 0.14 | |
| 2. Lid skin deepest inside the globe, pitch -30..+25, yaw +-30, blink 0..1 | 0.012 mm | 0.022 mm | <= 0.05 |
| the same from the keys alone, no guard: yaw 0 / all yaw | 0.98 / 1.19 mm | 0.97 / 1.28 mm | |
| keys alone at the six poses they were solved for | 0.01 mm | 0.06 mm | |
| margin back edge under the globe, worst pose | 0.10 mm | 0.10 mm | |
| margin back edge standing off the globe, worst pose | 2.0 mm | 2.1 mm | |
| 3. Upper margin above the pupil centre, rest | 4.03 mm | 4.05 mm | |
| over pitch -25..+20 | 3.62 to 4.05 mm | 3.66 to 4.07 mm | within 1 mm of rest |

The basis reaches no key within 0.3 mm at the worst margin vertex, so every key carries the
direct margin correction; the margin itself is on target exactly. The fit shapes the skin.

Number 2 holds for the skin. It does not hold for "margin standing off": where a key seats the
margin on the cornea and the eye has since yawed away, the back edge is left above the sclera,
0.9 mm at rest lids and 30 deg yaw (the template's own lid does this: its margin sits on the
cornea), up to 2 mm in the worst mid-blink pose looking down and sideways. At yaw 0 it is
0.06 mm or less from -25 to +10 deg and 0.43 mm at +20. It does not show in the yaw strips.
Pulling the margin down as well would need a second modifier that also moves it at rest; not done.

**`REST_LID_OPEN` = 1.0.** `lid_open` at 1.0 puts the upper margin 4.0 mm above the pupil
centre (template 3.24 / 3.33 mm; the clinical normal is 4 to 5). Chosen from the `cam_eyes`
reset frame at 0, 0.5, 1.0 and 1.5: at 1.0 the lid covers about the top millimetre of the iris;
at 1.5 the iris edge is almost bare and the eye starts to stare; at 0 and 0.5 the lid is heavy.

**`wrapper/rig.py` review.** Checked on paper and against numbers:
- `_set_local`: with pose = parent pose x (parent rest)^-1 x rest x basis, a bone's deformation
  is its parent's times `M basis M^-1`, so `basis = M^-1 L M` gives exactly "parent, then L".
  Every pivot is the bone's own head, so the basis is a pure rotation and location 0 is exact.
- Eye aim: each eye aims from its posed joint at one world point, in the head's rest frame,
  yaw then pitch (Fick, no torsion; real eyes follow Listing's law, a few degrees of iris
  twist at oblique gaze that nobody will see). Vergence comes from the shared point.
  `tools/check_lids.py` poses 385 gazes through the rig and its lid-inside-globe figure without
  the guard matches the numpy figure to the micron (1.194 / 1.276 mm), which checks the yaw and
  pitch signs and the composition order against an independent implementation.
- Head split: 35 / 65 about the neck and head joints. The two partial rotations do not
  compose to exactly the commanded yaw, pitch, roll, and it does not matter: the eyes aim at
  the world target from wherever the head ended up.
- Quaternion keys cannot flip sign between frames (all rotations are far below 90 deg), so
  the sub-frame samples motion blur takes are safe.
- Lid follow uses each eye's own in-head pitch, scaled by (1 - blink), and the tent weights
  sum correctly. Lid travel through a blink is monotonic from any gaze pitch.
- **One fix: `squint` now fades with (1 - blink).** It lowers the upper margin, and left on
  through a blink it pushed the closed upper lid 1.4 mm past the lower one at squint 0.3.
- Left as is: `brow_up` at 1.0 opens a closed lid by 0.26 mm (0.11 mm at 0.3).

**Looked at** (Cycles unless said): the `tools/rig_strips.py` strips from `cam_eyes`
(`outputs/tmp/m1/`: pitch -25, -12, 0, +10, +20; yaw -30, +30; blink 0, 0.33, 0.66, 1.0; brow,
squint, widen); the same poses close up from `cam_test_eye`, plus pitch +25 with widen, and
six combined poses with and without the guard (yaw 30; yaw 30 half closed; closed looking down
20; down 25 with yaw 30; closed with yaw 30). The iris never tucks under the lid from -25 to
+20, sclera shows below it at +20, the closed lid is one clean line, lashes stay on the lid.
Also `tools/look_shots.py -- --texture 9 --blink` (blink 0, 0.5, 1.0 from `cam_test_eye`):
nothing pokes through, upper lashes sweep down over the closure, the tear line stays on the lid.
**Forehead**: whole-face renders of the darkest set (`--texture 6`) at centre, +20, -25 and blink
1.0. A render with every lid key at 0 and one with `lid_open` at 1 differ only around the eyes
(under one grey level anywhere on the forehead); no lid key moves a vertex within 1 mm of the
midline (0.005 mm within 3 mm) or the forehead group by more than 0.09 mm. tex_06 does show a
soft vertical change of tone down the forehead on the template head in both renders, so it is
in the map or the light, not in a shape.

**Draft `left` video** (`--input left --quality draft`, 270 frames, 9.0 s, 8 saccades, 3 blinks).
It was not watched at playback speed: this session can only read frames. Instead every pair
of neighbouring frames was differenced (no frame differs from both neighbours by more than
they differ from each other, so no one-frame pops; the motion ramps are smooth), and Cycles
frames of the same track from `cam_eyes` were looked at for 33-48 (first saccade, 23.7 deg: the
eyes land in 3 frames with motion blur, the head follows to frame 48), 89-98 (blink: shut in
2 frames, open in 4) and 156-167 (blink during the return saccade, eyes about 20 deg off
centre: the closed lid is a clean line, no cornea through it). **Someone should still press
play on it.**

**Found / left for M3, M4, M5**
- **EEVEE drafts show the cornea as a mirror** since the M3 look (no refraction in the draft
  settings): the iris is hidden behind a reflection of the HDRI and lashes render as thick
  black wire. Draft videos are good for timing only. `setup_render("draft")` in
  `wrapper/eyes.py` needs raytraced refraction on the cornea and tear materials, or a plain
  draft material.
- **The nine stills in `outputs/stills/` are on the old lids** (stand-in, rest opening 0.5). On
  solved lids every identity's upper lid rests 4.0 mm above the pupil centre (their own rest is
  2.3 to 4.1 mm), so the eyes are more open. Re-render once (`python3 tools/render_stills.py`)
  after the iris work lands. Not done here.
- A short black dash at the outer end of the subject's right lower lid in every `cam_eyes`
  frame, also in M3's `outputs/tmp/m3/scene_check_eyes.png`: probably the tear line's mirror
  share picking up the black backdrop.
- Lashes and the tear line are bound to the shape keys, not to the guarded mesh. Where the
  guard lifts the lid edge over the cornea (up to about 1 mm in off-centre gaze) they stay
  put, but they are guarded themselves, so they sit on the cornea rather than inside it.
- `README.md` "How it works" should say the lids are solved on the globe and name the guard;
  `validate.py` still fails only "README: no TODO left" (5 lines, as before this session).
- `renders/`, `metadata.json` and the videos are still the pre-solve ones; M4 / M5 regenerate.
- Checks at the end: `python -m unittest discover tests` 18 pass; `tools/validate.py --blender`
  passes everything but the README line; direction check unchanged (left -13.8 / -14.2 px,
  right +14.2 / +13.8, up -14.0, down +14.0).

### Fri 13 Nov 2026 — M3 look: lashes, wet eye, skin, light (Fable)
Tuned on `tex_09` (identity male_white_9) with the two fixed test shots after every change, then
checked on all nine sets. Everything is in `tools/build_scene.py` unless named. `scene.blend`
rebuilt (9.4 MB); it now loads `tex_09` by default (`--texture` default 9, the hero set).

**Lashes** (`tools/lashes.py`, new). Mindfront set 02 was carried and rendered, and all five
sets were plotted side by side: every one is drawn as mascara clumps for MakeHuman's lid, and
through the registration the roots land up to 1 mm off GNM's lid edge, so upper lashes stand off
the lid and a tuft hangs at the outer corner. Trimming would not fix where they root. Lashes are
now grown per head on GNM's own lid margin: the socket rim is the back edge of the margin, the
first ring of outer skin (0.6-0.9 mm further out) is the front edge, and lashes root there.
135 upper (8.5 mm at the longest) and 62 lower (4.5 mm) per eye, 7 points each, radius 48 to
8 µm, jittered length, curl and fan, 22 % short ones, loose groups of two or three. Each lash is
bound to the triangle under its root, so it turns with the lid exactly as before. A lash that
would pass through skin (hooded lids: sets 02, 05, 08, 09) is uncurled in 5° steps until it
clears; on those sets the outer upper lashes run under the fold and show less.
`tools/carry_hair.py` carries brows only now.

**Eye.** Cornea shell is Glass IOR 1.376, roughness 0, transparent to shadow rays; the iris is
3.4 mm behind the apex in GNM, so the refraction is real and the catchlight sits on the cornea.
Eye interior: sclera subsurface 0.6 and darker toward the fornix; iris bumped from its own
fibres. Three shader-side corrections stand in for texture work (see "Iris" below):
`IRIS_SATURATION` 0.72, `IRIS_VALUE` 0.80, `LIMBAL_DARK` 0.55.

**Wetness.** Per-vertex masks on the head (`build_masks`): `wet` (lid margin and the pocket
behind it: roughness × 0.25, clear coat with a 0.5 mm ripple so the highlight breaks into
glints), `pink` (pocket and inner corner in wet red instead of the albedo's skin fill, strongest
within 4.5 mm of the inner corner). The tear line was invisible because its globe row sat 0.07 mm
under the eye's outer shell; it is now a 5-row concave fillet from three-quarters across the lid
margin to 0.75 mm up the shell, Glass IOR 1.34 plus 10 % mirror (Fresnel alone is too faint to
read at 1024 px; this is the one non-physical number).

**Skin.** Random-walk (skin) subsurface, weight 1, radius (1, 0.35, 0.18), scale 2.5 mm (4 mm
blurred the lid edge and pores), × 1.5 on the orbital skin. Lips: roughness × 0.7, coat 0.25.

**Light.** Two looks carried by the camera as custom properties and applied by
`wrapper/eyes.py apply_look()` (new; called from `render()` and `video()`): `face` for cam_face,
cam_test_face and the clockwise renders (HDRI 0.24, 45 × 60 cm key 17 W up and to image left,
plain dark-grey backdrop instead of the HDRI's window); `eye` for cam_eyes and cam_test_eye
(HDRI 0.14, black backdrop, 10 × 15 cm key 1.3 W from the nose side, depth of field: f/40 on the
100 mm test camera at 11 cm, f/11 on cam_eyes). AgX. Darkest set (06) is not crushed, lightest
(01, 09) not clipped.

**Found on the way: a step down the forehead midline.** It looked like a seam on set 06 and
survived removing the normal map, roughness, subsurface and the albedo. Cause: the stand-in lid
shapes (`lid_standins`) used the wink's whole displacement field as their mask, cut hard at
x = 0, so `lid_open` at its rest value 0.5 moved the left half of the forehead 0.46 mm and the
right half 0.31 mm, and `lid_up` / `lid_down` moved it up to 3.7 mm with the gaze. The mask now
fades out between 18 and 30 mm from the pupil. **The lid solve must keep lid shapes off the
forehead too.**

**Looked at**: both test shots at centre and 20° after each step (`outputs/tmp/m3/`), the eye
shot against "Eye Piece" at 0:11, the nine face stills and nine eye stills (`outputs/stills/`,
`outputs/stills/eye/sheet.png`), blink 0 / 0.5 / 1.0 on tex_09 (nothing pokes through, the
scanned-closed lids do not smear, upper lashes sweep down along the closure), and `scene.blend`
through `eyes.py --move` on both wrapper cameras. Unit tests pass (18).

**Render time** (M4, Metal, 1024², denoised). Subsurface is the cost: 10 s before it.

| Camera | 128 spp | 64 spp |
|---|---|---|
| cam_test_face / cam_face | 24 s / 16 s | 13 s / about 9 s |
| cam_test_eye / cam_eyes | 38 s / 37 s | 19 s / about 19 s |

About 900 video frames: eye camera 9.3 h at 128 spp, 4.7 h at 64; face camera 4 h at 128, about
2.2 h at 64; face plus eye inset 13 h at 128, about 7 h at 64. 64 spp was compared with 128 on
the eye shot and shows no visible difference in a still; check one moving second before
committing the videos to it. The two "about" figures for the wrapper cameras at 64 spp are scaled
from the test cameras, not measured.

**Iris: what `tools/make_iris.py` needs** (not done; textures were not rebuilt). With refraction
and the shader corrections the iris holds up in the close-up, but on a bare eye the tile still
looks painted:
1. Collarette: it is one flat colour from the pupil to 0.38 of the iris radius with a hard
   jagged edge. Blend it over ±8 % of the radius, let it reach outward as radial streaks, and
   keep its hue within about 15° of the outer zone.
2. Bake the shader's tone into the palettes (saturation × 0.72, value × 0.80), then set
   `IRIS_SATURATION` and `IRIS_VALUE` to 1. Brown (02, 03, 05, 06) should also be darker and
   warmer than the light tan it is; it reads grey-brown at face distance.
3. Limbal ring: start darkening at 72 % of the iris radius, reach × 0.45 at the limbus, and
   fade 0.03 UV into the sclera; then set `LIMBAL_DARK` to 0.
4. Crypts: now equal round dots in a ring at 60-70 % radius. Make them lozenges stretched
   along the radius, varied in size, densest just outside the collarette.
5. Sclera: bake the shader's falloff (30 % darker by UV radius 0.40).

**Left / known**
- Brow hair (carried Mindfront strands) is a heavy dark slab on 02-06 in the eye stills; thin
  it or drop the offset from the skin. tex_09 has none (its brows are in the colour map).
- Albedo tone patches at the top of the forehead on 02 and 04 (soft, from M2's bake); no hard
  seam on any frontal still. Behind the ears and the back of the neck are not in these stills.
- Wrap test and grey check were not rerun: the maps did not change.
- Recheck lashes and tear line at blink 1.0 once the solved lids are in.
- cam_eyes at f/11 is only mildly shallow; M4 picks the final inset framing and stop.

### Fri 13 Nov 2026, night — texture fixes and M3 mechanical parts (Opus)
**Texture sets**: `tools/build_textures.py` has an optional per-set `tone` (saturation about
luminance, hue rotation about grey, gain; linear light, before the detail layer). tex_02 to medium
brown (cheek Y 0.34 → 0.150, sRGB ≈ 145/97/68); tex_06 from red-brown 96/39/20 to deep brown
86/52/37 (Y 0.046, still the darkest); tex_05 brows lighter (opacity 0.75, density 1.2). Order by
cheek Y: 01 0.51, 07 0.47, 08 0.44, 05 0.38, 04 0.34, 02 0.15, 03 0.069, 06 0.046. Wrap tests of
02, 05, 06 looked at; contact sheet updated.

**M3**: see "Status 13 Nov, night" at the top of `docs/BRIEF_M3.md` for what is built, what is a
stand-in and what Fable must judge. New: `tools/carry_hair.py`, `tools/look_shots.py`; changed:
`tools/build_scene.py` (textured materials, hair, tear line, test cameras), `wrapper/eyes.py`
(`use_texture` only). `scene.blend` rebuilt (9.4 MB). Test shots 16 s per 1024² frame.
Looked at: the four test shots, the blink strip (0, 0.5, 1.0), a lower-margin crop.
Found on the way: the lash meshes store each hair's root ring last, so rings are now chained
through the faces and the root is the end lower along the skin normal (nearest-end flipped the
lower lashes). 27 lashes rooted more than 1.5 mm from the skin are dropped (one rendered as a
spike in every eye shot). Section 6: `tools/render_stills.py` renders a face still and an eye
close-up per set on its paired identity (9 sets, about 1 min each), all looked at; they are
plain-default placeholders until Fable's look work. `validate.py` "one still per set" now passes.

### Fri 13 Nov 2026, night — M2 scanned skin relief in every set (Fable)
The owner approved using the Infinite head scan's relief (CC BY 3.0, credit required). Its
displacement map now supplies the skin micro-relief; its colour map and mesh are not used.
The licence rule in `CLAUDE.md` has the exception, the README has the credit, TECH_NOTES has
the asset row. **The deck needs the credit line too.**

**Pipeline** (the three inputs are git-ignored; run in this order to rebuild)
1. `python3 tools/register_scan.py` → `assets/gnm/wrapped_to_scan.npz`. `tools/register_mh.py`
   was split into `register(...)` plus a MakeHuman `main()`; its output is byte-identical to
   before. 21 landmarks picked on a gridded front render of the scan (nose, lips, chin, the
   ends of the closed lash lines, brow hair) plus the nose tip. Four rings of skin round the
   eye pockets are not pulled, because the scan's eyes are closed. Identity fit: landmarks
   0.98 mm mean, surface 1.93 mm. After the snap: **face 0.035 mm mean, 0.096 mm p95**,
   0.52 mm max over 4,016 vertices. Scale 0.958 m per scan unit.
2. `$BLENDER -b --factory-startup -P tools/bake_scan.py [-- --colour]` →
   `assets/gnm/scan_height.npz` (4096², 16 samples, 85.9 % of the tile hit). `--colour` bakes
   the scan's colour as a check only: brows, lips, nostrils, ears and stubble all land where
   they should on the GNM template (`outputs/tmp/scan/check/check_sheet.png`).
   `tools/transfer_skin.py` now has a `__main__` guard so its helpers can be imported.
3. `tools/detail_maps.py` (new `--scan-relief`, default 1.0, 0 = generated only; without the
   npz it falls back to generated and says so): high-pass at 14 px (about 1.6 mm), soft clamp
   at 3.5 sd, drop patches whose local detail is under 0.35× or over 2.2–3.5× the median
   (smoothed sculpt layer, seams), even out local contrast (the jaw stubble is rougher than
   the cheeks), scale so the mean slope on nose, cheeks and forehead is 4.5°. Used on 90 % of
   the skin, 39 µm rms. Lids, a band round the brows, ears and lips stay generated. A third
   of the generated grain stays on top of the scan, since the bake holds nothing finer than
   a texel. The same valleys drive the pore tint in the colour detail and the pore roughness,
   reduced where the scan has stubble so no beard shadow appears.

**Looked at** (`outputs/tmp/m2/detail_scan/`): grey three-quarter and grey eye, generated vs
scan (`grey_three_quarter_pair.png`, `grey_eye_pair.png`, then `grey_v2.png` after the
fixes); the judges' wrap view old vs new (`wrap_front_pair.png`) and wrap plus textured eye
close-up after the stubble fix (`final_look.png`). On the grey head the difference is large:
forehead lines, crossing furrows on the cheeks, neck lines. In the wrap view the colour gains
fine real marks; the first pass put a stubble shadow on the chin of the young-woman skin,
gone after the fix.

**Known**
- The side of the nose next to the inner eye corner is rougher than its surroundings under
  raking light (the scan's own relief there).
- One person's micro-relief is on all 8 sets. Age and sex differences come from the per-set
  multipliers and the generated lid lines, as before.
- Sets 01–08 were rebuilt with `python3 tools/build_textures.py --skip-bake`.

**Set 09: the scan's own colour** (owner's go-ahead after seeing the colour check bake)
- `tools/bake_scan.py --albedo OUT.png` writes the scan's colour as a skin map: lid pockets and
  mouth get no source and are filled as in `transfer_skin.py`, the mouth sock gets a darkened
  lip colour, and luminance is capped at 8 % above its 1 mm neighbourhood to remove the small
  highlights baked into the photographs (1.65 % of texels). 85.4 % of texels come from the scan.
- `tools/build_textures.py` recipe `09` (`scan=True`): no drawn eyebrows (the scan's are in the
  colour), no generated colour detail (mottling, redness, freckles, moles, veins, pore tint all
  0), relief kept under the brows (`detail_maps.py --scan-brows`), hazel irises, seed 9.
  Every `set.json` now names the scan under `micro_relief`; set 09 also under `skin`.
- Looked at: wrap front and three-quarter (`outputs/tmp/m2/sets/tex_09/wrap_pair.png`) and the
  textured eye close-ups, front and three-quarter (`eye_pair.png`). It is the most real of
  the sets: real brow hair, skin tone and stubble, and the lids look right with the eyes
  open even though they were scanned closed. Not yet looked at during a blink.
- It is one man's likeness (his own scan, released CC BY). The other eight sets carry the
  variety; this one is the hero for the videos and the main still (see `docs/BRIEF_M3.md`).
- The iris is now the weakest part of the close-up: flat and painted next to real skin. M3.
- Repo size: each full rebuild of `textures/` adds about 350 MB of history. Commit rebuilt
  sets only when they are meant to stay.

### Fri 13 Nov 2026, night — M2 section 5: the 8 texture sets (Opus)
`tools/build_textures.py` builds `textures/tex_01 … tex_08` from a recipe table at the top of
the file (skin, brow set and brow flags, iris colour, seed, detail-map multipliers, GNM identity).
Per set: `transfer_skin.py` bake → `detail_maps.py --seed N` → `make_iris.py --color C --seed N`
→ albedo × detail in linear light → `skin.1001.png`, normal, roughness, `eye.1002/1004.png`,
`legacy/skin.png, eye_L.png, eye_R.png` (same bytes), `set.json`, then the wrap test on the
shipped files (front, three-quarter, profile, back) and its front as `preview.png`.
About 80 s per set. `python3 tools/build_textures.py` does all 8 and the sheet; `--sets 03 07`,
`--skip-bake`, `--skip-maps`, `--skip-check`, `--sheet-only`. Work files and the four wrap views
per set are in `outputs/tmp/m2/sets/tex_NN/` (git-ignored).

| Set | Who | Skin | Brows | Iris |
|---|---|---|---|---|
| 01 | young woman, light | onlytheghosts young eurasian F | 01 thin, mid brown | hazel |
| 02 | young woman, South Asian | cutoff3d indian female | 05, near black, opacity 0.8 | dark brown |
| 03 | middle-aged man, Black | mindfront male african middleage | 08 full, black | dark brown |
| 04 | old man, light | onlytheghosts old eurasian M | 05, ash brown, opacity 0.7 | blue |
| 05 | young man, East Asian | system young_asian_male | 08 full, black | brown |
| 06 | old woman, Black | system old_african_female | 01 thin, warm black | brown |
| 07 | young man, light freckled | toigo light skin male freckles | 05, auburn, opacity 0.7 | green |
| 08 | middle-aged woman, light | onlytheghosts middle-aged eurasian F | 01 thin, mid brown | grey |

Older sets get more lid lines and micro-furrows, male sets a little more pore depth, dark skins
half the redness, 07 more freckles (flags in `set.json`). Identity pairing for stills is in
`set.json` (`gnm_identity`: gender, ethnicity class, seed = set number; South Asian has no class,
paired with MIDDLE_EASTERN).

**Checks**: wrap test looked at for every set, front and three-quarter, plus profile and back;
eye crops at 2× for 01, 02, 04, 06, 07. Peaks 0.84 on light skins, 0.64–0.69 on 03 and 06.
`tools/validate.py` passes every texture check (8 sets, complete, all files under 50 MB; the
largest is the normal map, 21 MB). Assembly reruns byte-identical (md5 of tex_01 `skin.1001.png`).
`textures/` is 554 MB on disk; legacy files are identical blobs, so git stores them once.

**Changed on the way**
- First brow pass: grey brows on 04 read as blue painted bars, dark grey-brown on 06 was nearly
  invisible and bluish, auburn on 07 a flat band, 02 heavy. Fixed with lower opacity and shadow
  and warmer, darker colours. The pixels are warm (04 brow ≈ 80/72/63); the blue cast is contrast
  against orange skin, so keep brow colours warmer than seems right.
- 07 started on `toigo_light_skin_male_ginger`: its freckles smear into an orange streak along
  the inner corner of the left upper lid. Swapped for the same author's freckles skin, which is clean.

**Known, not fixed** (none of these need changes in the protected files to ship)
- Tone spread leans light: 02 (South Asian) reads light-medium on the template, and 05 reads
  as light as 01. Only 03 and 06 are dark. A medium-brown skin would widen it; the candidates
  (`callharvey3d_midtoned_female`, system `middleage_asian_*`) are also light-medium.
- 06 (system old_african_female) is saturated red-brown; plausible, but the reddest set.
- Dark-brown irises (02, 03) read grey at face size in the wrap test. That is the eye material
  issue from the tuning entry (default Principled specular, no cornea), not the texture.
- Most source skins carry shaved-scalp stubble; it shows on the back of the head in every set.
- 04: a lighter band above the brows comes from the source skin, not the brow drawing.
- `validate.py` still fails "stills: one per texture set": that is M3 (one still per set on its
  paired identity), not section 5.

### Fri 13 Nov 2026, night — M5 README, Dockerfile, validator (Opus)
**README.md** rewritten for evaluators: contents, setup (Blender 4.5.1 LTS, no add-ons, no pip
inside Blender), every wrapper command and flag, Python API, checks, Docker, conventions
(image-space directions, 35 cm plane, ±5 cm, cameras, clockwise order, every metadata key,
pixel origin, GNM → Blender axes), UV layout (UDIM tiles and legacy names, file list per set,
colour spaces, OpenGL normals), how to put a set on a bare GNM head, how it works, licences
and credits from TECH_NOTES. The bare-head section has the M2 wrap-test eye settings
(roughness 0.6, Specular IOR Level 0.1, cornea alpha 0) and an `apply_set(obj, folder)`
snippet that assigns one material per UDIM tile. Tested: stripped the materials from
`gnm_head` in `scene.blend`, ran the snippet on a scratch set (eurasian skin, detail seed 0,
brown irises), rendered `cam_face` and `cam_eyes` in Cycles and looked at both: skin, brows,
both irises and the clear cornea land correctly, no visible seam from the front.

**Dockerfile** + `.dockerignore`: Ubuntu 24.04, Blender 4.5.1 linux-x64 from
download.blender.org with its sha256 checked, Xvfb + Mesa for EEVEE, entrypoint starts the
display and runs any command; default renders `--move 0 0 --quality draft` to
`outputs/docker/draft.png`. Built and run on the M4 under amd64 emulation (Blender ships no
arm64 Linux build): **40 s, 30 s of it the render**; looked at the frame (grey debug head,
eyes centred, 512²). Not tested on a native x86_64 machine.
- Lessons: the first `.dockerignore` was a deny-list and pulled `.venv-gnm` (1.7 GB) into the
  context; with the build cache that filled the Mac's disk, Docker's VM went read-only and the
  Blender layer was left truncated (bus error on start). Now an allow-list (`scene.blend`,
  `wrapper`, `textures`, `tests`, `tools/validate.py`, `README.md`); rebuilt with `--no-cache`.
  `xvfb-run` hangs as PID 1 (waits for a signal that never comes), so the entrypoint starts
  Xvfb itself.

**tools/validate.py**, only what section D lacked:
- `wrapper`: `move`, `reset`, `render` defined, `move(h, v)` signature, flags `--input`
  (left/right/generate), `--texture`, `--clockwise`, `--seed`, `--quality` (AST + source, no bpy).
- `docs`: README covers setup, run commands, direction and UV conventions, licences, and has
  **no TODO left** (fails until the TODOs below are closed, on purpose); Dockerfile pins an exact
  Blender version and checks the hash.
- `scene` (with `--blender` or `$BLENDER`): opens `scene.blend` headless; Blender 4.5, bones
  `eye.L`/`eye.R`, `UDIM` and `legacy` UV maps, head materials, Timeline frame range, animated
  F-curves on the armature (16) and shape keys (13), no absolute file paths. All pass.
- `--root DIR` and `--zip FILE` (unzips to a temp folder, root = folder holding `scene.blend`)
  for the clean-unzip test. Tried on a test zip of the current files: same results as the repo.
- Current run: everything passes except textures (0 sets at the time), stills (0) and the
  README TODOs.

**TODO (depends on unfinished work)**
- Texture sets: `textures/tex_01…08` are being built by another session right now (untracked,
  not touched here). Then: README table of the 8 sets (skin source, tone, iris colour), check
  their file names and sizes with `validate.py`, one still per set in `outputs/stills/`.
- Final videos: `outputs/videos/*.mp4` are drafts on stand-in lids (EEVEE, 512²). Re-render
  after the lid solve (M1), the M3 look and the M4 framing; same for `renders/` and
  `metadata.json`, which are still uncommitted.
- Team and college name: README header, zip name `team_name.zip`, deck
  `CollegeName_TeamName.pdf`.
- Demo video link (≤ 3 min) in the README.
- Code licence for the repo (README says TODO; MIT suggested).
- CC BY credit line for the Lee Perry-Smith scan, only if its relief is adopted.
- README's `--texture` describes the M1 hookup (legacy UVs, albedo, normal, roughness);
  update if M3 changes the shading or the flag.
- M5 plan items not done: clean-clone test and zip test of the real bundle (run
  `validate.py --zip team_name.zip --blender …` on it), final renders overnight.
- Docker on native x86_64 is untested.

### Fri 13 Nov 2026, night — M2 eyebrow bake fix (Fable)
The strand eyebrows baked as hard, broken strokes because each hair is a tube about 0.08 mm
across, under one texel at 8.5 px/mm, and the ray bake sampled it as dashes.
`tools/transfer_skin.py` no longer bakes strand sets. It takes each hair's centreline from the
tube rings, projects it onto the wrapped GNM skin (closest point, then UV), and draws it in UV
as a tapered anti-aliased stroke, composited hair over hair in linear light.
- Extra hairs are seeded around each modelled one (root moved 0.35 mm, turned 5°, length
  0.7–1.1×), and about 30 % of hairs get a short fine stray off the edge, so the outline is soft.
  Per-hair width, tone and opacity vary. Two soft shadows of the hair density darken the skin
  underneath.
- New flags: `--brow-width` 0.13 mm at the root, `--brow-density` 1.4 hairs per modelled
  strand, `--brow-seed` 0. `--brow-shadow` default is now 0.45. `--brow-color` and
  `--brow-opacity` as before. Card (textured) eyebrow sets still go through the Cycles bake;
  that path is untested on a real set.
- Works for both strand layouts (4 rings in set 01; 5 and 6 rings in sets 05 and 08).
- Same command twice gives the same file (md5 checked on the first skin). About 40 s per skin.

Looked at, in `outputs/tmp/m2/brow_fix/` and `brow_fix_05/`: the brow at 3× in the flat
texture; the wrap test front (judges' view) and `tex_eye_front` for
`onlytheghosts_young_eurasian_female` + `mindfront_eyebrows_01`; the wrap test front for
`cutoff3d_indian_female_skin` + `mindfront_eyebrows_05`. The brows read as hair at face size
and in the close-up. Only the brow areas changed in the texture (diff against the old bake).

**For section 5**
- Set 01 is a thin arched brow, 05 is full; pick per skin and pass a `--brow-color` that
  suits the skin and iris (the default is dark brown).
- Set 01's inner ends hook down toward the nose on the GNM template; 05 does not show it.
- A few light specks sit in the upper-lid crease of the baked skin (there before this change,
  from the source skin or a bake miss); worth a look when the sets are made.
- The iris still reads grey and washed out in the wrap test, as logged in the tuning entry
  (eye material, not the texture).

### Fri 13 Nov 2026, night — scan test comparison (Opus)
The owner approved the download. `lpshead.zip` (43.6 MB) from the McGuire Computer Graphics
Archive is in `assets/third_party/lpshead/` (git-ignored); the licence file inside says
**CC BY 3.0**, "Infinite, 3D Head Scan by Lee Perry-Smith", based on a work at
www.triplegangers.com. Recorded in TECH_NOTES, Assets. Nothing derived from it is in the repo,
and the licence rule in `CLAUDE.md` is unchanged.

**What is in it**: `head.OBJ` (8,844 vertices, quads, ZBrush units), `lambertian.jpg` colour
4096², `bump.png` displacement 6000² 16-bit, a 1024² low-res bump. Eyes closed, thick brows,
stubble on cheeks, jaw and neck, a mole on the left cheek, photo highlights baked into the colour.

**Comparison**: `python3 -I tools/scan_compare.py` (2 s) → `outputs/tmp/scan/compare.png`.
Forehead, cheek and nose, 24 × 24 mm each at 20 px/mm. Columns: scan colour, our colour
(eurasian bake × detail layer, seed 0), scan relief, our relief. Both reliefs are shaded with
the same light and normalised to the same contrast, so compare structure, not depth (the
scan's displacement scale is unknown). The scan's scale (915 mm per unit) comes from its
cranial breadth and length against an average adult male head, good to about ±4 %. Its head
is pitched back, so its patch offsets were set separately and checked by drawing the boxes on
both maps. Texel density at those spots: scan colour 6–10 px/mm, scan displacement 8–14 px/mm,
ours 6–9 px/mm, so resolution is not the limit.

**Verdict, relief: the scan is clearly better.** It shows real skin microstructure: fine
furrows crossing in two or three directions, pores as irregular pits of mixed size, fine lines
on the cheek and forehead. Ours is the same isotropic pebble field everywhere with no
directional structure; next to the scan it reads as procedural. The scan's relief has problems
that need filtering: medium-scale sculpt lumps, a hard-edged smooth patch on the forehead
(a sculpt layer or seam), stretched streaks near the nostrils.

**Verdict, colour: not usable as albedo.** Real pores and blackheads on the nose and natural
redness, but white specular flecks baked in across the forehead, stubble on the cheek, a mole,
and one man's skin. At most a luminance detail on forehead and nose, which is not worth the
masking. Our colour detail is weak by comparison (soft round mottling and an even stipple of
dark dots that reads as noise), but that is a separate fix.

**Recommendation** (the owner decides; Fable does the work if yes):
1. Register the scan to GNM the way `tools/register_mh.py` did MakeHuman (landmarks on the
   scan, identity fit, smooth snap). Eyes closed and stubble do not matter for the relief.
2. Bake `bump.png` into tile 1001 as height, high-pass it (keep below about 2 mm), mask the
   artifacts, the lids and the lips, convert to a tangent normal map.
3. Use it as the micro-relief for every set in `tools/detail_maps.py`, blended over our
   undulation; keep our procedural lip creases and lid lines. One person's microrelief on all
   eight sets is fine; skin microstructure is generic, as ours is now.
4. Licence: add CC BY to the rule in `CLAUDE.md` and a credit line in the README and deck.
Estimated half a day. Weigh it against M3 and M4, which still need doing; this is the
single biggest gain available for the 60 texture points that I can see.
- A cheaper fallback without the scan: add anisotropic micro-furrows (two or three crossing
  directions, varying with region) to `detail_maps.py`. Less real than the scan, no licence change.

### Fri 13 Nov 2026, night — M1 plumbing (Opus), stand-in lids, handover to Fable
Fable's budget was out, so Opus 5.5 built sections 2–5 of `docs/BRIEF_M1.md` and left
section 1 (the lid solve) alone. **Fable: start with the brief's "Status 13 Nov" list.**

**New files**
- `tools/build_scene.py` → `scene.blend` (7.1 MB, 2 s). Mesh with `UDIM` + `legacy` UVs, one
  material slot per UDIM tile (debug greys; the eye interior is a procedural pupil / iris /
  sclera from the measured UV radii; cornea is Fresnel gloss + transparent to shadow rays).
  Armature `neck → head → eye.L, eye.R`; skin groups renamed to match. Shape keys `lid_up`,
  `lid_down`, `lid_open`, `blink`, `brow_up`, `squint` per side, plus `pupil` (−3…+3).
  Vertex groups `pupil_L/R`. Custom properties on `gnm_rig`: `eye_rest_L/R`, `eye_mid`,
  `forward`, `rest_pupil` −1.2, `rest_lid_open` 0.5, `lid_shapes` (`standin` / `solved`),
  `blink_keys` (`single` / `tent`). `cam_face` (50 mm) and `cam_eyes` (105 mm), both 40 cm in
  front of the eye midpoint, 1024². HDRI packed into the file (its source is git-ignored),
  strength 0.6, plus one disk key. AgX, Cycles 128 spp, motion blur shutter 0.5, 30 fps.
  `generate` seed 0 baked as keyframes (321 frames, linear interpolation).
- `wrapper/rig.py`: `Rig.apply(channels)`, `key`, `bake(track)`, `pupil_px`, `pupil_world`,
  `eye_rotations`. No drivers, no constraints. Bones are posed by writing
  `basis = M⁻¹ · L · M` (M = bone rest matrix, L = the rigid delta in rest space), so no
  depsgraph update is needed between parent and child.
- `wrapper/eyes.py`: `move`, `reset`, `render`, `static_pose`; CLI `--clockwise`,
  `--check-directions [--render]`, `--input left|right|generate`, `--move H V`, `--seed`,
  `--fps`, `--quality draft|final`, `--camera face|eyes`, `--texture NN`, `--limit N`.
  `--texture` is a minimal hookup (albedo, normal, roughness on the `legacy` UVs) until M3.
  Videos: PNG frames → `outputs/frames/<mode>/` → H.264 with Blender's own FFmpeg (VSE).
- `tools/validate.py`: layout, 10 renders at 1024², metadata schema and values, clockwise
  order, the direction signs from `outputs/direction_check.json`, reset ≤ 0.1 px, videos
  ≤ 15 s (reads the mp4 header, no ffprobe), texture sets and stills.
- `tools/rig_strips.py`: lid-follow, yaw, blink, brow, squint and widen strips from
  `cam_eyes` → `outputs/tmp/m1/`.

**Measured**
- Direction check, `cam_eyes`, ±1 input: left −13.8 / −14.2 px (L / R eye), right +14.2 /
  +13.8, up −14.0 y, down +14.0 y; cross-axis drift ≤ 0.01 px; reset returns exactly.
  At `cam_face` the same inputs move the pupils about ±6.5 px, as predicted.
- `metadata.json`: 10 records. `camera_matrix` reproduces `world_to_camera_view` to < 0.05 px
  (asserted for every frame). `--clockwise` takes 61 s (6 s per Cycles frame on Metal).
- `python tools/validate.py --skip textures`: all pass. `python -m unittest discover tests`:
  18 pass.
- Two builds give identical mesh, shape keys and keyframes (sha256 over all three).
- Template upper lid margin, column through the pupil: **3.24 mm (L), 3.33 mm (R)** above the
  pupil centre (the brief said 2.7). `lid_open` at 1.0 rotates it to 3.75 mm (1.99° L, 1.66° R).
- Draft videos (EEVEE, 512²): `left` 9.0 s, `right` 9.0 s, `generate` 10.7 s; 0.34–0.38 s per
  frame, about 100–120 s per video. Not committed; they are placeholders until M4.

**Looked at**: the direction sheet (reset, left, right, up, down, reset), clockwise
`frame_02`, the lid strips (pitch −25, −12, 0, +10, +20; yaw ±30; blink 0, 0.33, 0.66, 1.0;
brow, squint), `left.mp4` frames 32–40 (first saccade, 23.7°: the eyes jump in 2–3 frames,
the head follows) and 89–98 (first blink: closes in about 2 frames, opens in about 5), and
six frames across `generate` (glance, eye roll with brows and wide lids, look down with the
lids following).

**Stand-in lids** (`lid_standins` in `tools/build_scene.py`, replaced automatically by
`assets/gnm/lids.npz`): the closing-scaled M0 wink is `blink`; its per-vertex magnitude is a
falloff mask, and `lid_up / lid_down / lid_open` rotate the masked skin about the eye joint by
the brief's angles. They look right in the strips: the iris never tucks under the upper lid
from −25 to +20°, and a little sclera shows below the iris at +20°. Not done: basis fit,
collision pass, blink mid-poses, any of the section-1 numbers.

**Found / for Fable and M3–M4**
- **Baked animation overrides static poses at render time.** The render re-evaluates the
  F-curves at the current frame, so `move()` renders came out as frame 1 of `generate` until
  `eyes.static_pose()` was added (it clears the animation in memory; the file keeps it).
  Anything that poses statically must go through it.
- Blink 0.66 already looks nearly shut, because `lid_open` fades with (1 − blink) and the
  stand-in blink is a straight blend. Recheck with the solved tent keys.
- `squint` at 1.0 nearly closes the eye; the engine never sends more than about 0.3.
- EEVEE drafts show a faint vertical shading line down the forehead midline during brow
  raises; the Cycles frames do not. Check before trusting drafts for the look.
- `cam_eyes` at 105 mm frames the eyes and forehead at 1024²; M4 still has to choose the
  video framing (whole face tight plus an eye inset, per PLAN).
- Not committed: `renders/`, `metadata.json`, the draft videos and `outputs/direction_check*`.
  They are regenerated after the lid solve and the M3 look. `scene.blend` is committed.

### Fri 13 Nov 2026 — M2 tuning pass on irises, detail maps and checks
Did the "Added 13 Nov" list in `docs/BRIEF_M2.md` on `tools/make_iris.py`, `tools/detail_maps.py`
and `tools/check_detail.py`. Section 5 not started; `transfer_skin.py` untouched.
Before/after pairs (old maps vs new, same check settings): `outputs/tmp/m2/tune/pairs/`
(grey front, grey three-quarter, grey eye, `tex_face`, `tex_eye_front`, wrap front, wrap
three-quarter, iris sheet). Old maps kept in `outputs/tmp/m2/tune/before/`. All looked at.

**Checks** (`check_detail.py`)
- Each render prints `peak`, the 99.5th percentile of the head's brightest channel. Textured key
  is now 0.3× (per-mode default, `--key` overrides): `tex_face` 0.92 → 0.81,
  `tex_three_quarter` 0.85. Grey mode is unchanged (0.90; relief needs the hard key).
- New `--wrap` (with `--skin`): the judges' view. Plain Principled everywhere, skin = albedo ×
  detail + normal + roughness, no subsurface; eye tiles as base colour with default Principled
  settings; cornea alpha 0; grey world 0.6 plus one 0.5 m soft key; front and three-quarter at
  face size, peak 0.84. Default shots per mode, so the three modes are three plain commands.
- **Found in the wrap test:** with default Principled specular on the eye interior and no
  cornea, the irises read grey-brown and washed out at face size. That is a material issue,
  not a texture one; worth a line in the README on how to set the eye up (specular ≈ 0.1,
  roughness ≈ 0.6, as in our check and M3).

**Detail maps** (`detail_maps.py`; scales are now named constants at the top of the file, and the
flags stay multipliers around them)
- Pore depth 0.024 → 0.048 mm, micro-furrows 0.014 → 0.028 mm (2×). Normal tilt, mean / 95th
  percentile: nose 2.8 / 7.5° → 5.4 / 14.8°, cheek 2.1 / 5.9° → 4.1 / 11.6°, forehead
  1.5 / 3.9° → 3.0 / 7.9°, lids 1.2 → 2.4°; lips unchanged (2.3°). Grain now reads on nose,
  cheeks and forehead in the grey three-quarter at 1024²; the eye close-up is grainier but not
  orange peel. Pore tint and pore roughness are normalised to the new depth, so they did not double.
- New fine lines under the lower lid and at the outer corner (`--lid-lines`, depth 0.022 mm):
  valleys of constant distance below the lower-lid margin (front rim of `eye_sockets`, extended
  past the outer corner as a gently rising line), wavy and broken, a coarse and a fine set,
  strongest near the lid. Visible in the grey eye close-up and in `tex_eye_front`.
- Mottling 2× (3.5 → 7 %), redness 1.6× (G −10 → −16 %). At 2× the cheek redness read as a
  blush patch in the wrap test, so it was backed off. Albedo detail sd 4–6 → 8–10 on 128;
  1st–99th percentile about 100–140. Just visible in `tex_face` and the wrap shots. Freckles and
  moles unchanged; a mole now lands near the right outer eye corner for seed 0 (rng streams moved).

**Irises and sclera** (`make_iris.py`)
- Fibre contrast up (seeded range 0.55–0.8 → 0.8–1.0, amplitude 0.28 → 0.36). New radial
  streaks, light and dark, 12 and 26 polar columns wide (1.5–3 px when the iris is 60 px across),
  long along the radius, strength 0.22–0.32 per seed.
- Contraction furrows: 1–3 instead of 2–4, short arcs (gaps most of the way round), 0.15 dark
  instead of 0.35. The tree-ring look is gone.
- Collarette: width and brightness vary around the iris and 15–35 % of it is gaps; the edge of
  the pupillary zone is softer.
- Sclera veins: opacity follows width, so they fade as they taper; taper faster; wider spread of
  starting widths; the thinnest drawn on their own layer and blurred 0.7 px; colour 150/32/34 →
  160/64/62 and halo less saturated; fade over lim + 0.005 … 0.06.
- `sheet.png` has a second row: each iris at 60 px across, nearest-neighbour enlarged. Before,
  that row showed a flat disc with a ring; now the radial structure survives.
- In `tex_eye_front` only a few faint vessels show inside the visible almond (before: too many,
  too red). If the sets look too clean, raise the per-set `redness` structure parameter rather
  than the width.

**Reruns**: detail maps and irises are byte-identical on a second run (md5 checked).
Commands, unchanged: `make_iris.py --all --seed 0`, `detail_maps.py --seed 0`,
`check_detail.py -- --detail D --iris I [--skin S [--wrap]]`.

### Fri 13 Nov 2026 — M2 review of sections 3 and 4, and a change of order
Looked at `outputs/tmp/m2/iris/sheet.png`, `iris/brown_pair_1to1.png` and every render in
`outputs/tmp/m2/check_detail/`, then held them against "Eye Piece" and "Flexpressions".
The scripts are sound (measured radii match the mesh, Blender side is `bpy` + `numpy`);
the look reads as CG. Seeding and identical reruns were not re-run in this review.

**Measured**
- Normal map: mean tilt 2.4° on the nose, 2.3° on a cheek, 1.5° on the forehead, 1.8° on
  the lips (95th percentile 4 to 7°). Pores show only in the eye close-up under raking light.
- Albedo detail layer: standard deviation 4 to 6 on a 128 base (about ±4 %), 1st to 99th
  percentile 114 to 139. Not visible in `tex_face`, which is also overexposed.
- Irises: good at 1:1; at render size the fibres vanish and the concentric furrows and the
  collarette line dominate. Sclera veins are one width and saturated red.
- Eyebrows (section 2, `tools/transfer_skin.py`): the strand bake gives hard, thin, broken
  strokes in `skin.1001.png`; stippled in the close-up, pencil-thin at face size.
- Template eye: upper lid margin about 2.7 mm above the pupil centre (hides the top half of
  the iris); rest pupil 5.2 mm. Both passed to M1 in `docs/BRIEF_M1.md`.
- Lip creases are good; no seam at the back of the head or behind the ears.

**Decided**
- Base stays MakeHuman skins on GNM. Order of work and the reasons are in `docs/PLAN.md`,
  "Order of work from Fri 13 Nov"; the tuning list for Opus is in `docs/BRIEF_M2.md`,
  "Added 13 Nov".
- The organisers name MakeHuman / MPFB, GNM Head Editor and Textured FLAME as open assets
  and set no licence rule (`docs/REQUIREMENTS.md`). A CC BY head scan as a detail source is
  a one-hour test that has not been started and needs the owner's go-ahead.
- Section 5 waits for the tuning pass and the eyebrow fix.

### Fri 13 Nov 2026 — M2 sections 4 and 3: eyes and detail maps
**Eye UV radii** (`tools/make_iris.py --measure` → `assets/gnm/eye_uv.json`, also in GNM_FACTS).
Tiles 1002 and 1004 are the same concentric disc centred on (0.5, 0.5); +u = subject's left,
+v = up for both eyes, so nasal is −u on the left eye and +u on the right.
- **Pupil edge 0.0499** (2.60 mm), iris outer ring 0.1849, sclera inner ring 0.1912,
  **limbus 0.1881** (5.34 mm), **sclera extent 0.4608**. At 2048²: pupil 102 px, limbus 385 px.
- Rest lid opening in UV (z-buffered skin against the globe from the front): upper lid ≈ 0.055,
  lower ≈ 0.19, corners 0.27–0.38. Stored per 5°.

**Irises and sclera** (`tools/make_iris.py`, numpy + scipy, ~7 s per pair at 2048²).
- `--color {dark_brown,brown,hazel,green,blue,grey} --seed N --out DIR` writes `eye.1002.png`,
  `eye.1004.png`, `iris.json`. `--all --seed 0` writes all six plus `sheet.png` to
  `outputs/tmp/m2/iris/`. Structure parameters come from the seed and are shared; each eye has
  its own noise stream. Byte-identical on rerun.
- Iris, in polar coordinates between the measured pupil edge and limbus: wavy radial fibres
  (two scales), jagged collarette with its own pupillary-zone colour (amber in hazel and green),
  crypts with light rims, broken contraction furrows, a few iris freckles, limbal ring, crenellated
  pupil ruff. Pupil disc near-black up to 0.0499.
- Sclera: warm off-white (sRGB ≈ 206/195/183), yellower away from the cornea, pink toward the
  corners (nasal strongest, starting inside the visible almond), deep blurred episcleral vessels
  plus sharp branching conjunctival vessels (curvature with momentum) that reach close to the
  limbus, darker greyer rim beyond the rest lid line ramped over ~0.11 UV so gaze shifts show a
  gradient, faint grey band outside the limbus.
- Looked at: every colour at full resolution and in Blender on the template, close-up and in a
  1024² face shot. At face size the iris reads as its colour; close up the collarette, fibres
  and veins are visible.

**Detail maps** (`tools/detail_maps.py`, numpy + scipy, 26 s per set). `--seed N --out DIR` writes:
- `skin_normal.1001.png` 4096², tangent space, OpenGL (+G = +v), from a height field in mm:
  ~390 k pores stamped through each texel's surface Jacobian (round on the surface; densest and
  largest on the nose, fine on the forehead, sparse on the lids, none on the lips), ridged
  micro-furrows scale-matched to local texel size, 0.5–2 mm undulation from 3D noise, and
  vertical lip creases (valleys of constant x, wavy, broken) across both lips.
- `skin_rough.1001.png` 2048²: nose 0.34, forehead 0.40, lips 0.30, cheeks 0.55, default 0.52,
  rougher in pores, ±0.035 low-frequency variation.
- `skin_detail.1001.png` 4096²: albedo multiply in linear light, **128 = ×1** (factor = value/128).
  Mottling (luminance and a blood component, 2.5–16 mm), patchy redness on nose and cheeks,
  darker pores, freckles mostly on nose and cheeks, 2–6 moles, faint blue-grey veins at temples
  and lids, neutral on the lips. Section 5 applies it with
  `detail_maps.apply_albedo_detail(albedo, detail, strength)`.
- Strength flags for every component; `--variation 0.1` jitters them ±10 % from the seed so
  sets differ slightly. Low-frequency fields are 3D noise at the surface point, so nothing breaks
  at UV seams. Region weights are GNM vertex groups smoothed over the mesh.
- Byte-identical on rerun. Shared helpers in `tools/tex_core.py` (UV rasteriser with z-buffer,
  per-texel surface position and Jacobian, nearest fill, deterministic PNG writer).

**Grey check** (`tools/check_detail.py`, Blender, bpy + numpy). Grey Principled with only the
normal and roughness maps, one area key, no denoiser; front, three-quarter, profile, back, close
on the left eye and on the lips (`outputs/tmp/m2/check_detail/grey_*.png`, `grey_sheet.png`).
`--skin PNG` renders the same textured (albedo × detail). Pores and fine furrows read as relief on
the eye close-up and as grain on the three-quarter; lip creases are clear; no seam at the back
or behind the ears.

**For M3 and section 5**
- Under the cornea the eye interior wants near-diffuse shading (specular ≈ 0.1, roughness ≈ 0.6),
  or a frontal key lays a sheen over iris and sclera. The cornea needs Is Shadow Ray → Transparent
  (as TECH_NOTES says), or its glossy term shadows the nasal sclera and the limbus.
- GNM's rest pupil is 5.2 mm across, which looks dilated under a bright key; consider a negative
  `pupils_000` for stills.
- The pale-white look of the sclera in renders is AgX at that exposure; the texture itself is
  ≈ 206/195/183 with veins and pink in the visible band.
- Per set: `make_iris.py --color C --seed S --out textures/tex_NN` and
  `detail_maps.py --seed S --out textures/tex_NN`, then multiply the detail into the bake.
  Normal map PNG is 16.6 MB, detail 8 MB, roughness 1.4 MB, each eye ~1.8 MB.

### Thu 12 Nov 2026 — M2 sections 1 and 2: registration and skin transfer
**Registration** (`tools/register_mh.py`, numpy + scipy, 9 s). MakeHuman base head → GNM.
- `assets/mh_landmarks.json` (committed, written by `tools/pick_mh_landmarks.py`): 52 of GNM's
  68 landmarks as MakeHuman surface points (three vertex indices + weights). Lips are read off
  the painted vermilion border, lids come from where the eyeball shows through the opening,
  brows from the hair of `mindfront_eyebrows_01`. Jaw points other than the chin are not used.
- Identity fit (170 coefficients, 16 rounds): landmarks 1.03 mm mean, 2.49 mm max; surface
  1.79 mm mean; |c| = 15.6. Final similarity scale 0.093 (MakeHuman dm → GNM m).
- Smooth snap (thin-plate displacement, 8 passes): **face residual 0.040 mm mean, 0.114 mm at
  the 95th percentile**, 1.87 mm max, over 4,348 face vertices; all exterior skin 0.063 / 0.188 mm.
  Lid pockets, mouth sock and one ring around them are not pulled and follow their neighbours.
  The snap moves the skin 5.3 mm on average, up to 26 mm on the bib, where the two models differ most.
- Looked at: both meshes overlaid from front and profile (they interleave everywhere, including
  ears and bib) and GNM's lip, lid, nose and brow groups drawn on the textured MakeHuman head.
- Output `assets/gnm/wrapped_to_mh.npz` (git-ignored, rebuilt by the script).

**Transfer** (`tools/transfer_skin.py`, Blender headless, bpy + numpy, 36 s per skin at 4096²).
- Cycles bake, Selected to Active, cage 3 mm, ray 8 mm, margin 16 px, into float images: skin
  colour, hit mask, region mask, brow coverage. Composited in linear light, written as 8-bit sRGB.
- 936 of MakeHuman's 4,800 head quads are hidden inner sheets (eye pockets, mouth cavity) and are
  removed before baking, so nothing can land on the red socket paint.
- 85 % of the tile comes from the source. The rest (outside the islands, lid pockets, inner lip)
  is filled by push-pull; the mouth sock gets a darkened lip colour. Darkest texel 75/255, so no
  black or magenta.
- Brows: strand sets bake as individual hairs at 4096², plus a soft shadow under them.
- First skin `onlytheghosts_young_eurasian_female` + `mindfront_eyebrows_01`, checked on the
  unwrapped template from four angles: lip colour on the lip edge, brows above the orbit, nostril
  shading in the nostrils, clean ears, no seam at the back or behind the ears.

**Found**
- The face gets about 2 px per mm in a MakeHuman skin (2048² for the whole body) against 8.5 px
  per mm in GNM tile 1001 at 4096². The baked albedo is soft: it carries tone, lips, lash line
  and brows, not pores. **Section 3 must add fine colour detail to the albedo** (mottling,
  freckles, small veins) as well as the pore normal map.
- The `.obj` of the system eyebrow cards (`eyebrow001…012`) is **not** in base-mesh space; they
  sit 2 cm too high unless fitted through the `.mhclo` (`mh_core.load_proxy`). The Mindfront
  strand sets are in place either way. The cards are 512² for both brows, so prefer the strands.
- `makehuman_system_assets/skins/` has 17 more plain skins across three ethnicities, both sexes
  and three ages: use them for the tone spread in section 5.
- `.venv-gnm` has no matplotlib; system `python3` has numpy, scipy, matplotlib and PIL.

**For sections 3 to 5**
- `transfer_skin.py --skin <folder> --eyebrows <folder> --name <name> --check` writes
  `outputs/tmp/m2/<name>/skin.1001.png` and `check_sheet.png`. `--brow-color` is linear RGB.
- The inner lip is a flat dark band with a fairly hard edge; soften it if it shows in close-ups.
- Male skins want a denser brow set (`mindfront_eyebrows_05` or `_08`).

### Thu 12 Nov 2026 — gaze engine (part of M4, done early)
Written and tested in a cloud session with no Blender, so nothing here has been seen on the head yet.
- `wrapper/gaze/`: pure numpy, Python 3.11 syntax, no bpy. `generate(mode, seed)` returns a
  `Track` with 15 channels (listed in the `engine.py` docstring) on a 1 kHz clock;
  `track.frames(fps)` gives one dict per frame.
- Model: saccades on the main sequence (5° 30 ms, 10° 41 ms, 30° 99 ms peaking at 546°/s),
  10 % undershoot plus a corrective saccade on shifts over 12°, small glissade, fixational
  drift and microsaccades, ≥ 150 ms between saccades. Head takes 10–40 % of the shift, starts
  40 ms after the eyes and follows smoothly; eye-in-head = gaze − head, so gaze holds while
  the head catches up. Blinks close in 75 ms and open in 165 ms, come with large gaze
  shifts, never in the first or last 0.35 s, never during an eye roll. Brows rise with
  up-gaze. Fixation distance drives vergence and a small pupil response.
- Inputs: `left` and `right` are 9.0 s (glance, two refixations, blink, return, settle).
  `generate` is about 10.7 s (glance, eye roll with brows and wide lids, look down, look up
  and aside, closing blink). The seed changes timing, amplitudes and side.
- `tests/test_gaze.py`: 18 checks against the numbers in TECH_NOTES, all passing.
- The pupil channel is an offset; the rig adds it to a resting coefficient of about −1.2.
- Briefs for the next two sessions: `docs/BRIEF_M1.md` (rig, lid solve, wrapper) and
  `docs/BRIEF_M2.md` (texture transfer, irises, 8 sets).
- **Framing finding:** at the spec camera (40 cm, 50 mm, 1024²) a 15° eye turn moves the pupil
  only 12 px and the ±5 cm calibrated range about 6 px. Keep that camera for the 10
  clockwise renders, and shoot the three videos with the tighter `cam_eyes` so the motion
  and the textures can be seen.

### Thu 12 Nov 2026 — M0 setup and spikes
**Pinned:** Blender **4.5.1 LTS** (build 2025-07-29, already in `/Applications`), bundled
Python 3.11.11, numpy 1.26.4. `.venv-gnm` is Python 3.13.4 (uv).

**Done**
- GNM cloned to `assets/third_party/gnm` at `846ab76`. Weights downloaded straight from the
  Hugging Face CDN to `~/.cache/gnm/models/v3_0/gnm_head.npz` (53 MB, sha256 `61d78bbf…`).
- `docs/GNM_FACTS.md`: counts, joint order/parents/positions, groups, index ranges, UDIM, units,
  lid gap. TECH_NOTES corrected (joint order was wrong; tongue is 1 mean + 31).
- `tools/gnm_core.py` + `tools/export_gnm.py`: **numpy only**, no GNM import. Reproduces GNM's
  vertex-group masks, UDIM tiling and LBS from the source. Writes `assets/gnm/base.npz`
  (19.4 MB, byte-identical across runs). `--identity-seed`, `--identity-scale`; `--gender` /
  `--ethnicity` use GNM's IdentitySampler (tested, also byte-identical across runs).
- Checked against the installed package: `gnm_core.lbs` matches `GNM.__call__` to 4.5e-8 m with
  random identity, expression and pose; UDIM tiles and UVs match exactly.
- `tools/smoke_render.py`: mesh with `UDIM` + `legacy` UV layers, 4-bone armature from GNM
  joints and skin weights, shape keys from any `delta_*`, camera 40 cm in front of the eye
  midpoint, one area light, Cycles on Metal GPU, OIDN. Debug materials: transparent cornea
  shell, dark iris and pupil, so gaze reads by eye.
- Renders in `outputs/spike/` (git-ignored), all looked at: `neutral`, `blink_L`, `blink_R`,
  `blink_L_x1.4`, `blink_R_x1.35`, `gaze_left15`, `gaze_up15`, `id_seed3/neutral`,
  `id_f_asian3/neutral`. Gaze is correct by eye and in numbers: 15° left moves
  both pupils −12.2 px in x, 15° up moves them −12.2 px in y (up in the image). Eyeballs turn
  about their centres (radius change 1e-17 m, no skin vertex moves).
- MakeHuman Skins 01, Skins 02, Eyebrows 01, Eyelashes 01, system assets, `base.obj`, and the
  Poly Haven `brown_photostudio_02` 2K HDRI downloaded; URLs and CC0 checks in TECH_NOTES.

**Benchmark** (M4 10-core, 24 GB; Metal GPU; 1024², OIDN, adaptive sampling; grey scene;
best of 2 after a warm-up frame): **64 spp 3.8 s · 128 spp 4.4 s · 256 spp 4.9 s**. Most of that
is per-frame overhead, not sampling. The first frame of a session takes about 46 s while
Metal kernels compile. Re-measure once skin has subsurface.

**Blink spike** (after the GNM package install was allowed; TensorFlow 2.21). 64 samples per
class, seed 0, eye-region coefficients only. Full table in GNM_FACTS.
- WINK_LEFT closes the subject's left (+X) eye. A full wink also half-closes the other eye
  (8.36 → 6.68 mm), so one-side-only coefficients are needed.
- Lid gap left: 8.34 / 5.33 / **2.32 mm** at weight 0 / 0.5 / 1.0. Right: 8.36 / 5.30 / 2.23.
  **Weight 1.0 does not close the lid.** It closes (≤ 0.2 mm) at **×1.40 left, ×1.35 right**.
- Rendered: at ×1.4 / ×1.35 the lid shuts cleanly, with no cornea poking through, the other
  eye untouched and only a faint crease at the outer corner. At 1.0 a thin slit stays open.
- Shapes move no eyeball or lip/chin vertex. `brow_up` (SURPRISE) widens the lids 0.24 mm;
  `squint` narrows them to 3.3 mm.
- Vectors are in `assets/gnm/expr_*.npy` (git-ignored, rebuilt by the script);
  `blink_spike.json` holds the numbers.

**Surprises / for M1**
- Subject's left eye is at +X, so it appears on **image right**. `left` input (image-left)
  turns both eyes toward the subject's right (−X). Yaw toward image-left is −Z rotation in
  Blender after the `(x, y, z) → (x, −z, y)` axis swap.
- Pose correctives are all zero, so Blender's armature + LBS matches GNM exactly. Bone
  orientations are identity; eye bones in `smoke_render.py` point forward (−Y).
- The upper lid does not follow pitch: at 15° up the iris tucks under the lid. M1's lid driver
  is needed.
- A unit-Gaussian identity (`--identity-seed 3`) looks like a face, but the ears sink into the
  head. The IdentitySampler has a larger norm with intact ears, so use the sampler.
- `blink.L/R` need the closing scale (1.40 / 1.35) baked in, or a direct lid solve, before
  the mid-pose corrective work.

**For M2**
- `base.obj` includes MakeHuman helper geometry; keep only the body group when registering.
- Skins 01 is all female (23), Skins 02 all male (13). Several are tattooed or made-up; pick
  plain ones.
- Use the `files.` mirror if `files2.makehumancommunity.org` stalls.

### Thu 12 Nov 2026 — planning
- Read the hackathon PDF and the evaluation PPT; requirements are in `REQUIREMENTS.md`
- Chose GNM Head v3 as the base model and read its repo at commit `846ab76`
- Found: UDIM UV layout with separate tiles per eye, 4 joints including both eyes,
  no blink class but `WINK_LEFT` / `WINK_RIGHT` exist, 68 landmarks included,
  no skin texture included
- Wrote the plan, tech notes and the M0 brief
