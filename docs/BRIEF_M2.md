# Brief — M2 texture pipeline

Run on the Mac, in this repo. Fable for sections 1–2, Opus 5.5 is fine for 3–5.
Paste everything below the line.

---

You are doing milestone M2. Read `CLAUDE.md`, `docs/REQUIREMENTS.md`, `docs/GNM_FACTS.md`,
the "Skin texture transfer", "Iris and sclera generation" and "UV layout" sections of
`docs/TECH_NOTES.md`, and the latest entry in `docs/PROGRESS.md`.
`git pull --rebase` first; another session is building the rig in `tools/build_scene.py`,
`tools/solve_lids.py` and `wrapper/`. Do not touch those files.

This milestone is worth the most: 60 of 100 points are texture photorealism, and the
judges will wrap our maps on **their own bare GNM head**. Every texture has to look right
there, with no help from our scene.

## 1. Register MakeHuman to GNM once — `tools/register_mh.py`

- Load `assets/third_party/makehuman/base_mesh/base.obj`, keep only the body group, crop
  to head and neck.
- Rough align (scale, rotation, translation) from a dozen landmark pairs. GNM's come from
  the 68 landmarks in `base.npz`; pick the matching MakeHuman vertices once and store
  their indices in `assets/mh_landmarks.json` (committed).
- Fit GNM to the MakeHuman head: alternate closest-point matching with a linear
  least-squares solve for the 170 head identity coefficients (vertices are linear in
  them), landmarks weighted high, a prior on the coefficient norm. 10–20 rounds.
- Final snap: move each GNM skin vertex to the closest MakeHuman surface point whose
  normal agrees, then smooth the offsets. Protect lids, lips, nostrils and ears from
  snapping to the wrong sheet (inner mouth, eye holes).
- Save the wrapped GNM vertices to `assets/gnm/wrapped_to_mh.npz`.
- Check: mean and 95th-percentile GNM-to-MakeHuman distance over the face (report it),
  and an overlay render of both meshes from front and profile that you look at.

## 2. Transfer skins — `tools/transfer_skin.py`

- In Blender, headless: MakeHuman head with a skin and one eyebrow set as source, wrapped
  GNM as target. Cycles bake, Selected to Active, diffuse colour only, with a cage, into
  tile 1001 at 4096². Bake margin 16 px.
- Eyebrows are baked **into** the albedo.
- Fill texels with no source (inside of lids, mouth interior rim, neck cut) by inpainting
  from neighbours. No black or magenta anywhere in the tile.
- Check each result on the **unwrapped GNM template** (not the wrapped one): render front,
  three-quarter, profile and back with plain lighting. Look for: the lip line on the lip
  edge loop, brows above the orbit, nostril shading in the nostrils, no smear on the ears,
  no visible seam at the back of the head or behind the ears.

## 3. Detail maps — `tools/detail_maps.py`

- Pore-scale normal map for tile 1001 at 4096², procedural, stronger on nose and cheeks,
  finer on forehead, none on lips (lips get fine vertical creases instead). Compensate
  for UV stretch so pores stay round on the surface.
- Roughness map at 2048²: shinier on the nose, forehead and lips; duller on cheeks.
- These are shared across identities with small per-set variation.

## 4. Eyes — `tools/make_iris.py`

- First measure, from `base.npz`, the UV radius of the pupil edge, the iris edge (limbus)
  and the sclera extent in the eye-interior tile, using the `pupils`, `irises` and
  `scleras` vertex groups. Write them to `assets/gnm/eye_uv.json` and into `GNM_FACTS.md`.
- Generate tile 1002 (left) and 1004 (right) at 2048² following the recipe in
  TECH_NOTES: fibres, collarette, crypts, limbal ring, pupil ruff, sclera with veins and a
  warm tint toward the corners. The pupil disc is near-black; GNM moves its edge as geometry.
- Left and right share colour and structure parameters and use different seeds.
- Palette weighted toward browns. One set each of hazel, green, blue and grey is enough.
- Look at every iris at full resolution and at the size it has in a 1024² face render.

## 5. Assemble 8 sets — `tools/build_textures.py`

`textures/tex_01 … tex_08`, each with the files listed under "What we ship per texture
set" in TECH_NOTES, a `preview.png` (the set on the GNM template, front view) and a
`set.json` recording the source skin, eyebrow set, iris seed and colour, and the GNM
identity sampler settings (gender, ethnicity, seed) it is paired with for stills.

Pick plain skins only (no tattoos, no make-up) and spread them across skin tone, sex and
apparent age. Each PNG must stay under 50 MB; use 8-bit PNG.

## Done when

- 8 sets exist, each previewed and looked at on the GNM template from four angles
- The transfer residual and the eye UV radii are in `docs/PROGRESS.md`
- A contact sheet `outputs/stills/texture_sheet.png` of all 8 previews is committed
- Everything is committed and pushed (textures yes, third-party packs no)

If a skin transfers badly, drop it and use another rather than hand-fixing it. If the
registration itself is the problem, fix the registration: every set depends on it.
