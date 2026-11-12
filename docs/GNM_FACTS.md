# GNM facts

Measured on 12 Nov 2026 from the real weights, not from memory.

- Weights: `~/.cache/gnm/models/v3_0/gnm_head.npz`, downloaded from
  `https://huggingface.co/google/gnm-v3/resolve/main/v3_0/gnm_head.npz`
  (the same URL and cache path `GNM.from_remote` uses). 53.3 MB,
  sha256 `61d78bbfb4ad8e0b38495804a4caef3214d3df00f8c3f68761e63b41ce3747eb`, `version` = `3.0`.
- Source read: google/GNM at commit `846ab76` (`gnm_xnp.py`, `gnm_common.py`, `gnm_udim.py`,
  `gnm_landmarks.py`, `semantic_sampler.py`, `oss_data_loaders.py`).
- Read with plain numpy (`allow_pickle=False`) via `tools/gnm_core.py`. Checked against the
  installed GNM package (TensorFlow 2.21): with random identity, expression and pose,
  `gnm_core.lbs` matches `GNM.__call__` to 4.5e-8 m, and UDIM tiles and UVs match exactly.

## Mesh

| | |
|---|---|
| Vertices | 17,821 |
| Quads | 17,662 |
| Triangles | 35,324 (each quad split in two) |
| Mesh components | `skin, left_eye, right_eye, upper_teeth_and_gums, lower_teeth_and_gums, tongue` |

## Units and axes

- **Metres.** Template bounding box 0.255 × 0.342 × 0.239 m (x × y × z).
- **+Y up, +Z forward** (out of the face), **subject's left eye at +X**.
- A camera in front looking back along −Z sees +X on **image right**, so the subject's left
  eye is on the right of the image (normal mirror view).
- Blender is +Z up, so `tools/smoke_render.py` maps GNM `(x, y, z)` → Blender `(x, −z, y)`;
  the face then looks along Blender −Y.

## Joints

| Index | Name | Parent | Rest position (m) |
|---|---|---|---|
| 0 | `neck` | −1 (root) | (−0.00008, 0.13382, −0.00686) |
| 1 | `head` | 0 | (−0.00004, 0.20993, 0.01756) |
| 2 | `left_eye` | 1 | (0.03084, 0.30316, 0.09889) |
| 3 | `right_eye` | 1 | (−0.03087, 0.30311, 0.09898) |

- **Order is `neck, head, left_eye, right_eye`** (TECH_NOTES had it reversed).
- Eye joint distance: **61.7 mm**. Eye midpoint ≈ (−0.00001, 0.30314, 0.09893).
- `bone_aligned_template_joint_orientations` are all identity.
- Rotations are axis-angle in the **world frame**, applied by forward kinematics
  `T_world[i] = T_world[parent] @ T_local[i]`, then plain linear blend skinning
  (`gnm_common.linear_blend_skinning`). `tools/gnm_core.lbs` reproduces it.
- `pose_correctives_regressor` (36 × 53,463) is **all zeros** in v3.0, so posing is pure LBS.
- `joint_regressor` (4 × V) exists; joints for an identity come from `joint_identity_basis`.
- Skinning weights sum to 1. Non-zero counts: neck 5,839, head 16,022, left_eye 771,
  right_eye 771. Each eyeball is rigidly bound to its eye joint. Rotating an eye 15° changes
  no vertex's distance to the joint (max 1e-17 m) and moves no skin vertex.

## Eyes

- Eyeball vertex distance from the joint: min 12.8, median **14.58**, max 16.2 mm (cornea apex
  along +Z).
- Pupil centre (mean of `pupils` ∩ eye) at rest: left (0.03085, 0.30309, 0.11175), right
  (−0.03090, 0.30304, 0.11184), i.e. 12.9 mm in front of the joint.
- Projected at 40 cm, 50 mm lens, 36 mm sensor, 1024²: pupils at x ≈ 625 (left eye) and
  398 (right eye), y ≈ 512. A 15° eye rotation moves a pupil about 12.2 px.
- Lid gap at rest (column through the pupil, front rim of `eye_sockets`): **8.34 mm left,
  8.36 mm right**. Upper margin ≈ +3.0 mm above the pupil centre, lower ≈ −5.9 mm below.

## Identity: 253 coefficients

| Range | Names | Count |
|---|---|---|
| 0–169 | `head_000…169` | 170 |
| 170–172 | `eyes_000…002` | 3 |
| 173–252 | `teeth_000…079` | 80 |

A unit coefficient on the first head components moves vertices up to ~9 mm. A plain
N(0, 1) draw on all 170 head coefficients (`export_gnm.py --identity-seed 3`) gives a believable
face but the **ears collapse into the head**, so N(0, 1) is not the model's prior. The
IdentitySampler (`--gender female --ethnicity asian --identity-seed 3`) gives a larger vector
(|c| = 25.6 vs 13.6) with intact ears, so the problem is direction, not scale. Use the
sampler for identities.

## Expression: 383 coefficients

| Range | Names | Count | Vertices moved |
|---|---|---|---|
| 0–99 | `left_eye_region_000…099` | 100 | 1,694 (mean x +0.031, subject's left) |
| 100–199 | `right_eye_region_000…099` | 100 | 1,694 (mean x −0.031) |
| 200–349 | `lower_face_region_000…149` | 150 | 6,519 |
| 350 | `tongue_mean` | 1 | |
| 351–381 | `tongue_000…030` | 31 | |
| 382 | `pupils_000` | 1 | 279 (96 in `pupils`) |

TECH_NOTES' "32 tongue" is `tongue_mean` + 31 components. Several eye components are near zero
(e.g. index 99 moves < 0.1 mm per unit).

## Vertex groups (46, float weights; "member" = weight > 1e-4 as in GNM)

| Group | Members | Group | Members |
|---|---|---|---|
| skin | 12,466 | eyes | 1,542 |
| skin_exterior | 11,460 | left_eye / right_eye | 771 / 771 |
| left / right | 9,068 / 9,068 | eye_sockets | 608 |
| hockey_mask | 4,592 | eye_interiors | 770 |
| upper_lip / lower_lip | 145 / 145 | eye_exteriors | 772 |
| mouth_sock | 406 | scleras | 480 |
| tongue | 933 | irises | 290 |
| gums | 1,404 | pupils | 98 |
| teeth | 1,868 | ears | 1,054 |
| upper_teeth_and_gums | 1,440 | expression_basis_left_eye / right_eye | 1,919 / 1,919 |
| lower_teeth_and_gums | 1,440 | expression_basis_mouth_nose_ears | 8,495 |
| forehead_region | 371 | nose_region | 889 |
| left/middle/right_brow_region | 152 / 110 / 152 | left/right_temple_region | 62 / 62 |
| left/right_orbital_region | 668 / 668 | left/right_zygomatic_region | 105 / 105 |
| left/right_parotid_region | 125 / 125 | left/right_infraorbital_region | 142 / 142 |
| left/right_cheek_region | 182 / 182 | upper_lip_region / lower_lip_region | 338 / 372 |
| chin_region | 136 | | |

`eye_sockets` is the skin pocket wrapping behind the eyeball (up to 9.5 mm deep). Its forward
rows are the lid margins, which is what `gnm_core.lid_margins` uses.

## UV layout

- The weights hold only legacy `quad_uvs` / `triangle_uvs`, in [0.005, 0.998]². The UDIM layout is
  computed: a face whose vertices are all in a region gets that tile, then u += (tile − 1001).
- Tile assignment (quads): 1001 skin 12,410 · 1002 left eye interior 372 · 1003 left eye
  exterior 384 · 1004 right eye interior 372 · 1005 right eye exterior 384 ·
  1006 teeth and gums 2,828 · 1007 tongue 912. No quad is unassigned or claimed twice.
- Tiles 1002–1007 sit on the first row, so the UDIM u range is 0–7 and v stays in 0–1.

## Eye-interior UV (tiles 1002 and 1004)

Measured 13 Nov 2026 by `tools/make_iris.py --measure` on the template; the numbers are in
`assets/gnm/eye_uv.json` (committed). Both eyes are identical in UV.

- The tile is a disc of concentric vertex rings centred on **(0.5, 0.5)**: one centre vertex,
  two 12-vertex rings, then fifteen 24-vertex rings. Legacy eye UVs equal the UDIM ones minus
  the tile offset.
- **+u points to the subject's left (+X) and +v up, for both eyes.** So the nasal corner is at
  −u in tile 1002 (left eye) and +u in tile 1004 (right eye).

| Edge | UV radius | 3D radius from the eye axis | Group membership |
|---|---|---|---|
| Pupil edge | **0.0499** | 2.60 mm | last ring in `pupils` |
| Iris outer ring | 0.1849 | 5.23 mm | last ring in `irises` only |
| Sclera inner ring | 0.1912 | 5.44 mm | first ring in `scleras` |
| Limbus (midpoint, used for texturing) | **0.1881** | 5.34 mm | |
| Sclera extent | **0.4608** | 13.3 mm, 5.7 mm behind the equator | last ring in `scleras` |

- `pupils` rings are also in `irises` (weight 1 in both); the pupil edge is the outermost ring
  with non-zero `pupils` weight. At 2048² the pupil edge is 102 px from the centre and the
  limbus 385 px.
- Across the iris, UV radius is close to linear in 3D radius (about 19.5 mm per UV unit);
  across the sclera it is not (the rings follow the globe round to the back).
- `pupils_000` moves the pupil-edge ring 0.86 mm per unit, the next ring 0.55 mm and fades to
  zero at the limbus. The texture follows the mesh, so the dark disc stays on the pupil edge
  whatever the dilation.
- Rest-pose lid opening seen from the front, as UV radius from the centre: upper lid about
  0.055 (it covers the top of the iris), lower lid about 0.19, corners 0.27–0.38. Stored per
  5° in `eye_uv.json` (`lid_opening`); `make_iris.py` darkens the sclera beyond it.

## Landmarks

`gnm/shape/data/landmarks/head_sparse_68.txt`: 68 rows of three (vertex index, barycentric
weight) pairs. Landmark = Σ w·v over the three vertices. Exported as `landmark_indices`
(68 × 3) and `landmark_weights` (68 × 3).

## Samplers

- `ExpressionSampler` / `IdentitySampler` load Keras `.h5` decoders
  (`data/semantic_sampler/*.h5`) with `tf.keras.models.load_model`. They are seeded through
  `rng=np.random.default_rng(seed)` and draw latent `z ~ N(0, I)`.
- Expression classes 0–19: SURPRISE, DISGUST, SUCK, COMPRESS_FACE, STRETCH_FACE, HAPPY,
  SQUINT, PLATYSMA, BLOW, FUNNELER, SMILE_WIDE, CORNERS_DOWN, PUCKER, WINK_LEFT, WINK_RIGHT,
  MOUTH_LEFT, MOUTH_RIGHT, LIPS_ROLL_IN, SNARL, TONGUE_CENTER.
- Identity classes: Gender FEMALE 0 / MALE 1; Ethnicity MIDDLE_EASTERN 0, ASIAN 1, WHITE 2,
  BLACK 3.
- WINK_LEFT closes the **subject's left (+X)** eye, WINK_RIGHT the right (confirmed by the
  spike). A full wink also half-closes the other eye, so keep one side's coefficients only.

## Lid shapes (tools/spike_blink.py, 64 samples, seed 0)

Lid gap in mm, column through the pupil:

| Shape | Weight 0 | 0.5 | 1.0 | Scale that closes (≤ 0.2 mm) |
|---|---|---|---|---|
| blink_L (left gap) | 8.34 | 5.33 | 2.32 | **1.40** |
| blink_R (right gap) | 8.36 | 5.30 | 2.23 | **1.35** |
| full WINK_LEFT | L 2.32, R 6.68 at 1.0 | | | |
| brow_up (SURPRISE eye regions) | | | L 8.58, R 8.60 | |
| squint | | | L 3.37, R 3.27 | |

The eye-region-only vectors move no eyeball vertex and nothing in the lip/chin regions
(max displacement 5.6 mm). Rendered at the closing scale the lid shuts cleanly with no cornea
poking through and only a faint crease at the outer corner. At 1.0 a thin slit stays open.
The averaged vector is weaker than a single wink sample, so M1 should either bake the scale
into `blink.L/R` or solve the lid coefficients directly.

## base.npz (tools/export_gnm.py)

`vertices` (identity applied), `template_vertices`, `identity`, `quads`, `triangles`,
`quad_uvs`, `quad_uvs_udim`, `quad_udim_tiles`, `triangle_uvs`, `triangle_uvs_udim`,
`triangle_udim_tiles`, `joint_names`, `joint_positions`, `joint_parents`, `skinning_weights`,
`vertex_group_names`, `vertex_group_weights`, `vertex_group_masks`, `mirror_indices`,
`landmark_indices`, `landmark_weights`, `expression_names`, `expression_basis` (full 383),
`model_sha256`, `model_version`, `coordinates`, plus `expr_*` / `delta_*` for blink_L,
blink_R, brow_up and squint once the spike has run. All in GNM coordinates. The file is 19.3 MB
and byte-identical across runs (fixed zip timestamps).
