"""Checks the gaze engine against the numbers in docs/TECH_NOTES.md.

    python -m unittest tests.test_gaze -v
"""

import unittest

import numpy as np

from wrapper.gaze import CHANNELS, GazeParams, MODES, generate
from wrapper.gaze.engine import Look, Script, saccade_duration, saccade_peak_velocity, simulate

P = GazeParams()


def speed(track, a="gaze_yaw", b="gaze_pitch"):
    c = track.channels
    return np.hypot(np.gradient(c[a], P.dt), np.gradient(c[b], P.dt))


class MainSequence(unittest.TestCase):
    def test_small_saccades_take_30_to_45_ms(self):
        for amp in (5.0, 7.5, 10.0):
            self.assertTrue(0.028 <= saccade_duration(amp) <= 0.046, (amp, saccade_duration(amp)))

    def test_duration_grows_with_amplitude(self):
        d = [saccade_duration(a) for a in (2, 5, 10, 20, 30)]
        self.assertEqual(d, sorted(d))

    def test_30_degree_saccade_peaks_near_500(self):
        self.assertTrue(450 <= saccade_peak_velocity(30.0) <= 600)
        quiet = GazeParams(drift_deg=0.0, micro_rate=1e-9, head_sway_deg=(0, 0, 0),
                           undershoot_from=99.0, glissade_frac=0.0)
        tr = simulate(Script(2.0, [Look(0.5, 30.0, 0.0, blink=False, head=0.0)]), 0, quiet)
        self.assertTrue(450 <= speed(tr).max() <= 620, speed(tr).max())


class Behaviour(unittest.TestCase):
    def test_same_seed_same_motion(self):
        for mode in MODES:
            a, b = generate(mode, 3), generate(mode, 3)
            for k in CHANNELS:
                self.assertTrue(np.array_equal(a.channels[k], b.channels[k]), (mode, k))
            self.assertFalse(np.array_equal(a.channels["gaze_yaw"],
                                            generate(mode, 4).channels["gaze_yaw"]))

    def test_videos_fit_in_15_seconds(self):
        for mode in MODES:
            self.assertLessEqual(generate(mode, 0).duration, 15.0)

    def test_left_goes_image_left_and_right_goes_right(self):
        for seed in range(5):
            l, r = generate("left", seed), generate("right", seed)
            self.assertLess(l.channels["gaze_yaw"].min(), -20)
            self.assertLess(l.channels["gaze_yaw"].max(), 6)
            self.assertGreater(r.channels["gaze_yaw"].max(), 20)
            self.assertGreater(r.channels["gaze_yaw"].min(), -6)

    def test_starts_and_ends_on_the_viewer(self):
        for mode in MODES:
            for seed in range(5):
                c = generate(mode, seed).channels
                for k in ("gaze_yaw", "gaze_pitch"):
                    self.assertLess(abs(c[k][0]), 1.0)
                    self.assertLess(abs(c[k][-1]), 3.0, (mode, seed, k))

    def test_saccades_are_at_least_150_ms_apart(self):
        for mode in MODES:
            for seed in range(5):
                s = generate(mode, seed).meta["saccades"]
                for (t0, d0, _), (t1, _, _) in zip(s, s[1:]):
                    self.assertGreaterEqual(t1 - (t0 + d0), 0.149, (mode, seed))

    def test_eye_stays_in_oculomotor_range(self):
        for mode in MODES:
            for seed in range(5):
                c = generate(mode, seed).channels
                self.assertLessEqual(np.abs(c["eye_yaw"]).max(), P.eye_yaw_max + 1e-6)
                self.assertLessEqual(c["eye_pitch"].max(), P.eye_pitch_up + 1e-6)
                self.assertGreaterEqual(c["eye_pitch"].min(), -P.eye_pitch_down - 1e-6)

    def test_head_moves_less_and_later_than_the_eyes(self):
        tr = generate("left", 0)
        c, t = tr.channels, tr.t
        self.assertLess(np.abs(c["head_yaw"]).max(), 0.6 * np.abs(c["gaze_yaw"]).max())
        self.assertGreater(np.abs(c["head_yaw"]).max(), 4.0)
        t_eye = t[np.argmax(np.abs(c["gaze_yaw"]) > 10)]
        t_head = t[np.argmax(np.abs(c["head_yaw"]) > 0.5 * np.abs(c["head_yaw"]).max())]
        self.assertGreater(t_head, t_eye + 0.05)

    def test_gaze_holds_while_the_head_catches_up(self):
        tr = generate("left", 0)
        c, t = tr.channels, tr.t
        t0, d0, _ = tr.meta["saccades"][1]                    # corrective saccade has landed
        m = (t > t0 + d0 + 0.05) & (t < t0 + d0 + 0.45)
        self.assertGreater(np.ptp(c["head_yaw"][m]), 1.0)     # head still turning
        self.assertLess(np.ptp(c["gaze_yaw"][m]), 0.8)        # gaze stays put


class Blinks(unittest.TestCase):
    def test_closing_is_about_twice_as_fast_as_opening(self):
        tr = generate("generate", 1)
        b, t = tr.channels["blink_L"], tr.t
        t0 = tr.meta["blinks"][0][0]
        m = (t >= t0 - 0.01) & (t <= t0 + 0.4)
        v = np.gradient(b[m], P.dt)
        self.assertTrue(1.6 <= v.max() / -v.min() <= 2.8, v.max() / -v.min())

    def test_blink_rate_is_human(self):
        n = sum(len(generate(m, s).meta["blinks"]) for m in MODES for s in range(8))
        secs = sum(generate(m, 0).duration for m in MODES) * 8
        self.assertTrue(8 <= 60.0 * n / secs <= 32, 60.0 * n / secs)

    def test_no_blink_at_either_end(self):
        for mode in MODES:
            for seed in range(5):
                tr = generate(mode, seed)
                b, t = np.maximum(tr.channels["blink_L"], tr.channels["blink_R"]), tr.t
                self.assertEqual(b[t < 0.3].max(), 0.0)
                self.assertEqual(b[t > tr.duration - 0.3].max(), 0.0)

    def test_blinks_reach_closed_and_reopen(self):
        tr = generate("left", 2)
        b = tr.channels["blink_L"]
        self.assertGreater(b.max(), 0.84)
        self.assertEqual(b[-1], 0.0)


class Channels(unittest.TestCase):
    def test_all_channels_present_finite_and_in_range(self):
        for mode in MODES:
            tr = generate(mode, 0)
            self.assertEqual(set(tr.channels), set(CHANNELS))
            for k, v in tr.channels.items():
                self.assertTrue(np.isfinite(v).all(), k)
            for k in ("blink_L", "blink_R", "brow_L", "brow_R", "widen", "squint"):
                self.assertTrue(0.0 <= tr.channels[k].min() and tr.channels[k].max() <= 1.0, k)
            self.assertGreater(tr.channels["gaze_dist"].min(), 0.2)

    def test_frames_are_numbered_from_one(self):
        rows = generate("left", 0).frames(30)
        self.assertEqual(rows[0]["frame"], 1)
        self.assertEqual(len(rows), 270)

    def test_brows_rise_when_the_eyes_roll_up(self):
        tr = generate("generate", 0)
        c = tr.channels
        i = int(np.argmax(c["eye_pitch"]))
        self.assertGreater(c["eye_pitch"][i], 18.0)
        self.assertGreater(max(c["brow_L"][i], c["brow_R"][i]), 0.4)


if __name__ == "__main__":
    unittest.main()
