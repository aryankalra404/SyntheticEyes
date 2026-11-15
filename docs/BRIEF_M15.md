# M15 brief — sclera, second pass: no white ring, healthier whites (for Opus)

Written by Fable on Sun 15 Nov 2026 after reviewing the vessel rework (`cf04a3e`) against the
owner's screenshot of the web page ("Both eyes", gaze to image-left) and Eye Piece 0:11–0:15.

## What the review found

The vessel rework is accepted as drawing: trees that fork, wind, taper and fade are right, and
the blood-absorption model is right. What is wrong is **where** the blood and the pink are.
Open `textures/tex_09/eye.1004.png` and you see a target: iris, then a clean bright ring about
2.5 mm wide, then, on one circle, pink wash and every vessel at once. With the eye turned, that
reads exactly as the owner described: a white band hugging the iris, then red. Four causes, all
in `tools/make_iris.py`:

1. `fade = smoothstep(lim + 0.004, lim + 0.04, R)` multiplies all blood by a function of the
   radius alone. No vessel can end closer than its neighbour.
2. `r_stop` (`lim + 0.004 + U(0, 0.05) + 0.05 * (1 - horiz)`, forks `lim + U(0.006, 0.07)`) plus
   the 30 % tip fade end almost every vessel between 0.05 and 0.10 UV from the limbus.
3. The corner pink is `smoothstep(lim, 0.30, R)` at weight 0.7 toward (206, 138, 132): a strong
   wash that starts on a circle. With the vessels on top the eye looks irritated, not healthy.
4. Every other sclera term (yellowing, rim tint, the grey-blue band) is also a pure function of
   the radius, so the boundaries line up into rings.

Two smaller things: the wide vessels are a saturated crimson that reads as red marker in the
web page (no subsurface there), and the iris-to-white edge is a hard line in the web page.

## What a real eye does (the target)

- Conjunctival vessels come from behind the lids and run toward the cornea. **How far each one
  gets differs**: most twigs give out 0.5–2 mm short, some trunks run to within 0.2 mm and end
  in a small arcade (the tip forks and the forks turn sideways along the limbus).
- The 1–1.5 mm round the cornea has **fewer** vessels. It is not a different colour and it has
  no edge. Its outline is ragged and different in every sector.
- At rest a healthy young eye shows mostly clean white with a handful of thin vessels each side.
  Pink belongs to the far inner corner (next to the caruncle), faintly to the far outer corner.
- Thin vessels are a faint salmon, wide ones dark red. Nothing is neon.
- The limbus is a soft grey-blue transition about 1 mm wide, not a line.

1 mm is about 0.032 UV (limbus radius 0.19 UV is 5.9 mm); one texel at 2048 is about 15 µm.

## Rules for this milestone

- **Two phases, with a stop between them.** Phase 1 writes only to `outputs/tmp/m15/` and ends
  with a review pack. Do not touch `textures/`, `outputs/stills/`, `xr/assets/` or the public
  page until Fable has accepted the pack. Phase 2 is the rollout.
- The final videos must not be rendering while you work (your test renders fight them for the
  GPU and their frames are void once the tiles change). Check with `pgrep -fl "eyes.py"`. If a
  run is going, tell the owner and wait; do not kill it yourself.
- Never save `scene.blend`. For Cycles tests, do what the 15 Nov evening session did (PROGRESS,
  "sclera vessels rebuilt": `cam_test_eye`, gaze ±28°): a scratch script that points the eye
  image at the trial file and renders.
- The iris must not change in stages A and B: assert that every texel inside 0.9 × limbus radius
  is byte-identical before and after, for both eyes of two sets. `set.json` stays as it is.
- Same seed, same bytes. Keep the vessel generator on its own `vrng`.
- Commit rules as in CLAUDE.md: one plain lowercase line, no body, no attribution of any kind.

## Phase 1 — trial on tex_09 (hazel, seed 9), then spot checks

### Stage A: ragged reach, no ring (the main fix)

1. Replace the radial `fade` with a safety fade only: `smoothstep(lim + 0.002, lim + 0.010, R)`,
   there so that no blood lands on the iris, nothing more.
2. Give every vessel its own stopping distance from a skewed distribution, drawn per vessel and
   per fork: about 25 % stop at `lim + U(0.004, 0.012)`, about 45 % at `lim + U(0.012, 0.05)`,
   the rest at `lim + U(0.05, 0.11)`. Away from the horizontal add up to 0.03, not a fixed 0.05.
3. Limbal arcades: when a vessel of the first group comes within 0.012 UV of its stop, let its
   `bias` swing toward ±90° (tangential) over the last 30–60 texels and force one fork there, so
   it ends as a small sideways Y, not a point aimed at the iris.
4. Warp the radius used by every sclera term. Build one smooth 2D noise field `dR` (two
   octaves, sigma about 60 and 18 texels at 2048, amplitude ±0.025 UV total, from `rng`) and
   use `R + dR` in the pink, the yellowing, the rim tint and the grey-blue band. Keep `R` for
   the safety fade, the limbal ring and `FORNIX`. Do not change `FORNIX`, `LIMBAL_*` or `base`.
5. Density: the visible almond at rest (inside `lid_opening`, outside the limbus) should carry
   about **half** the blood it has now. Measure first (see Numbers), then thin it: fewer `fine`
   starts close in (push their start radius out: `lim + 0.08 + ...`), keep the trunks.

### Stage B: healthy whites and blood colour

1. Pink wash: weight 0.7 → 0.25, ramp `smoothstep(lim + 0.06, 0.38, R + dR)`, multiplied by a
   blotch field (the mid-frequency mottling remapped to 0.5–1.5). The nasal side keeps its lead.
   Most of the remaining pink in the corners should come from fine vessels, which are already
   densest there.
2. Blood colour: try `BLOOD = (0.12, 1.0, 0.95)` (blood takes out blue about as much as green;
   the current 0.80 leaves the twigs magenta-pink). Render both values side by side on the tile
   and in Cycles; put both in the pack, Fable picks.
3. Do not raise `VESSEL_TAU`. If the wide trunks still read as marker red in the web page at the
   screenshot pose, try 3.3 → 2.8 and show both.

### Stage C: softer limbus (separate commit, easy to drop)

In `make_eye`: widen the iris/sclera blend from `(rl - 0.002, rl + 0.006)` to
`(rl - 0.004, rl + 0.012)`; grey-blue band weight 0.12 → 0.20, sigma 0.008 → 0.012, centred
`lim + 0.008`. This changes the iris edge of every set, so judge it on hazel (tex_09), dark
brown (tex_03 or tex_06) and the lightest iris we ship, in Cycles and in the web page. If the
iris looks smaller or milky at the edge on any of them, halve the widening.

### Stage D: web page only (small)

The screenshot shows a moiré on the iris and a dead-flat white. In `xr/js/app.js`, on the eye
textures: mipmaps on, `LinearMipmapLinearFilter`, `anisotropy = renderer.capabilities.getMaxAnisotropy()`.
Check the colour space is sRGB. If the whites still look like paper, lower the eye interior's
`envMapIntensity` a little and say what you tried; do not add lights.

### Numbers to report (before and after, both eyes of tex_09)

- Blood coverage: fraction of texels with optical depth > 0.15, in three zones: inside the
  rest-pose opening; ring `lim .. lim + 0.035`; ring `lim + 0.035 .. lim + 0.10`.
- Reach: for each of 36 ten-degree sectors, the smallest `R - lim` with optical depth > 0.15.
  Report median and 10th–90th percentile. Now it is narrow; after, it should span roughly
  0.005–0.08 with no two neighbouring sectors alike.
- Ring test: mean linear luminance of the vessel-free base in `lim + 0.01 .. lim + 0.04` over
  the same in `lim + 0.06 .. lim + 0.10`, in the nasal and temporal 60° sectors. Target 0.97–1.03.

### Review pack, `outputs/tmp/m15/` (git-ignored), with an `INDEX.txt`

Every image is before | after, same crop, labelled.
1. Tile, tex_09 L and R: whole tile at 1100 px; 1:1 crops of the nasal sector, the temporal
   sector and straight up.
2. Cycles, final quality, `cam_test_eye`: tex_09 at yaw −28, 0, +28 and at pitch +20; tex_03
   and one light-skin set at 0 and +28.
3. Video scale: one face-camera frame at the `left` glance pose, both eyes cropped and shown at
   1x and 3x.
4. Web page, served locally with the trial textures (not published): "Both eyes" with the gaze
   hard to image-left, as in the owner's screenshot, and "Eye close-up" at extreme gaze.
5. `numbers.txt` with the table above, and the byte-identity result for the iris.

Then stop and tell the owner the pack is ready for Fable. Say plainly what you are unsure of.

## Phase 2 — rollout, only after Fable accepts

1. `build_textures.py --eyes-only` for all nine sets (tiles, legacy files, previews, sheet).
2. `tools/render_stills.py` for the nine faces and nine eye close-ups. Look at all eighteen.
3. `tools/export_xr.py` for the eye textures, `tools/publish_xr.sh`, check the public page.
4. `tools/validate.py` and the unit tests.
5. TECH_NOTES ("Iris and sclera generation": replace the vessel lines with what is now true),
   PROGRESS under your own entry, commit in small steps, `git pull --rebase`, push.
6. Tell the owner the finals can start **clean** (no `--resume`), and give the command.

## Not in scope

The iris pattern, the skin, the lids and lashes, the lights, the gaze engine, `scene.blend`
geometry, the three videos themselves.
