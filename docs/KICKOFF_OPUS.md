# Kickoff brief — M0 setup and spikes

Paste everything below the line into a new Claude Code session opened in this repo on the Mac.

---

You are starting milestone M0 of a hackathon project. Read `CLAUDE.md`,
`docs/REQUIREMENTS.md`, `docs/PLAN.md` and `docs/TECH_NOTES.md` first, in that order.
They hold the decisions already made; do not reopen them.

Machine: Apple Silicon Mac (M4). Work only inside this repo plus `~/.cache`.
Deadline for M0: tonight. Keep it mechanical; do not start on the rig, textures or shaders.

## Tasks

1. **Blender.** Check for `/Applications/Blender.app`. If missing, install the current LTS
   release (`brew install --cask blender` or the official download). Record the exact
   version and its bundled Python version in `docs/PROGRESS.md`. Confirm that
   `$BLENDER -b --python-expr "import bpy, numpy; print(bpy.app.version_string, numpy.__version__)"` runs.

2. **GNM environment.** Create `.venv-gnm` with Python 3.12 or 3.13 (use `uv` if present).
   Clone `https://github.com/google/GNM` into `assets/third_party/gnm` (git-ignored) and
   `pip install -e assets/third_party/gnm/gnm/shape`. Load the model with
   `gnm_numpy.GNM.from_remote(version=GNMMajorVersion.V3, variant=GNMVariant.HEAD)`.

3. **Inspect the real model** and write what you find to `docs/GNM_FACTS.md`:
   vertex, quad and triangle counts; `joint_names` with order, parents and rest positions;
   `vertex_group_names` with sizes; identity and expression dimensions; which expression
   indices are left eye, right eye, lower face, tongue, pupil; UDIM tiles present; units
   (metres or centimetres) and which axes are up and forward; distance between the eye joints.
   Read the package source for this rather than guessing. Correct anything in
   `docs/TECH_NOTES.md` that turns out to be wrong.

4. **`tools/export_gnm.py`.** Runs in `.venv-gnm`. Writes `assets/gnm/base.npz` with:
   template vertices, quads, triangles, `quad_uvs_udim`, `quad_udim_tiles`, legacy
   `quad_uvs`, joint names, positions and parents, skinning weights, vertex group masks,
   and the 68 landmark indices and weights. Takes `--identity-seed` and optional
   gender/ethnicity so later we can export other identities. Deterministic.

5. **Blink spike.** With the `ExpressionSampler`, draw 64 samples each of `WINK_LEFT`,
   `WINK_RIGHT`, `SURPRISE` and `SQUINT`, average them, keep only the eye-region
   coefficients for the relevant side, and save the vectors to `assets/gnm/expr_*.npy`.
   Save vertex deltas for `blink.L`, `blink.R`, `brow_up`, `squint` into `base.npz`.
   Measure the gap between upper and lower lid margins at weight 0, 0.5 and 1.0 and report
   it. If the lid does not close at 1.0, try scaling the vector and report what scale closes it.

6. **`tools/smoke_render.py`.** Runs under `blender -b`. Builds the mesh from `base.npz`
   with plain grey material, places a camera 40 cm in front of the eye midpoint looking at
   the face, 1024×1024, one area light, Cycles on Metal GPU. Renders three PNGs to
   `outputs/spike/`: neutral, left lid closed, right lid closed. Then renders neutral with
   the eye joints rotated 15° left and 15° up to confirm the eyeballs rotate about their
   centres. Open every PNG and check it before reporting.

7. **Benchmark.** Time a 1024×1024 Cycles frame at 64, 128 and 256 samples with denoising
   on the M4 GPU. Add the numbers to `docs/PROGRESS.md`.

8. **Assets.** Download into `assets/third_party/` (git-ignored): MakeHuman asset packs
   Skins 01, Skins 02, Eyebrows 01, Eyelashes 01 and the system assets from
   https://static.makehumancommunity.org/assets/assetpacks.html, the MakeHuman base mesh
   (or install the MPFB extension if that is the simplest way to get it with UVs), and one
   soft indoor 2K HDRI from Poly Haven. List each file, its source URL and licence in
   `docs/TECH_NOTES.md` under Assets. Confirm each licence on its download page.

9. **Housekeeping.** Make sure `.gitignore` covers everything large. Update
   `docs/PROGRESS.md`: what is done, measurements, anything surprising, what M1 and M2
   need to know.

## Done when

- `outputs/spike/` has the five renders and you have looked at each one
- `docs/GNM_FACTS.md` exists and matches the model
- `docs/PROGRESS.md` has the Blender version, the benchmark and the blink result
- everything is committed and pushed

## Rules

- Commit messages: one line, plain, lowercase, no AI attribution, no co-author lines.
- Do not put model weights, asset packs or the GNM clone in git.
- If the blink spike fails, stop and write up exactly what you saw. Do not build a workaround;
  that decision goes to the M1 session.
- If a download is blocked or a licence is not what the notes say, record it and move on.
