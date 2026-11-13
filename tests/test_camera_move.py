"""The video camera moves only while the eyes hold still.

    python -m unittest tests.test_camera_move -v
"""

import unittest

import numpy as np

from wrapper import camera_move as cm
from wrapper.gaze import generate

SEEDS = range(8)


class Glides(unittest.TestCase):
    def test_glides_lie_inside_fixations(self):
        for mode in cm.ORDER:
            for seed in SEEDS:
                tr = generate(mode, seed=seed)
                busy = cm.busy_mask(tr)
                for _, _, _, _, pieces in cm.plan(tr, mode):
                    for p0, p1 in pieces:
                        inside = (tr.t >= p0) & (tr.t <= p1)
                        self.assertFalse(busy[inside].any(), (mode, seed, p0, p1))

    def test_no_glide_across_a_saccade_or_blink(self):
        for mode in cm.ORDER:
            for seed in SEEDS:
                tr = generate(mode, seed=seed)
                pieces = [p for g in cm.plan(tr, mode) for p in g[4]]
                for t0, dur, _ in tr.meta["saccades"]:
                    for p0, p1 in pieces:
                        self.assertTrue(t0 + dur < p0 or t0 > p1, (mode, seed, t0, p0, p1))
                closed = np.maximum(tr.channels["blink_L"], tr.channels["blink_R"]) > 0.01
                for p0, p1 in pieces:
                    self.assertFalse(closed[(tr.t >= p0) & (tr.t <= p1)].any(), (mode, seed))

    def test_order_lengths_and_holds(self):
        for mode in cm.ORDER:
            for seed in SEEDS:
                tr = generate(mode, seed=seed)
                (a0, a1, f0, f1, pa), (b0, b1, f2, f3, pb) = cm.plan(tr, mode)
                self.assertEqual((f0, f1, f3), cm.ORDER[mode])
                self.assertEqual(f1, f2)
                for a, b, pieces in ((f0, f1, pa), (f2, f3, pb)):
                    need = cm.glide_time(a, b)
                    move = sum(p1 - p0 for p0, p1 in pieces)
                    self.assertTrue(0.75 * need <= move <= need + cm.MIN_PIECE, (mode, seed, move))
                    self.assertLessEqual(len(pieces), cm.MAX_PIECES)
                    for p0, p1 in pieces:
                        self.assertGreaterEqual(p1 - p0, cm.MIN_PIECE - 1e-6)
                    for (_, e), (s, _) in zip(pieces, pieces[1:]):
                        self.assertLess(e, s)
                self.assertGreaterEqual(a0, cm.MIN_HOLD - 1e-6)
                self.assertGreaterEqual(b0 - a1, cm.MIN_HOLD - 1e-6)
                self.assertGreaterEqual(tr.duration - b1, cm.MIN_HOLD - 1e-6)

    def test_first_gaze_shift_is_seen_with_both_eyes(self):
        for mode in ("left", "right"):
            for seed in SEEDS:
                tr = generate(mode, seed=seed)
                t0, dur, _ = next(s for s in tr.meta["saccades"] if s[2] >= cm.SHIFT_DEG)
                g0 = cm.plan(tr, mode)[0][4][0][0]
                self.assertGreaterEqual(g0, t0 + dur + cm.SHIFT_SEEN - 1e-6, (mode, seed))

    def test_same_track_same_move(self):
        a = cm.plan(generate("generate", seed=3), "generate")
        b = cm.plan(generate("generate", seed=3), "generate")
        self.assertEqual(a, b)


class Frames(unittest.TestCase):
    def test_eye_glides_are_slower(self):
        self.assertGreaterEqual(cm.GLIDE["eye"], 1.5)
        for mode in cm.ORDER:
            for _, _, a, b, pieces in cm.plan(generate(mode, seed=0), mode):
                if "eye" not in (a, b):
                    continue
                move = sum(p1 - p0 for p0, p1 in pieces)
                self.assertGreaterEqual(move, cm.glide_time(a, b) - 0.05, (mode, a, b, move))

    def test_blend_eases_and_head_follow_only_near_the_eye(self):
        for mode in cm.ORDER:
            tr = generate(mode, seed=0)
            rows, glides = cm.frames(tr, mode)
            self.assertEqual(len(rows), int(round(tr.duration * 30)))
            for row in rows:
                if "eye" not in (row["a"], row["b"]):
                    self.assertEqual(row["follow"], 0.0)
                elif row["a"] == row["b"] == "eye":
                    self.assertEqual(row["follow"], 1.0)
            for _, _, a, b, _ in glides:
                s = [r["s"] for r in rows if r["a"] == a and r["b"] == b]
                self.assertEqual(s, sorted(s))
                self.assertLess(s[0], 0.05)
                self.assertGreater(s[-1], 0.95)

    def test_camera_still_while_eyes_move(self):
        for mode in cm.ORDER:
            tr = generate(mode, seed=0)
            rows, _ = cm.frames(tr, mode)
            busy = cm.busy_mask(tr)
            for r0, r1 in zip(rows, rows[1:]):
                if (r0["a"], r0["b"], r0["s"]) != (r1["a"], r1["b"], r1["s"]):
                    span = (tr.t >= r0["time"]) & (tr.t <= r1["time"])
                    self.assertFalse(busy[span].any(), (mode, r0["frame"]))


if __name__ == "__main__":
    unittest.main()
