"""Checks the gaze engine against the numbers in docs/TECH_NOTES.md.

    python -m unittest tests.test_gaze -v
"""

import unittest

import numpy as np

from wrapper.gaze import CHANNELS, GazeParams, MODES, generate
from wrapper.gaze.engine import (Blink, Brow, Look, Script, saccade_duration,
                                 saccade_peak_velocity, simulate)

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


STILL = GazeParams(drift_deg=0.0, micro_rate=1e-9, head_sway_deg=(0, 0, 0), blink_mean_gap=1e6)


def band_share(x, dt, lo, hi):
    """Share of the signal's power (mean removed) between lo and hi Hz."""
    x = x - x.mean()
    f = np.fft.rfftfreq(len(x), dt)
    pw = np.abs(np.fft.rfft(x)) ** 2
    return pw[(f >= lo) & (f <= hi)].sum() / pw[1:].sum()


def rms(x):
    return float(np.sqrt(np.mean((x - x.mean()) ** 2)))


class Natural(unittest.TestCase):
    """The additions that make the motion less puppet-like (13 Nov, late)."""

    # 1. idle head sway
    def test_idle_sway_size_and_band(self):
        yaw, pitch, roll = [], [], []
        for seed in range(10):
            tr = simulate(Script(20.0, []), seed)
            c, m = tr.channels, tr.t > 0.5
            yaw.append(rms(c["head_yaw"][m]))
            pitch.append(rms(c["head_pitch"][m]))
            roll.append(rms((c["head_roll"] - P.head_roll_coupling * c["head_yaw"])[m]))
            for k in ("head_yaw", "head_pitch"):
                self.assertGreater(band_share(c[k][m], P.dt, 0.08, 0.55), 0.85, (seed, k))
        self.assertTrue(0.22 <= np.mean(yaw) <= 0.38, np.mean(yaw))
        self.assertTrue(0.22 <= np.mean(pitch) <= 0.38, np.mean(pitch))
        self.assertTrue(0.10 <= np.mean(roll) <= 0.20, np.mean(roll))

    def test_eyes_hold_the_target_through_the_sway(self):
        no_sway = GazeParams(head_sway_deg=(0, 0, 0))
        for mode in MODES:
            a = generate(mode, 0)
            b = generate(mode, 0, params=no_sway)
            self.assertGreater(np.abs(a.channels["head_yaw"] - b.channels["head_yaw"]).max(), 0.2)
            for k in ("gaze_yaw", "gaze_pitch"):
                self.assertLess(np.abs(a.channels[k] - b.channels[k]).max(), 1e-9, (mode, k))
            sway = a.channels["head_yaw"] - b.channels["head_yaw"]
            np.testing.assert_allclose(a.channels["eye_yaw"] - b.channels["eye_yaw"], -sway,
                                       atol=1e-9)

    # 2. eyes roll down and in under the lid
    def test_eyes_turn_down_and_in_during_a_blink(self):
        tr = simulate(Script(3.0, [Blink(1.0)]), 0, STILL)
        c, t = tr.channels, tr.t
        lid = c["blink_L"]
        half = np.degrees(np.arctan(P.eye_half_ipd / c["gaze_dist"]))
        half0 = np.degrees(np.arctan(P.eye_half_ipd / 0.40))
        i = int(np.argmax(lid))
        self.assertGreater(lid[i], 0.99)
        self.assertAlmostEqual(c["eye_pitch"][i], -P.blink_eye_dip, delta=0.05)
        self.assertAlmostEqual(half[i] - half0, P.blink_eye_nasal, delta=0.05)
        closing = (t > 1.0) & (t < t[i]) & (lid > 0.05)
        self.assertTrue((np.diff(c["eye_pitch"][closing]) <= 1e-12).all())   # goes as the lid goes
        after = t > 1.4
        self.assertLess(np.abs(c["eye_pitch"][after]).max(), 1e-6)            # and comes back
        self.assertLess(np.abs(half[after] - half0).max(), 1e-6)
        self.assertLess(np.abs(c["gaze_yaw"]).max(), 1e-9)                    # no conjugate yaw

    # 3. partial blinks
    def test_some_blinks_stop_short_but_never_the_first(self):
        amps = []
        for mode in MODES:
            for seed in range(30):
                tr = generate(mode, seed)
                b = tr.meta["blinks"]
                if mode in ("left", "right"):
                    self.assertGreaterEqual(b[0][1], 0.85, (mode, seed))
                amps += [a for _, a in b]
        share = np.mean(np.array(amps) < 0.8)
        self.assertTrue(0.10 <= share <= 0.25, share)
        self.assertTrue(all(0.6 <= a <= 0.8 for a in amps if a < 0.8))

    def test_a_partial_blink_closes_the_lid_to_about_70_percent(self):
        for seed in range(10):
            tr = generate("left", seed)
            for t0, a in tr.meta["blinks"]:
                if a < 0.8:
                    m = (tr.t > t0 - 0.01) & (tr.t < t0 + 0.4)
                    self.assertTrue(0.6 <= tr.channels["blink_L"][m].max() <= 0.8)
                    return
        self.fail("no partial blink in left, seeds 0-9")

    # 4. brow asymmetry per event
    def _brow_event(self, seed, t0=1.0):
        tr = simulate(Script(3.0, [Brow(t0, 0.5, 0.6)]), seed, STILL)
        c, t = tr.channels, tr.t
        pl, pr = c["brow_L"].max(), c["brow_R"].max()
        tl = t[np.argmax(c["brow_L"] > 0.5 * pl)]
        tr_ = t[np.argmax(c["brow_R"] > 0.5 * pr)]
        return min(pl, pr) / max(pl, pr), tr_ - tl

    def test_brows_differ_in_size_and_timing_per_event(self):
        ratios, lags = zip(*[self._brow_event(s) for s in range(20)])
        for r, d in zip(ratios, lags):
            self.assertTrue(0.849 <= r <= 1.0, r)
            self.assertTrue(0.015 <= abs(d) <= 0.045, d)
        self.assertGreater(np.ptp(ratios), 0.05)                  # amplitude drawn per seed
        self.assertTrue(min(lags) < 0 < max(lags))                # either side may lead

    def test_each_brow_event_draws_its_own_asymmetry(self):
        differ = 0
        for seed in range(10):
            tr = simulate(Script(5.0, [Brow(1.0, 0.4, 0.6), Brow(3.0, 0.4, 0.6)]), seed, STILL)
            c, t = tr.channels, tr.t
            out = []
            for a, b in ((0.8, 2.6), (2.8, 4.6)):
                m = (t > a) & (t < b)
                L, R = c["brow_L"][m], c["brow_R"][m]
                lag = t[m][np.argmax(R > 0.5 * R.max())] - t[m][np.argmax(L > 0.5 * L.max())]
                out.append((L.max() / R.max(), lag))
            (r0, d0), (r1, d1) = out
            self.assertTrue(abs(r0 - r1) > 0.005 or abs(d0 - d1) > 0.003, (seed, out))
            differ += abs(r0 - r1) > 0.01
        self.assertGreaterEqual(differ, 5)

    # 5. pupil
    def test_pupil_wanders_slowly_by_about_3_percent(self):
        sizes = []
        for seed in range(10):
            tr = simulate(Script(20.0, [], start_dist=0.6), seed, STILL)
            x = tr.channels["pupil"]
            sizes.append(rms(x) / P.pupil_range)
            self.assertGreater(band_share(x, P.dt, 0.25, 1.05), 0.85, seed)
        self.assertTrue(0.022 <= np.mean(sizes) <= 0.038, np.mean(sizes))

    def test_pupil_constricts_when_the_eyes_converge(self):
        look = Look(1.0, 0.0, 0.0, dist=0.30, blink=False, head=0.0)
        tr = simulate(Script(4.0, [look], start_dist=1.6), 0, STILL)
        c, t = tr.channels, tr.t
        far, near = c["pupil"][t < 1.0].mean(), c["pupil"][t > 3.0].mean()
        self.assertLess(near, far - 0.05 * P.pupil_range)

    # 6. effort of a large gaze shift in left and right
    def test_large_shifts_lift_the_brows_and_tense_the_lids_then_relax(self):
        for mode in ("left", "right"):
            for seed in range(5):
                tr = generate(mode, seed)
                c, t = tr.channels, tr.t
                brow = np.maximum(c["brow_L"], c["brow_R"])
                self.assertTrue(0.2 <= brow.max() <= 0.3, (mode, seed, brow.max()))
                self.assertTrue(0.07 <= c["squint"].max() <= 0.13, (mode, seed))
                t0 = tr.meta["saccades"][0][0]                     # the glance out
                peak = brow[(t > t0) & (t < t0 + 0.6)].max()
                self.assertGreater(peak, 0.2)
                held = brow[np.argmin(np.abs(t - (t0 + 1.2)))]
                self.assertLess(held, 0.5 * peak, (mode, seed))


if __name__ == "__main__":
    unittest.main()
