# Progress

Newest entry first. One entry per working session: what changed, what was measured,
what the next session needs to know.

## Status

| Milestone | State |
|---|---|
| M0 Setup and spikes | not started |
| M1 Rig and calibrated wrapper | not started |
| M2 Texture pipeline | not started |
| M3 Look | not started |
| M4 Motion | not started |
| M5 Compliance and packaging | not started |
| M6 Ship | not started |

## Open questions

- Does the DRM-locked `Evaluation_for_SyntheticEyes.pptx` differ from `_1.pptx`?
- What does the second reference video (youtu.be/TAZIvyAJfeM) show?
- College and team name for the zip and deck (`CollegeName_TeamName`)
- Exact Blender version to pin (set in M0)

## Log

### Thu 12 Nov 2026 — planning
- Read the hackathon PDF and the evaluation PPT; requirements are in `REQUIREMENTS.md`
- Chose GNM Head v3 as the base model and read its repo at commit `846ab76`
- Found: UDIM UV layout with separate tiles per eye, 4 joints including both eyes,
  no blink class but `WINK_LEFT` / `WINK_RIGHT` exist, 68 landmarks included,
  no skin texture included
- Wrote the plan, tech notes and the M0 brief
