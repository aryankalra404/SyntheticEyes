# Brief — M3 look

Run on the Mac, in this repo, with Fable. Needs M1's `scene.blend` and `tools/build_scene.py`,
and at least one texture set from M2. Paste everything below the line.

## Status 13 Nov, night (Opus): mechanical parts built, look not started

**Built** (rebuild: `python3 tools/carry_hair.py`, then `$BLENDER -b --factory-startup -P tools/build_scene.py`)
- Section 1: `tools/look_shots.py` renders `face` (`cam_test_face`, 85 mm, forehead to chin) and
  `eye` (`cam_test_eye`, subject's left eye from 30° to that side, 5° up, 100 mm at 11 cm) at gaze
  centre and 20° toward image right into `outputs/tmp/m3/current/`; the run before moves to
  `previous/`, and `pairs/` shows previous | current. `--blink` renders the eye shot at blink
  0, 0.5, 1.0 into `outputs/tmp/m3/blink/`. 16 s per 1024² frame at 128 spp (Metal).
- Texture hookup: skin and both eye-interior materials have image nodes `tex_albedo`,
  `tex_normal`, `tex_rough`, `tex_eye` on the UDIM UVs, filled from `textures/tex_NN` by
  `wrapper/eyes.py use_texture` (`--texture NN`; build default 01). Paths relative, nothing packed.
  `use_texture` also shows the brow hair object named in the set's `set.json` and sets its colour.
- Section 3: lashes (Mindfront eyelashes 01) and the three Mindfront strand brow sets carried
  through `wrapped_to_mh.npz` (`tools/carry_hair.py` → `assets/gnm/hair_binding.npz`). Lashes bind
  per root triangle, brows per point. Each is a hidden carrier mesh with the head's shape keys
  (driven by the head key of the same name) and bone weights, plus a Curves object that reads it
  through Object Info and renders as Cycles hair. (Curves made by a modifier on a mesh object do
  not render in Cycles 4.5; that is why the carrier is separate.)
- Section 2, geometry only: `tear_line.L/R`, a 3-row strip along the lower lid from inner to
  outer corner: lid row between the socket rim and the next ring in, globe row 0.35 mm up the
  globe (tapered to 0 at the corners), middle row sunk 0.1 mm. Follows the lid keys the same way.
  Material is the brief's spec only: Principled, transmission 1, roughness 0, IOR 1.34.

**Stand-ins / plain defaults** (Fable judges all of these): skin is plain Principled (no
subsurface); eye interior specular 0.1 / roughness 0.6 as in M1; cornea is M1's; hair is a
default Principled Hair BSDF with direct colour; lighting, HDRI and AgX are M1's; lid shapes are
still M1's stand-ins.

**Fable must judge / fix**
- Lashes: 27 strays rooted more than 1.5 mm from the skin are dropped (`ROOT_MAX` in
  `carry_hair.py`; one stood up as a spike in every eye shot). A tuft at the outer corner still
  hangs down, visible at blink 1.0; the lower set is long and dense for the MakeHuman set.
  Try `mindfront_eyelashes_02…05`, or trim lower lashes by length in `carry_hair.py`.
- At blink 1.0 the lower lashes disappear under the closing upper lid (stand-in blink overlaps
  the lower lid). Recheck with the solved lids.
- Brow hair sits a median 0.9–1.3 mm off the skin (MakeHuman's strands do); hair plus the painted
  brow may read too heavy. Consider flattening the normal offset or thinning.
- Tear line: built and following the keys, but invisible at the test-shot size with this
  material; needs wetness/shading work and a close look.
- Section 6 is built: `python3 tools/render_stills.py` exports each set's `gnm_identity` with
  `export_gnm.py` (→ `assets/gnm/id_<gender>_<ethnicity>_<seed>.npz`, cached), builds a scene for
  it with `build_scene.py --npz ... --no-bake --texture NN` (`outputs/tmp/m3/scenes/`, rebuilt when
  the builder or the hair binding changes), and renders `outputs/stills/tex_NN.png` and
  `outputs/stills/eye/tex_NN_eye.png` through `look_shots.py --still`, plus
  `outputs/stills/eye/sheet.png`. About 1 min per set. All 9 sets looked at. Rerun it after
  every look change; the stills in the repo are plain-default placeholders.

---

You are doing milestone M3. Read `CLAUDE.md`, `docs/REQUIREMENTS.md`, the "Reference bar" and
"Shading recipe" sections of `docs/TECH_NOTES.md`, `docs/GNM_FACTS.md` and the latest entries
in `docs/PROGRESS.md`. `git pull --rebase` first. Materials, lights and extra eye geometry go
into `tools/build_scene.py`; do not change the rig, the shape keys or `wrapper/`.

The organisers' two reference videos set the bar. Open both at the timestamps listed in
TECH_NOTES before you start, and again whenever you compare a render. "Eye Piece" at 0:11 is
the target for the eye; "Flexpressions" at 0:16 and 0:22 is the target for surface relief.

The whole face is judged (60 points for texture), and the eye is where the judges will look
longest. Work in this order and stop to look after each step.

**Hero set: `tex_09`** (added 13 Nov). Its skin colour is photographed (the Infinite head scan)
and its relief comes from the same skin, so it is the most real of the sets. Tune the look on
it first, use it for the three videos and the main still, then check the other sets under the
same settings. Its eyebrows are in the colour map; hair-curve brows for it should follow that
shape, or be left off if they fight it.

## 1. Two test shots, fixed for the whole milestone

- `face`: whole face, forehead to chin, 1024².
- `eye`: close on the subject's left eye, three-quarter, about the crop of "Eye Piece" at 0:11.
Render both after every change, at gaze centre and at 20° to the side. Keep the previous
pair to compare against. Put them in `outputs/tmp/m3/`.

## 2. Wet eye

This is what "Eye Piece" gets most of its realism from, and we have none of it.
- **Tear line**: a thin strip of geometry along the lower lid margin, bridging lid and globe,
  clear and glossy (IOR about 1.34). Built from the lower margin rows
  (`gnm_core.lid_margins`), as a shape that follows the lid shape keys.
- **Lid margins**: lower roughness and a slight coat on the margin band, so it glints.
- **Inner corner**: the caruncle and the inside of the lids are pink-red wet tissue, not skin.
  The lid pocket in the albedo is currently filled with skin tone by `tools/transfer_skin.py`;
  either tint it there or in the shader by vertex group (`eye_sockets`).
- **Cornea**: clear refractive shell, IOR 1.376, roughness 0, transparent to shadow rays so
  the iris is lit. Check the catchlight is sharp and sits on the cornea, not the iris.
- **Sclera**: light subsurface, slightly glossy, a soft shadow under the upper lid.

## 3. Lashes

MakeHuman eyelashes (`assets/third_party/makehuman/eyelashes01/` or the system set), CC0.
- Fit them to the MakeHuman base with `mh_core.load_proxy`.
- Carry them to GNM through the M2 registration: `assets/gnm/wrapped_to_mh.npz` holds GNM's
  skin lying on the MakeHuman head. For each lash vertex, find the closest wrapped GNM
  triangle, store its barycentric weights and its offset along the normal, then rebuild the
  lash on the GNM template (and on any identity) from the same triangle.
- Bind the lashes to the head so they follow the blink and lid-follow shape keys
  (the stored triangle binding is enough; evaluate it per frame or bake it as shape keys).
- Upper and lower lids. Dark, thin, slightly glossy. Check for lashes passing through the lid
  at blink 1.0.
- **Brows as hair too.** Carry a Mindfront strand eyebrow set the same way and render it as
  hair curves over the painted brows. The painted brows stay in the albedo, softened, because
  the judges wrap the textures on a bare head with no hair.

## 4. Skin

- Principled BSDF with subsurface, red-dominant radius at millimetre scale. Albedo, normal
  and roughness from the texture set.
- Lips: lower roughness, a little coat. Eyelid skin: thinner, so a touch more subsurface.
- **Grey check**: swap the albedo for mid-grey and render both shots. Pores and lip creases
  must already be visible from the normal and roughness maps alone. If they are not, the
  detail maps are too weak; fix them in `tools/detail_maps.py`, not in the shader.

## 5. Light

- The CC0 studio HDRI for fill and reflections, plus one large soft key placed so a window
  catchlight lands in the upper outer quadrant of each cornea.
- Same lighting for all texture sets and for the 10 clockwise renders.
- AgX view transform. Check the darkest skin set is not crushed and the lightest not clipped.
- For the `eye` shot and the eye inset in the videos: dark background, the key from the
  side, shallow depth of field focused on the iris. Much of how "Eye Piece" reads as a
  photograph is this, not the textures. The 10 clockwise renders keep the plain constant light.

## 6. Stills

For each texture set: one whole-face still and one eye close-up, each set paired with the GNM
identity named in its `set.json`. Whole-face stills go to `outputs/stills/`.

## Done when

- The `eye` shot holds up next to "Eye Piece" at 0:11 at the same crop: wet margin, tear
  line, lashes, catchlight, a sclera that is not white
- The grey check shows pores and lip creases
- No seam on any whole-face still: look at the hairline, behind the ears, the neck
- Every set also passes the wrap test from `tools/check_detail.py` (bare template, plain
  material, no hair, no tear line): this is what the judges see when they apply our maps
- Blink at 0, 0.5 and 1.0 with lashes and tear line: nothing pokes through
- Render time per 1024² frame is measured again and written in `docs/PROGRESS.md`; the three
  videos are about 900 frames, so say what the full set will cost
- Everything is committed and pushed

Not in scope: wrinkle maps driven by expressions. That is a stretch item after M5.
