# Tech notes

Facts checked against source on 12 Nov 2026, and against the real v3.0 weights in M0.
Measured numbers live in `docs/GNM_FACTS.md`; this file keeps only what decisions need.

## GNM Head v3

Source: https://github.com/google/GNM (commit `846ab76`, 10 Nov 2026), Apache-2.0.
Technical report: https://arxiv.org/abs/2607.23687

- 17,821 vertices covering skin, eyeballs, teeth and tongue
- 4 joints in this order: `neck` (root), `head` (parent neck), `left_eye`, `right_eye` (both
  parented to head). Linear blend skinning, world-frame axis-angle rotations `[num_joints, 3]`.
  Pose correctives are all zero in v3.0. Units are metres, +Y up, +Z forward, subject's left
  eye at +X (image right for a front camera). Eye joints are 61.7 mm apart.
- Identity: 253 coefficients (170 head, 3 eyeball, 80 teeth), typical range −3..+3
- Expression: 383 coefficients: 0–99 left eye region, 100–199 right eye region,
  200–349 lower face, 350 `tongue_mean`, 351–381 tongue, 382 pupils (confirmed from
  `expression_names`).
- Pupil coefficient: −3 closes the pupil to a point, 0 is half the iris radius, +3 is full iris
- Eyeball is a two-sphere model (sclera + cornea); sclera radius is fixed at about 14.6 mm
- 46 vertex groups, including `skin`, `left_eye`, `right_eye`, `eye_interiors`,
  `eye_exteriors`, `scleras`, `irises`, `pupils`, `eye_sockets` (the lid pocket; its front rim
  is the lid margin), per-side brow, orbital and cheek regions, `upper_teeth_and_gums`,
  `lower_teeth_and_gums`, `tongue`. Full list with sizes in `GNM_FACTS.md`.
- 68 sparse landmarks ship in `gnm/shape/data/landmarks/head_sparse_68.txt`
  (vertex indices + barycentric weights) — use these for registration
- Weights download from Google's Hugging Face CDN on first `GNM.from_remote(...)` and are
  cached in `~/.cache/gnm/models/`. `GNM.from_custom_file(path)` loads a local `.npz`.
  The file is a plain numpy archive at
  `https://huggingface.co/google/gnm-v3/resolve/main/v3_0/gnm_head.npz` (cache path
  `~/.cache/gnm/models/v3_0/gnm_head.npz`); `tools/export_gnm.py` reads it with numpy alone.
  The UDIM layout is not stored; it is computed from vertex groups (`gnm_udim.py`), and
  `tools/gnm_core.py` reproduces that.
- Package needs Python ≥ 3.12 and pulls TensorFlow (for the semantic samplers). Keep it in
  its own env; never import it inside Blender.
- No skin texture ships with GNM. `data/textures/` holds only an edge-flow test image.

### Semantic expression classes
`SURPRISE, DISGUST, SUCK, COMPRESS_FACE, STRETCH_FACE, HAPPY, SQUINT, PLATYSMA, BLOW,
FUNNELER, SMILE_WIDE, CORNERS_DOWN, PUCKER, WINK_LEFT, WINK_RIGHT, MOUTH_LEFT, MOUTH_RIGHT,
LIPS_ROLL_IN, SNARL, TONGUE_CENTER`

There is no blink class. Plan for lid shapes:
- `blink.L` = left-eye components of a `WINK_LEFT` sample, `blink.R` likewise. Zero the
  lower-face part so a blink does not pull the cheek and mouth.
- `brow_up` and upper-lid raise from the eye components of `SURPRISE`
- `squint` from `SQUINT`
- Lid follow for up and down gaze: least-squares solve on the periocular basis so the lid
  margin tracks the limbus at ± pitch
- Samplers are stochastic; sample many, average, and store the vectors as `.npy` so the
  build is deterministic and TensorFlow is needed only once.

### UV layout
Two layouts for the same unwrap:

| Tile | Region |
|---|---|
| 1001 | Skin |
| 1002 | Left eye interior: sclera, iris, pupil |
| 1003 | Left eye exterior: cornea |
| 1004 | Right eye interior |
| 1005 | Right eye exterior |
| 1006 | Teeth and gums |
| 1007 | Tongue |

- UDIM (`quad_uvs_udim`, recommended): one tile per region, u spans 0..7
- Legacy per-region (`quad_uvs`): every region in the unit square, overlapping; left and
  right eyes land on nearly the same area
- A legacy skin texture is already a valid tile 1001. A legacy eye texture maps to
  1002+1003 (left) or 1004+1005 (right).
- The eye interior tile is a disc with the iris and pupil at the centre.

**What we ship per texture set**
```
textures/tex_NN/
  skin.1001.png        4096²  albedo, brows baked in
  eye.1002.png         2048²  left eye interior
  eye.1004.png         2048²  right eye interior
  skin_normal.1001.png 4096²
  skin_rough.1001.png  2048²
  legacy/skin.png, legacy/eye_L.png, legacy/eye_R.png   same pixels, per-region names
  preview.png          the set wrapped on the GNM template
```
Judges may load either layout, so both names exist. Because left and right eyes overlap in
the legacy layout, "separate iris maps for left and right" needs two materials or UDIM.

## Skin texture transfer

Source: MakeHuman community asset packs, CC0 — Skins 01 (female), Skins 02 (male),
Eyebrows 01, Eyelashes 01, system assets.
https://static.makehumancommunity.org/assets/assetpacks.html

Method (the "bake by comparing UV maps" route from the evaluation PPT):
1. Load the MakeHuman base head with a skin and eyebrows applied.
2. Fit GNM to it: rigid align on landmarks, solve GNM identity coefficients against the
   landmarks and closest points, then shrinkwrap the GNM skin onto the MakeHuman surface.
3. Cycles bake, Selected to Active, diffuse colour only, with a cage, from
   MakeHuman head + eyebrow cards → GNM tile 1001 at 4096².
4. Dilate islands, inpaint texels with no source (inside of lids, mouth interior edge,
   under the neck cut).
5. Wrap on the unfitted GNM template and render front, three-quarter, profile, back.

The registration is done once; each further skin is a bake of a few seconds.

What the bake alone gets wrong on a bare head, and where it is put right (14 Nov audit):
- **Brows** (`tools/transfer_skin.py`): the modelled strands give the place and outline only.
  Hairs are grown inside it (upright at the inner end, up and out along the lower edge, down
  and out along the upper edge, flat in the tail) and drawn about a texel wide with skin
  between them. One stroke per modelled strand was a slab or a few pen lines.
- **Painted scalp, eye area, lips** (`tools/skin_fix.py`, strengths per set in the recipe's
  `fix`): the red-orange shaved cap is pulled to the tone of the skin round it, carried inward
  over the mesh (the hairline, the band behind the ears and round the nape, and the forehead
  patches were all its edge); broad tone and drawn lines round the eye; lip colour; redness at
  the nose wings and lid rims. Placed on the surface, never in UV, so it cannot open a seam.
- **The UV seam** runs down the back midline from the crown to the neck base. Anything
  filtered in UV has one side only there: the scan relief's high-pass left a cliff along it,
  so `tools/detail_maps.py` narrows that filter toward island borders. Normals are written in
  Blender's frame (bitangent at right angles to the tangent, not along +v): the scalp unwrap
  is sheared about 17 degrees, opposite ways on the two sides.
- **Soft colour at 1:1** (`tools/detail_maps.py`, `grain`): a baked MakeHuman skin holds about
  2 px per mm, so at 1:1 it is a blur with a few dark pore specks. The two finest bands of the
  height map (1.5 px, and 1.5 to 6 px) go into the colour detail, valleys darker, ridges
  lighter, as in a photograph of skin. Fine band of log-luminance on cheeks and forehead:
  1.04-1.14 % before, 1.62-1.70 % after, 1.76 % on the photographed set. Amplifying the bands
  of the albedo itself only darkens the specks; there is nothing finer in it to amplify.
- **Stubble relief** (`stubble`): the scanned relief is a man's, coarse with follicles from
  under the nose down. Sets made as women's skin keep 0.3 of it there.
- Padding outside the islands of the albedo is a push-pull fill (`tex_core.fill_smooth`); the
  normal and roughness maps keep a nearest-texel fill. Neither is ever sampled.

Optional extra source: FFHQ-UV, 50,000+ face UV maps derived from photos, HiFi3D++
topology. Stated as research use, so only use if time allows and note it in the README.
https://github.com/csbhr/FFHQ-UV

## Iris and sclera generation

Work in polar coordinates around the tile centre, then warp to the disc.
- Stroma fibres: noise stretched along the radius, gently wavy
- Collarette: a low broken ridge at roughly a third of the iris width; the pupillary zone
  blends into the ciliary zone over ±0.08 of the width and reaches outward along radial
  spokes, its hue within 15° of the outer zone
- Crypts and furrows: dark lozenges stretched along the radius, varied in size, densest just
  outside the collarette; faint concentric contraction rings
- Limbal ring: wide soft shadow from 72 % of the limbus radius to × 0.45 at the limbus,
  fading 0.03 UV into the sclera
- Final tone is in the palettes (the eye shader adds none): the M3 shader correction
  (linear HSV saturation × 0.72, value × 0.80) is baked in, browns darker and warmer
- Pupil ruff: thin dark-brown rim at the pupil edge
- Colour from a small palette (dark brown, brown, hazel, green, blue, grey), most sets brown
- Left and right share the palette and structure parameters but use different noise seeds
- Sclera: off-white with a warm tint toward the corners and fine branching veins, 30 % darker
  by UV radius 0.40 (toward the fornix)
- The pupil is geometry (GNM's pupil coefficient), so keep the texture's pupil region dark
  and let the mesh set the size

## Shading recipe (Cycles)

As built in M3 (13 Nov); every number lives in `tools/build_scene.py`.

- **Skin**: Principled BSDF, random-walk (skin) subsurface at weight 1, radius (1, 0.30, 0.15),
  scale 2.0 mm, 1.5× on the thin skin round the eyes. Albedo, tangent normal (strength 1.8) and
  roughness (as it is) from the set. A thin sharp coat (weight 0.18, roughness 0.2) reflects off
  a procedural 0.5 mm micro-relief laid in rest coordinates, so pores sparkle under a raking
  light without the millimetre blobs a sharp gloss shows on the map's own normal. The nose
  (`nose` mask) gets + 0.22 roughness and no coat; on the nose and between the brows (`calm`
  mask, spread wide) the normal map drops to strength 0.6. Four more per-vertex masks on the head mesh: `wet` (lid margin and the pocket
  behind the lids: roughness × 0.25 under a clear coat with a fine ripple, which breaks the
  highlight into glints), `pink` (the same pocket and the inner corner: red wet tissue instead
  of the skin fill in the albedo), `lips` (roughness × 0.7, coat 0.25), `lids`.
- **Eye interior** (iris and sclera, one tile): matte Principled under the shell, the tile's
  colour as it is (tone, limbal ring and fornix falloff are in the tile since the iris rework).
  Sclera has subsurface 0.6; the iris part is bumped from its own fibres.
- **Cornea**: the eye's outer shell is Glass, IOR 1.376, roughness 0, with a Transparent BSDF for
  shadow rays (Light Path → Is Shadow Ray) or the iris renders black. It covers the sclera too,
  so the whole eye is wet. The iris sits 3.4 mm behind the apex, so refraction is real.
- **Tear line**: a concave strip of water (Glass IOR 1.34 plus a tenth of mirror) in the angle
  between the lower lid margin and the globe, 0.75 mm up the globe.
- **Lashes**: grown per head on the front edge of the lid margin (`tools/lashes.py`), 135 upper
  (up to 9 mm) and 80 lower (up to 6.5 mm) per eye, 60 → 8 µm radius, in clumps of 3–5 with the
  tips pulled 75–95 % together (one in ten alone). Principled Hair, colour (0.015, 0.010, 0.0065),
  roughness 0.15, IOR 1.2: dark strands with a thin glint; the rim lights them.
- **Dark hair under the hard key**: Principled Hair's surface reflection does not depend on the
  fibre's colour. At hair's real IOR 1.55 the raking key turned black brows and lashes grey and
  brown ones straw (a pure black colour rendered the same grey); only a lower IOR took it off.
  Brows and lashes use IOR 1.2 (`DARK_HAIR_IOR`), random roughness 0.15. The fine facial hair
  keeps 1.55: it is pale and is meant to catch the light.
- **Brows**: grown per head on the brow painted in the albedo of the set the scene is built with
  (`tools/brows.py`, `brows_grown`, `brow_set` = that set): 450–600 hairs per brow inside GNM's
  brow regions where the albedo is darker than the skin round it; inner third up and out, body
  along the arch, top and bottom rows meeting in the middle, 8° of scatter; 3.5–11 mm, 45 → 14 µm,
  lying 8–15° off the skin at the root with the tip 0.3–0.8 mm up. Roughness 0.25, IOR 1.2. Colour
  from set.json `eyebrows.color_linear`, else (0.020, 0.013, 0.008). Kept out of the rim. For any other set the carried Mindfront strands.
- **Fine facial hair**: grown per head on the face front (`tools/vellus.py`), about 8,100 hairs of
  0.6–3.5 mm, 9 → 3 µm radius, none on lips, lid margins or brows. Each takes the skin texture's
  colour under its root (less saturated, lifted a little), so it suits every set.
- **Lighting**, two looks picked by the camera (`LOOKS`, `wrapper/eyes.py apply_look`).
  `face` = HDRI at 0.24, a 45 × 60 cm key up and to image left and a rim, plain dark backdrop:
  the constant light of `cam_face` and the 10 clockwise renders.
  `eye` = everything else (videos, stills, eye close-ups), on black with the HDRI at 0.03
  (`EYE_LIGHTS`; places are from the subject's left pupil):
  - key: 5 cm disk, 3.0 W, warm, 0.5 m, 78° to the temple side and 30° up. Hard and raking.
    (88° / 42° leaves the globe of the tex_09 head in the shadow of the brow and orbital rim.)
  - fill: 50 cm disk, 0.4 W, warm (1.0, 0.92, 0.85), 60° to the nose side, hidden from glossy
    rays (its reflection is a pale patch over half the cornea). 0.2 W blacked out tex_06's
    shadow side under the contrast look.
  - rim: 6 × 30 cm strip, 2.5 W, 155° round and 20° up, behind the temple; it backlights the fine
    hair on the silhouette. Light linking keeps it off the brow hair (it greyed them); the lashes
    take it since 14 Nov.
  - iris spots: one 5.5° spot per eye, 1.5 W, diffuse only, on the head bone. A raking key
    leaves a deep-set iris dull. (At 3.0 W the whites were the brightest thing in frame on the
    dark-skinned heads and glowed out of the shadow side of the face.)
  - catchlight: a 6 × 10 cm card 30° to the temple side and 28° up whose material emits only
    into singular reflection rays: the cornea and the tear line see it, nothing else is lit.
  - sclera strip (`sheen_eye`): a second card made the same way, 30 × 60 cm, 0.8 m away, 70° to
    the temple side and 10° up, strength 2.5: a long soft reflection on the temple side of the eye.
    (At 4 it was a hard white bar across a dark iris, as bright as the catchlight.)
  - flag: a scrim (65 % dense) shaped as the nose's outline seen from the key, 24 % of the way
    from the nose to the key, held on the key-to-nose lines by a Geometry Nodes step as the head
    moves. Shadow rays only. It keeps the key from making the nose the brightest thing in frame.
- **Camera**: `cam_face` 40 cm from the eye midpoint, 50 mm lens on a 36 mm sensor, 1024×1024.
  Stills: `cam_test_face` (126 mm from 0.56 m, mid forehead to chin, no scalp) and `cam_test_eye`
  (the videos' eye framing). Videos: `cam_move` (see PROGRESS, M4).
- **Colour**: AgX view transform; the look is per camera (`view_look` in `LOOKS`): "AgX - Medium
  High Contrast" for `eye`, "None" for `face`.

## Calibrated control (`eyes.move`)

- Eye midpoint = midpoint of the two eye joint positions
- Fixation plane 35 cm in front of it, perpendicular to the forward axis
- `move(h, v)` places the target at (h · 5 cm, v · 5 cm) on that plane; both eyes aim at it.
  Maximum gaze angle is atan(5 / 35) ≈ 8.1°, and the eyes converge by a few degrees.
- Image-space convention: θ = 0 is top (h = 0, v = 1); clockwise in the render means
  h = +1 is image-right
- `pupil_center_2D`: world position of the pupil centre on the evaluated mesh, projected
  with the render camera to pixel coordinates (origin top-left, state this in the README)
- `eye_rotation_L/R`: world-frame Euler XYZ in radians of each eye bone
- `camera_matrix`: 3×4 projection (K · [R | t]); also write K and the 4×4 world matrix

## Gaze engine numbers

From Ruhland et al., "A Review of Eye Gaze in Virtual Agents, Social Robotics and HCI",
Computer Graphics Forum 2015.
https://scispace.com/pdf/a-review-of-eye-gaze-in-virtual-agents-social-robotics-and-2c9hut2mca.pdf

- Saccade duration grows about linearly with amplitude; 5–10° takes 30–40 ms
- A 30° saccade peaks around 500°/s; acceleration and deceleration are very fast
- Minimum gap between saccades about 150 ms; fixation durations follow an exponential distribution
- Saccade latency to a new target about 200 ms
- Lid saccades always accompany vertical eye saccades
- Relaxed lid is about 80% open
- Blinks: Poisson process, 8–21 per minute in primary gaze; closing phase about twice as
  fast as opening; often coincide with the start of large gaze shifts, especially over 30°
- Head joins the movement beyond about 15–20°; for a reactive target the head starts
  20–50 ms after the eyes
- Vestibulo-ocular reflex: eyes counter-rotate against head rotation with 7–15 ms latency,
  so gaze stays on target while the head catches up
- Smooth pursuit breaks down above about 30°/s and needs catch-up saccades
- Animator guideline: no blinks in the first or last 5–10 frames of a shot

Implementation consequences:
- At 30 fps a typical saccade is one or two frames. Evaluate the motion at sub-frame
  times and turn on motion blur; never ease a gaze shift over half a second.
- Add a small overshoot or undershoot with a corrective saccade on large shifts.
- Hold fixations with slow drift plus tiny jitter rather than a frozen eye.
- Upper lid height is a function of eye pitch at all times, on top of blinks.

## Reference bar

Both videos the organisers link are by Chris Jones. Stills from each were looked at on
12 Nov 2026 (motion and sound were not). The frames are his work and this repo is public,
so they are **not** stored here; the timestamps below say where to look.

To look again from a session: open the normal watch page in the browser pane (the `/embed/`
player refuses to play), make sure the pane is showing, then set
`document.querySelector('video').currentTime = <seconds>` and take a screenshot.

**"Eye Piece"** (https://youtu.be/TAZIvyAJfeM, 47 s, 2014; Lightwave, Sculptris, Krita). An
extreme close-up of one eye on a small patch of face, fully textured, then the same shot as
wireframe. This is the bar for the eye itself.

| Time | What is on screen |
|---|---|
| 0:09 | lid almost closed: lash strands, glints along the wet lid margin, pores catching light |
| 0:11 | eye open, three-quarter: cornea bulge, catchlight, iris fibres, limbal ring, sclera veins, tear line |
| 0:14 | eye turned away: mostly sclera, pink toward the corner, lower lid pulled by the globe |
| 0:19 | wider: the model is only a patch around one eye, lit by a hard key against black |
| 0:24 | wireframe: coarse skin mesh, lashes and brow as real strands |
| 0:30–0:37 | dense wireframe with rig handles on brow, lid and cheek |

What makes it read as real: wet lid margins with bright specular glints and a tear line on the
lower lid; lashes on both lids; a sclera that is not white (veins, pink corners, red caruncle);
thin lid skin with fine creases; one hard light, so every wet surface shows.

**"Flexpressions"** (https://youtu.be/gh6WbaYzwFc, 31 s, 2021; Blender, Krita, Cycles). A whole
head in **untextured grey**, pulling strong expressions. No colour map at all.

| Time | What is on screen |
|---|---|
| 0:04 | hard squint with bared teeth: crow's feet, nose scrunch, forehead bunching |
| 0:10 | sneer with lowered brows: asymmetric, the whole face involved |
| 0:16 | near-neutral close-up: pores visible as relief on a grey surface |
| 0:22 | lips close-up: vertical lip creases as relief |
| 0:27 | topology overlay on the same head |

What makes it read as real: brows, lids, cheeks and nose move together; wrinkles form with
the motion; pores and lip creases are relief, so they survive without colour.

**What the organisers ask for, in their words** (evaluation PPT):
- "natural eye and eyelid motion with fully textured, seam-free face and realistic eyeballs"
- textures "should include face and eyes texture"
- "animate the eyelids as well as eye iris and eyebrows to get realistic feel"
So the **whole face** is expected, textured and seam-free, with the eyes as the thing that
moves. Lids and brows moving with the gaze are asked for by name. Wrinkles are not.

What this means for us:
- Stills and videos show the whole face. Frame it tight (forehead to chin) so the eyes are
  large, and add an eye close-up as an inset or a second shot. Not an eye-only video.
- Wetness, lashes and the tear line count for more than the iris pattern. We have none yet.
- Relief carries the high frequency. The pore and lip-crease normal maps matter as much as
  the albedo, and must look right on a grey head.
- Brows and a slight squint travel with the gaze (already channels in the gaze engine).
- Stretch only, after everything else ships: wrinkle normal maps that fade in with brow raise
  and squint. Not in the rubric.

## Assets and licences

| Asset | Use | Licence |
|---|---|---|
| Google GNM Head v3 | head mesh, rig, UVs | Apache-2.0 |
| MakeHuman Skins 01/02, Eyebrows 01 | skin source, brow hair | CC0 |
| MakeHuman system assets, base mesh | registration target, default eyebrows/lashes | CC0 |
| Poly Haven `brown_photostudio_02` 2K HDR | lighting | CC0 |

Downloaded in M0 (12 Nov 2026) into `assets/third_party/` (git-ignored). Each licence was
checked on its download page: every asset row on the MakeHuman pack pages says CC0, and
Poly Haven's licence page says all its assets are CC0.

| File | Source URL | Licence | Contents |
|---|---|---|---|
| `makehuman/skins01_cc0.zip` (104 MB) | https://files.makehumancommunity.org/asset_packs/skins01/skins01_cc0.zip (page: https://static.makehumancommunity.org/assets/assetpacks/skins01.html) | CC0, 23/23 assets | 23 skins (female) |
| `makehuman/skins02_cc0.zip` (76 MB) | https://files.makehumancommunity.org/asset_packs/skins02/skins02_cc0.zip (page: …/assetpacks/skins02.html) | CC0, 13/13 | 13 skins (male) |
| `makehuman/eyebrows01_cc0.zip` (11 MB) | https://files.makehumancommunity.org/asset_packs/eyebrows01/eyebrows01_cc0.zip (page: …/assetpacks/eyebrows01.html) | CC0, 14/14 | 14 eyebrow proxies (Mindfront) |
| `makehuman/eyelashes01_cc0.zip` (3.5 MB) | https://files.makehumancommunity.org/asset_packs/eyelashes01/eyelashes01_cc0.zip (page: …/assetpacks/eyelashes01.html) | CC0, 5/5 | 5 eyelash proxies (Mindfront) |
| `makehuman/makehuman_system_assets_cc0.zip` (281 MB) | https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip (page: …/assetpacks/makehuman_system_assets.html) | CC0, 94/94 | default skins, eyes, eyebrows, eyelashes, teeth, tongue, hair, clothes, proxies |
| `makehuman/base_mesh/base.obj` (1.7 MB) | https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/3dobjs/base.obj | CC0 (file header and repo `LICENSE.md` section C) | 19,158 v, 21,334 vt, 18,486 f. Includes helper geometry (joints, clothing helpers); keep only the body group when registering |
| `hdri/brown_photostudio_02_2k.hdr` (6.5 MB) | https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/brown_photostudio_02_2k.hdr (page: https://polyhaven.com/a/brown_photostudio_02) | CC0 (https://polyhaven.com/license) | soft studio with window light, medium contrast |
| `lpshead/zip/lpshead.zip` (43.6 MB, sha256 `cc683bb0…19ca`), downloaded 13 Nov; the zip itself is **not in the bundle** | https://casual-effects.com/g3d/data10/research/model/lpshead/lpshead.zip (McGuire Computer Graphics Archive; original: http://www.ir-ltd.net/infinite-3d-head-scan-released) | **CC BY 3.0** ("Infinite, 3D Head Scan by Lee Perry-Smith", based on a work at www.triplegangers.com; `Infinite-Scan_License.txt` in the zip) | `head.OBJ` 8,844 v (ZBrush units, about 915 mm per unit), `lambertian.jpg` colour 4096², `bump.png` displacement 6000² 16-bit, `bump-lowRes.png`. Eyes closed, stubble, one mole. Used from 13 Nov: its displacement map, high-passed to pore scale and masked, is the skin micro-relief in every set (`tools/register_scan.py`, `tools/bake_scan.py`, `tools/detail_maps.py`), and its colour map is the skin of `tex_09` (`tools/bake_scan.py --albedo`). The mesh is not shipped. Credited in the README; credit it in the deck too |

The `files2.makehumancommunity.org` mirror stalled twice mid-download; the
`files.makehumancommunity.org` mirror worked.
| Blender | renderer | GPL (tool only, not redistributed) |
| blender-mcp (ahujasid) | dev iteration only | MIT |

Looked at and not used in the bundle:
- GNM Head Importer add-on by Nathan Dickson (free; good for exploring the model, has an
  eye look-at rig). Its optional skin texture is CC BY-NC-SA, so it is not shipped.
- GNM Head add-on by derQwertzus (GPL-3.0).
- FLAME: the rubric allows its UV map, but GNM is the model the judges wrap textures on.

## Hardware note

Meta's device comparison lists Quest 3S tracking as head and hand only, so it cannot record
eye movement. https://developers.meta.com/horizon/resources/compare-devices/
