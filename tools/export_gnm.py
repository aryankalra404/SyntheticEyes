"""Export the GNM v3 head to a plain .npz that Blender can read with numpy alone.

    .venv-gnm/bin/python tools/export_gnm.py                       # template identity
    .venv-gnm/bin/python tools/export_gnm.py --identity-seed 3     # random identity
    .venv-gnm/bin/python tools/export_gnm.py --identity-seed 3 --gender female --ethnicity asian

Reads the model weights directly (same file and cache path as GNM.from_remote).
Only --gender / --ethnicity import the GNM package (its TensorFlow identity
sampler); everything else is numpy. Output bytes are deterministic.

Output (default assets/gnm/base.npz), GNM coordinates: metres, +Y up, +Z forward.
If assets/gnm/expr_{blink_L,blink_R,brow_up,squint}.npy exist (written by
tools/spike_blink.py), their vertex deltas are stored as delta_<name>.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gnm_core as core  # noqa: E402

EXPR_SHAPES = ("blink_L", "blink_R", "brow_up", "squint")


def sample_identity(model, seed: int | None, gender: str | None,
                    ethnicity: str | None, scale: float) -> np.ndarray:
    dim = model["vertex_identity_basis"].shape[0]
    if gender or ethnicity:
        sys.path.insert(0, str(core.GNM_SRC.parents[1]))
        from gnm.shape import semantic_sampler as ss  # needs .venv-gnm with GNM installed
        g = ss.Gender[(gender or "female").upper()]
        e = ss.Ethnicity[(ethnicity or "white").upper()]
        rng = np.random.default_rng(0 if seed is None else seed)
        return ss.IdentitySampler().sample_identity(g, e, 1, rng=rng)[0].astype(np.float32) * scale
    if seed is None:
        return np.zeros(dim, np.float32)
    # Plain Gaussian on the 170 head coefficients; eyeball and teeth stay at the mean.
    ident = np.zeros(dim, np.float32)
    ident[:170] = np.random.default_rng(seed).standard_normal(170) * scale
    return ident


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=None, help="gnm_head.npz (default: GNM cache)")
    ap.add_argument("--out", type=Path, default=core.REPO / "assets/gnm/base.npz")
    ap.add_argument("--identity-seed", type=int, default=None)
    ap.add_argument("--identity-scale", type=float, default=1.0)
    ap.add_argument("--gender", choices=["female", "male"])
    ap.add_argument("--ethnicity", choices=["middle_eastern", "asian", "white", "black"])
    args = ap.parse_args()

    model_path = core.fetch_model(args.model or core.default_model_path())
    m = core.load_model(model_path)
    groups = core.Groups(m)

    identity = sample_identity(m, args.identity_seed, args.gender, args.ethnicity, args.identity_scale)
    verts = (m["template_vertex_positions"]
             + np.einsum("i,ivk->vk", identity, m["vertex_identity_basis"])).astype(np.float32)
    joints = (m["template_joint_positions"]
              + np.einsum("i,ijk->jk", identity, m["joint_identity_basis"])).astype(np.float32)

    quad_tiles = core.udim_tiles(m, m["quads"])
    tri_tiles = core.udim_tiles(m, m["triangles"])
    lm_idx, lm_w = core.load_landmarks()

    out = {
        "vertices": verts,
        "template_vertices": m["template_vertex_positions"].astype(np.float32),
        "identity": identity,
        "quads": m["quads"].astype(np.int32),
        "triangles": m["triangles"].astype(np.int32),
        "quad_uvs": m["quad_uvs"].astype(np.float32),
        "quad_udim_tiles": quad_tiles,
        "quad_uvs_udim": core.udim_uvs(m["quad_uvs"], quad_tiles).astype(np.float32),
        "triangle_uvs": m["triangle_uvs"].astype(np.float32),
        "triangle_udim_tiles": tri_tiles,
        "triangle_uvs_udim": core.udim_uvs(m["triangle_uvs"], tri_tiles).astype(np.float32),
        "joint_names": m["joint_names"],
        "joint_positions": joints,
        "joint_parents": m["joint_parent_indices"].astype(np.int32),
        "skinning_weights": m["skinning_weights"].astype(np.float32),
        "vertex_group_names": m["vertex_group_names"],
        "vertex_group_weights": m["vertex_groups"].astype(np.float32),
        "vertex_group_masks": np.stack([groups.mask(n) for n in groups.names]),
        "mirror_indices": m["mirror_indices"].astype(np.int32),
        "landmark_indices": lm_idx,
        "landmark_weights": lm_w,
        "expression_names": m["expression_names"],
        "expression_basis": m["expression_basis"].astype(np.float32),
        "model_sha256": np.array(core.sha256(model_path)),
        "model_version": m["version"],
        "coordinates": np.array("metres, +Y up, +Z forward (out of face), subject left eye at +X"),
    }

    expr_dir = args.out.parent
    for name in EXPR_SHAPES:
        f = expr_dir / f"expr_{name}.npy"
        if f.exists():
            vec = np.load(f, allow_pickle=False).astype(np.float32)
            out[f"expr_{name}"] = vec
            out[f"delta_{name}"] = np.einsum("e,evk->vk", vec, m["expression_basis"]).astype(np.float32)

    core.save_npz_deterministic(args.out, out)
    deltas = [k for k in out if k.startswith("delta_")]
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB): "
          f"{len(verts)} verts, {len(out['quads'])} quads, joints {list(map(str, m['joint_names']))}, "
          f"identity |c|={np.linalg.norm(identity):.2f}, deltas {deltas or 'none (run spike_blink.py)'}")


if __name__ == "__main__":
    main()
