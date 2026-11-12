# Progress

Newest entry first. One entry per working session: what changed, what was measured,
what the next session needs to know.

## Status

| Milestone | State |
|---|---|
| M0 Setup and spikes | mostly done; blink spike blocked (GNM package not installed yet) |
| M1 Rig and calibrated wrapper | not started |
| M2 Texture pipeline | not started |
| M3 Look | not started |
| M4 Motion | not started |
| M5 Compliance and packaging | not started |
| M6 Ship | not started |

## Open questions

- Does the DRM-locked `Evaluation_for_SyntheticEyes.pptx` differ from `_1.pptx`?
- What does the second reference video (youtu.be/TAZIvyAJfeM) show?
- College and team name for the zip and deck (`CollegeName_TeamName`)
- Does `WINK_LEFT` close the subject's left (+X) eye, and does its eye-region part close the lid
  at weight 1.0? (blink spike, pending)

## Log

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
  (19.3 MB, byte-identical across runs). `--identity-seed`, `--identity-scale`; `--gender` /
  `--ethnicity` import GNM's IdentitySampler (needs the package, untested).
- `tools/smoke_render.py`: mesh with `UDIM` + `legacy` UV layers, 4-bone armature from GNM
  joints and skin weights, shape keys from any `delta_*`, camera 40 cm in front of the eye
  midpoint, one area light, Cycles on Metal GPU, OIDN. Debug materials: transparent cornea
  shell, dark iris and pupil, so gaze reads by eye.
- Renders in `outputs/spike/` (git-ignored), all looked at: `neutral`, `gaze_left15`,
  `gaze_up15` and `id_seed3/neutral`. Gaze is correct by eye and in numbers: 15° left moves
  both pupils −12.2 px in x, 15° up moves them −12.2 px in y (up in the image). Eyeballs turn
  about their centres (radius change 1e-17 m, no skin vertex moves).
- MakeHuman Skins 01, Skins 02, Eyebrows 01, Eyelashes 01, system assets, `base.obj`, and the
  Poly Haven `brown_photostudio_02` 2K HDRI downloaded; URLs and CC0 checks in TECH_NOTES.

**Benchmark** (M4 10-core, 24 GB; Metal GPU; 1024², OIDN, adaptive sampling; grey scene;
best of 2 after a warm-up frame): **64 spp 3.8 s · 128 spp 4.4 s · 256 spp 4.9 s**. Most of that
is per-frame overhead, not sampling. The first frame of a session takes about 46 s while
Metal kernels compile. Re-measure once skin has subsurface.

**Blocked: blink spike (task 5) and the two lid-closed renders.** Claude Code's auto-mode
safety check refused `pip install -e assets/third_party/gnm/gnm/shape` (it installs and runs
code from an external repo, plus TensorFlow). The ExpressionSampler loads Keras `.h5`
decoders, so the spike cannot run without that install. No workaround was built.
`tools/spike_blink.py` is written but **untested**. To finish:

    uv pip install --python .venv-gnm/bin/python -e assets/third_party/gnm/gnm/shape
    .venv-gnm/bin/python tools/spike_blink.py      # writes expr_*.npy + blink_spike.json
    .venv-gnm/bin/python tools/export_gnm.py       # adds delta_blink_L/R, brow_up, squint
    $BLENDER -b --factory-startup -P tools/smoke_render.py   # adds blink_L.png, blink_R.png

The lid-gap measure is ready and checked at rest: **8.34 mm left, 8.36 mm right** (column
through the pupil, front rim of `eye_sockets`).

**Surprises / for M1**
- Subject's left eye is at +X, so it appears on **image right**. `left` input (image-left)
  turns both eyes toward the subject's right (−X). Yaw toward image-left is −Z rotation in
  Blender after the `(x, y, z) → (x, −z, y)` axis swap.
- Pose correctives are all zero, so Blender's armature + LBS matches GNM exactly. Bone
  orientations are identity; eye bones in `smoke_render.py` point forward (−Y).
- The upper lid does not follow pitch: at 15° up the iris tucks under the lid. M1's lid driver
  is needed.
- A unit-Gaussian identity (`--identity-seed 3`) looks like a face, but the ears sink into the
  head. Use the IdentitySampler, or scale ≤ 0.5, for identities.

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
