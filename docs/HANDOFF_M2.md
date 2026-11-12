# Handoff — M2 sections 1 and 2 (registration, skin transfer)

Written Thu 12 Nov 2026 by a session that ran out of usage before writing any pipeline code.
**Delete this file when sections 1 and 2 are committed** (or update it if you also stop early).
The brief is `docs/BRIEF_M2.md`. The owner's instruction for this run: do sections 1 and 2,
commit and push, then stop, report the transfer residual and show the four-angle check
renders for the first skin. Do not start sections 3 to 5 until told.

## State

- Nothing from M2 is in the repo yet: no `tools/register_mh.py`, no `tools/transfer_skin.py`,
  no `assets/mh_landmarks.json`. Only exploration was done.
- Scratch helpers (a numpy z-buffer rasteriser for looking at meshes, and view scripts) are
  in `outputs/tmp/m2/` (git-ignored, this Mac only). Use or ignore.

## Facts measured this session

**Python.** `.venv-gnm` (3.13) has numpy, scipy, PIL, cv2, trimesh, no matplotlib and no pip.
System `python3` (3.13) has numpy, scipy, matplotlib, PIL, no cv2. Blender's Python has numpy
only. So `register_mh.py` can use numpy + scipy; anything run by Blender must be numpy only.

**MakeHuman `base.obj`.**
- Units are decimetres, +Y up, +Z forward, subject's left at +X: same axes as GNM, scale ≈ 0.1.
- `g body` is vertices 0–13379, 13,378 quads. Everything else is helpers and joint cubes.
- Joint cubes (mean of the cube): `joint-l-eye` (0.308, 7.284, 1.245), `joint-r-eye` mirrored,
  so eye distance is 61.6 mm against GNM's 61.7 mm. `joint-head` (0, 6.975, 0.161),
  `joint-neck` (0, 5.89, 0.068), `joint-jaw` (0, 6.191, 1.425).
- The body has **no holes** at the eyes or mouth: lids fold into closed socket pockets and the
  lips into a mouth cavity. Those inner sheets are what the snap must not land on.
- Eyeball helpers are `helper-l-eye` / `helper-r-eye` (vertices 14598–14741).
- GNM's skin reaches down to y = 0.066 m (a bib over the upper chest, ±0.128 m wide), 23.7 cm
  below the eyes. Crop MakeHuman at about y > 4.5 and |x| < 1.7 so the source covers it.

**GNM landmarks.** The 68 are the standard iBUG layout: jaw 0–16, brows 17–26, nose 27–35,
right eye 36–41, left eye 42–47, outer lip 48–59, inner lip 60–67. Eye points sit on the lid
margin, 48–59 on the vermilion border of the `upper_lip` / `lower_lip` groups. The template's
lips are slightly parted, like MakeHuman's.

**Skins.** All 2048². Skins 01 (23 female), Skins 02 (13 male, three files are NRM/SPEC maps),
plus 17 more in `makehuman_system_assets/skins/` (young/middle-aged/old × caucasian/asian/
african × both sexes), which widens the skin-tone spread for section 5. The socket interior is
painted red in the skins, and some have stubble painted on the scalp.

**Eyebrows.** Two kinds:
- `makehuman_system_assets/eyebrows/eyebrow001…012`: small cards (124 vertices) with an alpha PNG.
- `eyebrows01/mindfront_eyebrows_01…14`: real strand geometry (about 9,500 vertices), black
  diffuse, **no texture**. Baked at 4096² these give individual hairs.
The `.obj` of each is already in base-mesh space, so no `.mhclo` fitting is needed on the
unmodified base mesh.

## Design decided, not yet built

**`tools/register_mh.py`** (plain Python, numpy + scipy, `gnm_core.load_model()` for the
identity basis; base.npz does not carry it).
1. Landmarks. Reading vertex numbers off a plot does not work around the eyes (several sheets
   overlap). Pick points in a front or side view of the textured head instead, ray-cast each
   onto the front-most body surface and store it as three vertex indices plus barycentric
   weights, the same format as GNM's `head_sparse_68.txt`. Pick the subject's left side and
   mirror. Wanted: eye corners and two upper and two lower lid points per eye (at the same x
   fractions as GNM's 37/38/40/41), nasion, nose tip, subnasale, alar bases, mouth corners,
   mid upper and lower vermilion, inner lip midpoints, brow inner/peak/outer taken from where
   the eyebrow asset sits, chin. Jaw points at low weight. Ears have no landmark in the 68, so
   add extremes (top, lobe, rearmost, outermost) of GNM's `ears` group and of the MakeHuman ear.
2. Similarity align from those pairs, then 10–20 rounds of closest-point + least squares on the
   170 head coefficients, landmarks weighted high, norm prior, re-estimating the similarity
   each round. Leave `eye_sockets` and `mouth_sock` out of the data term.
3. Final snap as a sparse solve: offsets d minimise Σ wᵢ|dᵢ − tᵢ|² + λ|L d|² + landmark term,
   with wᵢ = 0 where the closest point's normal disagrees or the vertex is in a protected
   region (lid pocket, mouth sock, nostril interior, ear folds). Protected areas then follow
   their neighbours instead of jumping to the wrong sheet. A few passes with falling λ.
4. Save `assets/gnm/wrapped_to_mh.npz` with the wrapped vertices and the MakeHuman → GNM
   similarity, so the transfer script can place the source in the same frame.
5. Report mean and 95th-percentile distance over `hockey_mask`; render overlay and a distance
   heat map, front and profile, and look at them.

**`tools/transfer_skin.py`** (Blender headless, numpy only).
- Bake into 32-bit float images and convert to sRGB 8-bit in numpy, so compositing is linear.
- Cycles bake does not see through alpha, so brows cannot be baked in one pass. Bake three:
  skin colour (Selected to Active, diffuse colour, cage extrusion of a few mm), brow colour,
  brow coverage; then albedo = skin·(1 − a) + brow. For card brows leave the image Alpha socket
  unlinked on the colour pass so the colour stays premultiplied. For strand brows the coverage
  is the hit mask and the colour is a per-set hair colour.
- Bake a hit mask (white emission on the source) to find texels with no source, and also mark
  texels of `eye_sockets` / `mouth_sock` faces as no-source whatever they hit.
- Fill no-source texels and everything outside the islands with a push-pull pyramid in numpy
  (cv2 is not available inside Blender). Bake margin 16 px as the brief says.
- Checks render on `template_vertices` from `base.npz`, four angles, plain light. Put them in
  `outputs/tmp/m2/` and send the sheet to the owner.

## Rules that still apply

`git pull --rebase` before each push. Do not touch `tools/build_scene.py`, `tools/solve_lids.py`
or `wrapper/`. One-line plain commit messages, no AI attribution. Add to `docs/PROGRESS.md`
only under an M2 entry, including the transfer residual.
