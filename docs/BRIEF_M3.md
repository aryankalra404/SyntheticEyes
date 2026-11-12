# Brief — M3 look

Run on the Mac, in this repo, with Fable. Needs M1's `scene.blend` and `tools/build_scene.py`,
and at least one texture set from M2. Paste everything below the line.

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

## 6. Stills

For each texture set: one whole-face still and one eye close-up, each set paired with the GNM
identity named in its `set.json`. Whole-face stills go to `outputs/stills/`.

## Done when

- The `eye` shot holds up next to "Eye Piece" at 0:11 at the same crop: wet margin, tear
  line, lashes, catchlight, a sclera that is not white
- The grey check shows pores and lip creases
- No seam on any whole-face still: look at the hairline, behind the ears, the neck
- Blink at 0, 0.5 and 1.0 with lashes and tear line: nothing pokes through
- Render time per 1024² frame is measured again and written in `docs/PROGRESS.md`; the three
  videos are about 900 frames, so say what the full set will cost
- Everything is committed and pushed

Not in scope: wrinkle maps driven by expressions. That is a stretch item after M5.
