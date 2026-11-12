# Progress

Newest entry first. One entry per working session: what changed, what was measured,
what the next session needs to know.

## Status

| Milestone | State |
|---|---|
| M0 Setup and spikes | done |
| M1 Rig and calibrated wrapper | not started |
| M2 Texture pipeline | sections 1–4 done (registration, skin transfer, detail maps, eyes); the 8 sets (section 5) pending |
| M3 Look | not started |
| M4 Motion | gaze engine done and tested; rig adapter, bake and videos pending |
| M5 Compliance and packaging | not started |
| M6 Ship | not started |

## Open questions

- College and team name for the zip and deck (`CollegeName_TeamName`)

## Log

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
