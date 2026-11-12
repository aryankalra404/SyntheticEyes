# Progress

Newest entry first. One entry per working session: what changed, what was measured,
what the next session needs to know.

## Status

| Milestone | State |
|---|---|
| M0 Setup and spikes | done |
| M1 Rig and calibrated wrapper | not started |
| M2 Texture pipeline | not started |
| M3 Look | not started |
| M4 Motion | gaze engine done and tested; rig adapter, bake and videos pending |
| M5 Compliance and packaging | not started |
| M6 Ship | not started |

## Open questions

- Does the DRM-locked `Evaluation_for_SyntheticEyes.pptx` differ from `_1.pptx`?
- What does the second reference video (youtu.be/TAZIvyAJfeM) show?
- College and team name for the zip and deck (`CollegeName_TeamName`)

## Log

### Thu 12 Nov 2026 — gaze engine (part of M4, done early)
Written and tested in a cloud session with no Blender, so nothing here has been seen on the head yet.
- `wrapper/gaze/`: pure numpy, Python 3.11 syntax, no bpy. `generate(mode, seed)` returns a
  `Track` with 15 channels (listed in the `engine.py` docstring) on a 1 kHz clock;
  `track.frames(fps)` gives one dict per frame.
- Model: saccades on the main sequence (5° 31 ms, 10° 42 ms, 30° peaks about 550°/s),
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
