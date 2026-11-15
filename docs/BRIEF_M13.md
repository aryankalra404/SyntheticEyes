# Brief — M13 motion rework

Written by Fable on Sun 15 Nov 2026 for an Opus 5.5 session. Fable reviews the result from the
review pack in section 6, not from the diff. Read `CLAUDE.md` and the 15 Nov afternoon entry of
`docs/PROGRESS.md` first; that entry says what is wrong with the previews and why.

**Kickoff prompt for Opus:** "Implement `docs/BRIEF_M13.md` stage by stage, in order. After each
stage run its checks, look at what you rendered, commit, and add to your own M13 entry in
`docs/PROGRESS.md`. Stop after the review pack in section 6; do not render finals."

## 0. What this fixes, in one paragraph

The eyeball motion is right; the face around it is not. Lids ignore sideways gaze, the head
carries half of `left` and `right` as a stiff turn, and the eye roll in `generate` is a smooth
orbit with the lids held wide, which reads as startled. The owner rejected all three previews.
Fix in this order and stop at the first stage that cannot be finished cleanly: A (engine, no
Blender), B (panes), C (lids follow sideways), D (blink detail). Finals need 16 to 20 h, so the
review pack must exist by **Mon 16 Nov, 10:00**.

Do not touch: textures, materials, lights, `cam_face`, `move()`, `reset()`, `--clockwise`,
`metadata.json`. `--check-directions` must give the same pupil shifts as before (13.8 to 14.2 px).

## A. Engine and choreography (`wrapper/gaze/`, `tests/test_gaze.py`)

### A1. `left` and `right`: the eyes carry it (`behaviours._glance`)
- `GLANCE_HEAD` 0.5 → **0.22**. First target yaw `u(22, 26)` (was 25 to 29). Result to hit:
  head yaw peaks at **4.5 to 6.5 deg**, eye-in-head sits at **16 to 20 deg** for at least 2 s.
- Everything else in `_glance` stays (no blink on the way out, two refixations, blink on the way
  back, settle on the viewer).

### A2. A head that is not a turntable (`engine.py`)
- `head_freq` 1.5 → **1.2** Hz.
- `head_roll_coupling` −0.10 → **−0.20**.
- New: the head dips as it turns. During any head yaw move, `head_pitch` drops by about
  **0.15 deg per deg of yaw travelled**, peaking mid-move and back to zero when the head stops
  (drive it from the head yaw speed, low-passed; target 0.7 to 1.0 deg at the peak in `left`).
- `head_sway_deg` (0.30, 0.30, 0.15) → **(0.55, 0.45, 0.30)**, `head_sway_band` → **(0.08, 0.35)**.
  The eyes already counter-rotate, so gaze still holds.

### A3. Slow blinks (`engine.py`)
- `Blink` gets a field `slow: float = 1.0` that multiplies close, hold and open for that blink.
  Default behaviour unchanged. Spontaneous and gaze-evoked blinks stay at 1.0.

### A4. `generate` rewritten as one beat (`behaviours.generate`)
The deck's own example is "move left and right or roll eyes upwards". New script, seeded jitter
of about ±10 % on every time and angle, side A chosen by the seed, total 10 to 11.5 s:

| # | Start | Event | Notes |
|---|---|---|---|
| 1 | 0.9 s | `Look` to side A: yaw ±18..22, pitch −2..+2, far, `head=0.2`, `blink=False` | hold 1.0 to 1.2 s, one refixation of 3 to 5 deg inside it |
| 2 | | `Look` to side B: yaw ∓18..22, far, `head=0.2`, `blink=True` | a 40 deg shift blinks; hold 0.9 to 1.1 s |
| 3 | | `Look` to the viewer, `dist=CAMERA`, `blink=None` | hold 0.8 to 1.0 s |
| 4 | | the eye roll, below | 1.3 to 1.6 s |
| 5 | | `Look` to the viewer from low, `blink=False`; later a flick of 1.5 to 2.5 deg and back; one soft closing `Blink` at least 1.3 s after the slow one | ends on the viewer |

The eye roll, in order (t = its start):
1. **Brows first.** `Brow(t − 0.12, dur ≈ 0.75, amp u(0.35, 0.45))`. No `Lids(widen=...)` at all:
   the lid already follows pitch, and the widening is what made it look startled.
2. **Launch, fast.** `Look(t, yaw A·u(10, 13), pitch u(20, 23), blink=False, head=0.22)`: a saccade.
3. **Over the top, slow.** `Sweep(t + 0.16, dur u(0.45, 0.60), [(A·u(−2, 2), u(25, 27)),
   (−A·u(12, 15), u(17, 20))], head=0.22)`. The head tips back about 5 deg and across with it.
4. **Down and out under a slow blink.** `Look(yaw −A·u(4, 8), pitch −u(12, 15), dist=0.40,
   blink=False, head=0.15)` right after the sweep, with `Blink(same time − 0.03, slow=u(1.8, 2.2))`.
   The lids close while the eyes travel down and open on the lowered gaze.
5. **Hold low** 0.35 to 0.5 s (lid_down follows), then row 5 of the table.

This gives left, right, up and down in one clip.

### A5. Tests
Update the tests these numbers break (`test_head_moves_less_and_later_than_the_eyes`,
`test_idle_sway_size_and_band`, anything on the old `generate`). Add:
- `left`/`right`, seeds 0 to 7: peak |head_yaw| in 4 to 8 deg; |eye_yaw| ≥ 15 deg for ≥ 2 s.
- `generate`, seeds 0 to 7: gaze yaw passes −15 and +15, pitch passes +20 and −10; `widen`
  stays under 0.2 during the roll; peak gaze speed over the top is under half the launch's.
- a `slow=2.0` blink lasts twice as long as a default one; duration ≤ 14.5 s.

Check: `python -m unittest discover tests`, then
`python -m wrapper.gaze --mode <m> --seed 0 --plot outputs/tmp/m13/<m>_curves.png` for all three.
Open the three plots. Commit.

## B. Right pane: both eyes, not one (`wrapper/eyes.py`, maybe `tools/build_scene.py`)

The deck says "both eyes move", and the one-eye pane rides on the head, so it shows a flick and
then an eye looking back at its camera. `cam_move_eyes` (both eyes straight on, world-fixed,
13 cm across) already exists in the scene.

- Add `--pane eye|eyes` (default **eyes**) choosing the second pass of `--camera split`
  (`eyes.py` line 672). Keep `eye` working. Update docstring, `--help`, README row.
- Rebuild the scene first (stage A changed the baked `generate`), then render split stills of
  `left` at frames 1, 40, 60, 150 with both panes (`--quality preview --frames ...`).
- If the brows or the lower lids are cut at any of them, change `MOVE_EYES` in `build_scene.py`
  (width, centre) until brows to cheekbones sit in frame through the head turn, and rebuild.
- In `left` the old 14 deg turn took both eyes into shadow. Say in PROGRESS whether the eyes at
  frame 60 are still readable with the smaller turn. Do not change lights.

The owner picks the pane from these stills, so keep both sets.

## C. Lids follow the eye sideways (`tools/solve_lids.py`, `tools/build_scene.py`, `wrapper/rig.py`)

The riskiest stage. If C is not clean by its checks, revert it and ship A + B.

- Two new keys per side: **`lid_in.S`** (eye turned 25 deg toward the nose) and **`lid_out.S`**
  (25 deg toward the temple), pitch 0. Subject's left eye (`L`, +X): nasal is yaw < 0.
- Solve them like `lid_up` (least-squares line over `FRACTIONS`), with two parts:
  1. **Apex shift.** Per-column rim angles, zero at both corners: columns over the cornea's new
     position open, columns it left close. Upper margin ±0.5 mm at its peak, lower margin
     ±0.3 mm (upper rises / lower drops over the cornea). Starting values; Fable judges them.
  2. **Seat and drape on the yawed globe.** `drape()` and `clearance()` already take `yaw`;
     `pose()` does not, so thread it through. This is what makes the bulge travel under the lid.
  No retract. Same 18 to 30 mm reach fade as the other lid keys.
- `rig.py apply()`: per eye, `nasal = -yaw` for L, `+yaw` for R (degrees, head frame);
  `lid_in = clip(nasal / 25, 0, 1.2) * (1 - b)`, `lid_out = clip(-nasal / 25, 0, 1.2) * (1 - b)`.
  The existing `self.keys.get(k)` guard keeps older scenes working.
- The lash, brow and tear-line carriers copy the head's shape keys by name: make sure the new
  keys reach them.

Checks, all required:
- `tools/check_lids.py` on `id_male_white_9.npz`: no lid skin or lash inside the globe anywhere
  on its pitch × yaw × blink grid, worst clearance no worse than before (compare with the
  committed `outputs/lid_check.json`).
- `tools/rig_strips.py`: `yaw_-30` and `yaw_+30` before and after, side by side, into
  `outputs/tmp/m13/lids/`. Look at them: the lid outline must change shape with the eye, with
  no dent, no step at the corners, no lash through skin.
- `--check-directions --render` unchanged; unit tests pass.

## D. Blink detail (`wrapper/rig.py`, `tools/build_scene.py`) — small, do last

- The brow dips with a blink: `brow_up.S = brow_S − 0.08 * b`. The key's `slider_min` is 0 and
  Blender clamps to it, so set `slider_min = −0.5` for `brow_up.*` on the head and on every
  carrier. Check on a blink strip that the brow drops under 1 mm and the forehead shows no step.
- Nothing else. New GNM expression shapes (cheeks, brow furrow) are out of scope for M13.

## 6. Review pack for Fable (`outputs/tmp/m13/`, git-ignored)

1. The three curve plots from A5.
2. EEVEE drafts of all three for timing only: `--input <m> --quality draft --camera face`, and a
   contact sheet of each built from `outputs/frames/<m>/` with PIL (every 6th frame, frame
   number on each tile). No ffmpeg on this Mac.
3. Cycles preview split stills (`--quality preview --frames`): `left` 1, 36, 40, 60, 150, 165;
   `generate` at the roll's launch, top, mid slow blink, low hold, and one frame of each glance.
4. The lid pairs from C and the blink strip from D.
5. A PROGRESS entry: what was done per stage, every number measured against the targets above,
   what was skipped and why. One line per check, pass or fail.

Then stop. Fable reviews, the owner watches the drafts at speed, and only then previews and finals.

## 7. Out of scope

Finals, packaging, deck, new expression shapes, lighting, textures, the camera move.
