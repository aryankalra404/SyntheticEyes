# SyntheticEyes — Samsung PRISM XR Hackathon 2026, Track 1

Synthetic Eye Movement & Virtual Camera Rendering. Goal: win the track.
**Final submission: Wed 18 Nov 2026, 11:59 PM IST. No extension.** Aim to submit by 8 PM.

Read `docs/REQUIREMENTS.md` before building anything and `docs/PROGRESS.md` before
starting a session. Update `docs/PROGRESS.md` at the end of every session.

## What scores

The organisers' mail says the criteria are the outputs on slide 2 of the evaluation PPT,
with extra credit for natural, human-like, realistic simulation.

| Area | Points | What it means for us |
|---|---|---|
| Texture photorealism | 60 | 5–10 skin + eye texture sets in GNM UV space, seam-free, high-frequency detail |
| Kinematic accuracy | 20 | `left`, `right`, `generate` inputs → natural eye, lid and brow motion, video ≤ 15 s each |
| Code & UV portability | 20 | `.blend` that loads the head with the expression on the Timeline; script runs unattended |

Spend effort in that proportion. A beautiful gaze model on a plastic face loses.
We also satisfy the older PDF spec (calibrated `eyes.move(h,v)`, 10 clockwise renders,
`metadata.json`) because it is cheap and the jury may check it.

## Decisions already made (do not reopen without a reason written in PROGRESS.md)

- **Blender only.** Unity and the Quest 3S are out of scope until after submission.
- **Head model: Google GNM Head v3** (Apache-2.0). Not FLAME, not MakeHuman as the final mesh.
- **Textures target GNM's UV layout**, shipped as UDIM tiles and as legacy per-region files.
- **Skin source: MakeHuman CC0 skins**, transferred onto GNM UVs by baking. Eyebrows are baked
  into the albedo so the texture looks right on a bare GNM head.
- **Irises are generated procedurally**, different seed for left and right.
- **Render engine: Cycles** (Metal GPU on the M4) for finals, EEVEE behind `--quality draft`.
- **GNM's Python package never runs inside Blender.** A tools step exports plain `.npz`;
  everything Blender-side uses only `bpy` + `numpy`.
- **Directions are in image space** (as the camera sees them). `h > 0` moves pupils to
  image-right, `v > 0` moves them up. `left` input means image-left.

## Repo layout

The repo root mirrors the submission zip, so zipping the root (minus dev files) is the bundle.

```
scene.blend            built by tools/build_scene.py, never hand-edited
wrapper/eyes.py        public API + CLI: move(h, v), reset(), render(), --input left|right|generate
wrapper/gaze/          gaze engine: saccades, lids, blinks, head, vergence (pure numpy, no bpy)
wrapper/rig.py         poses bones and shape keys from the gaze channels
tests/                 unit tests that run without Blender
textures/tex_NN/       one texture set per folder (UDIM tiles + legacy names + preview)
renders/               10 clockwise frames for the PDF spec
metadata.json          per-frame ground truth for those 10 frames
outputs/videos/        left.mp4, right.mp4, generate.mp4
outputs/stills/        one still per texture set
tools/                 build pipeline, not needed by evaluators
assets/                third-party inputs and exported GNM data (large files git-ignored)
docs/                  requirements, plan, tech notes, progress
Dockerfile
```

## Commands

```
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender

# rebuild the scene from scratch
$BLENDER -b -P tools/build_scene.py

# what evaluators run
$BLENDER -b scene.blend -P wrapper/eyes.py -- --input left --texture 03
$BLENDER -b scene.blend -P wrapper/eyes.py -- --clockwise          # 10 renders + metadata.json
$BLENDER -b scene.blend -P wrapper/eyes.py -- --input generate --seed 7 --quality draft

# checks
python tools/validate.py              # layout, metadata schema, direction signs, video length
python -m unittest discover tests     # gaze engine against the published numbers
python -m wrapper.gaze --mode left --seed 0 --plot /tmp/left.png   # see the motion as curves
```

## Working rules

- **Headless first.** Every feature must work with `blender -b`. Blender MCP is for looking
  and iterating, never the only way something gets done.
- **Deterministic.** All randomness takes a seed. Same command, same pixels.
- **Look at what you render.** After any change to mesh, shader, light or motion, render a
  frame and open the image. Compare against the reference bar in `docs/TECH_NOTES.md`.
  Do not report "done" on something you have not looked at.
- **Never edit `scene.blend` by hand.** Change `tools/build_scene.py` and rebuild.
- **Relative paths only** inside the `.blend` and in scripts. Evaluators unzip anywhere.
- **Large files stay out of git**: model weights, downloaded packs, frame sequences, caches.
  Final textures, final stills, the three videos and `scene.blend` are committed
  (keep each file under 50 MB; do not pack 4K textures into the `.blend`).
- **Licences.** Only CC0, Apache-2.0, MIT or our own work goes in the bundle. Record every
  third-party asset in `docs/TECH_NOTES.md` under Assets. No NC-licensed textures shipped.
- **Verify, don't assume.** GNM was released in July 2026. Read the code in the installed
  package rather than relying on memory for its API.
- If a requirement is ambiguous, pick the reading that satisfies both spec documents,
  write the convention in the README, and move on.

## Git rules

- Commit messages are **one line**, written the way a person would write them:
  lowercase, plain, specific. `add blink coupling to large gaze shifts`,
  not `feat(gaze): Implement comprehensive blink coupling subsystem`.
- **No body, no bullet lists, no emoji, no conventional-commit prefixes.**
- **No AI attribution of any kind**: no `Co-Authored-By`, no "Generated with", no session
  links, no mention of Claude in commit messages or PR text.
- Commits are authored as the repo owner (the git identity already configured). Never
  change `user.name` / `user.email` to an AI identity.
- Small commits, one logical change each. Commit working states often; push after each milestone.
- Work on `main`. This is a one-week solo sprint.
- Sessions run in parallel on different files. `git pull --rebase` before every push, and
  only add to `docs/PROGRESS.md` under your own milestone's entry.

## Who does what

| Model | Use for |
|---|---|
| Fable | Rig and eyelid solve, UV transfer between topologies, skin/eye shading review, the gaze model, final QA. Anything where a wrong call costs a day. |
| Opus 5.5 | Well-specified bulk work: environment setup, asset downloads, iris generator variants, batch renders, validators, README, Dockerfile, deck text. |

Milestones M1 (rig) and M2 (textures) touch different files and can run in parallel sessions.
