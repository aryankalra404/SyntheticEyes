# Demo video

The one video the submission form asks for: **3 minutes or shorter**, a YouTube or Drive link.
(One slide says 5 minutes; stay under 3.) It is recorded and cut by hand. It is not the three
output videos (`left.mp4`, `right.mp4`, `generate.mp4`), which Blender renders from the script;
those are clips inside it.

Aim for about 2:40. No section should run long: the jury has many of these to watch.

## Needs to exist first

- The three final videos in `outputs/videos/` (not the drafts)
- The nine stills and `outputs/stills/eye/sheet.png`
- `scene.blend` as committed, opening in Blender 4.5.1
- Team and college name for the title card

## Shot list

| Time | Shot | Source | Caption on screen |
|---|---|---|---|
| 0:00–0:08 | The eye close-up, moving: a gaze shift and a blink | first seconds of `generate.mp4` or `left.mp4` | none; let it play |
| 0:08–0:14 | Title card | made in the editor | SyntheticEyes · Track 1 · team, college |
| 0:14–0:26 | `left.mp4`, whole clip or its best 10 s | `outputs/videos/left.mp4` | Input: left |
| 0:26–0:38 | `right.mp4` | `outputs/videos/right.mp4` | Input: right |
| 0:38–0:52 | `generate.mp4` | `outputs/videos/generate.mp4` | Input: generate (seeded, natural gaze, blinks, brows) |
| 0:52–1:12 | The nine faces, then the nine eye close-ups, about 1 s each | `outputs/stills/tex_NN.png`, `outputs/stills/eye/tex_NN_eye.png` | 9 texture sets in GNM UV space |
| 1:12–1:27 | One texture set flat in the image editor, then on the head; switch between three sets | Blender, UV editor beside the viewport | Skin, normal, roughness, left and right eye; UDIM and legacy names |
| 1:27–1:42 | Wireframe over the textured head, toggle to rendered view; zoom on the lid: lashes and tear line as geometry | Blender viewport | Google GNM Head v3, unmodified topology |
| 1:42–1:57 | Select the rig, turn an eye bone, drag the blink and lid sliders | Blender, shape keys panel | Lids solved to stay on the eyeball |
| 1:57–2:12 | Press play on the Timeline; eyes, lids and brows move | Blender, Timeline visible | The expression is keyframed in `scene.blend` |
| 2:12–2:27 | Terminal: one command runs, frames render, the mp4 appears. Then the 10 clockwise renders and `metadata.json` open side by side | terminal, Finder, a text editor | One command, no manual steps; calibrated `eyes.move(h, v)` with ground truth |
| 2:27–2:40 | Back to the eye close-up, hold, credits | `generate.mp4`, editor | Credits: GNM (Apache-2.0), MakeHuman (CC0), Poly Haven (CC0), "Infinite, 3D Head Scan by Lee Perry-Smith" (CC BY 3.0) |

The credit for the head scan is required by its licence. Do not drop it.

## Recording in Blender

- Open `scene.blend`. Use Material Preview or Rendered viewport shading for anything textured;
  Solid mode shows a grey head.
- Before the wireframe shot, hide the helper objects so the view is clean: everything named
  `*_carrier`, `globe_guard.L` and `globe_guard.R`, and the brow hair objects that are not in
  use. Do not save the file afterwards.
- For the Timeline shot, make the Timeline tall enough that the keyframes are visible, set the
  frame to 1 and press play. Record at least one full loop.
- For the texture switch, run this in Blender's Python console (the path must be the repo root):

  ```python
  import sys; sys.path.insert(0, "/path/to/samsung-prism")
  from wrapper import eyes
  eyes.use_texture(3)
  ```

- Command for the terminal shot (draft quality renders in a few minutes, good for a recording):

  ```bash
  /Applications/Blender.app/Contents/MacOS/Blender -b scene.blend -P wrapper/eyes.py -- --input left --quality draft
  ```

- Record the screen at 1920 × 1080 or higher, 30 fps. Hide the dock and notifications.

## Editing

- Cut on motion, not on stillness: start each clip just before a gaze shift.
- Captions short, bottom of the frame, same font throughout. No voice-over is needed; if one
  is added, keep it to one sentence per shot.
- Music is optional. If used, it must be free to use and credited.
- Export 1080p H.264. Watch it once at full speed before uploading and check the length.

## After upload

- Put the link in `README.md` (there is a TODO line for it) and in the deck.
- Make the YouTube video Unlisted or Public, or the Drive link "anyone with the link"; the jury
  must be able to open it without signing in.
