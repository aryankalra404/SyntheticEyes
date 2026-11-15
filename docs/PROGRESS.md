# Progress

Newest entry first. One entry per working session: what changed, what was measured,
what the next session needs to know.

## Status

| Milestone | State |
|---|---|
| M0 Setup and spikes | done |
| M1 Rig and calibrated wrapper | done (13 Nov): lids solved (`tools/solve_lids.py`), globe guard, rig reviewed; `scene.blend` rebuilt with `lid_shapes = "solved"` |
| M2 Texture pipeline | done (13 Nov), audited on the bare head and rebuilt (14 Nov): 9 sets in `textures/`, all with scanned skin micro-relief; brows painted as grown hairs, shaved-scalp cap removed, back-of-head seam fixed; `tex_09` (photographed skin) is the hero set; contact sheet in `outputs/stills/texture_sheet.png` |
| M3 Look | done; the `eye` look (hard raking key on black, fine facial hair, pore sparkle) is on the videos, the nine stills and the eye close-ups (14 Nov); `scene.blend` is built on the tex_09 head |
| M4 Motion | **M13 motion rework reviewed and accepted by Fable (15 Nov); `generate` trimmed to 8.3 s. The owner chose the one-eye pane (`--pane eye`, now the default). Waiting for the owner to watch the three drafts at speed; then finals.** Split video: fixed face camera on the left, `--pane` on the right. **Final videos not rendered** |
| M5 Compliance and packaging | README, Dockerfile (built and run) and validator done (Opus, 13 Nov); clean-clone and zip test of the real bundle and the final renders wait for M1–M4; TODOs listed in the M5 entry |
| M6 Ship | not started |
| M14 Quest 3S bonus (WebXR) | built by Opus and reviewed by Fable (15 Nov): works on the laptop, tests pass; **the headset path has never run on a device: the owner's test is next**; live at https://aryankalra404.github.io/syntheticeyes-xr/ (public copy of `xr/`, `tools/publish_xr.sh`) |

## Open questions

- College and team name for the zip and deck (`CollegeName_TeamName`)
- Time of day of the 22 Nov deadline

## Log

### Sun 15 Nov 2026, evening — the WebXR bust on a public link (Opus)
Nothing here touched `scene.blend`, `wrapper/` or `textures/`; the finals kept rendering.

- **Link: https://aryankalra404.github.io/syntheticeyes-xr/**
- Pages on `Samsung-Prism` was tried first and refused ("Your current plan does not support
  GitHub Pages for this repository"), so, as the owner authorised, a separate **public** repo
  `aryankalra404/syntheticeyes-xr` holds only the page: `index.html` at its root, `js/`,
  `assets/`, `vendor/three/`, the xr README (with a short preface) and `.nojekyll`. No
  `.certs`, no `tests/`, no `serve.py` or `package.json` (the server serves the main repo root
  and would not run there). Pages builds from `main` at `/`. `Samsung-Prism` is still private.
- Commits there are authored as aryankalra404 with the GitHub noreply address, so the
  personal email is not public.
- `tools/publish_xr.sh [message]` syncs `xr/` to that repo in one command (creates the repo
  and turns Pages on if missing, uses the aryankalra404 gh token without switching accounts,
  says so if `xr/` has uncommitted changes). Pages takes about a minute to rebuild after a push.
- Checked in the browser pane on the live link: the page loads, the head turns to follow the
  mouse left and right, no console messages, `head.glb`, `rig.json`, the five textures, the
  scripts and three.js all return 200. Not tried in the headset; being HTTPS, the Quest can
  open the link directly with no certificate step.
- Link added to `xr/README.md` and the main README (next to the demo video TODO).
- **Then, on the owner's ask, the page for the jury.** One-line heading ("SyntheticEyes, a
  synthetic head that looks back at you", the tagline hidden under 400 px); the credit footer
  removed from the page (the organisers said the README is enough; both READMEs keep it);
  three.js's "XR NOT SUPPORTED" replaced by "Open this link in a VR headset to see it in your
  room" when no immersive session is available. Controls: *View* (Face / Both eyes / Eye
  close-up = `cam_test_eye`) and *Follow mouse* on/off. In the close-ups the camera rides with
  the head bone (gaze target taken from the unmoved camera), the head's channels are scaled by
  0.35 (`?closeuphead=`) so the eyes do the visible moving, and the mouse moves the gaze target
  up to 35 deg sideways and 20 deg up or down. Without that, the head took most of the turn
  (head −22 deg, eyes −17 deg) and the riding camera cancelled it. Looked at in the browser pane at
  1280x800 and 375x812, no console messages, 14 node tests pass. A frame-rate pass was
  asked about and set aside: the owner wants no quality reduced.
- **Follow: You (camera)**, on the owner's ask. *Follow* is now Mouse / You (camera) / Off.
  `xr/js/facefollow.js`: MediaPipe BlazeFace short range (`xr/assets/face_detector.tflite`,
  230 KB, Apache-2.0) on the webcam, CPU delegate, one detection per camera frame; the eye
  keypoints give the direction and, against a 63 mm pupil distance and a 60 deg camera, the
  distance; smoothed (0.12 s). The tasks-vision 1.1.1 runtime (13 MB of wasm) loads from
  jsDelivr only when the mode is picked. The first sighting is the centre; lean x2.5 to the
  orbit (10 cm at 55 cm = 26 deg), lean in brings it closer, no face for 1 s is walking away.
  The close-ups steer the gaze with it as with the mouse. Checked: the detector finds the
  rendered bust's face (score 0.96, eyes symmetric), the mapping with scripted positions (right
  +26, left -26, up and down ±16, 40 cm -> 0.51 m, gone -> not present, back -> present), and a
  blocked camera falls back to Mouse with the reason shown. **Not tried with a real webcam**
  (the browser pane blocks cameras). MediaPipe logs one "INFO: Created TensorFlow Lite XNNPACK
  delegate" line at error level when the mode starts; it is harmless.
- **Speed, no quality change.** Measured in the visible browser pane at 1280x800, DPR 2
  (2560x1600 canvas), with the new `?prof=1` (gaze, rig, render with `gl.finish`): a steady
  frame costs 0.5 ms median, 2.3 ms worst, render included, so the page is far inside 16 ms on
  the M4. The lag was the **first frame: 1089 ms** (every shader compiled and the 2K textures
  uploaded at once). Now `initTexture` + `renderer.compileAsync` run behind "preparing…"
  (209 ms, mostly off the main thread) and the first frame takes 52 ms. The normal map ships as
  **lossless WebP** (6.31 -> 4.45 MB, every pixel identical, checked with numpy; Pages does
  not compress PNGs but already gzips `head.glb` and the scripts); `tools/export_xr.py` writes
  it with `cwebp` and removes the PNG. Rest of the page: 13.0 -> 11.1 MB. Not measured on the
  Quest. What still reads as "slow" is by design: the camera eases to the mouse over 0.25 s
  and the head starts about 0.5 s after the wearer moves (`head_trigger`, see the Fable review).
- **Snappier camera, head delay kept** (the owner left the call to me). A 30 deg mouse step at
  60 fps: the camera reached 90 % in 0.57 s (easing 0.25 s), eyes moved at 0.06 s, the head at
  0.42 s. The camera easing is now 0.1 s (`?ease=` overrides): 90 % in 0.23 s at any frame rate;
  the eyes still lead (0.05 to 0.12 s) and the head follows at about 0.3 s. The gaze model's
  own numbers are untouched; eyes first, head later is the behaviour that reads as natural.

### Sun 15 Nov 2026, 15:40 — review of the M14 WebXR bust: accepted for the headset test (Fable)
Reviewed from `outputs/tmp/m14/xr/` (face against the Cycles still, the five laptop positions,
the step and walk curves), the node tests (14 pass), the unit tests (51 pass) and the live page
in the browser pane (`http://localhost:8000/xr/`: the head follows the camera, no console
messages). `scene.blend` md5 `d6e016e4…`, `wrapper/` and `textures/` untouched since the finals
started; the finals are still rendering (`generate`, face pass, about 45 s a frame).

- **Accepted as built**: export, page, rig port, lids without the guard (no bake needed),
  lashes, the laptop mode with "mouse off the page is walking away", credits, sizes (13 MB).
  It is the same man, flatter and paler than Cycles, with a hard nose shadow: fine for a bonus.
- **Opus's own numbers in `LIVE`** (head goal rate 50 deg/s, 0.7 feed-forward, glances that do
  not move the head, blink gap cap, the double blink of the greeting): accepted; each one is
  explained by a failing seed.
- **Changed by Fable**: the engine's roll (−0.20 per degree of head yaw) and dip were tuned on
  6 deg turns. Live, the head held a 6 deg tilt at 28 deg of yaw and 12.6 deg at the 60 deg
  limit, with a 3.9 deg nod on a fast turn. Both now level off (`roll_max` 3.0, `dip_max` 2.5,
  a tanh): step path roll −5.9 → −3.2, dip −3.9 → −2.6; walk path roll −12.6 → −3.4; the still
  path is unchanged to two decimals. 14 node tests pass. New dumps: `outputs/tmp/m14/xr/review/`.
- **Not judged, because it cannot be from here**: anything in the headset (placement, scale,
  passthrough, frame rate, lash flicker), and how the behaviour feels at speed. On the step
  curve the head starts about 0.5 s after the wearer starts moving; if that feels slow in the
  headset, lower `head_trigger` (12 deg) first.
- For the owner's test: port 8000 is held by the Opus session's preview server, so start the
  headset server with `python3 xr/serve.py --http-port 8001`. Hosting is still undecided.

**Later, after the owner tried the laptop page**: "good, just the eyelashes are worse in the
browser". Close up they were opaque black wedges with grey highlights (flat ribbons 1.5x the
lash width, roughness 0.45). Now each ribbon carries a UV (u across, v root to tip,
`tools/export_xr.py`) and the page draws it through a small generated alpha map: a soft core
across the width, solid from the root, fading out over the outer half; dark brown, roughness 1,
no environment reflection, no depth write. `head.glb` re-exported (5.48 MB; `scene.blend` md5
unchanged, export check PASS, 14 node tests pass). Looked at in the browser pane at
`?view=eye` and `?view=face`: fine strands that thin out to the tip, a soft lash line at face
distance, no console messages. Not seen in the headset.
The repo is private, so GitHub Pages cannot serve it on a free account; for a jury link the
plan is a separate small public repo holding only `xr/`, after the headset test, on the
owner's go-ahead.

### Sun 15 Nov 2026, night — M14 WebXR bust, stages A to F and the review pack (Opus)
The finals were rendering throughout (`generate` first); nothing here touched `scene.blend`,
`wrapper/` or `textures/` (scene.blend md5 `d6e016e4…` before and after every Blender run).
Blender runs here only read the scene.

**A. Export** (`tools/export_xr.py`)
- `xr/assets/head.glb` 3.19 MB: `gnm_head` skinned to `neck` → `head` → `eye.L/R`, 21 named
  morph targets with morph normals, TEXCOORD_0 = `UDIM` folded per face (u − floor of the
  face's mean u), TEXCOORD_1 = `legacy`, one primitive per material slot named after it, all
  weights 0, no animation, no modifier applied. Materials are flattened in memory so only their
  names travel.
- `xr/assets/rig.json`: axis map, eye centres, pupil centres, bone heads, the rig constants
  imported from `wrapper/rig.py` and every `GazeParams` field from `wrapper/gaze/engine.py`
  (imported, not copied), all in the glTF frame (Y up, the face looks along +Z).
- Textures from `tex_09`: albedo 2048 JPEG 0.47 MB (rms error 1.5/255 against a box-filtered
  original), normal 2048 PNG 6.31 MB, roughness 1024 0.18 MB, eyes 1024 0.10 + 0.11 MB:
  7.2 MB together (budget 8). Tiles: 1002 = left eye (`eye_L.jpg`), 1004 = right.
- Check **pass**: `--check` reloads `head.glb` in an empty Blender, 17 821 vertices (merged),
  4 bones, 21 morph targets whose names match `rig.json`. The importer's icosphere bone shape
  is not counted. `git status`: `scene.blend` unmodified.

**B. The page, still** (`xr/index.html`, `xr/js/app.js`, `xr/vendor/three/`)
- three.js **0.185.1** (npm, 1 Jul 2026, MIT) vendored unmodified, 936 KB: the two minified
  builds plus GLTFLoader, BufferGeometryUtils, SkeletonUtils, XRButton, ARButton,
  RoomEnvironment. An import map, no build step, nothing from a CDN.
- Materials: skin `MeshPhysicalMaterial` (albedo, normal at 1.2, roughness map, specular 0.45, a
  little sheen); eye interiors with their tiles; the cornea is a black, mirror-smooth physical
  shell with **additive blending**, so it adds only its reflections (the catch light) over an
  untouched iris. No transmission or refraction. Teeth and tongue flat colours.
- Light: RoomEnvironment at 0.1 for fill and reflections, one shadow-casting directional key
  from the Blender `key` position (upper image-left, in front), slightly warm. ACES at exposure
  0.75: AgX left the skin pale and grey without subsurface. The rim light from the stills is
  off by default: its specular drew a glossy streak down the shadow side of the nose.
- Plinth: dark cylinder fitted to the lowest 3 cm of the skin, top 12 mm inside the cut. Bust
  (head + plinth + key light) is one group.
- `?view=face|eye|video` puts the camera where `cam_test_face`, `cam_test_eye`, `cam_video` are,
  `?size=N` renders a fixed square, `?shot=1` hides the overlays.
- Check **pass**, by eye: `outputs/tmp/m14/xr/B_rest_face_vs_still.png` (page left, Cycles still
  right) is the same person; flatter, paler and with no 3D brow hair, as expected. No seam, no
  black eye, no inverted normals; `B_rest_eye.png` shows the iris and a small catch light.
  No console errors.

**C. The rig** (`xr/js/rig.js`, `xr/tests/rig.test.mjs`)
- C1: `Rig.apply()` ported line for line (neck 35 %, head 65 %, each eye aimed at a point,
  lids from each eye's own pitch and yaw, tent blink keys, brow dip, squint fading with the
  blink, pupil). Blender's `rot3` = Rz(yaw) Rx(−pitch) Ry(roll) becomes Ry(yaw) Rx(−pitch)
  Rz(−roll) in the glTF frame. Input is the target point (or the wrapper's gaze yaw / pitch /
  distance for the debug pose). Bones get bust-space deltas about their own heads, turned into
  local quaternions from the rest world rotations read off the loaded skeleton
  (`bonesLocal`, the `_set_local` idea), so no bone-axis sign is assumed anywhere.
- C2 **pass**: 8 node tests (rest pupils, gaze ±20 → pupils ±X, ±15 → ±Y with the lids
  following, head yaw / pitch / roll signs, eyes hold a world target through ±30 deg head yaw,
  near vergence, `bonesLocal` against random rest rotations, the shape-key rules). In the
  browser the skinned pupil vertices land within 0.025 mm of the `rig.js` prediction at rest,
  gaze ±20, ±15 and head yaw 30 (the same 0.025 mm at rest: centroid of the selected vertices
  against the vertex-group centre). Screenshots `C2_directions.png`: gaze +20 image-right, +15
  up, head +20 turns the face image-right while the eyes stay on the camera.
- Same lid shapes as Blender: `C_page_vs_blender.png`, page (left) against `rig_strips.py`
  (right; `m13/lids/after/` yaw ±30, blink 0.33 / 0.66, `m13/blink_D/` blink 1.0), both from
  `cam_eyes` at gaze distance 1.6 m.
- C3 lids without the guard: `C3_lids_grid.png` (blink 0 / 0.33 / 0.66 / 1.0 × gaze (0,0),
  (±20,0), (0,±15), left eye close up) and the worst poses `C3_worst_*.png`: **no cornea
  through a lid in any shot**. Measured (`C3_lid_inside.json`): of 117 lid-skin vertices per
  eye outside the globe at rest, at most 17 sink 0.2 to 1.4 mm into it, all at the lid margin
  where it only thins the slit edge; closed lids hide the eye at every gaze to ±28 / +22 / −25.
  So **neither fallback was needed**: no guard baked into the keys, no extra clamp beyond the
  brief's eye range (±28 yaw, +22 / −25 pitch). If the headset shows a sliver at the corners,
  the key bake in the brief is the next step.

**D. Real-time gaze** (`xr/js/gaze.js`, `xr/tests/gaze.test.mjs`, `xr/tests/sim.mjs`)
- `step(state, viewer, dt)`, pure JS, a fixed 2 ms internal tick counted in whole ticks, the
  viewer interpolated between calls, seven seeded random streams (look, glance, saccade, head,
  blink, brow, noise) so a decision that moves by one tick at another frame rate cannot reorder
  the others. Every engine number is `GazeParams` (a test checks all of them against
  `rig.json`, which the exporter reads from the engine; `saccadeDuration` and the skewed profile
  match the Python to 2e-6).
- Rules as briefed: three face points (±3.2 cm, mouth 7 cm down), dwell 0.6–1.8 s, mouth one
  jump in six; glances every 5–10 s for 0.4–1.0 s, eyes only; saccades on the main sequence
  with undershoot, corrective, glissade and `min_isi`; pursuit with catch-up past 2 deg; head
  goal 80 % of the way when eye-in-head (to where the eyes are going) passes 12 deg or stays
  past 6 for 1.2 s, 0.04–0.10 s after the eyes, 1.2 Hz critically damped, roll −0.20/deg, dip,
  sway; limits; lost (absent, past head + eye range, past 2.5 m) → hold 2 s → recentre and look
  around → back in range: saccade, brow flash 0.35 for 0.4 s, blink; blinks, partial blinks,
  evoked blinks, brow and squint effort, vergence, near pupil, hippus.
- **Numbers that are mine, not the brief's or the engine's** (all in `LIVE` with a comment):
  - the head's goal moves at most 50 deg/s, 20 deg/s when it recentres or looks around while
    searching (a 60 deg step through the bare follower peaks near 166 deg/s);
  - 0.7 velocity feed-forward into the follower, low-passed 0.1 s (without it a moving wearer
    pushed eye-in-head onto the 28 deg clamp in 6 of 8 seeds of test 2; with it 22–25 deg);
  - the head aims at the wearer's face centre, the eyes at an eye (aiming at an eye put the
    head share at 74–86 %);
  - glances are 6–12 deg in total from the face centre, to a side or 25–50 deg below
    horizontal, and never move the head (stacked on the eye offset they crossed the 12 deg
    trigger and gave head yaw rms 2.9 deg in test 1);
  - no face jumps or glances while the wearer moves faster than 5 deg/s;
  - spontaneous blink gaps capped at 3× the mean of their random part (6.4 s at most; an
    uncapped tail gave seed 3 two blinks in 20 s);
  - the greeting's blink needs only 0.1 s after the last one (a double blink), so it always
    happens;
  - while recentring the eyes look 15 deg ahead of the head toward the middle, and the
    look-around starts once the head is back within 2 deg (before, the eyes sat pinned at
    −28 deg in the head for 2 s, and look points kept turning the head away from centre);
  - pursuit: 0.95 of the target's angular speed (low-passed 0.08 s) plus a 0.5/s pull.
- Tests, seeds 0–7 (`outputs/tmp/m14/xr/node_test.txt` has every seed's numbers), all **pass**:
  1. still: head yaw rms 0.34–0.63 deg, blinks 4–8, saccades 17–21, glances 2, eye-in-head
     max 9.2–13.1 deg.
  2. step: on the wearer 0.05–0.70 deg 0.3 s after, eyes start 3.03–3.22 s and the head
     0.28–0.50 s later, head share 75–76 %, eye-in-head max 21.9–25.3 deg, 0.3–9.1 deg at the
     end (which eye it is on).
  3. walk: head to 60.0, head speed max 58–60 deg/s, lost, back to 0.0 deg while away,
     greeting with saccade, blink and brow peak 0.34.
  4. 0.25 m: vergence 13.6–13.7 deg, within 0.41 deg of the geometry.
  5. same seed same channels; 72 against 120 Hz head yaw rms 0.000 (still, step) and
     0.016–0.020 deg (walk).
- Curves, seed 0, 90 Hz: `curves_still.png`, `curves_step.png`, `curves_walk.png` (shading:
  glance, lost, search; dotted: greeting). Looked at: eye-to-eye jumps every ~1.2 s, mouth
  looks at −5.7 deg, two glances (side; down and side); in the step the eyes lead, the head
  starts ~0.3 s later, overshoots ~2 deg and settles at 76 %, dipping 4 deg as it turns; in the
  walk the head follows to 60, holds where it lost the wearer, drifts back over 3 s while the
  eyes step ahead of it, looks around, then greets.
- Watch in the headset: roll is −0.20 per degree of yaw (engine), so −12 deg at the 60 deg
  limit; it reads as a tilt on the curves.

**E. In the headset and on the laptop** (`xr/js/app.js`)
- `XRButton` (three's standard pattern: `renderer.xr.enabled`, `setAnimationLoop`):
  `immersive-ar` when offered, else `immersive-vr`; `local-floor` required, hand tracking
  optional. AR clears the background (passthrough), VR keeps the dark room. Antialias on.
- Placement: two frames after the session starts, the bust's eye midpoint goes 0.7 m in front
  of the wearer at their eye height, the bust turned to face them; any `select` on the session
  (trigger or pinch) places it again. Each frame the XR camera is turned into bust space (the
  wearer's position, right and up) and fed to the gaze.
- Laptop: the camera is the wearer on an arc round the eyes (mouse ±50 deg sideways, ±20 up and
  down, wheel 0.3 to 1.5 m, smoothed 0.25 s so it moves like a person). Touch drag does the same,
  two-finger pinch the distance. **Taking the mouse off the page is walking away**: the wearer
  becomes absent, so a jury without a headset can see it lose them and greet them again.
- Checks: no console errors; gaze + rig cost 0.03 ms a frame in the browser. Placement checked
  with three mock headset poses (`placeBust` / `viewerFrom` from the console): eyes 0.700 m ahead,
  0.000 m height difference, the wearer straight ahead in bust space with right = +X. **The real
  headset path is untested** (checklist below).
- Laptop screenshots, canvas captures: `E_laptop_five_positions.png` (centre: head 0.5 deg;
  camera −48: head −36.3, eye −6.1; up-left −34/+18: head −24.3/+12.5; +48: head 38.8, eye 8.9;
  low right at 0.30 m: head 16.7/−12.6, eyes converged) and `E_laptop_walk_away_and_back.png`
  (holds 2 s where you were, recentres and looks round, back: saccade, blink 0.30 at 70 ms,
  brow 0.26, head back to you in 0.4 s).

**F. Lashes and tear lines** (`tools/export_xr.py`, materials in `app.js`)
- Lashes: `lashes_carrier` is 430 polylines of 7 points, the same points the scene's lash curves
  are made from (Mesh to Curve). Each becomes a ribbon (two vertices per point, offset along the
  lid's tangent, taken round the eye in the frontal plane), with the carrier's skin weights and
  its 20 shape-key offsets, so the lashes ride the lids through gaze and blink. Width 1.5× the
  real lash (`hair_radius` × 2): at 1× a lash is a fraction of a headset pixel at 0.7 m; 2.5×
  read as mascara. Colour twice the Blender lash colour (its hair shader has a sheen a flat
  ribbon lacks), double-sided, no shadow (lash shadows at a 1024 map only flicker).
- Tear lines: `tear_line.L/R` exported as they are (110 vertices, skinned, their side's 9
  keys), drawn like the cornea (black, additive, mirror-smooth): only a glint.
- glb 3.19 → 5.43 MB (smooth-shaded ribbons and sparse morph accessors; flat shading had split
  them to 10 320 vertices and 6.94 MB). Head check still **pass**; scene.blend unmodified.
- Looked at: `F_lashes_strip.png` (cam_eyes: rest, gaze up 15, blink 0.66, 1.0: the lashes
  follow, no gaps, nothing through the lid), `F_bust_0.7m.png` (a soft lash line at headset
  distance), `F_face_vs_still.png`. Clean page load: no console messages.

**6, 7. Server, README, credits**
- `xr/serve.py`: HTTPS on 0.0.0.0:8443 with a self-signed certificate it makes with openssl
  on first run (`xr/.certs/`, git-ignored, SAN = the LAN address, 127.0.0.1, localhost, the
  host name, 30 days) plus plain HTTP on 127.0.0.1:8000 for the laptop and `adb reverse`.
  Smoke-tested on other ports for a few seconds: page, glb (`model/gltf-binary`) and JS
  (`text/javascript`) all 200 over both, then stopped. Nothing deployed anywhere.
- `xr/README.md`: how to run it (Wi-Fi, USB), controls, files, the export command, debug URLs,
  credits with the main README's wording for the Infinite scan. The page carries the same
  credits line. three.js recorded in `docs/TECH_NOTES.md` under Assets.

**Sizes** (`xr/` 13 MB, budget 25; no file over 10 MB): `head.glb` 5.43 MB,
`skin_normal.png` 6.31 MB, `skin_albedo.jpg` 0.47, `skin_rough.jpg` 0.18, `eye_L.jpg` 0.10,
`eye_R.jpg` 0.11, `rig.json` 3 KB (`xr/assets/` 12.6 MB); `vendor/three/` 0.94 MB.

**Checks at the end**: `node --test` 14/14; `python3 -m unittest discover tests` 51 OK;
`python3 tools/validate.py --blender …` 122 pass, **2 fail**: "README: no TODO left" (4 lines)
and "AI_DISCLOSURE: no TODO left" (1 line). Both were failing before M14 (same two in this
morning's `outputs/tmp/m14/validate.log`) and M14 touched neither file: they are the packaging
TODOs (team and college name, demo link, licence, the videos line). `scene.blend` md5
`d6e016e4…` unchanged; nothing under `wrapper/` or `textures/` changed.

**Review pack**: `outputs/tmp/m14/xr/INDEX.txt` (`outputs/tmp/m14/` already held an earlier
session's M11/M12 files, so the pack has its own folder).

**Skipped, and why**
- The headset itself: no device here. The XR path follows three's standard pattern and the
  placement maths is checked with mock poses; the owner's test is the real check.
- Blender renders of gaze ±20 / ±15 and the 40 deg head turn: none exist, and rendering them
  would compete with the finals on the GPU. The page shots stand alone there.
- The lid-key bake of C3: not needed (no poke-through seen; numbers above).
- Vellus and grown brow hair: out of scope (brows are in the albedo). No hosting.
- Left untracked: `.claude/launch.json` (the browser pane's dev server entry).

**For the owner, in the headset** (full list in `xr/README.md`): run `python3 xr/serve.py`,
open the printed `https://…:8443/xr/` in the Quest browser (or `adb reverse tcp:8000 tcp:8000`
and `http://localhost:8000/xr/`), START XR, then: does it find me and stand at eye height; do
the eyes arrive before the head when I step aside; does it lose me behind it and greet me when
I come back; is anything clipping (eye through lids, lashes, neck cut) or flickering (lashes,
lid edges, tear line, nose shadow); is the frame rate smooth; is it the same man as in the
videos.

### Sun 15 Nov 2026, evening — the owner chose WebXR for the Quest bonus; brief for Opus written (Fable)
- Decision: a WebXR page (three.js), not a Unity app. Brief: `docs/BRIEF_M14.md`, same split as
  M13 (Fable briefs, Opus builds, Fable reviews from `outputs/tmp/m14/`).
- **The finals are rendering in the owner's Terminal** (started this afternoon, `generate`
  first). Each input is a fresh Blender start that reads `scene.blend` and `wrapper/`, so
  nothing may change those, or `textures/`, until `outputs/videos/` holds the three finals.
  The brief says so and M14 only adds files.
- Facts the brief rests on, read from `scene.blend`: the eyeballs are part of `gnm_head` (slots
  `eye_interior.*`, `cornea.*`, skinned to `eye.L/R`); 17 821 vertices, 21 shape keys; lid skin
  is kept off the globe by two shrinkwrap modifiers that a glTF export loses, so the brief has
  a lid check without the guard and a fallback (bake the guard into each key); hair is
  geometry-nodes curves on point carriers, so lashes need their own export.
- What Fable specified and nobody has built or seen yet: the real-time gaze rules (three face
  points, glances away, eyes lead and the head follows past 12 deg, lost and greeted again) and
  their five node tests. Expect the numbers to need a pass once it is seen moving.
- Not decided: hosting on a public link. The brief forbids deploying; the headset test runs
  from a local HTTPS server on the Mac.

### Sun 15 Nov 2026, late afternoon — deadline is 22 Nov; Quest 3S reopened as a bonus (Fable)
- The owner says the final submission is **Sun 22 Nov 2026**, not 18 Nov. `CLAUDE.md` updated.
  Time of day not confirmed yet.
- The owner accepted the motion and the roll-top frame ("all good") and is starting the three
  finals by hand in Terminal (one command, `generate` then `left` then `right`, logs in
  `outputs/tmp/finals/<input>.log`; a restart must add `--resume`, a plain rerun starts clean).
  No final frame has been timed or rendered from a session.
- The owner wants a bonus for an XR hackathon: this head in their Meta Quest 3S, looking at the
  wearer and turning its head when they move. This reopens the "Blender only" decision; the
  reason is the four extra days. It scores nothing on the rubric, so it stays outside the
  bundle's required files and starts after the finals are rendering and the core is packaged.
  Fable's recommendation, not decided: a WebXR page (three.js, head exported from Blender as
  glTF with the eye bones and lid shape keys, a real-time port of the gaze rules) over a Unity
  app, because it opens from a link in the Quest browser with passthrough, also runs on a
  laptop for a jury without a headset, and a session can check it in a browser.

### Sun 15 Nov 2026, 14:30 — review of the M13 pack: accepted, `generate` cut to its beat (Fable)
Reviewed from `outputs/tmp/m13/` (curves, draft sheets, preview split stills of both panes, lid
pairs, blink strips, `lid_check` before and after), plus a strip of every second draft frame
through the eye roll. 51 tests pass. Stages A to D are accepted as built.

Rulings on what Opus left open:
- **`check_lids` 7 and 12 µm over the baseline: accepted, C stays.** Both worst cases sit at
  yaw 30 with pitch 25 or −30, poses no input reaches (largest eye-in-head yaw in the three
  inputs is 22 deg), the values are a tenth of the guard offset, and rim-over fell from 2.2 to
  1.6 mm. In the zoomed pairs the lid outline leans with the cornea, with no dent, no corner step
  and no lash through skin. `GUARD_OFFSET` is not changed.
- **Head tips back 2.6 to 4.5 deg in the roll, roll lasts 1.59 to 1.70 s: accepted.** In the frame
  strip the roll reads as launch (120), travel over the top (122 to 136), a beat up and across
  (138 to 144), lids down (146 to 152), open on the low gaze (154 to 164), viewer (170). The
  sclera under the iris at the top is what an up gaze shows; with `widen` at 0.12 and the brows
  at 0.39 it does not read as startled.
- **Third glance fixation past 20 deg eye-in-head (up to 22): accepted**, well inside the range
  people use without turning the head.
- **Pane: Fable recommends `eyes`, the owner decides.** With `eye` the camera sits where the eye
  is looking in `left`, so frames 40, 60 and 150 show an eye looking nearly into the lens and
  the glance does not read as left; it is the better close-up of iris and lashes, though. `eyes`
  shows what the deck asks for ("both eyes move"), the lids leaning and both brows.

Changed in this session (the brief's own fault, not Opus's): `generate` ran 10 to 11.5 s but its
beat is over at about 5.7 s, which left 4.7 s of looking at the viewer with one flick and one
blink. The clip now ends with the beat: back on the viewer, flick 0.7 to 0.9 s later, back
0.6 to 0.8 s after that, the soft blink 0.25 to 0.4 s later, 1.0 to 1.2 s more and out.
Seeds 0 to 7: **8.3 to 8.6 s** (seed 0: 8.3 s, 249 frames, was 321), closing blink 2.56 to 2.69 s
after the slow one. Every draw up to the return to the viewer is unchanged, so the pack's stills
of the glances and the roll (frames 43 to 163) are still the motion. Test range 10–11.5 → 7.5–9.5.
`scene.blend` rebuilt (the Timeline now holds the 8.3 s `generate`). New draft, curves and a
sheet of the tail: `outputs/tmp/m13/review/`; `outputs/videos/generate.mp4` is that draft too.

Not judged here, because stills cannot show it: how the three clips feel at playback speed.
That is the owner's check on `outputs/tmp/m13/drafts/{left,right}_draft.mp4` and
`outputs/tmp/m13/review/generate_draft.mp4` (EEVEE, face camera only, timing not looks).

**Later the same afternoon: the owner chose the one-eye pane** after seeing both sets of stills
(Fable had recommended `eyes`; the owner prefers the close-up, and in `left` the eye turning
toward its lens is accepted). `--pane` now defaults to `eye`, so the command evaluators run
makes the videos we ship; `eyes` still works. Docstring, `--help` and the README row updated.
Checked with `--input generate --quality preview --frames 131 215` and no `--pane`: the second
pass is `cam_move_eye`, stills in `outputs/frames/generate/split_eye_stills/`, looked at (roll
top: iris high under the lid, brow raised, lashes and skin sharp). 51 tests pass.

Next: owner watches the drafts; then finals of the three inputs with
`--camera split` (pane `eye` by default): 270 + 270 + 249 = 789 frames, two passes each (72 fewer frames
than before the trim). Then `--clockwise`, `--check-directions --render`, `tools/validate.py`
and packaging. Finals are mechanical: an Opus session can run them.

### Sun 15 Nov 2026, evening — M13 motion rework, stages A to D and the review pack (Opus)
Implements `docs/BRIEF_M13.md`. Review pack in `outputs/tmp/m13/` (git-ignored). Finals not rendered.

**Stage A, engine and choreography** (`wrapper/gaze/`, tests). Done.
- A1: `GLANCE_HEAD` 0.5 → 0.22, first glance target `u(22, 26)`; rest of `_glance` unchanged.
- A2: `head_freq` 1.2 Hz, `head_roll_coupling` −0.20, sway (0.55, 0.45, 0.30) in (0.08, 0.35) Hz.
  Head dip: `head_pitch −= head_dip_gain · lowpass(|d head_yaw / dt|, 60 ms)` on the follow
  (sway excluded), `head_dip_gain` 0.064 s, which is 0.15 deg per deg of yaw at 1.2 Hz.
- A3: `Blink.slow` multiplies close, hold and open. A slow blink is never made partial (its
  partial-blink draw is still taken, so every other draw stays put). `meta["blink_slow"]` added
  next to `meta["blinks"]`, whose shape is unchanged.
- A4: `generate` rewritten as the brief's one beat; total `u(10.0, 11.5)` s.
  **Engine change the beat needed, not in the brief:** a `Sweep` used to wait for `free_at`
  (last saccade + 150 ms), and a 24 deg launch schedules an undershoot correction ~0.25 s
  later, so the sweep at launch + 0.16 s was pushed to ~+0.45 s and started from the corrected
  target, not from where the gaze was. Now a sweep starts once the last saccade begun before it
  has landed, from the gaze sample at that moment, and drops any saccade scripted after its
  start (the pending correction). Old scripts never hit this (their sweeps had time to spare).
  The drop after the sweep still waits `min_isi` (0.15 s), so `generate` puts it there and the
  slow blink 0.03 s before it.
- A5 tests: `test_head_moves_less_and_later_than_the_eyes` (head < 0.35 of gaze), sway test
  (40 s clips so 0.08 Hz resolves, band 0.06–0.40, new rms windows), brow-on-roll test 0.4 → 0.3
  (the brief's roll brow is 0.35–0.45, was 0.6–0.8). New class `M13`: eyes carry the glance,
  head dip, slow blink length, generate through all four directions, roll fast/slow/not wide.
  `test_camera_move`: two tolerances loosened (0.75 → 0.70 of the glide, −0.05 → −0.06 s) for the
  new `generate`, whose fixations are shorter; `--camera move` is not the video camera any more
  and was left alone. 51 tests pass.

| Check (seeds 0–7 unless noted) | Target | Measured | |
|---|---|---|---|
| head yaw peak, left/right | 4.5–6.5 deg | 4.9–6.3 without sway, 5.6–6.7 with it | pass (three seeds 6.55–6.69 with sway) |
| eye-in-head ≥ 15 deg, left/right | ≥ 2 s | 2.9–4.3 s in total; longest single stretch 1.5–1.8 s (4.0–4.3 s in two seeds) | pass on total; see note |
| head dip peak, left/right | 0.7–1.0 deg | 0.77–1.00 | pass |
| head dip, generate (40 deg shifts) | — | 1.15–1.32 | as designed |
| generate duration | 10–11.5 s | 10.1–11.4 | pass |
| gaze yaw passes ±15 / pitch +20 and −10 | yes | yaw −21.6..+21.7, pitch +25.4..+26.7 and −13.1..−16.0 | pass |
| widen during the roll | < 0.2 | 0.110–0.130 (only the brow-driven share) | pass |
| speed over the top / launch | < 0.5 | 90–122 / 517–540 deg/s (≤ 0.23) | pass |
| slow blink | 2× default | slow 1.82–2.13, test ratio 2.0 ± 0.25 | pass |
| head tips back in the roll | ~5 deg | 2.6–4.5 deg (1.2 Hz follow does not reach 0.22 × 21 deg in 0.7 s) | short, Fable's call |

Note on eye-in-head: the first fixation sits at 18.5–20 deg (1.3–1.6 s), the second refixation
comes 4–7 deg back toward the nose (eye ~12–14 deg), the third goes 1.5–3.5 deg past the first
(eye 19–22 deg). So "16–20 for 2 s" holds in total, not in one stretch, and the third fixation
can exceed 20. Untouched because A1 says everything else in `_glance` stays.
Curves: `outputs/tmp/m13/{left,right,generate}_curves.png`, looked at.
Fixed later the same session, found while picking the review frames: the low hold was timed
from the drop's onset, but the slow blink lasts ~0.53 s, so the eyes reopened as they left for
the viewer and the lowered gaze was never seen open. The hold now counts from the slow blink
being 85 % open: low and open 0.43–0.49 s (seeds 0–7); the roll, launch to back at the viewer,
is 1.59–1.70 s (brief 1.3–1.6: over by up to 0.1 s, the price of a visible hold).

**Stage B, right pane** (`wrapper/eyes.py`, README). Done.
- `--pane eyes|eye` (default `eyes`) picks the second pass of `--camera split`: `eyes` is
  `cam_move_eyes` (fixed, both eyes and brows straight on), `eye` is `cam_move_eye` as before.
  Pane frames go to `outputs/frames/<input>/<pane>/`; `--frames` stills to
  `outputs/frames/<input>/split_<pane>_stills/` (was `split_stills/`), so both sets are kept.
  Docstring, `--help` and README row updated.
- Scene rebuilt after stage A (18 s; `generate` seed 0 baked, 321 frames).
- `left` split stills at 1, 40, 60, 150, preview quality, both panes:
  `outputs/tmp/m13/B/split_{eyes,eye}_stills/` and tiled in `outputs/tmp/m13/B_left_split_*.png`.
  Looked at. `eyes` pane: brows to the upper lip in frame at all four, nothing cut through the
  turn, so `MOVE_EYES` is unchanged. Frame 60 (eyes held left, head ~5 deg): both eyes readable;
  the subject's left eye (image right) sits a little darker but iris and lids read. Lights not
  touched. 10 s/frame for the `eyes` pane, 9 s for `eye`, 7.5 s for the face, at preview.

**Stage C, lids follow the eye sideways** (`tools/solve_lids.py`, `wrapper/rig.py`). Done, one
check fails by the letter (below); kept for Fable to judge rather than reverted.
- New keys `lid_in.S` / `lid_out.S` (eye 25 deg toward the nose / temple, pitch 0), least-squares
  line over `FRACTIONS` like `lid_up`. Apex shift (`Eye.apex_angles`): along each lid a half sine
  from the nasal corner to the pupil column and an opposite one to the temporal corner, margin
  travel over the rim's distance from the joint's x axis; upper 0.5 mm, lower 0.3 mm at the peak
  (`APEX_MM`). `targets()`, `pose()` and `drape()` now take `yaw`, so the lid is seated and draped
  on the yawed globe. No retract. Same reach fade. `posed()` and the solver's own report use the
  new keys too. `SIDE_YAW = 25`.
- Numeric check on the hero head, `lid_in.L` at −25 deg: upper margin +0.56 mm on the nasal half,
  −0.45 mm on the temporal half, lower −0.36 / +0.27 mm, corners ≤ 0.06 mm; the margin comes
  forward 1.1 mm where the cornea arrives and sinks 1.2 mm where it left. `lid_out` mirrors it.
- `rig.py`: `eye_yaw` per eye (head frame), `nasal = −yaw` for L, `+yaw` for R,
  `lid_in = clip(nasal/25, 0, 1.2)(1 − b)`, `lid_out = clip(−nasal/25, 0, 1.2)(1 − b)`; `eye_yaw`
  added to `state`. Older scenes are unaffected (key guard).
- Carriers get the keys by name: lashes, vellus and brow hair carriers 16 → 20 driven keys,
  tear lines 7 → 9. Template `assets/gnm/lids.npz` re-solved (old copy in
  `outputs/tmp/m13/lids_template_before.npz`); the hero head is solved inside the build.
- `rig_strips.py --only <shots>` added to render a subset.

| Check | Target | Measured | |
|---|---|---|---|
| solver keys-only, hero head (no guard) | — | rim under 1.84 → 1.71 (L) / 1.82 → 1.70 (R) mm; rim over 2.21 → 1.63 / 2.31 → 1.77; skin 1.26 / 1.27 unchanged | better |
| `check_lids` L skin inside | ≤ 0.026 mm | 0.033 at (25, −30, 0.83) | **fail by 7 µm** |
| `check_lids` R skin inside | ≤ 0.032 | 0.030 | pass |
| `check_lids` rim under L / R | ≤ 0.103 / 0.099 | 0.103 / 0.099 | pass |
| `check_lids` rim over L / R | ≤ 2.213 / 2.307 | 1.631 / 1.768 | pass, better |
| `check_lids` lash inside L | ≤ 0.017 | 0.016 | pass |
| `check_lids` lash inside R | ≤ 0.025 | 0.037 at (−30, −30, 0) | **fail by 12 µm** |
| strips `yaw_±30` before/after | outline follows the eye, no dent, no corner step, no lash through skin | as wanted, looked at in `outputs/tmp/m13/lids/yaw_zoom_before_after.png` | pass |
| `--check-directions --render` | 13.8–14.2 px | left −13.78 / −14.16, right +14.15 / +13.80, up/down 13.97–13.99; `direction_check.json` byte-identical | pass |
| unit tests | pass | 51 OK | pass |

Why the two fails are not penetration: `check_lids` measures against the globe as a smooth
radius profile (max radius per 0.6 deg bin), but the guard shrinkwraps to the polygonal shell.
Shell face centres sit up to 0.227 mm inside that profile (measured, both eyes), and the guard
puts skin and lashes 0.12 mm outside the faceted shell, so a guarded point can read up to about
0.107 mm "inside" without crossing the surface that renders. Before and after values (0.016 to 0.037)
all sit in that band. If Fable wants the letter met, `GUARD_OFFSET` 0.12 → 0.14 mm would do it
(not done: it moves every guarded pose, and the brief did not ask for it). To drop C:
revert its commit, re-run `python3 tools/solve_lids.py` and rebuild.
Pairs: `outputs/tmp/m13/lids/{yaw_-30,yaw_+30}_before_after.png` and the zoom above; the
baseline and the new check are `outputs/tmp/m13/lid_check_{before,after}.json`.

**Stage D, blink detail** (`wrapper/rig.py`, `tools/build_scene.py`). Done.
- `brow_up.S = brow_S − 0.08 · b` (`BLINK_BROW_DIP`). `brow_up.*` keys get `slider_min −0.5`
  in `build_shape_keys`; every carrier copies its limits from the head (checked in the built
  scene: head, lashes, vellus, brows_grown, six brow-hair carriers and both tear lines at −0.5).
  At blink 1 the head key and the carriers' driven key both read −0.08.
- Brow drop: the `brow_up.L` key moves the brow at most 3.14 mm at 1.0, so the dip peaks at
  0.25 mm at a full blink (target < 1 mm): pass. Blink 0.66 strip without and with the dip
  (`outputs/tmp/m13/blink_D/blink_0.66_noDip_vs_dip.png`), looked at: a hair lower, no step on
  the forehead: pass. Strips at 0.33 / 0.66 / 1.00 in `outputs/tmp/m13/blink_D/`. Tests 51 OK.

**Review pack** (`outputs/tmp/m13/`, index in `INDEX.txt`). Scene rebuilt last with everything
above (`generate` seed 0 baked, 321 frames).
1. Curve plots of seed 0, all three: done, looked at.
2. EEVEE drafts, `--camera face`, all three: `drafts/*_draft.mp4` (9.0, 9.0, 10.7 s) and contact
   sheets (every 6th frame, numbered): done, looked at. The drafts also overwrote the untracked
   `outputs/videos/{left,right,generate}.mp4`: those are drafts now, not previews.
   `left`: eyes out at 1.2 s with a small head follow, blink in the hold at 2.8 s, back at 5.2 s.
   `generate`: glance A 1.0–2.0 s, blink across to B 2.2–3.0 s, viewer 3.2–3.9 s, roll up and over
   4.0–4.7 s, slow blink 4.8–5.3 s, low hold to 5.6 s, viewer, flick, soft blink at 9.4 s.
3. Cycles preview split stills, both panes: `left` 1, 36, 40, 60, 150, 165; `generate` 43 (glance
   A), 82 (glance B), 120 (launch), 131 (top), 148 (mid slow blink), 163 (low hold): done, looked
   at, sheets in `stills/`. For Fable: at the roll top the lower lid shows a band of sclera under
   the iris in the eye pane (expected looking up, but it is the frame to judge "startled" on).
4. Lid pairs (C) and blink strips (D): done, see above.

Not done, by the brief: finals, packaging, deck, new expression shapes, lights, textures, the
camera move. Open for Fable: the two `check_lids` numbers over baseline (C), the head tipping back
2.6–4.5 deg instead of ~5 in the roll (A), the roll running 1.59–1.70 s (A), the third glance
fixation going past 20 deg eye-in-head (A1 left `_glance` as it was), which pane the owner wants.

### Sun 15 Nov 2026, afternoon — the owner rejected the motion in the previews; drafts and both reference videos watched as motion (Fable)
The owner watched `left_split_preview`, `right_preview_v2` and `generate_preview_v2` and said the
animation is not realistic. No code changed in this session; this is the diagnosis and the plan
put to the owner. Nothing below is started until the owner says go.

`Evaluation_for_SyntheticEyes (4).pptx` read: same two slides and same text as `_1` and `(3)`.

**Watched, every frame of the three previews** (decoded with Blender's sequencer, no ffmpeg here):
- The eyeball motion is sound (saccade lengths, undershoot and correction, the eye counter-rotating
  as the head catches up). The face around it is what reads as a doll:
- Lids follow eye pitch only (`rig.py`: `lid_up`, `lid_down`). When the eye turns sideways the lid
  margin does not move with the cornea, so the iris slides under a fixed opening.
- Brows peak at 0.25 of `brow_up` in `left`/`right`, about 2 mm. Nothing moves below the lower lid.
  No brow dip or lower-lid rise in a blink.
- `left`/`right` are told by the head: 14 to 16 deg of head, eyes settle at about 13 deg in the
  head. The head turn is pure yaw of a cut bust on a critically damped curve, then holds almost
  still for 4 s. In `left` the turn carries both eyes into the shadow side of the key.
- The eye pane rides on the head, so it shows a flick and then an eye looking back at its camera.
- `generate` is five separate gestures, each about a second, with a return to the camera and a
  blink between each: reads as a rig test.

**Reference videos watched as motion for the first time** (timed contact sheets in the browser
pane; nothing stored):
- "Eye Piece": lid opens slowly over 1.0 to 4.5 s; three blinks inside 1.1 s (5.67, 6.00, 6.70 s),
  one on each gaze shift; the upper lid bulge travels with the cornea; lids half-closed again at
  9 to 10 s; eye wide and darting at 13 to 14.5 s. One eye, three-quarter, extreme close-up.
- "Flexpressions": the whole face works: deep forehead lines with the brow raise, squint with the
  cheeks, mouth, head tilt, asymmetric.

**Plan proposed to the owner, in order of effect per hour:**
1. Eyes carry `left`/`right`: head share 0.5 to about 0.2 (5 to 6 deg, with a little pitch and
   roll and a slower settle), eyes 18 to 20 deg in the head.
2. Horizontal lid follow: new shape keys from the lid solve so the lid apex moves with the cornea.
3. More face: brow amplitude up, brow dip and lower-lid rise in blinks, cheek with squint, from
   GNM expression classes already exported by the tools step.
4. `generate` as one motivated beat (left, right, eye roll with brows, slow blink back).
5. Right pane films both eyes and brows from the front instead of one eye on the head bone
   (reopens the 15 Nov split choice; owner's call).
Finals still need 16 to 20 h of render, so motion has to be accepted by Mon 16 Nov night.

**Later the same afternoon:** the owner also called the eye roll in `generate` unnatural. Watched
frames 68 to 102: a smooth 0.84 s orbit at near-constant speed with `widen` 0.57 and brows 0.6,
head pitch +1 deg, no lid droop at the end: reads as startled, not as an eye roll. The owner
proposed the split and Fable agreed: Fable writes the brief, Opus 5.5 implements, Fable reviews. The brief is
`docs/BRIEF_M13.md` (stages A engine, B both-eyes pane, C sideways lid follow, D blink detail;
review pack by Mon 16 Nov 10:00). Plan item 3's new GNM expression shapes are out of scope for M13.

### Sun 15 Nov 2026 — M11 stage 2 + ears of 01 to 08: adopted, 3D brow hair for 06/12/14, scene rebuilt (Opus)
**scene.blend changed (rebuilt). The hero frame is unchanged**, so the final videos can start from it.

**Adopted:**
- Fable's verdicts on M11 stage 1: gender-free labels for all nine sets; brows of 01 (outline 12),
  05 (softer), 08 (outline 14); brown irises on 02, 03, 05, 06.
- Ear relief and roughness (`ear_skin`) on 01 to 08.
- Builds: 01 05 06 08 in full, 02 03 04 07 `--skip-bake` (raw bakes from `outputs/tmp/m2/sets`,
  all four present), 09 `--eyes-only --skip-check`.
- Commits: recipes a47ddfa (ears) and 48f9cf6 (06).

**Set 06 brows: outline 06** (676 mm2, colour 0.004/0.003/0.0025, opacity 1.0, width 0.14,
density 1.8, shadow 0.45).
- At 1:1, single strokes run through the body with skin between them in the lower half. Outline
  01's core is near-solid.
- From the front it reads as a full brow with a soft, hairy head and lower edge, not a slab.
  Outline 01 stays a thin arc.
- Evidence: `outputs/tmp/m14/brow06_1to1.png`, `brow06_body3x.png`, `brow06_front_zoom.png`.
  The M11 trial was re-rendered with today's check; the two fronts differ only at brows and
  ears.

**Diff against the previous textures/** (`outputs/tmp/m12/diffcheck.py`, backup in
`outputs/tmp/m14/textures_before/`):
| set | albedo changed / bbox (y, x) | normal | rough | eye tiles |
|---|---|---|---|---|
| 01 | 2,078,282 / 0-2384, 0-4095 | 754,978 ear | 179,326 ear | identical |
| 02 | 462,313 / 1146-2945, 525-3567 | 754,847 ear | 179,233 ear | new iris |
| 03 | 113,254 / 1149-2079, 535-3562 | 754,979 ear | 178,554 ear | new iris |
| 04 | 529,242 / 1132-2093, 518-3569 | 756,140 ear | 178,553 ear | identical |
| 05 | 812,451 / 0-2367, 0-4095 | 750,527 ear | 178,592 ear | new iris |
| 06 | 236,301 / 1149-2079, 536-3563 | 748,455 ear | 179,310 ear | new iris |
| 07 | 566,826 / 1142-2092, 523-3568 | 756,560 ear | 178,563 ear | identical |
| 08 | 3,067,257 / 0-2352, 0-4095 | 754,206 ear | 179,209 ear | identical |
| 09 | 0 | 0 | 0 | identical (only `set.json`, the label) |

- **Normal and roughness:** changes are in the ear zone; 36-56 and 0-4 texels sit at its edge,
  within 1 texel.
- **02, 03, 04, 07 albedo:** ear zone only, plus at most 194 texels by 1 level within 18 texels
  of it (and one texel of 02 off by 1, rounding).
- **Accepted by the owner: a 1-3 level spread outside the brow and ear areas on 01, 05, 06, 08**
  (`outputs/tmp/m14/outside.py`; texels outside brow regions + about 5 mm and the ear zone):

| set | texels | under the scalp-fix weight | size |
|---|---|---|---|
| 01 | 1,416,354 | 1,086,698 | ≤ 2 levels |
| 05 | 198,613 | 151,310 | ≤ 2 levels |
| 08 | 2,394,992 | 1,784,561 | ≤ 2 levels |
| 06 | 34,733 | none (no scalp fix) | ≤ 3 levels, around the larger outline |

  - **Cause:** the scalp fix rebuilds the cap's tone by a harmonic fill anchored on the skin
    around it, so the new brows shift the whole cap by a level or two. The rest is the rebake's
    own fill.
  - **It is what was reviewed:** 01, 05 and 08 equal the M11 trial except the ear zone (at most
    178 texels outside it, by 1). It is invisible.
  - The brief counted it as a failure, so the first pass stopped. The owner accepted it, and the
    kept build was adopted as is.
- **Protected files, md5:** tex_09's maps, `renders/` and `metadata.json` are byte-identical,
  and `wrapper/` matches HEAD. Another session committed `wrapper/eyes.py` at 12:13; I did not
  touch it.

**3D brow hair:**
- `tools/carry_hair.py` SETS and `build_hair`'s list now carry 01, 05, 06, 08, 12 and 14, with
  none dropped. carry_hair took the new three in about a second (1776 / 1990 / 2430 hairs,
  rebuild error 0), and left 01, 05 and 08 byte-identical.
- `scene.blend` rebuilt with the CLAUDE.md commands: `lids.npz` unchanged (7d45359c…),
  `scene.blend` 76ef2d72…, 14.8 MB.
- Hero frame `--move 0 0 --samples 32`, before against after: 92 px differ, max 1. Two runs of
  the same scene differ by 83 px, max 1 (GPU noise), so the frame is unchanged.
- Geometry hashes: every old object is identical; three hidden brow hair objects were added.
- `--texture 01 / 06 / 08` show brow_hair_12 / _06 / _14, sitting on the painted brow
  (`outputs/tmp/m14/brows3d_crop.png`). tex_09 still shows its grown brows.
- `--check-directions`: `outputs/direction_check.json` is byte-identical to the committed file.

**Sheets and stills:** `texture_sheet.png`, the eight stills and the eye stills were rerendered,
and `eye/sheet.png` rebuilt. Every identity scene was rebuilt first: `build_scene.py` and the hair
binding were newer.
- Looked at: both sheets, all eight stills (in 2x2 grids at full size), and the before/after
  pixel diff per still.
- Face stills change 6k-36k px (>4), in the brows and ears. Eye stills change more (13k-130k):
  irises, new brows, and the rebuilt identity scenes. Nothing broken.

**Still looks weak** (none of it new from this build):
- 06's near-black 3D brow hair catches a grey sheen along its top in the hero scene.
- 06's face is very dark in the still lighting.
- 01 has grey shading painted round the mouth.
- 04's cheeks look blotchy and posterised at still size.
- 05's brows are still a fairly solid black at face distance.
- 03's ear keeps its painted concha shading.

**Docs and checks:** README texture table carries the nine labels, plus one line saying they hold
no gender or ethnicity. TECH_NOTES has the iris `radial` options under the iris notes, and the ear
note now says 01 to 08 take the relief and roughness too. `unittest`: 46 OK. `validate.py
--blender`: only README TODO (4 lines) and AI_DISCLOSURE TODO (1 line) fail.

**Not done:** the ear colour fix on 01 to 08 (not asked). Videos not rerendered, as the final
video session owns them. `outputs/tmp/m11` (1.5 GB) and `outputs/tmp/m14` can go after
submission.

### Sun 15 Nov 2026, noon — the owner chose side by side for the final videos (Fable)
The owner watched the previews and chose the split format (face pane and eye pane, 2048x1024)
for all three final videos. `--camera split` is now the default for `--input`, so the command
an evaluator runs gives what we ship; `--camera face` is the single 1024x1024 view. Docstring,
`--help` and the README row say so. Unit tests 46 OK. Not run in Blender after the one-word
default change (the texture build was baking at the time); the split path itself was tested
in the entry below.

**Final renders, not started.** They wait for M11 stage 2, which rebuilds `scene.blend`. Then,
one at a time, each resumable:
```
caffeinate -i $BLENDER -b scene.blend -P wrapper/eyes.py -- --input left --samples 64
caffeinate -i $BLENDER -b scene.blend -P wrapper/eyes.py -- --input right --samples 64
caffeinate -i $BLENDER -b scene.blend -P wrapper/eyes.py -- --input generate --samples 64
```
After an interruption, the same command with `--resume`. Expected from the preview timings:
65 to 85 s per frame for both panes, so 5 to 6.5 h for `left` and `right` each and 6 to 7.5 h
for `generate`: 16 to 20 h in all. Look at frames 40, 110 and 240 of the first one after ten
minutes before leaving it overnight.

**Handover: this session ends here; a new Fable session takes the finals.** Open, in order:
1. Wait for M11 stage 2 (texture build, `scene.blend` rebuild, pushed). Nothing below before it.
2. `renders/` and `metadata.json` date from 14 Nov 18:45, before the tex_09 ear fix and the
   stage 2 rebuild: rerun `--clockwise`, look at the frames, rerun `--check-directions --render`.
3. `generate` was previewed face-only, never in split: render split stills of an eye roll frame,
   a look-down frame and a blink (`--input generate --frames ... --samples 64`) and look at the
   eye pane before its final.
4. The three finals. A teammate may render `right` on another machine from a fresh clone after
   a 10-frame test (send back the `[eyes] Blender` log line, s/frame and frame 0005); compare
   that frame with ours before accepting the video.
5. Opus has a packaging brief (licence, README blanks, deck, demo shot list, zip; its part 2
   waits for the videos). Final QA after that.
The owner has seen the previews of `left`, `right`, `generate` (face) and `left` (split) and
chose split; no objection to the new motion was raised, and no explicit sign-off either.

### Sun 15 Nov 2026, noon — review of M11 stage 1 and the ear trial on 01 to 08 (Fable)
Looked at `outputs/tmp/m11/review.png` (all rows), `outputs/tmp/m11/outlines.png` and
`outputs/tmp/m13/review_ears_1to1.png`. Nothing built or changed here; stage 2 is one Opus job.

| item | verdict |
|---|---|
| Labels without gender or ethnicity | adopt as listed |
| 01 brows, outline 12 | adopt. Reads as hair at 1:1 and as a brow from the front; the pencil arc is gone |
| 08 brows, outline 14 | adopt |
| 05 brows, softer | adopt. The hard painted edge is gone and they stay black |
| 06 brows, darker on outline 01 | adopt as the fallback. It is still the thin arc, and at 1:1 a near-solid stroke. Stage 2 tries outline 06 (676 mm2) once, with the darker colour, and keeps whichever shows single hairs in the body at 1:1 |
| Brown irises 02, 03, 05, 06 | adopt. Warm ring and darker rim show on the bare head, nothing directional, no glow in the lit eyes of 03 and 05 |
| 3D brow hair for `--texture 01 / 08` | option (a): carry every outline a set now uses into `scene.blend`, rebuild, check the hero frame did not move |
| Ear relief and roughness on 01 to 08 (`ear_skin`) | adopt in the same build. Modest but in the right direction; ear colour of 01 to 08 is left alone |

Still reads as CG on the bare head, not fixable in a texture: the grey veil and grey pupil are
the judges' plain cornea reflecting the world, the same for every team. 03's ear keeps the
painted shading of its MakeHuman skin.

**Order that matters**: stage 2 rebuilds `scene.blend`, so the final videos start only after it.

### Sun 15 Nov 2026 — M12 follow-up: ear relief and roughness for sets 01 to 08, trial only, waits for M11 stage 2 (Opus)
The owner asked for the tex_09 ear relief and roughness (`detail_maps.py --ear-skin`, recipe key
`"ear_skin": 1.0` in `detail`) on sets 01 to 08, to land after M11. **M11 stage 2 has not run**
(its recipes for 01/05/06/08 brows and 02/03/05/06 irises are committed but `textures/` is the
old build). So this is a trial only: nothing in `textures/`, `tools/` or the recipes changed. The
key is NOT in the recipes yet, so M11's stage 2 build stays exactly what M11 reviewed.

**Review: `outputs/tmp/m13/review_ears_1to1.png`** (bare head, plain material, subject's left ear
at 1:1, before | after per set) and `outputs/tmp/m13/review.png` (the same shots, wider).
Trial sets: `outputs/tmp/m13/sets/tex_NN`, built by `outputs/tmp/m13/trial.py` (patches the
recipe in memory, `--skip-bake` on copies of the shipped raw bakes from `outputs/tmp/m2/sets`).
- Seen: a fine-grained ear and less sheen (02 lobe, 06 helix, the rims of 01 and 08). It is a
  modest change. The ears of 01, 02, 06 and 08 do not read coarser than their faces, though they
  measure higher (below). What still limits these ears is the baked colour: 03's painted concha
  shading, and the blurry lobes of 01 and 02 with a faint vertical line. The colour fix (`skin_fix`
  key `ears`) was not tried on them.
- Measured (ears group / cheek groups), mean normal tilt before -> after, cheek; roughness median
  before -> after, cheek:

| set | tilt | cheek tilt | rough | cheek rough |
|---|---|---|---|---|
| 01 | 1.90 -> 4.37 | 3.58 | 0.451 -> 0.502 | 0.549 |
| 02 | 2.03 -> 4.42 | 3.51 | 0.478 -> 0.525 | 0.537 |
| 03 | 1.95 -> 3.88 | 5.26 | 0.463 -> 0.510 | 0.549 |
| 04 | 2.47 -> 4.49 | 5.27 | 0.490 -> 0.541 | 0.576 |
| 05 | 1.76 -> 3.71 | 5.16 | 0.475 -> 0.522 | 0.584 |
| 06 | 2.32 -> 4.37 | 3.50 | 0.482 -> 0.533 | 0.561 |
| 07 | 1.91 -> 4.23 | 5.21 | 0.486 -> 0.533 | 0.545 |
| 08 | 2.06 -> 4.30 | 3.58 | 0.478 -> 0.525 | 0.557 |

- Difference masks, trial against shipped (`outputs/tmp/m12/diffcheck.py`,
  `outputs/tmp/m13/spill.py`):
  - Normal: 748k-757k texels changed per set, 36-56 just outside the ear zone, all within
    1 texel.
  - Roughness: about 179k texels changed, at most 4 outside the zone, within 1 texel.
  - Albedo: the six light sets carry relief grain in their colour, so the albedo changes too
    (88k-577k texels, max 12 levels). 0 to 194 texels outside the zone, all by 1 level and
    within 18 texels of the zone. One exception: a single texel of 02 about 1,000 texels away,
    off by 1, which is rounding.
  - Eye tiles: 01, 04, 07, 08 byte-identical. 02, 03, 05, 06 differ only because the trial ran
    on M11's new iris recipes.

**To adopt, after M11 stage 2 has landed and no Blender render is running:**
1. Add `"ear_skin": 1.0` to the `detail` dict of sets 01 to 08 in `tools/build_textures.py`.
2. Run `python3 tools/build_textures.py --sets 01 02 03 04 05 06 07 08 --skip-bake`. It
   rewrites skin maps, eye tiles (unchanged after M11), set.json (gains the flag), previews and
   the sheet.
3. Diff the new sets against the post-M11 `textures/` with `outputs/tmp/m12/diffcheck.py`:
   only the ear zone may change.
4. Rerender the stills with `python3 tools/render_stills.py --sets 01 ... 08` if their ears are
   in frame (they are in tex_09's).
5. No `scene.blend` rebuild is needed: the build reads only the hero set's skin.

### Sun 15 Nov 2026 — split face and eye video, --resume, previews of `right` and split `left` (Opus)
**For the owner: `~/Downloads/syntheticeyes_drafts/right_preview_v2.mp4` (new motion, fixed face
camera) and `left_split_preview.mp4` (face and eye side by side).** Both Cycles preview, 768 px
per pane brought to 1024, 32 spp.

Code (`wrapper/eyes.py`; `scene.blend`, `build_scene.py`, `wrapper/gaze/`, textures untouched):
- `--camera split` (videos only): two passes over the same baked Timeline, `cam_video` into
  `outputs/frames/<input>/face/` and `cam_move_eye` (subject's left eye, 15 cm, on the head bone,
  `eye` look, focus 0.15 m f/45, as saved in the scene) into `.../eye/`; each pane brought to
  1024x1024 and joined into one 2048x1024 frame in `.../video/`, no divider or text. `--frames`
  with split writes `face_####`, `eye_####` and the joined `####.png` to `.../split_stills/`.
  Rejected for stills like `move`. `encode_mp4` unchanged (takes the size from the first frame).
- `--resume` (videos only): keeps `outputs/frames/<input>/`, deletes the newest PNG in each pane
  folder, renders with `use_overwrite = False` so Blender skips existing frames, rebuilds
  `video/` and the MP4. Without it a run deletes the folder as before. The pass log now says how
  many frames were rendered and how many kept, and s/frame counts only the rendered ones.
- Default behaviour unchanged: `--input X` without `--camera` films `cam_video` alone at 1024.
- README flag table and the module docstring cover both flags.

Checked:
- Resume: draft split `--limit 20` killed with 20 face and 6 eye frames on disk; rerun with
  `--resume` dropped face 0020 and eye 0006, re-rendered 1 face and 15 eye frames, left 19 + 5
  frames with their original modification time, 20/20/20 frames, 2048x1024 MP4 encoded.
- Draft `left` split, `--limit 60`, frames 1, 34, 45, 60 plus split stills 84 and 86: both panes
  show the same instant (mid-saccade at 34, head turned at 45 and 60, eye open at 84 and shut at
  86 in both), the eye stays framed through the head turn, nothing cropped or stretched.
- The preview `left` split: 12-frame sheet and frames 123 and 172 at true aspect: same as the draft.
- The preview `right`: 12-frame sheet; glance to image-right with the head taking about half,
  hold, back to the viewer by frame 172, face in frame throughout.
- `tools/validate.py` only checks video duration and size, never width: no change needed;
  `left.mp4` (2048 wide) passes. Unit tests 46 OK; validate fails only the two known TODO checks.

**`right` in the eye pane:** `cam_move_eye` sits 24 deg to the nose side and in `right` this eye
turns toward the temple. Largest eye-in-head angle with the lids open is frame 35 (eye yaw
23.7 deg, head 0.9 deg); largest total gaze is frame 122 (29.8 deg, 15.3 in the head). Cycles
preview stills of both (`outputs/frames/right/split_stills/`): the iris still reads. At frame
35 it is foreshortened into the outer corner, all of it visible, its edge touching the lower
lash line, with the pupil, iris fibres and corneal highlight clear and a wide wedge of sclera
on the nose side. Frame 122 is easier. Camera not changed.

Timings (Cycles Metal, preview 768 px, 32 spp, 270 frames):
| run | pane | s/frame |
|---|---|---|
| `right` | face (`cam_video`) | 9.62 |
| `left` split | face (`cam_video`) | 11.07 |
| `left` split | eye (`cam_move_eye`) | 13.01 |
The `left` split preview took 6580 s (1 h 50 min) in all. Final-quality estimate, scaling by
pixels (x1.78) and samples (x2 to 64 spp): about 39 s/frame for the face pane and 46 s/frame
for the eye pane, so a split final of one 9 s video is about 6.4 h at 64 spp (twice that at the
scene's 128). Estimate only; no final was rendered.

Not done: no final-quality render; `generate` not filmed in split; nothing pushed.
`outputs/videos/left.mp4` is now the split preview and `right.mp4` the new preview.

### Sun 15 Nov 2026 — M12: the ear of tex_09, trial built, reviewed and adopted (Opus)
**Review sheet: `outputs/tmp/m12/review.png`.** Row a: bare head, plain material, the
subject's left ear before | after, plus a 2x zoom. Row b: lit scene, `--input left` frames 110
and 150, 64 spp, CPU, ear cropped at 1:1, before | after. Row c: tex_01 and tex_03 as shipped.
Trial set: `outputs/tmp/m12/sets/tex_09/`; its intermediates are in `outputs/tmp/m12/work/`.

**Adopted later the same day, once no Blender render was running** (the trial waited out another
session's `--input generate --quality preview` render):
- `textures/` matched `md5_before.txt` before the copy. After it, `diffcheck.py` gives 0 changed
  texels against the trial, and the md5 diff shows only the 4 tex_09 skin files (normal
  `2eeab7cd…`, rough `611b3ee6…`, albedo and `legacy/skin.png` `59ca7a6e…`). `set.json` is
  untouched.
- `scene.blend` rebuilt (solve_lids + build_scene, `id_male_white_9`): `lids.npz` is unchanged
  (`7d45359c…`) and `scene.blend` is now `e29eddb9…`. Every object's vertex and point positions
  (head, brows grown and carried, lashes, vellus, tear lines, guards) hash the same as before
  (`outputs/tmp/m12/geomhash.py`), so the brows did not move. **The three videos show the
  old ear until they are rerendered from this scene.**
- `preview.png` and `outputs/stills/texture_sheet.png` rerendered. Changes are in the ears
  only: 5,902 px in the front view, 17,187 px in the three-quarter view, inside the ear's
  bounding box.
- `outputs/stills/tex_09.png`: both ears are in frame, so it was rerendered
  (`render_stills.py --sets 09`, which also rebuilt `outputs/tmp/m3/scenes/male_white_9.blend`
  because a dependency was newer). 34,622 px changed by more than 2, all in the ear columns
  (x < 120 or x ≥ 900). The face between is max 1. Ear crops before | after:
  `outputs/tmp/m12/cmp_still_ears.png`. The eye still changed by at most 1 (noise), so the
  committed one was restored, and `eye/sheet.png` was rebuilt with `--sheet-only`.
- Before | after previews: `outputs/tmp/m12/cmp_front.png`, `cmp_tq.png`. Old copies are in
  `outputs/tmp/m12/prev_before/`.

Code (committed, gated per set, off by default):
- Colour: `tools/skin_fix.py`, new fix key `ears`. It goes there because that is where a baked
  albedo gets corrected, with the mesh-space masks and `harmonic_fill`, and it needs no Blender
  re-bake (in `bake_scan.py` it would). The ear's tone at 3 mm and coarser is replaced by a
  harmonic fill from the skin around the ear, so the join has no border. From 6 mm inside the
  ear's root (geodesic over the ear) the fill's chroma gives way to the median hue of the parotid
  and temple on that side. The rim of the helix (the farthest part from the root) and the lobe
  (the lowest quarter) get a small log shift (+0.03, -0.07, -0.06). Anything finer than 3 mm stays.
  The ear's luminance is filled as well, because the smear carried the photo's shadow in the
  concha. With only the chroma swapped, the concha read grey-brown.
- Relief and roughness: `tools/detail_maps.py --ear-skin` with `EAR_SKIN` (pores 3.0/mm2,
  sigma 0.035 mm, depth 0.5; furrows 2.0x, from the same noise field as the rest of the face;
  roughness 0.53). This is blended in last, from its own random stream (`[seed, 12]`), so the main
  stream and every texel outside the ear are unchanged.
- Shared mask: `detail_maps.ear_weight` = GNM's `ears` group, full weight about 2 mm past it,
  half at about 5 mm, exactly 0 from about 13 mm.
- Recipe: 09 gets `fix=dict(ears=1.0)` and `"ear_skin": 1.0` in `detail`. Sets 01 to 08 are
  untouched. Checked: tex_01 rebuilt with the new code gives byte-identical normal, roughness and
  albedo, and the tex_09 baseline before the change was byte-identical too.
- `tools/check_detail.py`: new shot `wrap_ear_l` (bare head, camera beside the left cheek).

Measured, trial against shipped tex_09 (left ear group / reference):
| | shipped ear | trial ear | reference |
|---|---|---|---|
| chroma r-g / g-b (log) | 0.655 / 0.297 (yellow-orange) | 0.565 / 0.179 | parotid 0.539 / 0.073, temple 0.559 / 0.158 |
| mean normal tilt | 1.90 deg | 4.07 deg | cheek 5.35, forehead 4.10, temple 3.72 |
| roughness median | 0.494 | 0.541 | cheek 0.545, parotid 0.525 |

Changed texels (difference mask, trial against shipped):
| map | changed | right ear bbox (y, x) | left ear bbox (y, x) | outside ear weight |
|---|---|---|---|---|
| skin.1001.png (and legacy/skin.png, identical) | 711,370 | 1199-2055, 553-1098 | 1200-2057, 3001-3540 | 0 |
| skin_normal.1001.png | 752,456 | 1147-2086, 528-1150 | 1146-2086, 2946-3566 | 55, all within 1 texel (finite differences) |
| skin_rough.1001.png (2048) | 178,628 | 574-1040, 265-572 | 575-1039, 1476-1782 | 1, within 1 texel (2x2 downsample) |
Eye tiles and their legacy copies: 0 changed. Both ears change, since the mask is symmetric. The
ear lies inside the main UV island, so there is no padding or seam at its edge. The check script
is `outputs/tmp/m12/diffcheck.py SHIPPED_DIR TRIAL_DIR`.

**Looked at**: UV crops of albedo, normal and roughness before | after at each step (three colour
trials: the plain harmonic fill went grey-beige, chroma only left the concha grey-brown, the third
kept); the normal map at 1:1, ear against cheek; bare-head ear and three-quarter before | after;
the lit frames; the review sheet, all rows.
- Bare head: the orange concha is gone. The ear has the hue of the skin in front of it, fine
  texture, no wet sheen, and no visible join. The rim and lobe are only slightly pinker.
- Lit scene: the orange-yellow glow is gone. The concha is a warm red-brown where light passes
  through it (subsurface), not yellow, and the wet highlight on the lower ear is gone. **The ear
  does not glow after the texture fix**, so the skin shader needs no change.

**tex_01 and tex_03 as shipped** (row c, not fixed): same flat, glossy ear. Mean tilt on the ear
1.92 / 2.11 deg against the cheek's 3.47 / 5.40; roughness 0.447 / 0.455 against the cheek's
0.549 / 0.541. Colour is not the problem there: 03 matches its parotid; 01 is a little more orange
(r-g 0.65 against 0.54). 03 also has dark shading painted into the concha (MakeHuman source) and
a visible sheen on the helix. 01 has a small red-brown mark at the top of the ear root. Using
`"ear_skin": 1.0` alone (relief and roughness, no colour fix) would likely suit both; the owner's
call.

**Adoption, to run when `pgrep -fl "Blender -b"` shows nothing** (all checked except where noted):
```
cp outputs/tmp/m12/sets/tex_09/{skin.1001.png,skin_normal.1001.png,skin_rough.1001.png} textures/tex_09/
cp outputs/tmp/m12/sets/tex_09/legacy/skin.png textures/tex_09/legacy/skin.png
python3 outputs/tmp/m12/diffcheck.py outputs/tmp/m12/sets/tex_09 textures/tex_09   # expect 0 everywhere
md5 textures/tex_*/*.png textures/tex_*/legacy/*.png textures/tex_*/set.json | diff - outputs/tmp/m12/md5_before.txt   # only the 4 tex_09 skin files
python3 tools/solve_lids.py && $BLENDER -b --factory-startup -P tools/build_scene.py -- --npz assets/gnm/id_male_white_9.npz
python3 -c "import sys; sys.path.insert(0, 'tools'); import build_textures as b; b.check('09', 'wrap_front,wrap_three_quarter')"   # preview.png + the two sheet views (not run)
python3 tools/build_textures.py --sheet-only                                    # outputs/stills/texture_sheet.png (not run)
```
(Not `build_textures.py --sets 09 ...`: every mode of it rewrites set.json, see below.)
- **Does the build read the changed maps? Yes.** `build_scene.grow_brows` loads
  `textures/tex_09/skin.1001.png` for the darkness map that places the grown brow strands. The
  ear change reaches the brow region of that map only at 4e-14 (rounding in `brows.box_blur`'s
  cumulative sums), so the brows should come out the same, but the scene must still be rebuilt.
  `lids.npz` md5 before: 7d45359c…, `scene.blend` 97fffcc8….
- `preview.png` and the contact sheet: the `check` line above renders front and three-quarter
  into `outputs/tmp/m2/sets/tex_09/` (what `--sheet-only` reads) and copies the front to
  `preview.png`. The three-quarter shows the ear, so the sheet does change. The tex_09 still in
  `outputs/stills/`: compare before | after with a pixel diff, rerender only if the ear is in frame.
- **set.json**: the brief allows only the skin maps to change, so it was not touched. Any
  `build_textures.py` run that writes set 09 (even `--eyes-only`) regenerates it from the recipe,
  which now records `skin_fix: {ears: 1.0}` and `ear_skin`, **and M11's new label for 09**. M11's
  stage 2 does that anyway.

**Checks**: `python -m unittest discover tests` gives 46 OK. `validate.py --blender` on the
current tree: only the two known TODO-line checks fail (README 4 lines, AI_DISCLOSURE 1 line).
After adoption: 46 OK, and `validate.py --blender` fails only the same two.

TECH_NOTES (Skin texture transfer) has an entry for the ear fix.
**Not done**: rerendering the three videos with the new ear (left to the session that owns
them). No change to the ears of tex_01 to tex_08, the skin shader or the README. Nothing pushed.
`outputs/tmp/m12` holds about 0.3 GB.

### Sun 15 Nov 2026, early — the owner watched the drafts: fixed camera, head and blink changes (Fable)
The owner watched the three drafts at playback speed for the first time and rejected them:
brows and lashes "glitchy", white dots round the eye, low quality, "random zoom in zoom out",
motion not realistic. What each one was, and what changed:

- **Glitchy hair, white dots: the draft renderer, not the scene.** `--quality draft` is EEVEE at
  512 px upscaled to 1024, with hair as flat strips and the cornea and tear line swapped for a
  Fresnel gloss. The strips shimmer from frame to frame and the gloss sparkles along the lid
  margin. Checked on Cycles frames of the same motion (four consecutive 64 spp frames across the
  gaze shift, and consecutive 768 px preview frames): hair holds still between frames, the lid
  margin is a smooth wet line, no dots. Drafts are for motion only; the README now says so.
- **New `--quality preview`**: the Cycles look at 768 px and 32 samples, 12 s/frame on the M4
  (about 55 min for a 9 s video), so a video can be judged before the long render. Nobody should
  judge the look on an EEVEE draft again.
- **Zooming: the camera move is no longer the default.** Videos are now filmed with the fixed
  `cam_video` (`--camera face`), retuned from 72 mm to 112 mm at 0.56 m: forehead to under the
  chin, 18 cm across, eyes about 3x larger than before, whole face in frame through the head
  turn (looked at 12 frames of a fixed-camera draft of `left`). `--camera move` still works.
  This reopens the M4 decision; reason: the owner, watching at speed, read the glides as zooming
  for no reason, and the rubric scores the eye, lid and brow motion, which a still frame shows best.
- **Motion** (`wrapper/gaze`):
  - `left`/`right`: the head takes half of the held glance (`GLANCE_HEAD = 0.5`, 13 to 16 deg,
    was 9 to 12), so the eyes lead and then sit about 13 deg in the head instead of holding
    17 to 18 deg off centre for four seconds.
  - The head no longer re-aims for a refixation under 9 deg (`head_min_shift`); it used to walk
    back and forth 3 deg during the hold.
  - No blink on the way out, so the gaze shift itself is seen. Blinks sit in the hold, on the
    way back and at the viewer, 2.0 to 2.5 s apart (were 3 inside 2.3 s). Forced blinks keep
    1.3 s apart (`blink_forced_gap`), spontaneous ones 1.6 s (`blink_min_gap`, was 0.9).
  - Three new tests (blink spacing, the first shift is not hidden by a blink, the head holds
    through a small refixation); 46 pass.
- `scene.blend` rebuilt (camera, new `generate` on the Timeline). `--check-directions` gives the
  same pupil shifts as before (13.8 to 14.2 px), `cam_face` and the rig are untouched, so
  `renders/` and `metadata.json` stand.

**Not done**
- The owner has not yet watched the new motion. A preview of `left` is the thing to watch
  first; `right` and `generate` previews after it.
- `outputs/videos/right.mp4` and `generate.mp4` are still the rejected drafts.
- Final videos: about 48 s/frame expected at 1024 px and 64 spp, so roughly 3.5 h each. Only
  after the owner accepts the previews.

### Sat 14 Nov 2026, night — M11 stage 1: labels, brows and brown irises on the bare head, trials only (Opus)
Stage 1 of 2: trials and a review sheet; nothing under `textures/` changed. **For the Fable
review: `outputs/tmp/m11/review.png`** (one row per changed set, before | after: bare-head front,
bare-head eye close-up, 1:1 albedo crop of the subject's right brow; plus a row with the rejected
06 alternative and the lit eye of 03 and 05) and **`outputs/tmp/m11/outlines.png`** (all 14
Mindfront outlines on the tex_01 skin: bare-head front over a 1:1 albedo crop, with areas).
Trial sets built by the real command are in `outputs/tmp/m11/sets/` (01, 05, 06, 08 complete;
02, 03 eye tiles and set.json only), their intermediates in `outputs/tmp/m11/work/`.

Code (committed): `tools/build_textures.py` (labels, recipes for 01/05/06/08, `--work`, `--cpu`,
`assemble_eyes` creates its folder), `tools/make_iris.py` (gated `radial` options, brown and
dark_brown palettes). **The recipes in the code are now ahead of `textures/` until stage 2 runs.**
To reject an item, put back the old values listed below.

**1. Labels** (no gender, no ethnicity; age, skin tone, brows, iris). `identity` dicts unchanged.
| set | new label |
|---|---|
| 01 | young adult, light skin, brown brows, hazel eyes |
| 02 | young adult, medium brown skin, dark brown brows, dark brown eyes |
| 03 | middle-aged, dark brown skin, black brows, dark brown eyes |
| 04 | older adult, light skin, ash brows, blue eyes |
| 05 | young adult, light warm skin, black brows, brown eyes |
| 06 | older adult, deep brown skin, black brows, brown eyes |
| 07 | young adult, light freckled skin, auburn brows, green eyes |
| 08 | middle-aged, light skin, brown brows, grey eyes |
| 09 | adult, light skin with stubble, photographed skin, hazel eyes |

**2. Brows** (recipe changes only; `transfer_skin.py` not edited)
- Outline areas, both brows (mm2): 01 382, 02 358, 03 456, 04 470, 05 963, 06 676, 07 987,
  08 843, 09 570, 10 574, 11 761, 12 722, 13 895, 14 641. In range 600-900: 06, 08, 11, 12, 13, 14.
- **01: outline 01 -> 12** (722 mm2): upright hairs at the head, full body, a clean taper to a fine
  tail and a natural arch; 11 is bushier at the head, 13 ends blunt. Colour, opacity, width
  0.14, density 1.8, shadow 0.40 unchanged.
- **08: outline 01 -> 14** (641 mm2): flatter and a little lighter than 12, tapers to a point,
  suits a middle-aged face and keeps 01 and 08 apart. Rest of the recipe unchanged.
- **05**: outline 08 kept. color 0.014/0.011/0.009 -> 0.016/0.012/0.009, opacity 0.85 -> 0.72,
  width 0.12 -> 0.11, density 1.5 -> 1.4, shadow 0.35 -> 0.20. Three trials: opacity 0.6 / shadow
  0.15 and opacity 0.5 / shadow 0.10 read as hair but grey and sparse for black brows; this one
  keeps them black and drops the hard painted edge (the edge was mostly the follicle shadow).
- **06**: outline 01 and width 0.15 kept. color 0.010/0.007/0.006 -> 0.004/0.003/0.0025, opacity
  0.9 -> 1.0, shadow 0.45 -> 0.60, density 2.0 kept. Brow/skin linear luminance over one common
  footprint: 0.50 before, 0.45 after. The stronger trial (0.003, density 2.4, shadow 0.8) gets
  0.42 but its core is a solid black stroke at 1:1, the slab the M2 audit removed; it is the
  "06 ALTERNATIVE" row of the sheet, not in the recipe. Darker colour alone has a floor here:
  skin shows between hairs, and the plain material's grey sheen lifts the near-black brow.
- Check: the real command (`build_textures.py --sets 01 05 06 08 --out-root --work`) gave albedos
  byte-identical to the trial driver's, normal maps byte-identical to the shipped ones, and a
  trial with the unchanged 01 recipe gave `textures/tex_01/skin.1001.png` byte for byte.

**3. Brown irises** (02, 03 dark_brown; 05, 06 brown). Under the judges' plain material the
whole eye sits under a grey reflection of the world in the clear cornea: the pupil renders mid
grey and the old browns became flat grey-mauve discs. New `radial` options per palette (only
brown and dark_brown have them): stroma contrast x1.3, a lighter warm zone round the collarette
(gaussian at 0.40 of the iris width, sd 0.13, mix 0.4, following the fibres), limbal colour weight
0.7 -> 0.95 and limbal brightness 0.45 -> 0.32, darker stroma out to 0.16 round the pupil (x0.65 at
the edge). Palette colours more saturated and warmer (old and new values are in the code).
Every term is a function of the radius and the fibre noise, none of the angle: no highlight,
catchlight or one-sided shadow. Iris annulus, linear luminance mean / sd: dark_brown seed 3
0.0137 / 0.0067 -> 0.0184 / 0.0121; brown seed 5 0.0305 / 0.0139 -> 0.0384 / 0.0232.
A first, stronger candidate (+65-80 % mean) went orange and was dropped.
- `make_iris.py --color hazel --seed 9` is byte-identical to `textures/tex_09/eye.100{2,4}.png`
  (checked after both edits). Eye tiles of 01 and 08 rebuilt byte-identical.
- Bare head: the amber zone and darker rim show; the grey veil and grey pupil stay (the cornea,
  not the tile). Lit eye (`eye` look, identity scenes, Cycles GPU, no video render running at
  the time): 03 and 05 a little warmer in the middle with a darker rim, no glow.

**Looked at**: the 14-outline sheet and a 1:1 crop of the five candidates; every trial of 01, 05,
06, 08 (front and eye, before and after); the iris tiles at full size and at render size; the
bare-head eyes zoomed; the lit eyes zoomed; the final review sheet, all rows.

**Not sure about**
- **3D brow hair in `scene.blend` for --texture 01 / 08.** `scene.blend` carries strand brows for
  Mindfront 01, 05 and 08 only (`tools/carry_hair.py`, `build_hair` in `build_scene.py`), and
  `eyes.use_texture` picks one by the last two digits of `set.json`'s eyebrow source. With 12 and
  14, `eyes.py --texture 01` or `--texture 08` would show no 3D brow hair, only the painted brow
  (the videos use tex_09 and are not affected; the per-set stills grow their brows from the
  albedo and are fine). Options: (a) add 12 and 14 to `carry_hair.py` and to the `brows` list
  in `build_hair`, rerun `carry_hair.py`, rebuild `scene.blend`; (b) use outline 08 (843 mm2,
  already carried) for 01 and 08 instead, at the cost of its blunt tail; (c) accept it. Reviewer's
  call; not tried.
- 06 is only a little better at face distance; the sheen floor above limits what the albedo can do.
- 01 with outline 12 is a fairly full brow on a pale skin; density 1.8 was set to fill the thin
  outline and was not lowered.
- The amber ring of the irises is subtle on the bare head; a stronger one went orange.

**Not done**: nothing in `textures/`, no stills, no sheets, no README, no TECH_NOTES (the iris
`radial` options belong under the iris notes in stage 2). `transfer_skin.py` untouched.

**Other sessions' edits in the working tree, not mine and not committed**: `scene.blend`,
`wrapper/eyes.py`, `wrapper/gaze/behaviours.py`, `wrapper/gaze/engine.py` and
`tools/build_scene.py` (video camera lens 72 -> 112 mm) changed between 20:25 and 20:28, after my
md5 baseline (20:17); that session ran out of usage. Its draft `--input left` render ran during
this session; my check renders were moved to `--cpu` while it ran. `textures/`, `renders/`,
`metadata.json` are byte-identical to the baseline (`outputs/tmp/m11/md5_{before,after}.txt`).
Disk: 3.9 GB free at the end; `outputs/tmp/m11` is 1.5 GB and can go after stage 2.

**Stage 2 commands** (check `pgrep -fl Blender` first; add `--cpu` to `build_textures.py` if a
video render is running, and do not run `render_stills.py` until it has finished)
```
python3 tools/build_textures.py --sets 01 05 06 08                  # bake, maps, irises, set.json, checks
python3 tools/build_textures.py --sets 02 03 --eyes-only            # new irises, set.json, preview
python3 tools/build_textures.py --sets 04 07 09 --eyes-only --skip-check   # new labels in set.json only
python3 tools/build_textures.py --sheet-only                        # outputs/stills/texture_sheet.png
python3 tools/render_stills.py --sets 01 02 03 05 06 08             # then: python3 tools/render_stills.py --sheet-only
```
- The `--eyes-only` run of 04, 07, 09 rewrites their eye tiles byte-identical (their palettes
  have no `radial`) and their `set.json` with the new label: that changes `textures/tex_09/set.json`.
- `render_stills.py` rebuilds every identity scene whose `build_scene.py` is older, which the
  other session's uncommitted edit triggers. Changing to 12/14 also moves the grown 3D brow hair
  in the stills of 01 and 08 (`tools/brows.py` roots on the painted darkness).
- README texture table: put in the nine labels above. Expected in the history: about 92 MB of
  new albedos (01, 05, 08 about 26 MB each, 06 13 MB; the legacy copy is the same blob) and
  8 eye tiles of about 2 MB.

### Sat 14 Nov 2026, night — readiness check before the final videos (Fable)
Read every doc, ran the checks, looked at the committed images, and ran the evaluator commands on
a copy holding only the tracked files of `763d9c7` (copy-on-write, in a scratch folder, removed
afterwards). No code, texture, render or `scene.blend` changed.

**Passes**
- 43 unit tests; `tools/validate.py --blender` passes all but the two TODO checks (README 4
  lines, AI_DISCLOSURE 1).
- Tracked files only, Blender 4.5.1: `scene.blend` opens with every image path relative and
  found (HDRI packed), no libraries; Timeline 1-321 at 30 fps with actions on the rig (16
  F-curves), the head's shape keys (17) and `cam_move` (7). `--move 1 0 --texture 03 --quality
  draft --out` renders the tex_03 skin on the scene head. `--input left --quality draft` wrote a
  9.00 s `left.mp4` in 234 s (0.87 s/frame). So a fresh clone runs with nothing from
  `assets/gnm/*.npz` or `tools/`.
- Looked at: both sheets, tex_09 and tex_01 stills, tex_09 eye, clockwise frame 0, the 64 spp
  frames 45 and 150 of `left`, and a 16-frame sheet plus a saccade and blink strip of the fresh
  draft. Nothing broken: both eyes in frame through the turn, lids close fully, no roll.

**Blocks the final videos**
- **Disk: 0.9 GB free** on the Mac (the first try at a real clone filled it). The finals write
  about 860 PNGs of 1.1-1.3 MB, and macOS needs room of its own. `outputs/tmp/` is 4.3 GB of
  working sheets (git-ignored), `outputs/frames/` 0.9 GB of old draft frames. Owner's call.
- **A video run cannot resume**: `eyes.py --input` deletes `outputs/frames/<mode>/` and starts
  from frame 1, so a sleep or a full disk two hours in loses that video. Run the three as
  separate commands under `caffeinate -i`.
- Still nobody has watched the drafts at playback speed. The motion and camera code have not
  changed since the drafts in `outputs/videos/` (13:46), only the look, so those show the final
  motion. 30 s of watching before 6.4 h of rendering.

**Not ready, none of it code**: final videos; deck `CollegeName_TeamName.pdf`; demo video and
its link; team and college name; names in `AI_DISCLOSURE.md`; `LICENSE` and the README line;
commit `outputs/videos/`; zip and `validate.py --zip`. Docker on native x86_64 still untested.

**Opinion, as a judge**: the tex_09 eye close-up and the 64 spp video frames are the strongest
things here. Weakest for the 60 texture points, in the bare-head sheet the judges will
reproduce: 01, 02, 06 and 08 are labelled women and sit on heads that read as men; brows on 01,
05 and 08 are thin drawn arcs; irises go flat without our cornea. The `face` framing of the
videos shows the bust on black with the eyes about 60 px wide; the motion reads in the other
two framings.

### Sat 14 Nov 2026, evening — M7 review against "Eye Piece": dark hair shading, tidier brows, dimmer eye lamps (Fable)
Judged the five M7 steps against the reference at 0:11 and 0:14 (looked at again in the browser
pane, full frame and a crop of the eye) on tex_09, tex_03 and tex_06, and tuned the numbers that
fell short. No new systems. Code: `tools/build_scene.py`, `tools/brows.py`, `tools/lashes.py`;
recipe in `docs/TECH_NOTES.md`. `scene.blend`, the nine stills and eye stills, the sheet and
`renders/` regenerated on the rebuilt textures of `8791849`; `metadata.json` and
`outputs/direction_check.json` byte-identical. Working sheets in `outputs/tmp/m8/` (not committed).
**Final videos not rendered, drafts not rerendered.**

**Verdict per step**
1. **Grown brows: closer in shape, wrong in shading, now fixed.** The tail read straw on 09 and
   grey felt on 03 / 06. Cause, tested on 03: a pure black fibre colour rendered the same grey,
   and only a lower IOR took it off, so it is the hard key reflecting off the fibre surface, which
   Principled Hair (Chiang) does not tie to the colour and has no weight for. Roughness alone
   (0.2 to 0.6) and thicker strands alone did not help. Now IOR 1.2 (`DARK_HAIR_IOR`), roughness
   0.25, random roughness 0.15, for grown and carried brows. On 09 the straw was also the fibre
   colour letting the key through: `BROW_GROWN_COLOUR` (0.05, 0.032, 0.02) → (0.020, 0.013, 0.008).
   Strands 35 → 8 um became 45 → 14 um (the tips were under a third of a pixel and blended into
   the lit skin). Direction: scatter 12 → 8 deg, strays 1 in 15 up to 30 deg → 1 in 25 up to
   20 deg, end hairs 4-6 → 3.5-5 mm; the tail was tangled wool, now it lies along the arch.
   Density unchanged (549 + 560 on every head, also on the repainted brows of 04 and 07).
   IOR 1.2 is not hair's real 1.55: it is a look choice, written up in TECH_NOTES.
2. **Lashes: clumps kept, colour and highlight changed.** They read as a pale brown fringe (09)
   and frosty (03 / 06 lower outer); the reference has dark spikes with small glints. Same cause
   as the brows. Now colour (0.03, 0.02, 0.013) → (0.015, 0.010, 0.0065), roughness 0.25 → 0.15,
   IOR 1.2. Clump pull 60-80 % → 75-95 % so clumps close into spikes, upper length 10 → 9 mm
   (false-lash look on the male heads), tip 6 → 8 um. Taking the lashes out of the rim was tried
   and made little difference once the IOR was down; they stay lit by it. `check_lids` on the new
   `scene.blend`: lash past-root depth in the globe 0.017 / 0.025 mm, as before (not zero).
3. **Shadows: kept as they are.** Fill 0.4 W warm: at 0.25 W tex_06's shadow cheek goes again;
   cool against warm hardly shows in the eye shot and warm is what the reference has. Contrast
   "AgX - Medium High Contrast": "None" is flat, "High" crushes tex_06's socket to black.
   Subsurface (1.0, 0.30, 0.15) × 2.0 mm against the old (1.0, 0.35, 0.18) × 1.6 mm: mean
   difference 0.3 / 255, I cannot tell them apart. Kept, but it is not doing visible work.
4. **Sclera strip: kept, weaker.** The reference has the same tall window on the temple side of
   the cornea. At strength 4 it crossed the dark irises of 03 / 06 as a hard white bar as bright
   as the catchlight: now 2.5. Fine hair 1.0-3.5 mm: kept.
5. **Outside the handover list, changed:** iris spots 3.0 → 1.5 W (my own number from the `eye`
   look entry). On 03 and 06 the whites were the brightest thing in frame and glowed out of the
   shadow side of the face; 2.0 and 1.2 W were both rendered, 1.5 sits between them and was
   looked at in the final stills only. The 09 iris is a little duller for it.

**Denoising (step 5): no change to the denoiser and no more depth.** The 256-sample crop misled:
most of what it shows as pores in the raw half is sampling grain. Test: the cheek under the tex_09
eye, 399 px square, against a 2048-sample render with no denoiser and no adaptive sampling
(`outputs/tmp/m8/denoise/sheet_0.png`, `sheet_1.png`). RMS error on a 0-255 scale:

| | 64 spp | 128 | 256 |
|---|---|---|---|
| no denoiser | 12.4 | | 6.6 |
| OIDN as now (albedo + normal, prefilter accurate) | 3.8 | 3.4 | 3.1 |
| OIDN prefilter fast / none / colour only, 64 spp | 4.1 / 4.3 / 4.3 | | |

The 2048-sample patch is itself smooth with faint pores: that cheek is lit by the fill and the
subsurface, and the sparkle lives in the coat, which needs the key. Micro-relief ×2 and ×3 changed
nothing there through the denoiser. Cost, eye still at 64 spp: 26.0 s with the denoiser, 23.4 s
without, so it is 2.6 s a frame, about 0.6 h of the 6.4 h for three videos. Matching it without a
denoiser needs about 685 spp (error falls with the square root of the count), near 10 times the
render time; 256 spp raw is about 3.3 times the time and still worse. Prefilter none keeps a
touch more of the faint pores and saves 2.5 s a frame, but the render seed is fixed, so what it
lets through would sit still on the screen while the face moves. Not tested in motion, not used.
Measured on one patch of one head in a still pose.

**Rerendered and looked at**: nine stills on their own heads (875 s) and the sheet; 03, 06, 09 eye
stills at full size, 01 / 04 / 05 / 07 as crops; clockwise frame 0 before / after (226 s, about
10,000 px differ per frame, mean level 82.4, was 82.6); direction check (unchanged); `left`
frames 45 / 150 / 245 at 64 spp: 34.3 / 15.5 / 28.4 s, so the three videos stay at about **6.4 h**.
**Checks**: 43 unit tests pass; `tools/validate.py --blender $BLENDER` passes all but the two
"no TODO left" lines (README 4, AI_DISCLOSURE 1), not from this session.

**Left**
- Final videos (owner). Nobody has watched the new look in motion; the drafts in
  `outputs/videos/` are from before this pass.
- 04's brow tail is still a little ashy and 07's is ginger straw: both are the set's own brow
  colour (grey-brown, red), not the reflection. Not changed.
- The whites of 03 are still bright next to the skin at 1.5 W.
- The stills committed in `8791849` were rendered while this session's edits were half done;
  the ones committed now replace them.

### Sat 14 Nov 2026 — brows and skin detail of sets 01-08 (Opus)
**Superseded for the shipped sets.** This was done on the sets as of `f88a962`. When it was merged,
`main` already had the bare-head rebuild (`8791849`, entry below: grown painted brows, scalp cap,
eye area, lips, the back-of-head seam). The rebuilt sets were kept and these refined files were
dropped; `tools/refine_skin.py` is kept as an opt-in tool, not called by `build_textures.py`.
Before using it on the new sets: `tools/brows.py` roots the 3D brow hairs on the darkness of the
painted brow, so the refinement also moves those hairs; rebuild `scene.blend` and look. The
numbers below are for the old sets.

New `tools/refine_skin.py`, run on the shipped files (no Blender, GNM or source skins needed);
`tools/build_textures.py` calls it after assembling a set, so a rebuild reproduces it. Sets 01-08
rewritten (albedo, legacy albedo, normal, roughness, set.json); `tex_09` untouched.

**Brows.** Before: opaque drawn strands on untouched skin, a hard outline, crossed strands at the
tails of 03 and 05, a solid block at each head. Now: the brow is found by darkness, the skin under
it is inpainted and each texel unmixed into skin + hair; rebuilt with a soft pigment and shadow
under-layer, per-strand coverage and shade (noise smeared along the hair flow), crossing strands
thinned, the head faded to 55 % coverage over 70 px, 80 fine stray hairs per brow growing out of
the edge, strand relief in the normal map, roughness up to +0.10 under the brow. The residual of
the unmixing goes back in, so the pores between hairs stay.
Bugs found by looking and fixed: a pale streak along the dense core (coherence is meaningless
where there are no edges), and a pale block under the brow head on the dark sets (the socket's
shadow was read as faint hair; hair now has to be line-like or very dark).

**Skin.** Measured on cheeks and forehead, the light sets had 1.05-1.14 % rms of fine detail
(log-luminance band at 1.5 px) against 1.6 % on the scan, and 1.7-2.6 % mid detail (1.5-6 px)
against 3.7 %. The two bands are raised by a per-set gain, capped at 1.45 / 1.6, soft-limited,
chroma kept, brows excluded. After: fine 1.38-1.46 %, mid 2.30-2.70 %. 03 and 06 already sit at
the scan's level and get gain 1.0. This amplifies detail that is there; it cannot make the soft
MakeHuman sources sharp, and pushing further brought out blotches rather than pores.

**Checked:** before/after crops of every set's brows, brow heads at 4x, lips and nostrils (no
halos), the whole map, the brow normal lit from the side; `legacy/skin.png` byte-identical to
`skin.1001.png`; a second run is skipped (`refine` in set.json). Unit tests 43 pass.

**Not done / stale:** nothing was rendered. `preview.png` in each set, `outputs/stills/` and
`texture_sheet.png` still show the old brows: rerun `tools/build_textures.py --sheet-only` after
the wrap checks, and `tools/render_stills.py`. The 3D brow hair in `scene.blend` is separate and
unchanged, so our own stills change less than a judge's bare-head wrap. Repo size: committing
these eight sets adds about 380 MB to the history (measured; the legacy albedo is the same blob).

### Sat 14 Nov 2026 — audit against the evaluation deck and the organisers' GitHub checklist (Fable)
Written against `f88a962`. Since then `main` rebuilt `scene.blend` and rerendered `renders/`
(`7156ec7`, 13:47), rebuilt the nine texture sets and rerendered the stills (`8791849`, 16:55), so
"Stale outputs" and the texture observations below describe that older state. `metadata.json`
and `outputs/direction_check.json` were last changed in `110c5f6` (05:31), before that rebuild.

Done on a Windows machine with no Blender, so nothing was rendered and `scene.blend` was not
opened (it is zstd-compressed and could not be read as text either). `tools/validate.py` was not
run. Everything below was read from the files or computed with numpy.

**Missing from the checklist** (Submission Package, Source Code, Presentation, Video, AI
Disclosure, README, APK/SDK; now in `docs/REQUIREMENTS.md`, section C)
- Presentation: no deck in the repo.
- Video: no demo video or link, and `outputs/videos/` has never been committed, so the three
  rubric videos are missing too.
- AI disclosure: there was none. `AI_DISCLOSURE.md` is a draft written from `CLAUDE.md` and this
  log; it has a TODO for the team to add names and check it.
- No `LICENSE` file; the README still says the code licence is a TODO. Owner's choice.

**Stale outputs.** `scene.blend` was last committed 14 Nov 00:07 on the tex_09 identity.
`renders/` and `outputs/stills/` date from 13 Nov 22:10, `metadata.json` and
`outputs/direction_check.json` from 13 Nov 16:58, on the earlier head. A judge who runs
`--clockwise` gets other pixels and other pupil coordinates than the committed ones. Rerun all of
them from the final scene (the list under "Left, in order" in the entry below).

**Checked and correct**
- `metadata.json`: 10 records, every key of the PDF schema, theta, h = sin, v = cos exact;
  `camera_matrix` equals `K [R | t]` rebuilt from `camera_world_matrix` to 5e-4; K gives a 50 mm
  lens. Eye rotations recomputed from the stated geometry (target at (h, v) x 5 cm on a plane
  35 cm ahead, half IPD 30.8 mm from the vergence angle) agree with the file to 0.01 deg in all
  10 frames, both eyes. The pupil spacing puts the pupils 40.1 cm from the camera.
- `renders/`: 10 PNGs, 1024 x 1024. A dark-pixel centroid in each frame follows the metadata
  pupil (correlation 0.98 or better, both axes, both eyes) but sits 2 to 7 px higher, most likely
  the lash shadow in so crude a measure; it does not test pixel accuracy.
- Direction check: left and right +-14 px, up and down +-14 px on `cam_eyes`, reset back to
  0.00. On `cam_face` (the 10 renders) the same gaze moves the pupil +-6.6 px: right for the
  geometry, small to the eye.
- Textures: 9 sets, each skin 4096 x 4096, normal 4096 x 4096, roughness 2048 x 2048, two eye
  tiles 2048 x 2048; `legacy/` files byte-identical to the UDIM ones; left and right eye differ.
- Gaze engine, seeds 0 to 19: left and right 9.0 s, generate 10.4 to 11.1 s (limit 15 s); first
  large shift -25.6 to -28.8 deg for left, +24.9 to +28.6 for right; same seed gives identical
  arrays; saccade durations 24 / 30 / 41 / 54 / 68 / 99 ms at 2 / 5 / 10 / 15 / 20 / 30 deg
  against the 2.2 ms/deg + 21 ms line (25 / 32 / 43 / 54 / 65 / 87); blinks 190 to 250 ms above
  5 % closure, about 27 a minute counting the scripted and gaze-evoked ones.
- Dockerfile: the Blender 4.5.1 sha256 matches download.blender.org.

**Looked at, as a judge would** (opinion, from the committed stills)
- The eye close-ups are the strongest images: iris structure, lashes, tear line, sclera veins.
- `tex_09` reads as a real face. 01 to 08 read as CG: thin drawn brows on 01, 05 and 08; the
  01 albedo is soft at 1:1 (4096 px of file, less than that of detail); the sets labelled as
  women sit on heavy heads and 01 has stubble-like specks on the upper lip.
- No hard seam on any frontal still. No still shows the back of the head or behind the ears.
- The normal and roughness maps have streaked padding along the bottom and top edges, outside
  the face.

**Changed**
- `wrapper/device.py` (new), `wrapper/eyes.py`: Cycles picks the first GPU backend with a device,
  in the order OptiX, CUDA, HIP, oneAPI, Metal, else the CPU. Before, only Metal was tried, so a
  Windows or Linux machine rendered the final videos on the CPU. `tests/test_device.py` (5 tests,
  a stand-in for the Cycles preferences). **Not run in Blender**: run one `--move 0 0` on the
  M4 and check the log line still says Metal.
- `README.md`: the stale "textures are not in the repo" note is gone; a table of the nine sets
  from their `set.json`; `--cpu` row; Windows path; AI disclosure linked; "our own work" reworded.
  Four TODO lines left: team and college name, demo link and deck, the videos, the code licence.
- `tools/validate.py`: checks that `AI_DISCLOSURE.md` exists and has no TODO. Not run.
- `docs/REQUIREMENTS.md`: the GitHub checklist; `tex_09` in section D.
- Unit tests: 43 pass.

**Not verified**
- That `scene.blend` opens and plays the motion on the Timeline after the 14 Nov rebuild.
- The 18 Nov deadline: the evaluation deck says "Submission Due: Oct 28, 2026" and neither the PDF
  nor the organisers' mail is in the repo.
- The CC BY 3.0 licence of the head scan (the archive's page returned no content when fetched).
  Google's GNM repository is public and Apache-2.0; its README names neither "Head v3" nor the
  UDIM tiles.
- Peak saccade velocity runs high for mid-size shifts (446 deg/s at 10 deg); durations are on
  the published line and at 30 fps a 40 ms saccade is one frame, so it does not show.

### Sat 14 Nov 2026 — M2 bare-head audit of the nine sets: seam, brows, scalp cap, painted skin (Fable)
The sets were looked at the way the judges get them: `tools/check_detail.py --wrap` on the bare
template, plain Principled, neutral light, nothing of ours on it. Ten views per set (front,
three-quarter, both profiles, back, behind each ear, top, neck from behind, eye close-up; the last
five are new shots in `check_detail.py`), before and after, all looked at. Then the nine lit stills
and `outputs/stills/eye/sheet.png`. Code: `tools/detail_maps.py`, `tools/transfer_skin.py`,
`tools/build_textures.py`, `tools/check_detail.py`, new `tools/skin_fix.py`; `docs/TECH_NOTES.md`
(skin transfer). All nine sets rebuilt once (`skin.1001.png`, normal, roughness, `preview.png`,
`set.json`; eye tiles byte-identical), `outputs/stills/` and both sheets rerendered. `scene.blend`,
`renders/` and the videos were not touched. Build, lash, brow, vellus and wrapper code not edited.

Before / after: `outputs/tmp/m9/before_after.png` (all nine, front and eye), `outputs/tmp/m9/after/
sheet_NN.png` (per set, all ten views, before on top), `stills_face_before_after.png` and
`stills_eye_before_after.png` (the lit stills). Not committed (outputs/tmp).

**What read least real, worst first, and what was done**

1. **A seam down the back of the head** (the only UV seam on the skin: the midline from the crown
   to the neck base). On 03 and 06 a hard line through the highlight; on 02 and 04 the two halves
   of the nape shaded differently with a straight edge between them. Not the albedo (2 px either
   side of the seam the colour agrees within 3 %). It was the scanned relief: its high-pass (14 px)
   has one side only next to an island border and cannot remove a slope across it, which left
   +1.0 sd on one side of the seam and -1.2 sd on the other, a small cliff. `scan_relief` now uses
   narrower high-passes toward the border (7 and 3.5 px, generated grain alone on the last half
   millimetre). Two smaller errors fixed on the way: the height outside the islands was zero, so
   border texels sloped toward it; and normals were written with the v slope as the bitangent
   slope, while Blender's bitangent is at right angles to the tangent (the scalp unwrap is sheared
   about 17 degrees, opposite ways left and right). **Left:** a soft band about 3 mm wide with
   finer grain, visible on 03 and 06 only when the highlight sits on it.
   Hairline, behind the ears and nape: no UV seam there. What showed was the edge of the painted
   shaved-scalp cap (item 3). Neck base: the mesh ends there, nothing to fix.
2. **Brows** (02 to 06 a dark slab, 01 / 05 / 08 a few pen lines). `transfer_skin.py` no longer
   draws one stroke per modelled strand. The strands give the outline (382 mm2 for Mindfront 01,
   843 for 08, 963 for 05, both brows); inside it hairs are grown: upright at the inner end, up
   and out along the lower edge, down and out along the upper edge, flat in the tail, thinner
   toward the upper edge and both ends, about a texel wide, 1,225 to 2,554 per set. The wide soft
   shadow under the hair (the smudge) is gone; a 4 px follicle shade stays. Same place, same
   outline: nothing moved. Recipe changes: 01 and 08 width 0.14 / density 1.8, 05 opacity 0.85 /
   density 1.5, 06 width 0.15 / density 2.0, 07 density 1.4.
3. **The shaved-scalp cap** of the MakeHuman skins (01, 02, 04, 05, 07, 08): red-orange on the
   scalp, with an edge across the top of the forehead, behind the ears and round the nape, and the
   soft forehead patches on 02 and 04 where it is uneven. `skin_fix.py` `scalp` (0.75 on those six)
   pulls the cap's tone at 2 mm and coarser toward the tone of the skin round it, carried inward
   over the mesh from the forehead, temples and neck. Stubble dots stay (04 still reads as a
   shaved head). 03 and 06 keep their dark cropped hair, which reads as hair.
4. **Painted skin.** `skin_fix.py`, strengths per set in the recipe's `fix` (also in `set.json`):
   - tex_04: confirmed orange on the bare head, worst round the eyes. Tone saturation 0.82, hue -3
     degrees; `orbital` 0.6 evens the blotchy lower lid.
   - tex_03: two things. Crow's feet drawn in the colour (`delines` 0.8 fades thin dark lines
     round the eye, lash line kept), and long single grooves on the cheek in the **normal map**,
     which are the scan's sculpt strokes and were on every set. `detail_maps.py` turns the scan
     relief down where one direction carries the local slope (structure tensor, cheeks and nose
     only; forehead and neck lines kept). Gone in the lit stills of 01, 03, 05, 07, 08.
   - Lips (`lips`): the light sets had lips the colour of the skin. Redder, darker toward the line
     between the lips, fine vertical streaks and soft blotches. 0.8 to 0.9 on 01, 05, 08.
   - Redness at the nose wings, lower lid rim and inner corner (`flush`), 0.4 to 0.8.
   tex_09: colour untouched (`skin.1001.png` byte-identical); only its normal and roughness maps
   changed (seam, cheek grooves).

**Stills** (`tools/render_stills.py`, all nine, scenes rebuilt by it): looked at as grids and 04 at
full size. The grown brow strands still sit on the repainted brows on all nine. On 04 and 07 the
strands come out thinner than before, as the paint under them is lighter now and `tools/brows.py`
roots by darkness (0.10 to 0.30, chosen on the slab paint). Not changed here: for the look session.
The stills were rendered with the working tree's uncommitted `build_scene.py`, `lashes.py` and
`brows.py` of the other sessions; the tex_09 brow strands are darker than in the committed still.

**Checks**: `tools/validate.py` passes all but "README: no TODO left" (5 lines), as before; 38 unit
tests pass. Trial build and final build of every set are byte-identical (md5 of albedo and normal).
`textures/` is 659 MB (was 554): the corrected albedos compress less; largest file 24.6 MB.
`python3 tools/build_textures.py --out-root DIR` now builds trial sets without touching `textures/`.

**Still reads as CG on the bare head**
- Irises: flat grey-brown discs on 02, 03, 05, 06 under plain light (no cornea in the judges'
  material); the eye tiles were not part of this pass.
- 03: an ashy patch on the inner lower lid is fainter but there; dark lines outside the orbital
  region (toward the temple) were not faded.
- 04: cheeks are blotchy red rather than orange; plausible for the age, the reddest set.
- 01 and 08: jaw and chin still slightly grey-green; brows thin by design (thin arched outline).
- 06: brows low in contrast against the skin.
- 09: a pale dash 1 cm long on the back of the head, in the scan's colour, near the seam; ears
  yellowish inside. Not touched (photographed skin).
- Lips are smooth in colour next to real lips; the relief carries the creases.
- Back of 03 / 06: the soft band of item 1.

**Evening follow-up: the teammate's audit checked on the rebuilt sets, `refine_skin.py` removed**
Code: `tools/detail_maps.py` (`--grain`, `--stubble`), `tools/skin_fix.py`, `tools/tex_core.py`
(`fill_smooth`), `tools/build_textures.py` (recipes), `tools/check_detail.py` (`cheek` shot);
`tools/refine_skin.py` deleted. Rebuilt once: the albedo of 01 to 08, and the normal and roughness
maps of 01, 02, 06, 08. Untouched and byte-identical: all of tex_09, the normal and roughness maps
of 03, 04, 05, 07, every eye tile. Stills of 01 to 08 and both sheets rerendered. Labels, skin
sources and iris colours did not change, so the README table stands.

The four findings of the audit entry above (made on the sets before the rebuild):
- **01 to 08 read as CG next to 09.** Narrowed by the rebuild (brows, scalp cap, eye area, lips,
  04's colour) and by the two items below; not closed. What still reads as CG is listed under
  "Still reads as CG" above, less the stubble.
- **The 01 albedo is soft at 1:1.** Confirmed on the rebuilt sets, on all six light skins: a blur
  with a few dark specks. Fine band (1.5 px) of log-luminance on cheeks and forehead 1.04-1.14 %
  against 1.76 % on 09. **Fixed** in `detail_maps.py`: the two finest bands of the height map go
  into the colour detail (valleys darker and a little redder, ridges lighter), and the pore specks
  are taken to 0.6 on those six. After: 01 1.62, 02 1.65, 04 1.70, 05 1.64, 07 1.68, 08 1.62 %
  (03 and 06 unchanged at 1.71 %, grain 0). Looked at 1:1 against 09 (cheek, forehead) and on the
  bare head (front, cheek, lips, eye; front, three-quarter, profile and back of all eight): fine
  stipple, no blotches, nothing visible at face distance.
- **Stubble-like specks on the upper lip of 01.** Confirmed, and it is relief, not colour: the
  scan is a man's, and from under the nose down its relief is stubble follicles. Under the raking
  key the mouth, chin and jaw of 01, 02, 06 and 08 (made as women's skin) were covered in them.
  **Fixed**: `--stubble 0.3` on those four turns the scan relief down there, where it is coarser
  than elsewhere. Looked at in grey (lips, front) and in the four lit stills: gone. The strength
  of the grain and the pore tint is scaled on the relief before the cut, so those four sets get
  the same grain elsewhere as the others (the first build did not, and came out 15 % stronger).
- **Streaked padding in the normal and roughness maps.** Confirmed; it is the nearest-texel fill
  outside the UV islands, never sampled by a render. **Dismissed** for those two maps: rewriting
  nine normal maps for it is about 230 MB of history. The same streaks were in the albedos since
  the rebuild (my `skin_fix.py` used the same fill); those are smooth again (push-pull), as the
  albedo files were being rewritten anyway.

**`tools/refine_skin.py`: tried, not adopted, deleted** (with the skin-only mode added in
`6178c63`, which is the path tested here). Skin half only on tex_01 and tex_05, fine gain as
written, mid target 0.020: fine 1.04 → 1.40 %, mid 1.64 → 1.98 % on 01. On the bare head (front,
cheek, lips, eye) there is no visible difference; at 1:1 the cheek and forehead show the same
blur with the existing specks and a comb-shaped mark of the pore tint on the forehead a little
darker. It amplifies what is in the albedo, and there is nothing pore-sized in it. The relief
grain above does what it was meant to. Also a reason to remove it rather than leave it opt-in: on
the rebuilt sets its fine gain is 1.0 and its mid gain still about 1.4 (stale 0.026 target), which
is the blotch direction. The brow half was never run.

Also changed: lip streaks a third fainter (they read as bar lines at 1:1).
Checks: `tools/validate.py` fails only the two TODO checks (README, AI_DISCLOSURE; the owner's);
43 unit tests pass. A set without the stubble cut rebuilds byte-identical maps after the last code
change (05 compared). `textures/` is 699 MB; largest file 28.6 MB.
Before / after: `outputs/tmp/m10/` (`crop_final_01.png`, `crops_final_a.png`,
`grey_stubble_01.png`, `stills_mouth_before_after.png`, `wrap_final_a.png`, `wrap_final_b.png`).

### Sat 14 Nov 2026 — M7 eye close-up: grown brows, clumped lashes, deeper warmer shadows (Opus)
Closing the gap to "Eye Piece" (0:11, 0:14, 0:19 looked at: near-black shadow side, dense clumped
lashes with pale highlights, deep shadow under the brow) in brows, lashes and shadow depth.
Textures untouched; the `eye` look, the nose flag, the catchlight card and `tools/vellus.py` kept,
only the listed numbers changed. Code: new `tools/brows.py`; `tools/build_scene.py`,
`tools/lashes.py`, `tools/vellus.py`, `tools/check_lids.py`, `tools/render_stills.py` (brows.py is a
rebuild dependency), `wrapper/eyes.py` (`use_texture`, `apply_look`); docs in the shading recipe and
the `check_lids` line of CLAUDE.md. `scene.blend`, the nine stills and eye stills, the sheet and
`renders/` regenerated and committed; `metadata.json` and `outputs/direction_check.json` came out
byte-identical.

Method: baseline and every step = eye still (`cam_test_eye`) and face still (`cam_test_face`) of
tex_09, tex_03, tex_06 on their own heads, 1024², 128 spp, in `outputs/tmp/m7/<step>/`; each
sheet is previous | current, rows 09 / 03 / 06, columns eye, eye, face, face:
`outputs/tmp/m7/sheet_base_vs_step1.png`, `sheet_step1_vs_step2.png`, `sheet_step2_vs_step3.png`,
`sheet_step3_vs_step4.png` (not committed; outputs/tmp is ignored).

**1. Brows grown per head — kept.** `tools/brows.py` (pure numpy, bound to triangles like the
lashes, seed fixed). Roots inside GNM's left/right_brow_region where the set's albedo is darker
than the skin round it (`1 - L / skin level`, skin level = a ~6 mm blur of the luminance with the
dark pixels left out; no hair under 0.10, full weight at 0.30, roots drawn in proportion). 450-600
per brow (549 + 560 on these heads; 9,000-20,000 of 40,000 candidate roots fall on the paint),
6 points, 6-11 mm in the body, 4-6 at both ends, 35 → 8 um. Inner third 60 deg up and out, body
along the arch, rows leaning 20 deg toward the middle line, 12 deg scatter, 1 in 15 a stray up to
30 deg. 8-15 deg off the skin at the root, tip 0.3-0.8 mm up, each point laid on the plane of the
nearest skin vertex so the hair follows the brow ridge; crossing test from `tools/lashes.py`, a
crossing hair is lifted ×1.3 up to 12 times, else dropped (tex_09 left brow: 10 dropped, all tail
hairs that dive into the lid fold; none on 03 and 06). Colour `eyebrows.color_linear` from set.json,
else (0.05, 0.032, 0.02) (tex_09). The object is `brows_grown` with `brow_set` = the `--texture` the
scene is built with; `use_texture` shows it only for that set and the carried Mindfront brows for
any other. Result: the brow reads as strands sitting on the paint instead of a painted smear, on
all three heads and all nine stills.
Rim: tested with the rim reaching the grown brows (`outputs/tmp/m7/step1_rim/`): it greys the tail
further (tex_06's tail goes nearly white), so they stay in `keep_rim_off`.

**2. Lashes — kept.** Upper up to 10 mm, lower 80 lashes up to 6.5 mm, 60 → 6 um, clumps of 3-5
with tips pulled 60-80 % together, 1 in 10 alone; a lash the pull would push through the lid skin
keeps its own shape (8-28 per eye). `lash_hair` colour (0.03, 0.02, 0.013), roughness 0.25; the rim
lights the lashes again. They read as dark clumped strands with a pale highlight, as in the
reference. `tools/check_lids.py` now also measures the evaluated lash carrier past each root
(the root starts 0.15 mm under the margin skin by design): on `scene.blend`, deepest lash point
0.017 mm (L) / 0.025 mm (R) inside the globe, at gaze -12.5 / ±30 deg, lid 0.17-0.33 closed.
That is under half a lash radius and less than the lid skin's own 0.026 / 0.032 mm, but **not
zero**. With roots counted it is 0.05 / 0.06 mm (25 deg up, 30 deg side, lid 2/3 closed).

**3. Shadow depth and colour — kept, fill at 0.4 W, not 0.2.** Fill colour (1.0, 0.92, 0.85);
skin subsurface radius (1.0, 0.30, 0.15), scale 2.0 mm; `view_look` in `LOOKS`, set on each camera
(`look_view`) and applied by `apply_look`: "AgX - Medium High Contrast" for `eye`, "None" for
`face`. Eye shots: warmer skin, deeper shadow under the brow and round the eye. At 0.2 W
tex_06's face still went black on the shadow side (cheek and jaw lost against the backdrop);
0.3 W still lost the jaw; **0.4 W** (warm) reads (`outputs/tmp/m7/step3_fill/`). In the tex_09 eye
shot 0.2 and 0.4 W look the same: the contrast and the warmth do the work there.
Clockwise renders: `cam_face` gets look "None" (checked: after an `eye` camera, `apply_look(cam_face)`
puts it back); their mean level is unchanged (82.6-82.7 / 255), and they differ only round the
brows and lashes (about 9,000 px per frame) and through the subsurface change.

**4. Sclera strip and longer fine hair — kept.** `sheen_eye`, a second reflection-only card made by
`build_catch` (30 × 60 cm, 0.8 m, 70 deg temple side, 10 deg up, strength 4): a long soft
reflection on the temple side of the eye and along the tear line. `tools/vellus.py` LENGTH
1.0-3.5 mm: single pale hairs on the lit cheek and a fuzz on the silhouette, no white frost on
tex_03 or tex_06. Note the step-4 sheet's step-3 column has the fill at 0.2 W.

**5. Denoising, for the reviewer** (nothing changed): `outputs/tmp/m7/step5/cheek_denoise_vs_raw.png`,
tex_09 eye at 256 spp, the cheek under the eye at full size. OIDN smooths the fine relief there
into a waxy patch; raw keeps the pores with visible grain.

**Rebuild and cost.** `solve_lids.py` + `build_scene.py --npz assets/gnm/id_male_white_9.npz`.
Cycles 64 spp, `--input left --frames 45 150 245`: both eyes 34.0 s, face 15.4 s, eye 28.3 s
(check_lids was running on the CPU at the same time). Three videos about **2.0 + 2.0 + 2.4 =
6.4 h** (was 6.3), under 7.5 h.

**Checks**: 38 unit tests pass; directions unchanged (left -13.8 / -14.2 px, right +14.2 / +13.8,
up -14.0, down +14.0); `tools/validate.py --blender` passes all but "README: no TODO left"
(5 lines), as before. Nine stills rerendered and the sheet looked at (01 and 08 at full size too:
grown brows on every set). Clockwise set looked at (frame 0 before / after). Draft videos (EEVEE,
`outputs/videos/`, not committed) rerendered, 9.00 / 9.00 / 10.70 s; five frames of each looked at
across all three framings and a blink.

**For Fable**
- Step 1 grown brows: kept. `sheet_base_vs_step1.png`, `step1_rim/`. Unsure: the brow tail nearest
  the key reads ash-blond on tex_09 and grey on tex_06 (the key's highlight on the hair, not the
  rim); a darker colour or a rougher hair for the brows would fix it but was not on my list.
  Ten tex_09 tail hairs dropped. The darkness threshold (0.10-0.30) and the 6 mm skin blur were
  chosen by plotting tex_09, 03 and 06 only.
- Step 2 lashes: kept. `sheet_step1_vs_step2.png`. Unsure: the lower outer lashes on tex_03 and
  tex_06 go a little frosty under the key and rim; lash past-root depth in the globe 0.017 / 0.025
  mm, not zero (see above).
- Step 3 shadows: kept with the fill at 0.4 W instead of 0.2. `sheet_step2_vs_step3.png`,
  `step3_fill/`.
- Step 4 sclera strip and vellus 1.0-3.5 mm: kept. `sheet_step3_vs_step4.png`. The strip also shows
  as a tall bright window on the temple edge of the cornea in the eye close-up; looks wet to me,
  may be too strong.
- Step 5: `step5/cheek_denoise_vs_raw.png`, your call.
- Final videos not rendered.

### Sat 14 Nov 2026, early — the `eye` look: hard raking key on black, skin, fine facial hair (Fable)
The videos, the nine stills and the eye close-ups now share one look, after "Eye Piece": one hard
raking light on black. Code: `tools/build_scene.py`, `wrapper/eyes.py`, new `tools/vellus.py`;
docs in `tools/look_shots.py`, `tools/render_stills.py`, `CLAUDE.md`, `README.md` (build command,
`--frames`) and the shading recipe in `docs/TECH_NOTES.md`. `scene.blend`, the nine stills and eye
stills, `renders/`, `metadata.json` and `outputs/direction_check.json` regenerated and committed.
Textures untouched.

**0. Build.** `scene.blend` is built on the tex_09 identity, so the videos show the hero still's head:
`$BLENDER -b --factory-startup -P tools/build_scene.py -- --npz assets/gnm/id_male_white_9.npz`
(CLAUDE.md, README). It also carries the sway / partial-blink motion on the Timeline now.
On this head the both-eyes framing cut an eye in half in `right` (the outer lashes reach 6.1 cm
from the frame centre in the 12-13 deg turns; the frame was 11 cm, sized on the template), so
`MOVE_EYES` is 13 cm wide: it now shows the face from the lower forehead to the top lip, edge to
edge. The eye and face framings fit as they were. `metadata.json` and the direction-check pixels
changed because the head did; the shifts are as before (left -13.8 / -14.2 px, right +14.2 / +13.8,
up -14.0, down +14.0).

**1. The `eye` look** (`EYE_LIGHTS`, `LOOKS["eye"]`; every camera but `cam_face` uses it,
`cam_video` and `cam_test_face` included). The 13 Nov test numbers did not carry over as given:
- **key** at 88 / 42 deg left the whole globe in the shadow of the brow and orbital rim on this
  head. Now 78 deg to the temple side, 30 deg up, 5 cm disk, 0.5 m, warm, 3.0 W.
- **fill** 50 cm disk, cool, 60 deg nose side, 0.4 W, hidden from glossy rays (its reflection was
  the pale patch on the cornea and a sheen down the nose). HDRI 0.03, black.
- **catchlight**: a 6 x 10 cm card (`catch_eye`) whose material emits only into singular reflection
  rays, so only the cornea and the tear line see it and it lights nothing. As a glossy-only lamp
  it glazed the whole face (that was most of the "wet leather" skin). 30 deg temple side, 28 deg
  up: on the cornea in all three framings and through the head turns.
- **iris spots** `iris_eye.L/.R`: a 5.5 deg spot per eye, 3.0 W, diffuse only, on the head bone.
  Without them the iris is dull under a side key. An area lamp with a narrow spread blotched the
  skin at 64 spp; spots are clean.
- **flag** `flag_eye`: a scrim (stops 65 % of the key), shadow rays only, shaped as the nose's
  outline seen from the key. Its mesh rides on the head bone and a Geometry Nodes step pulls it
  toward the key, so it stays on the key-to-nose lines: looked at head turns of +-12 deg, the nose
  keeps its shade. Fully black it read as a dark wedge beside the nose in the face stills.
- **rim** `rim_eye`: strip behind the temple, 155 / 20 deg, 2.5 W, for the fuzz on the silhouette.
  Light linking keeps it off the brow hair and lashes (it turned the outer brow hairs grey).
- `apply_look` also switches objects that carry `look_prop` (flag, catch card).

**2. Skin** (`skin_textured`): normal strength 1.8 and subsurface 1.6 mm as in the test; roughness
x 1.0, not x 0.8 (x 0.8 read as an oily forehead under the hard key); nose roughness + 0.22 from a
new `nose` mask; and a thin sharp coat (0.18, roughness 0.2) that reflects off a procedural 0.5 mm
micro-relief in rest coordinates (Generated x bounding box, so it does not swim), none on the
nose. Looked at close (cheek, lid) and at face distance (forehead, cheek): pores show as relief
with a fine sparkle, no blobs.

**2b. Nose side of the eye close-up** (owner's note on the first sheet: the skin at image left
looked blocky). The nose and the skin between the brows are the nearest things to the eye camera
and out of its focus; at normal strength 1.8 the blurred pore relief there read as coarse lumps,
like orange peel. A `calm` mask (nose and mid-brow regions, softened 8 steps) takes the normal map
down to 0.6 there (`NOSE_NORMAL`). Before / after looked at on 03, 04 and 09: the nose side is
smooth and soft as in the reference, the cheek and lid keep their relief. Stills, `renders/` and
the direction check rerendered after it.

**3. Frames, Cycles 64 spp**: 17 frames over every framing, both glides and three blinks of the
three videos (`--frames`, new: `eyes.py --input left --samples 64 --frames 45 129 150 185 245`),
looked at. Seconds per frame, 1024², Metal on the M4:

| framing | s/frame | frames (left / right / generate) |
|---|---|---|
| both eyes | 32-33.5 | 112 / 109 / 133 |
| eye | 26-33 | 79 / 72 / 95 |
| face | 14.4-17.7 | 79 / 89 / 93 |

  About **2.0 + 1.95 + 2.4 = 6.3 h** for the three final videos (was 4.8 h). A first set, before
  the fuzz, the rim and the wider framing, measured 25-28 / 20-21.5 / 12-13.5 (about 4.9 h). Static
  frames with the rim off or the fuzz hidden were no faster (22.8 / 26.3 / 13.2 s either way), so
  the rise is motion-blurred hair or a warm machine after sustained rendering; not settled. These
  timings were taken before the last small changes (scrim, rim at 2.5 W, light linking).

**4. Stills** (`tools/render_stills.py`, all nine sets on their own heads, 128 spp, looked at as a
sheet and 02 / 09 at full size). `cam_test_face` is 126 mm from 0.56 m: 16 cm, mid forehead to
chin, no scalp or ears. `cam_test_eye` is the videos' eye framing. The 10 clockwise renders keep
the constant `face` look.

**5. Fine facial hair** (`tools/vellus.py`, grown like the lashes, bound to triangles): 8,142
hairs on the face front, 0.4-2.4 mm, 9 to 3 um radius, none on lips, lid margins or brows. Each
takes the skin texture's colour under its root (`skin_uv` attribute, less saturated, gamma 0.8):
one pale colour was white lint on the darker sets. With the rim it shows on the temple and
cheek silhouette against black and as single hairs on the lit cheek.

**Checks**: `python -m unittest discover tests` 38 pass; `tools/validate.py --blender` passes all
but "README: no TODO left" (5 lines), as before. Draft videos (EEVEE, `outputs/videos/`, not
committed) rendered in the new look, 0.74-0.84 s/frame; 18 frames of each looked at: both eyes stay
in frame through the turns, the flag works in EEVEE. **Drafts show no catchlight** (the card
needs Cycles' singular rays); the finals have it.

**Left**
- Final videos not rendered (owner): `--input left|right|generate --samples 64`, about 6.3 h.
- Nobody has watched a draft at playback speed; the pauses inside a glide are still unjudged.
- The both-eyes framing at 13 cm is nearly a face shot. If that is too loose, the other way is to
  let that camera follow the head sideways instead of widening it.
- tex_06's forehead edge still takes a bright line from the rim in the eye still.
- The `eye` look is tuned on the tex_09 head; the other eight were only checked as stills.

### Fri 13 Nov 2026, night — M4 one moving camera for the videos (Opus)
The face-plus-inset video is gone. Videos are filmed by one camera, `cam_move`, that holds a
framing, glides to the next, holds, glides to the last and holds to the end. Code:
`tools/build_scene.py` (cameras only), `wrapper/eyes.py` (video path), new
`wrapper/camera_move.py` (when to glide, pure numpy) and `tests/test_camera_move.py` (8 tests).
`scene.blend` rebuilt (it also carries the sway / partial-blink motion of the entry below now).
No material, light or texture touched.

**Framings** (cameras in `scene.blend`, each with `move_dist` and `move_fstop`; all filmed with the `eye` look)
- `eye`: `cam_move_eye`, 100 mm, 15 cm from the subject's left pupil, 24 deg toward the nose side,
  6 deg above (panel D of `outputs/tmp/m4/angles_sheet.png`), f/45. On the head bone, like the old
  `cam_inset`, which it replaces.
- `eyes`: `cam_move_eyes`, straight on, 100 mm, 11 cm wide at the pupils, centred 1.2 cm below the
  eye centres: just above the brows to the cheeks and the base of the nose. 12 cm showed half a
  forehead and the lips; 11 cm still keeps both outer eye corners in through the 12 deg head turns
  of left / right. f/45.
- `face`: `cam_video` as it was (72 mm, 0.56 m), f/40.
- Focus follows the left pupil every frame (along the view axis; the pupil rides on the eye bone).
  The stop goes f/45 at the eye and both eyes to f/40 at the face. Note on the brief's "open the
  stop as the camera pulls back": pulling back already deepens the field (at f/45 the face is
  sharp from the nose tip to the ears within one pixel), so the stop opens only to f/40; f/38 is
  the widest that keeps the ears inside a one-pixel blur circle with focus on the pupil.

**Order and timing** (`wrapper/camera_move.py`)
- left, right: both eyes (the first gaze shift is seen here), face, eye. generate: eye, both eyes, face.
- The camera moves only inside fixations. Busy = every saccade in the track's list (30 ms before
  onset to 60 ms after the end, for the glissade), every blink (closure above 0.01, padded 30 ms)
  and gaze faster than 12 deg/s for 40 ms or longer (the eye-roll sweep). Microsaccades and drift
  are part of a fixation.
- Fixations in these tracks last 0.5 to 1 s, and the only 1.5 s one is at the end of the clip. So
  a glide is a fixed amount of motion (1.5 s to or from the eye framing, 1 s between both eyes and
  face) spread over up to three consecutive fixations; each piece is eased to a stop (smoothstep)
  and the camera stands still through the saccade or blink between pieces. Pieces shorter than
  0.3 s are not used.
- Placement is a joint search over both glides; cost = distance of each hold from its nominal
  (3 s / 3 s for left and right, 2 s / 2 s for generate; the first hold counts double), missing
  motion, pauses, and a last hold under 1.5 s. 3 + 1 + 3 + 1.5 s does not fit a 9 s clip, so in
  left and right the face hold gives way: the both-eyes shot is the one the rubric's "both eyes
  move left" is judged on. Left / right also wait until the first gaze shift of 5 deg or more has
  landed plus 0.5 s.
- Seed 0 (s, pieces of motion; the camera holds between them):

  | | first glide | second glide | holds |
  |---|---|---|---|
  | left | eyes → face 2.50-2.94, 3.58-4.14 | face → eye 5.70-6.55, 6.66-7.30 | 2.5 / 1.6 / 1.7 |
  | right | eyes → face 2.53-2.94, 3.50-4.04 | face → eye 5.60-6.27, 6.39-7.05, 7.17-7.47 | 2.5 / 1.6 / 1.5 |
  | generate | eye → eyes 1.77-2.26, 2.96-3.29, 3.67-4.33 | eyes → face 6.30-6.71, 7.42-8.01 | 1.8 / 2.0 / 2.7 |
- Every glide plans for seeds 0-39 in all three modes.

**Camera path** (`wrapper/eyes.py`, `_blend` and `_camera_matrix`)
- Camera position and look-at point are interpolated separately; the orientation is built from
  the look-at with world up every frame, never blended between end orientations. Roll is 0.00 deg
  on every frame of all three videos (it was up to about 20 deg in the face-to-eye glide when the
  end orientations were blended).
- Look-at point moves straight; the camera's direction from it turns on the sphere; distance, lens
  and stop change geometrically, so the frame width does too.
- Staggered so the camera never sweeps close past the nose: a glide that pulls back (eye to both
  eyes) moves out over the first half of its progress, then across over the second, and backs
  out 40 % past its end distance before coming in as it turns. A glide that pushes in (face to
  eye) turns at face distance and comes in last.
- In the eye framing the camera's position and look-at point ride on the head bone; the follow is
  blended out (generate) or in (left, right) over the glide next to it.
- All five channels (location, rotation, lens, focus distance, f-stop) are keyed on every frame,
  linear in-betweens, and each piece is snapped inward to whole frames, so motion blur never
  samples a moving camera outside a fixation.

**CLI**: `--camera move` is the default for videos; `--camera face` (`cam_video`) and
`--camera eyes` (`cam_eyes`) still film with one fixed camera; `--camera both`, `INSET`, the
compositor and `cam_inset` are removed. Draft frames are still rendered at 50 % and scaled up.
README `--camera` row updated.

**Looked at**: strips of 10 EEVEE frames through every glide of all three videos (after each
change: the first version rolled about 20 deg in the face-to-eye glide and swept past the nose
going from eye to both eyes; both fixed and looked at again), twelve frames across each final
draft (every framing in every video, mid-glide frames read as faces), and Cycles 64 spp frames
of each framing from `left` and `generate` (eye: lashes sharp, nose soft; both eyes: both eyes
sharp; face: sharp from the nose to the ear). The drafts decode in Blender as 1024², 30 fps,
9.00 / 9.00 / 10.70 s. Drafts are in `outputs/videos/` (not committed). Nobody has watched them at
playback speed in a player.

**Seconds per frame, Cycles 64 spp**, 1024², Metal on the M4, nothing else on the GPU, Blender
start-up and kernel load excluded:

| framing | s/frame | frames per video (left / right / generate, glides split at halfway) |
|---|---|---|
| both eyes (`cam_move_eyes`) | 24.7-27.5 | 112 / 109 / 133 |
| eye (`cam_move_eye`) | 19.0-19.1 | 79 / 72 / 95 |
| face (`cam_video` framing, `eye` look) | 12.6-13.7 | 79 / 89 / 93 |

  About **1.5 + 1.5 + 1.8 = 4.8 h** for the three final videos at 64 spp (the face-plus-inset
  videos were about 3.6 h). The close framings cost more per frame than the face, mostly skin
  filling the frame.

**Checks**: `python -m unittest discover tests` 38 pass (8 new); `tools/validate.py --blender`
passes everything but "README: no TODO left" (5 lines), as before; directions unchanged
(left -13.8 / -14.2 px, right +14.2 / +13.8, up -14.0, down +14.0).

**Left**
- Final videos not rendered. `--input left|right|generate --samples 64`.
- The `LOOKS` comment in `build_scene.py` still mentions "the eye inset in the videos"; it sits in
  the look code, so I left it for whoever touches the look next.
- Nobody has watched the drafts at playback speed in a player; frames were read as stills.
  Worth a look: the pauses inside a glide (the camera stops for each saccade) and whether
  1.6 s on the face in left / right is enough.

### Fri 13 Nov 2026, night — less puppet-like motion: sway, blink eye roll, partial blinks, brow asymmetry, pupil (Opus)
Six items from the owner's list. Code: `wrapper/gaze/engine.py` only (plus `tests/test_gaze.py`).
`rig.py`, `eyes.py` and `build_scene.py` untouched (another session has them).

**`scene.blend` needs a rebuild** (`$BLENDER -b -P tools/build_scene.py`) so the Timeline it ships
carries the new motion. `eyes.py --input` bakes the track itself, so videos rendered from it already
have it; the `.blend` an evaluator opens does not until the rebuild.

1. **Idle head sway** (`head_sway_deg` 0.30 / 0.30 / 0.15, `head_sway_band` 0.10–0.50 Hz, was
   0.35 / 0.25 / 0.20 at 0.08–0.45). Measured over ten 20 s clips with no looks: 0.30 yaw, 0.28 pitch,
   0.15 roll deg rms, over 85 % of the power in 0.08–0.55 Hz. Same number of random draws as before.
   The eyes hold the target: with and without sway, gaze_yaw/pitch agree to 1e-9 in all three modes
   and eye_yaw differs by exactly minus the sway (tested).
2. **Eyes roll down and in under a blink**: down 1.5 deg (`blink_eye_dip`, already there) and now
   1.0 deg toward the nose per eye (`blink_eye_nasal`), both scaled by the lid closure, so they go
   as the lid closes and come back as it opens. The rig has no per-eye yaw channel, so the nasal
   turn goes in as vergence: `gaze_dist` is shortened so each eye's half-angle grows by 1 deg
   (`eye_half_ipd` 0.0309 m, GNM's eye centre to midline). In the plots the fixation distance now
   dips under each blink (1.6 → 0.85 m when looking far, 0.40 → 0.33 m at the camera). The pupil's
   near response reads the un-blinked distance. Channel docstring updated.
3. **Partial blinks**: after the scheduling, every blink but the first rolls `blink_partial_rate`
   0.22 and if it hits closes to 0.65–0.75. Own generator (`[seed, 1]`), so no other draw moved.
   Over 3 modes × 30 seeds: 18 % of 375 blinks are partial (about one in six); the first blink of
   left and right is never partial (tested). Seed 0: the third blink of left and right (0.67, on the
   return to the viewer) and the third of generate.
4. **Brow asymmetry per event**: each large-shift effort and each two-sided `Brow` gets its own draw
   (`[seed, 2]` generator): one side up to 15 % weaker (`brow_side_amp`) and one side 20–40 ms later
   (`brow_side_lag`), sides chosen independently. The pitch-driven raise keeps the old per-clip
   lean (0.86–0.96, one side). One-sided `Brow` events are unchanged.
5. **Pupil**: the slow wander (`hippus`) is now 0.024 rms, 3 % of the ±0.4 range, at 0.3–1 Hz
   (was 0.07 at 0.15–0.6). Measured 2.8 % over ten clips. Constriction with convergence: the
   near response was 0.25 per dioptre (1.6 m → camera at 0.4 m constricted by 0.46, 57 % of the
   range). On the owner's call it is now `near_gain` 0.065: the same shift constricts by 0.119,
   **15 % of the range** (tested, 13–17 %). Seed 0 pupil now spans about −0.09 .. +0.13 in left and
   right. The pupil reads the fixation distance *before* the blink's nasal dip (`fix_dist`), so
   a blink leaves it alone: with `blink_eye_nasal` 0 or 1 the pupil channel is bit-identical in
   all three modes (tested).
6. **Brow lift and squint with large shifts**: already in (previous entry): left and right peak at
   0.25 brow and 0.10 squint, rising with the shift and relaxing in the hold. Now tested over five
   seeds per mode (peak 0.2–0.3, squint 0.07–0.13, under half the peak 1.2 s after the glance).

Tests: 38 pass (12 new in `Natural`; the camera-move session's tests included).
Plots for all three modes at seed 0 looked at (`python -m wrapper.gaze --mode <m> --seed 0 --plot <f>`).

**Draft videos** (seed 0, EEVEE, `--camera face`, 0.6–0.9 s/frame; in `outputs/videos/`, not
committed, replacing the earlier drafts there). The default `--camera move` stops with
`KeyError: cam_move`: the working-tree `eyes.py` (camera-move session, uncommitted) needs a
`scene.blend` rebuilt by its `build_scene.py`, so these drafts use the fixed face camera.
Looked at in `left`: the head turn (f30–60: eyes lead to image-left, head follows over about
0.6 s, brows lift a little), the full blink at 4.16 s (closed f128–130, open by f133) and the
partial one at 5.20 s (f159–162: the lid stops at a slit with the iris showing while the eyes
return to the viewer). Spot frames of `right` and `generate` (turn, eye roll with wide lids,
look down) are as before. The nasal and downward roll happens behind the closed lid and is not
visible at this framing, which is expected. Nobody has watched them at playback speed.

### Fri 13 Nov 2026, night — thinner brow hair, rim light, shift effort in left and right (Opus)
Three look changes from the owner's list. Code: `tools/build_scene.py` (brows, rim),
`wrapper/gaze/engine.py` (effort). `scene.blend`, the nine stills, the sheet and `renders/`
regenerated and committed. `metadata.json` and `outputs/direction_check.json` came out identical.

**Brow hair** (`thin_brows`, called from `build_hair`): each carried Mindfront set keeps 60 % of
its strands (seed `[2026, set]`, so 01: 789 → 462, 05: 1267 → 776, 08: 1130 → 667), the radius
is halved (48 → 24 um at the root), and every point that stands above the skin is brought down
to half its height. Root and skin point stay. Looked at the 02 and 06 eye stills before and after,
and at 02 with the hair hidden: most of the dark mass is the brow **painted into the albedo**,
and with the hair on, the eye still now looks almost the same as with it hidden, plus single hairs
along the lower edge and over the paint. If the brows still read as heavy, the next change is in
the albedo (textures/), not the hair.

**Rim light** (`rim` in `build_cameras_and_light`, `face` look is now `"key,rim"`): area
0.20 × 0.70 m, 40 W, 0.9 m from the middle of the head (7 cm behind the eye midpoint) at 150 deg
round from the camera toward image right and 12 deg up, aimed at the head. Checked with the rim
alone (key off, HDRI 0) and a difference image: it lands only on the scalp edge, temple, jaw,
cheek edge, ear (red SSS glow), neck and shoulder on image right. The front of the face is
unchanged (06 cheek mean 41.3 with and without). Clipping: at 80 W tex_01 had 2,236 fully white
pixels on the edge and shoulder, at 50 W 27, at **40 W none (peak 247)**. tex_06's edge still reads.
Tried and dropped: 135 deg (too faint), 145 deg at 150 W (lit the whole side of the face and the
top of the brow), 162 deg (both ears, no jaw). The `eye` look is unchanged (no rim).

**Shift effort** (`GazeParams.shift_*`, step 7 of `simulate`): every `Look` whose total
amplitude is over 10 deg adds effort, full from 24 deg. Effort rises over 0.20 s from the
saccade onset (raised cosine), then decays with tau 0.55 s through the hold. Brow gets 0.31 × effort
and squint 0.12 × effort, maxed with what was there, so after the low-pass and the one-sided lean
they peak at **0.25 brow and 0.10 squint** (left and right, seeds 0 and 3). Both happen on the glance out and
on the return. Shifts under 10 deg add nothing. `generate` keeps its larger scripted brows (0.6-0.7).
No new random draws, so the rest of every track is unchanged. Plot: `python -m wrapper.gaze
--mode left --seed 0 --plot <file>`. Tests: 25 pass (18 gaze plus the camera-move session's).

**Looked at**: the 02, 06 eye before/after crops, 01 and 06 face stills before/after and the rim
on its own, the new nine-still sheet, all ten clockwise frames, and four composited frames from
each draft video. The three draft videos (`outputs/videos/`, EEVEE, **not committed**) were
rendered with the committed `eyes.py`, so they still use the face plus `cam_inset` framing.
`tools/validate.py` with `$BLENDER`: as before, only "README: no TODO left" fails.

**For the next session**
- Another session is changing the video framing (`cam_move`, `wrapper/camera_move.py`, edits to
  `tools/build_scene.py` and `wrapper/eyes.py`). Those edits were uncommitted when this was
  written. The committed `scene.blend` has `cam_inset` and `rim`, no `cam_move`. Whoever commits the
  camera move must rebuild `scene.blend` after it; the rim and brow changes are already in
  `build_scene.py` on `main`.
- Final videos not rendered (owner).

### Fri 13 Nov 2026, late — after the lid solve and the iris pass: shader reset, video framing, drafts (Fable)
Picked up the two "For Fable" lists (iris entry and video framing entry below).

**Iris shader corrections removed** (`eye_textured` in `tools/build_scene.py`): `IRIS_SATURATION`,
`IRIS_VALUE`, `LIMBAL_DARK` and the fornix term are gone; the eye tile goes in as it is, so the
scene shows what the judges get when they wrap it. Nine stills re-rendered on the solved lids
(`outputs/stills/`, sheet too) and looked at: browns are dark and warm, hazel / green / blue have
a soft limbal ring and no flat collarette patch, and every set's lid now rests about 4 mm above
the pupil centre, so tex_09's outer upper lashes show again.

**Video framing** (the band of both eyes over the forehead read as a second pair of eyes):
- `cam_inset` (new, `build_test_cameras`): the `cam_test_eye` view of the subject's left eye from
  12.5 cm (45 mm wide), `eye` look, f/40, **parented to the head bone**, so the eye stays in frame
  through head turns and the inset shows the eye moving in the head.
- `cam_video` (new): the face camera for videos, 72 mm from the `cam_test_face` position. The
  head is 15 % smaller than in the test shot, which keeps a turning head clear of the inset.
- `wrapper/eyes.py`: `INSET` is now a 317 px square 12 px in from the top and right edges (that
  corner holds only backdrop and the side of the scalp); the eye is about 1.9 times its size in
  the face frame. `--camera both` renders `cam_video` and `cam_inset` (at inset size);
  `--camera eyes` alone is still `cam_eyes`.
- Looked at composited Cycles frames: `right` 1 and 110 (head turned toward the inset corner:
  it covers scalp only), `left` 120, `generate` 150 (eye roll with raised brows).
- Timing at 64 spp: face 12.3 s, inset 2.7 s, about **15 s per composited frame, 3.6 h for the
  861 frames**; 128 spp would be about twice that (not measured).

**Draft mode** (`draft_materials` in `wrapper/eyes.py`): EEVEE rendered the cornea shell and tear
line as mirrors, raytraced refraction did not help, so drafts swap those materials (in memory
only) for Fresnel gloss over transparency and render hair as strips. Looked at a draft eye and
face: the iris shows, lashes are thin. The tear line is a bright line in drafts.

**Regenerated on the final scene**: `renders/` (10 clockwise frames, Cycles 128 spp, `face` look),
`metadata.json`, `outputs/direction_check.json` and its renders, and the three draft videos with
the new framing (`outputs/videos/`, EEVEE, not committed: they are placeholders).

**Left**
- **Final videos**: `--input left|right|generate` with `--samples 64` (or the default 128).
  Someone should press play on a draft first; no session has seen one move.
- Brow hair is still heavy on sets 02-06 in the eye stills.
- The short dark dash at the outer end of the subject's right lower lid in `cam_eyes` frames
  (tear line at a grazing angle) is still there; `cam_eyes` is no longer in the default video.
- README: the `--camera` and `--samples` rows are updated; "How it works" still needs the lid
  solve, the guard and the M3 look, and the five TODO lines are open (M5).

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
