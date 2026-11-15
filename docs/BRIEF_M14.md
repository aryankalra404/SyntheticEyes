# Brief — M14 the head in the Quest 3S (WebXR bonus)

Written by Fable on Sun 15 Nov 2026 for an Opus 5.5 session. Fable reviews from the review pack
in section 8, not from the diff. Read `CLAUDE.md` and the two newest entries of
`docs/PROGRESS.md` first.

**Kickoff prompt for Opus:** "Implement `docs/BRIEF_M14.md` stage by stage, in order. After each
stage run its checks, look at the page in the browser, commit, and add to your own M14 entry in
`docs/PROGRESS.md`. Do not touch `scene.blend`, `wrapper/` or `textures/`: the final videos are
rendering from them. Stop after the review pack in section 8; do not deploy anything."

## 0. What this is

An unscored bonus for an XR hackathon: the hero head, life size, standing in the wearer's room
through the Quest 3S passthrough cameras. It looks at the wearer the way a person does (eyes
first, quick jumps between the wearer's eyes, blinks, short glances away) and turns its head
when the wearer moves. One web page, opened from a link in the Quest browser; on a laptop the
same page runs with the mouse as the wearer, so a jury without a headset can try it.

It must never cost the scored submission anything:
- **The finals are rendering right now** (`generate`, then `left`, then `right`, each a fresh
  Blender start that reads `scene.blend` and `wrapper/`). Until `outputs/videos/` holds three
  final videos, do not modify, rebuild or save `scene.blend`, and do not edit anything under
  `wrapper/` or `textures/`. Everything in M14 is new files.
- All of it lives in `xr/` plus one exporter, `tools/export_xr.py`. `tools/validate.py` and the
  unit tests must pass unchanged at the end.
- Stop rule: stages A to D by **Mon 16 Nov night**, E and F by **Tue 17 Nov night**. If the
  headset path (E) is not working on the device by Wed 18 Nov night, the bonus ships as the
  laptop page plus a screen recording.

## 1. What the scene gives you (checked in `scene.blend` on 15 Nov)

- `gnm_rig`: armature at the origin, bones `neck` → `head` → `eye.L`, `eye.R`. Custom properties
  `eye_rest_L`, `eye_rest_R`, `eye_mid`, `rest_pupil`, `rest_lid_open`, `blink_keys`.
- `gnm_head`: one mesh, 17 821 vertices, 17 662 faces, real size in metres. Material slots
  `skin`, `eye_interior.L/R`, `cornea.L/R`, `teeth`, `tongue`: the eyeballs are part of this
  mesh, skinned to the eye bones. 21 shape keys plus the basis: `lid_up`, `lid_down`, `lid_in`,
  `lid_out`, `lid_open`, `blink_33`, `blink_66`, `blink`, `brow_up`, `squint` (each `.L` and
  `.R`) and `pupil`. UV layers `UDIM` (skin on tile 1001, eyes on 1002 and 1004) and `legacy`.
- Modifiers on `gnm_head`: the armature, then two shrinkwraps onto `globe_guard.L/R` that keep
  lid skin 0.12 mm outside the eyeball. They cannot be exported. See C3.
- Textures, `textures/tex_09/`: `skin.1001.png` and `skin_normal.1001.png` (4096 px, 24 MB
  each), `skin_rough.1001.png` (2048), `eye.1002.png`, `eye.1004.png` (2048).
- Hair (`lashes`, `brows_grown`, `vellus`) is geometry-nodes curves grown from point-cloud
  carriers (`lashes_carrier`: 3010 points, the same 21 shape keys, armature). The brows are
  also painted into the albedo.
- `wrapper/rig.py` is 200 lines and is the whole rig: how head, neck and eye rotations and the
  21 key values come from the channels. `wrapper/gaze/engine.py` `GazeParams` holds every number
  of the motion model. Port from these; do not invent new numbers where one exists.
- On this Mac: `node` 22, `openssl`, `adb`. No ffmpeg.

## 2. Layout

```
tools/export_xr.py     blender -b scene.blend -P tools/export_xr.py   (reads the scene, never saves it)
xr/index.html          the page; ES modules, an import map, no build step
xr/js/rig.js           port of wrapper/rig.py: channels -> bone rotations and morph weights
xr/js/gaze.js          real-time gaze: (state, viewer position, dt) -> channels; no three.js, no DOM
xr/js/app.js           scene, materials, lights, XR session, laptop fallback
xr/vendor/three/       three.js (MIT), pinned release, only the files used
xr/assets/             head.glb, rig.json, resized textures
xr/tests/              node --test, no browser
xr/serve.py            local HTTPS server for the headset test (section 6)
xr/README.md           how to run it, controls, credits
```

Commit `xr/` (keep it under 25 MB in total, no file over 10 MB). Record three.js in
`docs/TECH_NOTES.md` under Assets.

## A. Export (`tools/export_xr.py`)

- Open `scene.blend`, clear the animation in memory, pose at rest, all keys at 0, and export
  `gnm_head` with its armature to `xr/assets/head.glb`: skinning, the 21 shape keys with their
  names and morph normals, both UV layers folded into 0..1 per material (`u − floor(u)`), no
  animation, no modifier applied, no materials worth keeping (they are rebuilt in `app.js`).
  Never call save on the scene.
- `xr/assets/rig.json`: the custom properties above, the bone head positions and the constants
  from `rig.py` (`NECK_SHARE`, `LID_*`, `WIDEN_GAIN`, `BLINK_BROW_DIP`), all in the exported
  (glTF, Y up) frame. State the axis map in the file.
- Textures to `xr/assets/`: skin albedo and normal at 2048 px, roughness 1024, eyes 1024;
  JPEG or WebP for colour, PNG for the normal map if lossy shows banding. Under 8 MB together.
- Checks: `head.glb` reloads in Blender with 17 821 vertices, 4 bones, 21 named morph targets;
  `git status` shows `scene.blend` unmodified.

## B. The page, still (`index.html`, `app.js`)

- three.js vendored at a pinned release that is at least two weeks old. `GLTFLoader`,
  `XRButton` (or `ARButton`), `RoomEnvironment`. Nothing from a CDN at run time.
- Materials: skin `MeshPhysicalMaterial` with albedo, normal and roughness maps; eyeball
  interior with its albedo; cornea as a thin transparent shell (low opacity, roughness near 0,
  strong specular, environment reflections) so the eye has a catch light. No transmission and no
  refraction: both are too slow in a headset. Teeth and tongue plain.
- Light: a soft environment for fill and reflections plus one key light from upper image-left,
  like the stills. It will not match the room in passthrough; that is accepted.
- A plinth: a plain dark cylinder under the neck cut, so it reads as a bust and not a floating
  head. The bust (head + plinth) is one group; everything below works in that group's space.
- Debug pose from the URL for screenshots: `?pose=1&gy=20&gp=0&hy=0&blink=0.66&brow=0.3`
  sets the channels directly and freezes time.
- Check: open `http://localhost:<port>/xr/` in the browser pane, no console errors, and compare
  a screenshot at rest with `outputs/stills/` of tex_09. It will look flatter than Cycles; it
  must look like the same person, with no seam, no black eye, no inverted normals.

## C. The rig (`rig.js`)

- C1. Port `Rig.apply()`: neck 35 %, head 65 %, each eye aimed at a world point (so vergence is
  free), lids from each eye's own pitch and yaw, tent-blended blink keys, brow, squint, pupil.
  The input is the gaze target as a point, not yaw/pitch/distance. Bones are posed as pure
  rotations about their heads; derive the local quaternions from the rest matrices as
  `_set_local` does and verify them, do not trust a sign from this brief.
- C2. Direction check, the same convention as the wrapper: a target to the viewer's right moves
  both pupils to image-right, up moves them up; `hy > 0` turns the face to image-right. Write
  it as a node test on the bone maths and confirm it on screenshots at `gy = ±20`, `gp = ±15`.
- C3. Lids against the eyeball without the shrinkwrap guard. Screenshot blink 0.33, 0.66, 1.0
  at gaze (0, 0), (±20, 0), (0, ±15), close up on one eye. If the cornea shows through a lid:
  first try exporting each lid and blink key from the evaluated mesh (guard on, the eye posed
  at the angle that key stands for) minus the evaluated rest, which bakes the guard into the
  single-key poses; if a corner case is left, clamp the eye-in-head range used by the demo. Say
  in PROGRESS which was needed.
- Check: the pose screenshots next to `tools/rig_strips.py` output of the same poses
  (`outputs/tmp/m13/lids/after/`, `outputs/tmp/m13/blink_D/`): same lid shapes.

## D. Real-time gaze (`gaze.js`) — the part that has to feel alive

Pure JavaScript, seeded, no clock of its own: `step(state, viewer, dt)` where `viewer` is the
wearer's head position (and right vector) in bust space, or `null`. Output: head yaw, pitch,
roll, the gaze target point, `blink_L/R`, `brow_L/R`, `widen`, `squint`, `pupil`.

Rules, with the engine's numbers:
- **Where it looks.** Three points on the wearer's face: their left eye, their right eye
  (±3.2 cm along their right vector) and the mouth (7 cm below). Dwell 0.6 to 1.8 s, then
  jump: mostly eye to eye, the mouth about one time in six.
- **Glancing away.** Every 5 to 10 s the eyes alone leave for 0.4 to 1.0 s, 6 to 12 deg to a
  side or down and to a side, never up, then return. Nobody holds eye contact without a break.
- **Jumps are saccades.** Duration and speed profile from `saccade_duration` and `_profile`;
  no jump within `min_isi` of the last. Between jumps the gaze tracks its point as the wearer
  moves (pursuit), and a catch-up saccade fires when the error passes 2 deg.
- **Eyes lead, head follows.** The eyes are always aimed in world space, so they hold the
  target while the head moves. The head wants to leave the eyes within 8 deg of centre: when
  the eye-in-head angle passes 12 deg, or stays past 6 deg for 1.2 s, the head's goal becomes
  about 80 % of the way to the target. It gets there through the engine's follower: 1.2 Hz
  critically damped, starting 0.04 to 0.10 s after the eyes, roll −0.20 per degree of yaw, the
  dip from `head_dip_gain`. Idle sway as in `head_sway_deg` and `head_sway_band`.
- **Limits.** Head yaw ±60, pitch −20 to +25. Eye-in-head yaw ±28, pitch +22 / −25 (inside what
  the lid keys were solved for). A wearer beyond head + eye range, further than 2.5 m, or
  absent, is lost: after 2 s the head drifts back to centre and looks around slowly (a new
  point every 1.5 to 4 s within ±20 deg). When the wearer is back in range: saccade to them, a
  brow flash (0.35 for 0.4 s) and a blink.
- **Blinks.** `blink_close`, `blink_hold`, `blink_open`, mean gap 3.2 s, minimum 1.6 s, the
  partial-blink share, a blink with most gaze shifts over 20 deg. Brow and squint effort on
  large shifts from the `shift_*` numbers.
- **Near.** Vergence comes from aiming each eye. The pupil narrows a little as the wearer comes
  close (`near_gain`) and wanders with `hippus`.
- Frame-rate independent: 72, 90 and 120 Hz must give the same behaviour.

Tests (`xr/tests/`, `node --test`), each on a scripted wearer path, seeds 0 to 7:
1. Still at 0.7 m for 20 s: head yaw rms under 1.5 deg, 4 to 9 blinks, 10 to 30 saccades,
   1 to 4 glances away, eye-in-head never past 15 deg.
2. A 0.5 m step to the side in 1 s: the gaze is on the wearer (under 2 deg) 0.3 s after the
   step ends; the head starts after the eyes; the head covers 65 to 85 % of the angle within
   1.5 s; eye-in-head never past 28 deg and under 10 deg at the end.
3. A slow walk through 150 deg at 20 deg/s: the head follows to its limit without a jerk
   (head speed under 80 deg/s), the wearer becomes lost, the head recentres, and reappearing
   brings the saccade, the brow flash and the blink.
4. Coming to 0.25 m: the two eyes' yaw differ as the geometry says (about 14 deg).
5. Same seed and path give the same channels; a run at 72 Hz and one at 120 Hz agree
   (head angles within 0.5 deg rms).
Dump the channels of paths 1 to 3, seed 0, to JSON and plot them with matplotlib into
`outputs/tmp/m14/curves_<path>.png`. Look at them.

## E. In the headset (`app.js`)

- "Enter AR": `immersive-ar` with `local-floor` (passthrough). If AR is not offered, fall back
  to `immersive-vr` on a dark background. Antialiasing on.
- On entering, place the bust 0.7 m in front of the wearer, its eyes at the wearer's eye height,
  facing them. The controller trigger or a hand pinch (`select`) places it again.
- The wearer's position is the XR camera's, converted to bust space each frame.
- **Laptop fallback** when there is no XR session: the camera is the wearer. Moving the mouse
  moves the camera on an arc around the head (±50 deg sideways, ±20 up and down), the wheel
  changes the distance (0.3 to 1.5 m), and the head tracks the camera exactly as in the
  headset. Touch drag does the same on a phone.
- A small credits line on the page (section 7).
- You cannot test the headset path. Follow the standard three.js XR pattern
  (`renderer.xr.enabled`, `setAnimationLoop`) and leave the owner the checklist in section 6.

## F. Polish, only after E works on the laptop

- Lashes: without them the eye looks bald. Build ribbons or lines from `lashes_carrier` (its
  points carry the same shape keys and skinning) and export them into the glb. Brows are in
  the albedo; vellus and grown brow hair are out of scope.
- The tear line meshes as a thin glossy strip, if they export cleanly.

## 6. Headset test, for the owner (`xr/serve.py`, `xr/README.md`)

`xr/serve.py` serves the repo root over HTTPS on the local network with a self-signed
certificate it generates on first run into a git-ignored folder, and prints the address. The
owner opens `https://<mac address>:8443/xr/` in the Quest browser, accepts the certificate
warning and taps "Enter AR". Also document the USB path (`adb reverse tcp:8000 tcp:8000`, then
`http://localhost:8000/xr/` on the Quest). Write the owner a checklist of what to look for:
does it find me, do the eyes arrive before the head, does it lose me behind it and greet me
when I come back, is anything clipping or flickering, is the frame rate smooth.

**Do not deploy to GitHub Pages or any public host.** Putting it on a public link is the
owner's decision, made after the review.

## 7. Licences and credits

three.js is MIT. The head is Google GNM Head v3 (Apache-2.0). The skin of `tex_09` uses the
Infinite head scan (CC BY 3.0): credit it on the page and in `xr/README.md`, with the wording
the main README already uses.

## 8. Review pack for Fable (`outputs/tmp/m14/`, git-ignored)

1. Screenshots from the browser pane: rest; gaze ±20 yaw and ±15 pitch; blink 0.33, 0.66, 1.0;
   the head turned 40 deg with the eyes on the camera; one eye close up. Each next to the
   Blender render of the same pose where one exists.
2. The curve plots of test paths 1 to 3.
3. Screenshots of the laptop fallback at five mouse positions, a few seconds apart.
4. `node --test` output, `python -m unittest discover tests` and `python tools/validate.py`.
5. A PROGRESS entry: what was done per stage, every check pass or fail, sizes of `xr/assets/`,
   what was skipped and why, and the owner's headset checklist.

Then stop. Fable reviews, the owner tries it in the headset, and hosting is decided after that.

## 9. Out of scope

Unity, hand or eye tracking of the wearer, speech, other texture sets or heads, subsurface
scattering, matching the room's light, any change to the scored deliverables.
