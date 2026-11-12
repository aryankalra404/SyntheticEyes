"""M0 blink spike: eyelid, brow and squint shape vectors from GNM's ExpressionSampler.

    .venv-gnm/bin/python tools/spike_blink.py            # needs GNM installed in .venv-gnm
    .venv-gnm/bin/python tools/export_gnm.py             # then re-export to add delta_* arrays

Draws N samples each of WINK_LEFT, WINK_RIGHT, SURPRISE and SQUINT (fixed seed),
averages them and keeps only the eye-region coefficients:

    expr_blink_L.npy   WINK_LEFT,  left_eye_region (0..99) only
    expr_blink_R.npy   WINK_RIGHT, right_eye_region (100..199) only
    expr_brow_up.npy   SURPRISE,   both eye regions
    expr_squint.npy    SQUINT,     both eye regions

WINK_LEFT is assumed to close the subject's left eye (+X); the script measures both
sides and reports if that is wrong instead of guessing.

Reports the gap between upper and lower lid margins (column through the pupil) at
weight 0, 0.5 and 1.0, and if the lid does not close at 1.0, the smallest scale up
to 3.0 that closes it. Writes everything to assets/gnm/blink_spike.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gnm_core as core  # noqa: E402

CLOSED_MM = 0.2  # gap at or below this counts as closed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, default=core.REPO / "assets/gnm")
    args = ap.parse_args()

    sys.path.insert(0, str(core.GNM_SRC.parents[1]))
    from gnm.shape import semantic_sampler as ss

    m = core.load_model()
    V0 = m["template_vertex_positions"].astype(np.float64)
    B = m["expression_basis"].astype(np.float64)
    margins = {s: core.lid_margins(m, s) for s in ("L", "R")}

    sampler = ss.ExpressionSampler()
    rng = np.random.default_rng(args.seed)

    def mean_sample(label):
        return sampler.sample_expression(label, num_samples=args.samples, rng=rng).mean(axis=0)

    def keep(vec, *regions):
        out = np.zeros_like(vec)
        for r in regions:
            out[r] = vec[r]
        return out.astype(np.float32)

    raw = {
        "wink_left": mean_sample(ss.Expression.WINK_LEFT),
        "wink_right": mean_sample(ss.Expression.WINK_RIGHT),
        "surprise": mean_sample(ss.Expression.SURPRISE),
        "squint": mean_sample(ss.Expression.SQUINT),
    }
    vecs = {
        "blink_L": keep(raw["wink_left"], core.EXPR_LEFT_EYE),
        "blink_R": keep(raw["wink_right"], core.EXPR_RIGHT_EYE),
        "brow_up": keep(raw["surprise"], core.EXPR_LEFT_EYE, core.EXPR_RIGHT_EYE),
        "squint": keep(raw["squint"], core.EXPR_LEFT_EYE, core.EXPR_RIGHT_EYE),
    }

    def gaps(vec, scale):
        V = V0 + scale * np.einsum("e,evk->vk", vec, B)
        return {s: round(core.lid_gap_mm(V, *margins[s]), 3) for s in ("L", "R")}

    report = {"samples": args.samples, "seed": args.seed, "closed_threshold_mm": CLOSED_MM,
              "rest_gap_mm": gaps(np.zeros(B.shape[0]), 0.0)}

    # Which eye does each full wink close? (checks the left/right assumption)
    report["full_wink_gap_mm"] = {k: gaps(raw[k], 1.0) for k in ("wink_left", "wink_right")}

    for name, side in (("blink_L", "L"), ("blink_R", "R")):
        r = {f"w{w}": gaps(vecs[name], w) for w in (0.0, 0.5, 1.0)}
        closing = None
        if r["w1.0"][side] > CLOSED_MM:
            for s in np.arange(1.05, 3.0001, 0.05):
                if gaps(vecs[name], s)[side] <= CLOSED_MM:
                    closing = round(float(s), 2)
                    break
        else:
            closing = 1.0
        r["scale_to_close"] = closing
        report[name] = r
    for name in ("brow_up", "squint"):
        report[name] = {"w1.0": gaps(vecs[name], 1.0)}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, vec in vecs.items():
        np.save(args.out_dir / f"expr_{name}.npy", vec)
    for name, vec in raw.items():
        np.save(args.out_dir / f"expr_raw_{name}.npy", vec.astype(np.float32))
    (args.out_dir / "blink_spike.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
