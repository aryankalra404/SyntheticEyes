# AI disclosure

SyntheticEyes was built with AI coding tools. This page says which parts they made, which parts
they did not, and what the team did. It is drawn from the repository's own records:
`CLAUDE.md`, `docs/PROGRESS.md` and the briefs in `docs/`.

> TODO (team): add the team members' names, check the "What the team did" section against what
> actually happened, and correct anything here that is wrong before submitting.

## Tools used

| Tool | Used for |
|---|---|
| Claude Code (Anthropic), running the models the work log calls Fable and Opus 5.5 | Writing and running the code, rendering and looking at test frames, writing the documentation |

`CLAUDE.md` is the instruction file those sessions worked from. Each entry in
`docs/PROGRESS.md` names the model that did that session's work.

No image-generation model is used. The texture pipeline in `tools/` imports numpy, scipy, Pillow
and Blender only, and every render comes out of Blender.

## Made with AI assistance

- **Code**: `wrapper/` (the `eyes.py` command line and API, the rig, the gaze engine, the camera
  move, the device choice), `tools/` (scene build, texture pipeline, lid solve, validator),
  `tests/` and the `Dockerfile`.
- **Documentation**: `README.md`, everything in `docs/`, and this file.
- **Parameter choices** in the gaze engine (saccade, blink, head and brow numbers), taken from
  the eye-movement literature cited in the README, and the lighting and shader settings in
  `tools/build_scene.py`.
- **Review of renders**: the sessions rendered test frames and judged them; the work log records
  what was looked at.

## Not made by AI

- **Head model**: Google GNM Head (Apache-2.0): mesh, joints, UV layout, expression basis.
- **Skin colour, sets 01 to 08**: MakeHuman CC0 skins, moved onto GNM's UVs by a baking script.
- **Skin colour of set 09 and the pore relief of all nine sets**: "Infinite, 3D Head Scan by
  Lee Perry-Smith" (CC BY 3.0).
- **Lighting**: Poly Haven HDRI `brown_photostudio_02` (CC0).
- **Irises, sclera and the remaining detail maps**: computed by the project's own scripts with
  numpy (procedural noise and drawing), not by a learned model.
- **Renders and videos**: Blender 4.5.1 (Cycles and EEVEE) from `scene.blend`.

Full credits and licences are in the README.

## What the team did

The work log (`docs/PROGRESS.md`) records these as the repository owner's:

- Approving the download and use of the head scan (CC BY 3.0), first for the skin relief and
  then for the colour of set 09, after looking at test bakes.
- Lists of changes to the look and to the motion, which the sessions then carried out.
- The strength of the pupil's response to near targets.

Still to be done by the team, by hand: rendering the final videos, recording the demo video and
writing the presentation.

## Checking

- `python -m unittest discover tests` runs the unit tests for the gaze engine, the camera move
  and the device choice.
- `python tools/validate.py` checks the bundle layout, the metadata, the direction signs, the
  video lengths and the texture files.
