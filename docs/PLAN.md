# Plan

## Strategy

60 of 100 points are texture photorealism, so the face has to look real before the eyes
move well. Most teams will build a gaze script on a default mesh. We win on three things:

1. **Textures that survive the judges' own wrap test.** They will put our maps on a bare
   GNM head. Skin, brows and eyes must look right with no help from our scene.
2. **Eyes that read as alive.** Lids that follow the eyeball, a wet refractive cornea, a wet
   lid margin and tear line, a lid shadow on the sclera, lashes, blinks tied to gaze shifts,
   brows that travel with the gaze, a head that joins big movements.
3. **A bundle that runs first time.** One command, no manual steps, fixed layout.

## Order of work from Fri 13 Nov

The first M2 check renders (generated irises and detail maps on the baked skin) were held
against the reference videos on 13 Nov and read as CG. Two causes: the look work (M3) has
not happened, and the skin detail is generated, not real. The base stays as decided
(MakeHuman skins on GNM); what changes is the order and where the realism goes.

| # | Work | Model | Depends on |
|---|---|---|---|
| 1 | M1 rig, `scene.blend`, wrapper (`docs/BRIEF_M1.md`). Plumbing done by Opus 13 Nov on stand-in lids; Fable does the lid solve and reviews the rig (see the brief's "Status 13 Nov") | Fable | nothing; it gates 40 points and every video |
| 2 | M2 tuning pass on irises and detail maps (`docs/BRIEF_M2.md`, "Added 13 Nov") | Opus 5.5 | nothing; runs beside 1 |
| 3 | Eyebrow bake fix in `tools/transfer_skin.py`. Done 13 Nov: strand hairs are drawn in UV, not ray-baked | Fable | nothing |
| 4 | Scan test, one hour, optional (below). Comparison done by Opus 13 Nov: relief clearly better, colour not usable. Integrated 13 Nov (Fable): the scan's relief is in every set's normal map and colour detail | Fable | done |
| 5 | M2 section 5, the 8 sets | Opus 5.5 | 2 and 3 |
| 6 | M3 look, M4 motion, M5 packaging, M6 ship | as below | 1 and 5 |

**Scan test.** Candidate: the Lee Perry-Smith head scan by Infinite Realities (CC BY 3.0,
colour and displacement maps of a real face). Download the original maps, put a cheek and a
nose crop next to our generated detail at the same scale, and keep it only if it is clearly
better. Its eyes are closed, so it could only supply detail away from the eyes (forehead,
cheeks, nose, lips, chin), layered onto every set through the same registration as
MakeHuman. Using it means adding CC BY to the licence rule in `CLAUDE.md` and a credit line
in the README and deck.

Result (13 Nov, `tools/scan_compare.py`, details in PROGRESS): the scan's **relief** is
clearly more real than our procedural pores; its **colour** is not usable as albedo (baked
highlight flecks, stubble, one identity). Recommendation: use its displacement, high-passed and
masked, as the micro-relief for every set; keep our procedural pores only on the lips and lids.
Cost: a second registration (scan to GNM, same method as MakeHuman), a bake into tile 1001,
artifact masks; about half a day. Needs the owner's OK for the CC BY licence change before
anything derived from it ships.

## Architecture

```
            tools/ (dev machine, own Python env)                 Blender (bpy + numpy only)
┌──────────────────────────────────────────────┐      ┌──────────────────────────────────────┐
│ export_gnm.py     GNM v3 → assets/gnm/*.npz  │ ───▶ │ build_scene.py                        │
│   mesh, UDIM UVs, joints, skin weights,      │      │   mesh + armature (neck, head,        │
│   shape deltas: blink L/R, lid follow,       │      │   eye.L, eye.R) + shape keys +        │
│   brow raise, squint, pupil                  │      │   drivers + materials + lights + cam  │
│                                              │      │   → scene.blend                       │
│ transfer_skin.py  MakeHuman skin → GNM UV    │ ───▶ │ textures/tex_NN/                      │
│ make_iris.py      procedural iris L/R        │      │                                       │
│ detail_maps.py    pore normal, roughness     │      │ wrapper/eyes.py                       │
└──────────────────────────────────────────────┘      │   move / reset / render               │
                                                      │   --input left|right|generate         │
                                                      │   gaze engine → keyframes → frames    │
                                                      │   → mp4, renders/, metadata.json      │
                                                      └──────────────────────────────────────┘
```

## Milestones

Each milestone ends with a commit, a rendered image or video you have looked at, and a
line in `docs/PROGRESS.md`.

### M0 — Setup and spikes (Thu 12 Nov, tonight) · Opus 5.5
Brief: `docs/KICKOFF_OPUS.md`.
- Blender installed, exact version pinned
- GNM env, model downloaded, `tools/export_gnm.py` writes `assets/gnm/base.npz`
- Facts confirmed from the real model: joint names and order, vertex groups, UDIM tiles,
  expression index ranges
- Blink spike: the eye-region part of `WINK_LEFT` / `WINK_RIGHT` closes each lid cleanly
- MakeHuman CC0 packs and one HDRI downloaded
- Cycles benchmark on the M4: seconds per 1024² frame

**Done when** an untextured GNM head renders headless from 40 cm and two images show the
left and right lids closed.

### M1 — Rig and calibrated wrapper (Fri 13 Nov) · Fable
- `tools/build_scene.py`: mesh, armature from GNM joints and skin weights, shape keys
- Eye aim: both eye bones track one 3D target (vergence comes free)
- Lid drivers: upper lid follows eye pitch, lower lid follows less; blink has a mid-pose
  corrective so the lid slides over the cornea instead of cutting through it
- Camera 40 cm from the eye midpoint, 1024×1024; fixation plane 35 cm, ± 5 cm
- `eyes.move(h, v)`, `eyes.reset()`, `eyes.render()`; `--clockwise` writes 10 frames and
  `metadata.json` with projected pupil centres
- `tools/validate.py` asserts the pupil's 2D shift has the right sign for L/R/U/D and
  returns to centre on reset

**Done when** the 5-direction check passes automatically and by eye.

### M2 — Texture pipeline (Sat 14 Nov) · Fable for the transfer, Opus 5.5 for volume
Can run in parallel with M1.
- Register the MakeHuman head to the GNM head once (landmarks, then surface fit)
- `tools/transfer_skin.py`: bake any MakeHuman skin plus its eyebrows into GNM tile 1001
  at 4096², fill uncovered texels, check the seam at the back of the head and around the ears
- `tools/make_iris.py`: 2048² eye interiors for tiles 1002 and 1004, different seed per eye
- `tools/detail_maps.py`: pore-scale normal map and roughness map in GNM UV
- 8 texture sets covering a spread of skin tone, age and sex

**Done when** each set wraps onto a bare GNM template with no visible seam in front,
three-quarter and profile renders.

### M3 — Look (Sun 15 Nov) · Fable
Brief: `docs/BRIEF_M3.md`. Needs M1's `scene.blend` and at least one M2 texture set.
The bar is "Eye Piece" (see TECH_NOTES, "Reference bar"); order of work follows what that
video gets its realism from.
- Wet eye first: tear line along the lower lid, glossy lid margins, wet inner corner
- Lashes on both lids (MakeHuman CC0), carried from MakeHuman to GNM through the M2
  registration and bound so they follow blinks
- Eye shader: refractive cornea that still lets light reach the iris, limbal darkening,
  sclera with veins and subsurface
- Skin shader: subsurface, roughness and normal detail; lips and eyelid rims handled
- Lighting: soft indoor HDRI plus one key light that puts a window catchlight in the cornea
- Relief check: the head in plain grey with only the normal and roughness maps must already
  show pores and lip creases
- 8 stills of the **whole face**, one per texture set, each paired with a matching GNM
  identity, plus one eye close-up per set

**Done when** an eye close-up at 1024² holds up next to "Eye Piece" at 0:11 at the same crop,
and a whole-face still shows no seam. Iterate render → look → fix; this milestone gets the
most review time.

### M4 — Motion (Mon 16 Nov) · Fable
- `wrapper/gaze/`: saccade generator, fixation jitter and drift, lid follow, blink model,
  eye–head coordination with counter-rotation, pupil, brows (done, see PROGRESS)
- `left`, `right`: gaze shift with head following, hold, blink, return. Never a linear tween.
- `generate`: seeded behaviour sequence — look around, eyes roll up with a brow raise, blink, settle
- Brows and a slight squint move with the gaze in all three; the rubric names eyelids,
  iris and eyebrows
- Motion baked to keyframes so the `.blend` plays it on the Timeline
- Three videos at 30 fps with motion blur, about 10 s each, hard cap 15 s
- Framing: the whole face, tight (forehead to chin), with an eye close-up inset from
  `cam_eyes`. The organisers ask for a "fully textured, seam-free face"; an eye-only video
  does not show it, and the 40 cm spec camera makes the motion too small to see
  (a 15° turn is 12 px). If the inset costs too much render time, use one 70 mm camera.

**Done when** the three videos look natural at full speed and frame by frame, and
opening `scene.blend` and pressing play shows the expression.

**Stretch, only after M5 is green:** wrinkle normal maps that fade in with `brow_up` and
`squint` (forehead lines, crow's feet). Echoes "Flexpressions"; not in the rubric.

### M5 — Compliance and packaging (Tue 17 Nov) · Opus 5.5
- `README.md` with setup, commands, conventions, licences
- `Dockerfile` that renders a draft-quality frame on CPU
- `tools/validate.py` covers layout, schema, video length, texture naming
- Clean-clone test on a fresh folder; zip test from the unzipped bundle
- Final renders run overnight

### M6 — Ship (Wed 18 Nov) · Fable reviews, Opus 5.5 assembles
- Demo video under 3 minutes
- Deck `CollegeName_TeamName.pdf`
- Final review against `docs/REQUIREMENTS.md` section D
- Submit by 8 PM

## Risks

| Risk | Mitigation |
|---|---|
| GNM has no labelled blink | Use the eye-region components of `WINK_LEFT`/`WINK_RIGHT`; confirm in M0. Fallback: solve lid coefficients so the upper lid margin meets the lower. |
| MakeHuman skins look flat | Measured: 2 px per mm on the face against 8.5 in the GNM tile, so the albedo is soft. Detail maps carry the relief, a fine colour layer is added to the albedo, and the shader, brows and lashes add most of the "face" read. |
| Renders read as CG next to the reference videos | Realism for the judges' wrap test goes into the texture files (tuning pass, brow fix, optional scan detail). Realism for our own stills and videos comes from M3: lashes and brow hair as geometry, wet lid edge, side key on a dark background, shallow depth of field. |
| Texture seams after transfer | Bake with a cage, dilate islands, inspect back-of-head and ear seams on every set. |
| Cornea glass blocks light, iris goes black | Make the cornea transparent to shadow rays. |
| Cycles too slow on the M4 for ~900 frames | Benchmark in M0; lower samples with denoise; EEVEE fallback for video only. |
| Blender version drift on the evaluators' machine | Pin and state the version; avoid add-ons; pure `bpy`. |
| Running out of time on motion | M4 is 20 points. Ship `left`/`right` first, then `generate`. |

## After submission (only if shortlisted)

Life-size head on the Quest 3S through WebXR or Unity that keeps eye contact with the
viewer's head position, for the 27 Nov live demo. The 3S has no eye tracking, so it is a
display, not a data source.
