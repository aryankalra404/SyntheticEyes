# Brief — M1 rig and calibrated wrapper

Run on the Mac, in this repo, with Fable. Paste everything below the line.

---

You are doing milestone M1. Read `CLAUDE.md`, `docs/REQUIREMENTS.md`, `docs/GNM_FACTS.md`,
the latest entry in `docs/PROGRESS.md`, `tools/smoke_render.py` and
`wrapper/gaze/engine.py` (its docstring is the channel contract) before writing code.
`git pull --rebase` first; another session may be working on textures in `tools/` and
`textures/`. Do not touch those files.

## Outcome

`scene.blend` holds a GNM head whose eyes, lids, brows, pupils and head pose are driven by
one Python object, and `wrapper/eyes.py` exposes the calibrated API and the three inputs.
Materials stay the grey debug ones from M0. Look development is M3.

## Design decisions (already made)

1. **No drivers, no constraints.** The wrapper computes every bone rotation and shape-key
   value in Python and writes them (and keyframes) directly. The `.blend` then plays on the
   Timeline in any Blender with nothing to evaluate but F-curves, and metadata is exact.
2. **The wrapper needs only `scene.blend`.** Nothing under `wrapper/` may import from
   `tools/` or read `assets/`. Anything it needs at run time (pupil-centre vertex indices,
   rest eye positions, resting pupil value) is stored in the `.blend` as vertex groups and
   custom properties by `tools/build_scene.py`.
3. **Lids come from a solve, not from scaling the wink.** Details below.
4. **One pose function.** `Rig.apply(channels)` takes the 15 channels in
   `wrapper/gaze/engine.py` and poses everything. `move(h, v)` and the three inputs both go
   through it.

## 1. Lid shapes — `tools/solve_lids.py` (runs in `.venv-gnm` or plain numpy on `base.npz`)

The lid margin has to stay on the surface of the globe. Rotating margin vertices about the
eye joint keeps them on that surface, so every target below is "rest margin rotated about
the eye joint's left–right axis by some angle". Use `gnm_core.lid_margins` for the rows.

For each eye, solve for the 100 eye-region coefficients `c` that minimise

    Σ_margin w·|B c − d_target|²  +  λ_fix Σ_far |B c|²  +  λ |c − c_prior|²

where `B` is that eye's expression basis restricted to the relevant vertices, `d_target`
the rotation displacement, `far` the outer ring of the orbital region (should not move),
and `c_prior` a multiple of the averaged wink vector for blink shapes and zero otherwise.

Shapes to produce (per eye, suffix `.L` / `.R`, subject's left / right):

| Key | Target |
|---|---|
| `lid_up` | eye pitched +20°: upper margin follows by 0.85 × pitch, lower margin by 0.35 × pitch |
| `lid_down` | eye pitched −25°: upper margin follows by 0.90 × pitch, lower margin by 0.45 × pitch |
| `blink_33`, `blink_66`, `blink` | upper margin rotated down 33 %, 66 %, 100 % of the way to the lower margin; lower margin rises 12 % of the gap |
| `brow_up` | per-side split of M0's `brow_up` (left coefficients → `.L`, right → `.R`) |
| `squint` | per-side split of M0's `squint` |

Plus one `pupil` key from expression index 382, slider range −3..+3.

After each solve, run a **collision pass** on the resulting vertex deltas: any eye-socket
or lid vertex that ends up inside the globe (sclera sphere of radius 14.6 mm or the cornea
bulge, measured from the eyeball mesh itself) is pushed out along the ray from the eye
joint to 0.15 mm above the surface, then the correction is smoothed over neighbours so
there is no dent. Check the pass with the eye yawed ±30° as well, since the cornea bulge
moves under the lid.

Blink is piecewise: weights for `blink_33 / blink_66 / blink` are tent functions of the
blink amount, so the lid travels along the arc over the globe instead of a straight line
through the cornea.

Report in `docs/PROGRESS.md`, for each eye:
- lid gap at blink 1.0 (must be ≤ 0.2 mm) and the basis-fit residual on the margin
- deepest lid-inside-globe penetration over pitch −30..+25°, yaw ±30°, blink 0..1 (must be ≤ 0.05 mm)
- distance from upper margin to pupil centre across pitch −25..+20° (must stay within
  ± 1 mm of its rest value: iris never tucks under the lid, no sclera shows above it)

If the basis cannot reach a target within 0.3 mm, keep the basis solution for the
surrounding skin and add a direct vertex correction on the margin rows with a smooth falloff.

## 2. `tools/build_scene.py`

Builds `scene.blend` from `assets/gnm/base.npz` plus the solved lid deltas. Start from
`tools/smoke_render.py` and move its reusable parts here.

- Mesh with `UDIM` and `legacy` UV layers, material slots split by UDIM tile
  (skin, eye interior L, cornea L, eye interior R, cornea R, teeth, tongue)
- Armature `neck → head → eye.L, eye.R` from GNM joints and skin weights
- Shape keys from section 1
- Vertex groups `pupil_L`, `pupil_R`; custom properties on the armature for rest eye
  positions, eye midpoint, forward axis, and the resting pupil coefficient (start at −1.2,
  about a 3.5 mm pupil)
- Camera `cam_face`: 40 cm in front of the eye midpoint, facing the face, 50 mm, 1024×1024.
  Camera `cam_eyes`: same position, 105 mm, aimed at the eye midpoint (used for videos)
- Constant lighting: the HDRI plus one soft key. Colour management AgX.
- Bakes `generate`, seed 0, onto the Timeline as keyframes and sets the frame range, so
  opening the file and pressing play shows the expression
- Saves with relative paths. Deterministic: two builds give the same geometry, shape keys
  and keyframes.

## 3. `wrapper/rig.py` — `Rig.apply(channels)`

- Head: split `head_yaw / pitch / roll` 35 % neck, 65 % head.
- Eyes: after the head pose, compute each eye joint's world position. Fixation point =
  eye midpoint + `gaze_dist` along the direction given by `gaze_yaw`, `gaze_pitch` in the
  world frame. Aim each eye at that point (this gives vergence), convert to the bone's
  local rotation, no torsion.
- Lid follow from each eye's own in-head pitch: positive pitch → `lid_up` weight
  `pitch / 20`, negative → `lid_down` weight `−pitch / 25`, both clamped to 0..1.2.
- Blink amount `b`: scale the lid-follow weights by `(1 − b)` and set the three blink keys
  from `b`. `widen` adds up to +0.25 to `lid_up`; `squint` sets `squint`.
- `brow_L`, `brow_R` → `brow_up.L`, `brow_up.R`. `pupil` adds to the resting coefficient.
- Remember the image-space sign convention: positive yaw is image-right, which is the
  subject's left (+X in GNM). M0 measured yaw toward image-left as −Z rotation in Blender.
- `Rig.key(frame)` inserts keyframes for everything `apply` touched.
- `Rig.pupil_px()` returns both pupil centres in pixels from the evaluated mesh;
  `Rig.eye_rotations()` returns world-frame Euler XYZ in radians.

## 4. `wrapper/eyes.py`

Module API and CLI in one file; it adds the repo root to `sys.path` so `wrapper.gaze` imports.

```
eyes.move(h, v)     head still, fixation point at (h·5 cm, v·5 cm) on the plane 35 cm ahead
eyes.reset()        same as move(0, 0)
eyes.render(path)   1024×1024 PNG from cam_face

--clockwise                       10 renders to renders/frame_00..09.png + metadata.json
--input left|right|generate       keyframes from wrapper.gaze → frames → mp4 in outputs/videos/
--seed N  --fps 30  --quality draft|final  --camera face|eyes  --texture NN (accepted, no-op until M2)
```

- `metadata.json` follows the schema in `docs/REQUIREMENTS.md` section B exactly, one
  record per frame, plus `K` and the camera world matrix as extra fields.
- Video: render PNG frames to `outputs/frames/<mode>/`, then encode H.264 MP4 with
  Blender's own FFmpeg output so no external tool is needed. Motion blur on, shutter 0.5.
  `--quality draft` uses EEVEE and half resolution.

## 5. `tools/validate.py`

Plain Python, no Blender. Checks: bundle layout; `metadata.json` schema, 10 records,
θ, h, v values; pupil shift sign versus the reset frame for left, right, up, down
(need a `renders/`-independent way: `eyes.py --check-directions` writes
`outputs/direction_check.json` with pupil pixels for reset and the four directions);
reset returns to the reset position within 0.1 px; each video ≤ 15 s.

## Done when

- `python tools/validate.py` passes
- You have looked at: a contact sheet of reset, left, right, up, down from `cam_eyes`;
  a lid-follow strip at pitch −25, −12, 0, +10, +20; a blink strip at 0, 0.33, 0.66, 1.0
  for each eye; and the draft `left.mp4`, frame by frame around the first saccade and the
  first blink
- The three numbers in section 1 are in `docs/PROGRESS.md`
- `scene.blend` opens and plays; everything is committed and pushed

If something in this brief turns out to be wrong for the real model, fix the approach,
say what you changed and why in `docs/PROGRESS.md`, and carry on.
