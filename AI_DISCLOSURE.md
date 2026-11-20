# AI disclosure

> Team Saccade, Vellore Institute of Technology: Harshit Aryan and Aryan Kalra.

SyntheticEyes is our idea, our design and our judgement, built with the help of an AI coding
assistant. We decided what the eyes should do and how the faces should look, checked
every result and fixed what needed fixing by hand. The AI turned those directions into code. This
page sets out who did what.

## What we did

- **The idea and the direction.** We chose the approach: one real head model, nine skin and eye
  sets on a single UV map, and eye motion driven by how real eyes move (fast jumps, eyes before
  head, blinks with big gaze shifts, lids that follow the eye). We set the priorities from the
  scoring, with textures first.
- **Choosing the assets.** We picked the head model and the skin sources, and decided to use the
  Lee Perry-Smith head scan (CC BY 3.0) after comparing test bakes, first for the pore relief and
  then for the skin colour of `tex_09`.
- **Reviewing every render.** We went through the test frames and stills and sent back lists of
  changes to the look (skin tone, shine, eye colour, lids, lashes) and to the motion (timing,
  how far the head turns, blinks, brows), until it looked and moved like a person. We also set how
  strongly the pupil reacts to near targets.
- **Fine-tuning in Blender.** We made changes by hand in Blender wherever they were needed.

## What the AI did

We used **Claude Code** (Anthropic) as a coding assistant.

- Wrote code from our directions and helped with bug fixes.
- Drafted the documentation, including the README and this page, which we
  then edited.
- Suggested starting values for the gaze engine (from eye-movement research), the lighting and
  the shaders, which we then tuned by eye.

## Not AI-generated

No image-generation model was used. Every texture and render comes from real sources or from our
own scripts:

- **Head model:** Google GNM Head (Apache-2.0).
- **Skin colour, sets 01 to 08:** MakeHuman CC0 skins, baked onto GNM's UVs.
- **Skin colour of set 09 and the pore relief of all nine sets:** "Infinite, 3D Head Scan by
  Lee Perry-Smith" (CC BY 3.0).
- **Lighting:** Poly Haven HDRI `brown_photostudio_02` (CC0).
- **Irises, sclera and detail maps:** procedural (numpy noise and drawing), not a learned model.
- **Renders and videos:** Blender 4.5.1 (Cycles and EEVEE).

Full credits and licences are in the README.

## Checking

- `python -m unittest discover tests` runs the gaze-engine tests.
- `python tools/validate.py` checks the bundle layout, the metadata, the direction signs, the
  video lengths and the texture files.
