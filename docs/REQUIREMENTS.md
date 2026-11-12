# Requirements

Three sources, in priority order. Where they disagree, satisfy all of them.

1. Organisers' mail: *"Criteria is all the outputs to be generated as per slide 2, and given
   the output, the brownie points are gained for more natural human-like realistic simulation."*
2. `Evaluation_for_SyntheticEyes_1.pptx` (the "evaluation PPT").
3. `XR_Hackathon_2026_Consolidated_Slides_for_sharing_v1.pdf`, Track 1 slides 3–7 and
   general rules slides 23–26 (the "PDF spec").

`Evaluation_for_SyntheticEyes (3).pptx`, read on 12 Nov 2026, has the same two slides as `_1`.
The evaluation PPT still says "Submission Due: Oct 28, 2026"; the PDF timeline (18 Nov) is current.

## A. Evaluation PPT, slide 2 (the rubric that counts)

### Texture photorealism — 60 pts
High-frequency skin and iris textures, natural looks, realistic colours and skin textures.
**Use the GNM or FLAME UV map only.**

Outputs:
1. Textured UV maps (5–10), including face and eye texture. "The textures will be directly
   wrapped around GNM Head Model."
2. Python script to render the output with the generated textures.
3. 5–10 rendered images with different textures.

### Kinematic accuracy — 20 pts
Coordinated eye rotation (left, right, up, down), realistic eyelid closure, natural
expressions similar to a human.

A Python script that renders these movements for these inputs:
- **Left** — both eyes move left, natural eye expression
- **Right** — both eyes move right, natural eye expression
- **Generate Motion** — a realistic eye movement expression (move left and right, or roll
  the eyes upward; create a natural expression)

Outputs:
1. Python script with an option to take any of the 3 inputs, render the frames and create a video.
2. Rendered videos for all 3 inputs, captured by the team. **Each video ≤ 15 seconds.**

### Code & UV portability — 20 pts
A `.blend` file that loads the head model and animates an expression using the
**Timeline panel in Blender**. For more realism animate eyelids, iris and eyebrows.
The goal is to imitate natural human expression.

### Evaluation standard
Visual photorealism, seam absence, kinematic smoothness, UV map compatibility.
Verification: direct asset portability and automated execution.

### Recommended flow (slide 1)
Load GNM head → script identity shape and expression → eye motion left/right/up/down →
eyelid closure coordinated with gaze (continuous, fully open to partly closed) →
apply built-in UV texture or bake skin textures from other sources by comparing UV maps →
separate high-resolution iris maps for left and right eyes → photorealism audit for seams
and artifacts.

### Reference videos named by the organisers
Introduced as "watch the below two videos to understand how natural eye expressions are
simulated. For ex:". Both are by Chris Jones; what each shows is in TECH_NOTES, "Reference bar".
- https://youtu.be/TAZIvyAJfeM — "Eye Piece": textured extreme close-up of one eye.
- https://youtu.be/gh6WbaYzwFc — "Flexpressions": untextured grey head pulling expressions.

## B. PDF spec, Track 1

### Key specifications
- Textured, articulatable face rig (MakeHuman / GNM / FLAME) with left/right eye bones
- Fixation target **35 cm** forward from the eye midpoint, motion bounds **± 5 cm**
- Render camera locked **40 cm** forward, facing the face
- **1024×1024 PNG** under constant lighting
- Deterministic Python controls `eyes.move(h, v)` / `eyes.reset()` / `eyes.render()`,
  normalised inputs in [-1, +1]
- 10 clockwise renders at θk = 2πk/10 (k = 0..9), h = sin θk, v = cos θk, starting at top
- Per-frame ground-truth JSON with 2D pupil centres

### Direction check (pass/fail)
Pupil shift must be visibly correct versus centre for Left, Right, Up, Down and Reset.
All 5 of 5 must pass.

### Bundle layout — "non-standard layouts fail"
```
team_name.zip
├── scene.blend          textured mesh, eye bones, materials
├── wrapper/eyes.py      eyes.move(h,v) / eyes.reset() / eyes.render()
├── renders/             10 clockwise frames
├── metadata.json        per-frame inputs, rotations, pupil centres
└── README.md            setup and run instructions
```

### metadata.json, one record per render
```
{
  "frame": 3,
  "theta": 1.8849,
  "input": { "h": 0.951, "v": 0.309 },
  "eye_rotation_L": [rx, ry, rz],
  "eye_rotation_R": [rx, ry, rz],
  "pupil_center_2D_L": [x, y],
  "pupil_center_2D_R": [x, y],
  "camera_matrix": [ ... ]
}
```
3D rotations in the world frame; 2D pupils projected at 40 cm.

### PDF scoring (superseded by the PPT, kept as a cross-check)
Execution & efficiency 40 (calibration 20, automation 20); quality & movement 60
(direction pass/fail 40, sequence & metadata 20).

## C. General submission rules (PDF slides 23–25)

- One submission per team through the Google Form, by **18 Nov 2026, 11:59 PM**
- Working prototype code in a public or shared GitHub repo
- README with reproducible setup instructions, Docker files and other requirements
- Demo video, **max 3 minutes** (slide 25; other slides say 5 minutes, so stay under 3),
  YouTube or Drive link
- Presentation, PPT or PDF, named `CollegeName_TeamName`, covering: theme ID, project title,
  team details, problem statement in own words, solution and architecture diagram, tools and
  tech stack, innovation highlights, results, limitations
- Not following the guideline means disqualification
- 23 Nov top 15 announced, 27 Nov live demo to a Samsung R&D jury, 2 Dec results

## D. Deliverables checklist

- [ ] `scene.blend` — GNM head, eye bones, materials, expression keyframed on the Timeline
- [ ] `wrapper/eyes.py` — `move`, `reset`, `render`, plus `--input left|right|generate`,
      `--texture NN`, `--clockwise`, `--seed`, `--quality`
- [ ] `textures/tex_01 … tex_08` — skin + left eye + right eye, UDIM and legacy names
- [ ] `outputs/stills/` — one render per texture set (5–10)
- [ ] `outputs/videos/left.mp4`, `right.mp4`, `generate.mp4` — each ≤ 15 s
- [ ] `renders/` — 10 clockwise 1024×1024 PNGs
- [ ] `metadata.json` — 10 records, schema above
- [ ] `README.md` — setup, run, conventions, licences
- [ ] `Dockerfile`
- [ ] Demo video ≤ 3 min
- [ ] Deck `CollegeName_TeamName.pdf`
- [ ] Zip named `team_name.zip`, tested from a clean unzip
