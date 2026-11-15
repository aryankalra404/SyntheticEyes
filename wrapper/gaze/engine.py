"""Gaze engine: turns a short script of intentions into continuous, human-like channels.

Pure Python + numpy, no bpy. Runs inside Blender's Python and outside it.

Sign conventions (image space, as the render camera sees the face):
    yaw   > 0  toward image-right        pitch > 0  up
    head roll > 0  top of the head tilts toward image-right

Channels (all sampled on the same clock, degrees unless noted):
    gaze_yaw, gaze_pitch     where the eyes point, in the world / camera frame
    gaze_dist                fixation distance in metres (drives vergence); shortens under a
                             blink, which is how the eyes turn toward the nose behind the lids
    head_yaw, head_pitch, head_roll    include an idle sway the eyes counter-rotate against
    eye_yaw, eye_pitch       eye-in-head = gaze - head; use eye_pitch for lid follow
    blink_L, blink_R         0 open .. 1 closed (subject's left / right eye)
    brow_L, brow_R           0 .. 1 brow raise
    widen, squint            0 .. 1 extra lid opening / lower-lid tension
    pupil                    offset to add to the rig's resting GNM pupil coefficient (about +-0.4)
"""

from dataclasses import dataclass, field
import math

import numpy as np

CHANNELS = (
    "gaze_yaw", "gaze_pitch", "gaze_dist",
    "head_yaw", "head_pitch", "head_roll",
    "eye_yaw", "eye_pitch",
    "blink_L", "blink_R", "brow_L", "brow_R",
    "widen", "squint", "pupil",
)


@dataclass(frozen=True)
class GazeParams:
    dt: float = 0.001                      # internal clock, s
    # Saccade main sequence: peak velocity saturates with amplitude.
    sacc_vmax: float = 550.0               # deg/s
    sacc_c: float = 6.0                    # deg
    sacc_min_dur: float = 0.018            # s
    min_isi: float = 0.15                  # s between saccades
    undershoot_from: float = 12.0          # deg; larger shifts land short
    undershoot: tuple = (0.06, 0.12)       # fraction of amplitude
    corrective_delay: tuple = (0.15, 0.22) # s after the primary saccade lands
    glissade_frac: float = 0.02            # post-saccadic overshoot, fraction of amplitude
    glissade_tau: float = 0.035            # s
    # Fixational movement
    drift_deg: float = 0.10
    micro_rate: float = 1.1                # per second
    micro_deg: tuple = (0.12, 0.35)
    # Oculomotor range, eye-in-head
    eye_yaw_max: float = 38.0
    eye_pitch_up: float = 27.0
    eye_pitch_down: float = 32.0
    # Head
    head_delay: float = 0.04               # s after the eyes start
    head_freq: float = 1.2                 # Hz, critically damped follow
    head_gain_small: float = 0.10          # share of gaze eccentricity taken by the head
    head_gain_large: float = 0.40
    head_gain_from: float = 10.0           # deg
    head_gain_to: float = 30.0             # deg
    head_roll_coupling: float = -0.20      # roll per degree of head yaw
    # The head dips as it turns: pitch drops with the head's yaw speed (low-passed), about
    # 0.15 deg per deg of yaw travelled at the peak, mid-move, and is back to zero once it stops.
    head_dip_gain: float = 0.064           # s; deg of dip per deg/s of yaw speed
    head_dip_tau: float = 0.06             # s
    head_min_shift: float = 9.0            # deg; a smaller refixation leaves the head where it is
    # Idle sway, rms deg in yaw, pitch, roll; band-limited noise. The eyes counter-rotate (eye =
    # gaze - head), so the gaze holds its target through it.
    head_sway_deg: tuple = (0.55, 0.45, 0.30)
    head_sway_band: tuple = (0.08, 0.35)   # Hz
    # Blinks
    blink_close: float = 0.075             # s
    blink_hold: float = 0.030
    blink_open: float = 0.165              # about twice the closing time
    blink_mean_gap: float = 3.2            # s, spontaneous
    blink_min_gap: float = 1.6             # s from any other blink to a spontaneous one
    blink_forced_gap: float = 1.3          # s between scripted or gaze-evoked blinks; the later one goes
    blink_guard: float = 0.35              # s kept blink-free at each end of the clip
    blink_evoked_from: float = 10.0        # deg; chance rises with gaze shift size
    blink_eye_dip: float = 1.5             # deg the eye rolls down under a closed lid
    blink_eye_nasal: float = 1.0           # deg each eye turns toward the nose under a closed lid
    eye_half_ipd: float = 0.0309           # m, GNM eye centre to midline; turns that into vergence
    blink_partial_rate: float = 0.22       # share of blinks after the first that stop short ...
    blink_partial_amp: tuple = (0.65, 0.75)  # ... at this closure (about one blink in six overall)
    # Vergence, brows, pupil
    verg_latency: float = 0.16
    verg_tau: float = 0.20
    brow_from_pitch: tuple = (6.0, 24.0, 0.45)   # start deg, full deg, amount
    brow_tau: float = 0.09
    brow_side_amp: float = 0.15            # per brow event one side is up to this much weaker ...
    brow_side_lag: tuple = (0.020, 0.040)  # ... and one side starts this much later (s)
    # Effort of a large gaze shift: the brows lift and the lower lids tense as the eyes go, then
    # both relax while the eyes hold on the new target
    shift_from: float = 10.0               # deg; smaller shifts carry no effort
    shift_full: float = 24.0               # deg; full effort from here on
    shift_brow: float = 0.31               # peaks near 0.25 after the brow low-pass and lean
    shift_squint: float = 0.12             # peaks near 0.10 after the lid low-pass
    shift_rise: float = 0.20               # s from the saccade onset to the peak
    shift_relax: float = 0.55              # s, time constant of the relaxation during the hold
    pupil_tau: float = 0.40
    pupil_range: float = 0.80              # the pupil channel spans about -0.4 .. +0.4
    hippus: float = 0.024                  # rms of the slow wander, 3 % of pupil_range ...
    hippus_band: tuple = (0.30, 1.00)      # ... in this band, Hz
    near_gain: float = 0.065               # per dioptre (near triad); 1.6 m -> 0.4 m is 15 % of range


# ---- script elements -------------------------------------------------------------------------

@dataclass
class Look:
    """Shift gaze to (yaw, pitch) with a saccade starting at t."""
    t: float
    yaw: float
    pitch: float
    dist: float = None        # new fixation distance in metres, None keeps the current one
    blink: bool = None        # True forces a blink with the shift, False forbids, None rolls
    head: float = None        # override the head's share of this shift


@dataclass
class Sweep:
    """Move gaze smoothly through waypoints [(yaw, pitch), ...] over dur seconds (eye roll)."""
    t: float
    dur: float
    points: list
    dist: float = None
    head: float = None


@dataclass
class Blink:
    t: float
    amp: float = 1.0
    slow: float = 1.0         # multiplies close, hold and open; 2.0 is a blink twice as long


@dataclass
class Brow:
    t: float
    dur: float
    amp: float
    side: str = "both"        # "L", "R" or "both"


@dataclass
class Lids:
    t: float
    dur: float
    widen: float = 0.0
    squint: float = 0.0


@dataclass
class Script:
    duration: float
    events: list = field(default_factory=list)
    start: tuple = (0.0, 0.0)
    start_dist: float = 0.40


# ---- small helpers ---------------------------------------------------------------------------

def minjerk(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * u * (10.0 - 15.0 * u + 6.0 * u * u)


def saccade_peak_velocity(amp, p=GazeParams()):
    return p.sacc_vmax * (1.0 - math.exp(-amp / p.sacc_c))


def _skew(amp):
    """Time-warp exponent: large saccades peak earlier and decelerate longer."""
    return 1.0 - 0.22 * min(amp / 30.0, 1.0)


def _profile(u, k):
    return minjerk(np.power(np.clip(u, 0.0, 1.0), k))


def _peak_factor(k, n=2000):
    u = np.linspace(0.0, 1.0, n)
    return float(np.max(np.gradient(_profile(u, k), u)))


def saccade_duration(amp, p=GazeParams()):
    """Duration that makes the profile's peak velocity sit on the main sequence."""
    if amp <= 1e-6:
        return p.sacc_min_dur
    k = _skew(amp)
    return max(p.sacc_min_dur, _peak_factor(k) * amp / saccade_peak_velocity(amp, p))


def _smooth_noise(rng, t, f_lo, f_hi, n=5):
    """Band-limited noise with unit RMS: a few sines with random frequency and phase."""
    out = np.zeros_like(t)
    for _ in range(n):
        f = rng.uniform(f_lo, f_hi)
        out += np.sin(2.0 * math.pi * (f * t + rng.uniform()))
    return out * math.sqrt(2.0 / n)


def _lowpass(x, tau, dt):
    if tau <= 0:
        return x.copy()
    a = dt / (tau + dt)
    y = np.empty_like(x)
    acc = x[0]
    for i, v in enumerate(x):
        acc += a * (v - acc)
        y[i] = acc
    return y


def _follow(cmd, freq, dt):
    """Critically damped second-order follower (smooth start and stop, no overshoot)."""
    w = 2.0 * math.pi * freq
    y = np.empty_like(cmd)
    pos, vel = cmd[0], 0.0
    for i, c in enumerate(cmd):
        acc = w * w * (c - pos) - 2.0 * w * vel
        vel += acc * dt
        pos += vel * dt
        y[i] = pos
    return y


def _catmull(points, n):
    """Catmull-Rom curve through points, n samples, parameterised by arc length."""
    pts = np.asarray(points, dtype=float)
    if len(pts) == 2:
        dense = np.linspace(pts[0], pts[1], 200)
    else:
        ext = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
        chunks = []
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
            s = np.linspace(0.0, 1.0, 60, endpoint=False)[:, None]
            chunks.append(0.5 * ((2 * p1) + (-p0 + p2) * s
                                 + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                                 + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3))
        dense = np.vstack(chunks + [pts[-1][None]])
    seg = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    length = arc[-1]
    u = np.linspace(0.0, 1.0, n)
    target = minjerk(u) * length
    return np.stack([np.interp(target, arc, dense[:, 0]),
                     np.interp(target, arc, dense[:, 1])], axis=1), length


def _envelope(t, t0, dur, attack=0.18, release=0.35):
    """Raised-cosine in, hold, raised-cosine out."""
    up = np.clip((t - t0) / attack, 0.0, 1.0)
    down = np.clip((t - (t0 + dur)) / release, 0.0, 1.0)
    return 0.5 * (1 - np.cos(math.pi * up)) * 0.5 * (1 + np.cos(math.pi * down))


# ---- track -----------------------------------------------------------------------------------

class Track:
    def __init__(self, t, channels, meta):
        self.t = t
        self.channels = channels
        self.meta = meta

    @property
    def duration(self):
        return float(self.meta["duration"])

    def sample(self, time):
        return {k: float(np.interp(time, self.t, v)) for k, v in self.channels.items()}

    def frames(self, fps=30):
        """One dict per frame, frame numbers starting at 1, sampled at the frame time."""
        n = int(round(self.duration * fps))
        out = []
        for f in range(n):
            row = self.sample(f / fps)
            row["frame"] = f + 1
            row["time"] = f / fps
            out.append(row)
        return out

    def to_dict(self, fps=30):
        return {"meta": dict(self.meta, fps=fps), "channels": list(CHANNELS),
                "frames": self.frames(fps)}


# ---- simulation ------------------------------------------------------------------------------

def simulate(script, seed=0, params=GazeParams()):
    p = params
    rng = np.random.default_rng(seed)
    dt = p.dt
    n = int(round(script.duration / dt)) + 1
    t = np.arange(n) * dt
    T = script.duration

    looks = sorted([e for e in script.events if isinstance(e, (Look, Sweep))], key=lambda e: e.t)

    # -- 1. gaze in the world frame: saccades, sweeps, glissades ------------------------------
    gaze = np.tile(np.asarray(script.start, dtype=float), (n, 1))
    head_cmd = np.zeros((n, 2))
    dist_cmd = np.full(n, 1.0 / script.start_dist)          # dioptres
    cur = np.asarray(script.start, dtype=float)
    free_at = 0.0                                            # earliest start of the next saccade
    saccades = []                                            # (t0, dur, amp) for tests and blinks
    blinks = []                                              # (t0, amp)
    busy = []                                                # intervals with no microsaccades
    quiet = []                                               # intervals with no spontaneous blink
    shifts = []                                              # (onset, amplitude) of every Look
    sweep_end = 0.0                                          # end of the last sweep

    def head_share(target, override):
        if override is not None:
            return override
        ecc = float(np.hypot(*target))
        f = np.clip((ecc - p.head_gain_from) / (p.head_gain_to - p.head_gain_from), 0.0, 1.0)
        return p.head_gain_small + (p.head_gain_large - p.head_gain_small) * f

    def add_saccade(t0, end):
        nonlocal cur, free_at
        t0 = max(t0, free_at)
        delta = end - cur
        amp = float(np.linalg.norm(delta))
        if amp < 1e-6:
            return t0, 0.0, 0.0
        dur = saccade_duration(amp, p)
        k = _skew(amp)
        gl = rng.normal(0.0, p.glissade_frac) * amp if amp >= 2.0 else 0.0
        unit = delta / amp
        land = end + gl * unit
        i0, i1 = int(round(t0 / dt)), min(n, int(round((t0 + dur) / dt)) + 1)
        if i0 >= n:
            return t0, dur, amp
        u = (t[i0:i1] - t0) / dur
        gaze[i0:i1] = cur + (land - cur) * _profile(u, k)[:, None]
        tail = t[i1:] - (t0 + dur)
        gaze[i1:] = end + (gl * unit) * np.exp(-tail / p.glissade_tau)[:, None]
        cur = end.copy()
        free_at = t0 + dur + p.min_isi
        saccades.append((t0, dur, amp))
        busy.append((t0 - 0.2, t0 + dur + 0.25))
        return t0, dur, amp

    for ev in looks:
        target = np.array(ev.points[-1] if isinstance(ev, Sweep) else (ev.yaw, ev.pitch), float)
        if isinstance(ev, Sweep):
            # A sweep is smooth, not a saccade: it may start as soon as the last saccade begun
            # before it has landed (no refractory gap), from where the gaze is at that moment.
            # A saccade scripted to start later (a pending correction) is overwritten by it.
            land = max([s0 + d for s0, d, _ in saccades if s0 < ev.t], default=0.0)
            t0 = max(ev.t, land, sweep_end)
            saccades[:] = [s for s in saccades if s[0] < t0]
            i0 = int(round(t0 / dt))
            m = min(n - i0, int(round(ev.dur / dt)) + 1)
            if m > 1:
                start = gaze[min(i0, n - 1)].copy()
                path, _ = _catmull([tuple(start)] + list(ev.points), int(round(ev.dur / dt)) + 1)
                gaze[i0:i0 + m] = path[:m]
                gaze[i0 + m:] = path[m - 1]
                cur = path[m - 1].copy()
            free_at = t0 + ev.dur + p.min_isi
            sweep_end = t0 + ev.dur
            busy.append((t0 - 0.2, t0 + ev.dur + 0.25))
            quiet.append((t0 - 0.4, t0 + ev.dur + 0.1))
            onset, amp = t0, 0.0
        else:
            delta = target - cur
            amp_total = float(np.linalg.norm(delta))
            if amp_total > p.undershoot_from:
                short = rng.uniform(*p.undershoot)
                onset, dur, amp = add_saccade(ev.t, cur + delta * (1.0 - short))
                add_saccade(onset + dur + rng.uniform(*p.corrective_delay), target)
            else:
                onset, dur, amp = add_saccade(ev.t, target)
            amp = amp_total
            shifts.append((onset, amp_total))
            want = ev.blink
            if want is None:
                chance = np.clip((amp - p.blink_evoked_from) / 22.0, 0.0, 0.85)
                want = bool(rng.uniform() < chance)
            if want:
                blinks.append((onset - 0.02, 1.0))
        # The head re-aims for a sweep or a real gaze shift. A small refixation on the same thing
        # is the eyes' alone: re-aiming for it walked the head back and forth during a hold.
        if isinstance(ev, Sweep) or amp >= p.head_min_shift:
            ih = min(n - 1, int(round((onset + p.head_delay) / dt)))
            head_cmd[ih:] = target * head_share(target, ev.head)
        if ev.dist is not None:
            iv = min(n - 1, int(round((onset + p.verg_latency) / dt)))
            dist_cmd[iv:] = 1.0 / ev.dist

    # -- 2. fixational drift and microsaccades ------------------------------------------------
    drift = np.stack([_smooth_noise(rng, t, 0.3, 1.6), _smooth_noise(rng, t, 0.3, 1.6)], axis=1)
    gaze += drift * p.drift_deg
    micro = np.zeros((n, 2))
    tm, off = 0.3, np.zeros(2)
    while True:
        tm += rng.exponential(1.0 / p.micro_rate) + 0.25
        if tm > T - 0.3:
            break
        if any(a <= tm <= b for a, b in busy):
            continue
        ang = rng.uniform(0, 2 * math.pi)
        new = rng.uniform(*p.micro_deg) * np.array([math.cos(ang), 0.6 * math.sin(ang)])
        i0, i1 = int(round(tm / dt)), min(n, int(round((tm + 0.02) / dt)) + 1)
        u = (t[i0:i1] - tm) / 0.02
        micro[i0:i1] = off + (new - off) * minjerk(u)[:, None]
        micro[i1:] = new
        off = new
    gaze += micro

    # -- 3. head: delayed smooth follow plus idle sway ----------------------------------------
    head_yaw = _follow(head_cmd[:, 0], p.head_freq, dt)
    head_pitch = _follow(head_cmd[:, 1], p.head_freq, dt)
    yaw_speed = np.abs(np.gradient(head_yaw, dt))
    head_pitch = head_pitch - p.head_dip_gain * _lowpass(yaw_speed, p.head_dip_tau, dt)
    sway = [_smooth_noise(rng, t, *p.head_sway_band) * a for a in p.head_sway_deg]
    ramp = np.clip(t / 0.5, 0.0, 1.0)                        # start the clip exactly at rest
    head_yaw = head_yaw + sway[0] * ramp
    head_pitch = head_pitch + sway[1] * ramp
    head_roll = p.head_roll_coupling * head_yaw + sway[2] * ramp

    # -- 4. blinks ----------------------------------------------------------------------------
    total = p.blink_close + p.blink_hold + p.blink_open
    quiet += [(e.t - 0.3, e.t + e.dur) for e in script.events
              if isinstance(e, Lids) and e.widen > 0]
    lo, hi = p.blink_guard, T - p.blink_guard - total * 1.15
    forced = [(min(max(a, lo), hi), b, 1.0) for a, b in blinks]
    forced += [(min(max(e.t, lo), hi - total * (e.slow - 1.0)), e.amp, e.slow)
               for e in script.events if isinstance(e, Blink)]
    kept = []
    for tb0, amp, slow in sorted(forced):                    # scripted and gaze-evoked first
        if all(abs(tb0 - k[0]) > p.blink_forced_gap for k in kept):
            kept.append((tb0, amp, slow))
    tb = lo
    while True:                                              # then spontaneous ones where there is room
        tb += p.blink_min_gap + rng.exponential(p.blink_mean_gap - p.blink_min_gap)
        if tb > hi:
            break
        if any(a <= tb <= b for a, b in quiet):
            continue
        if all(abs(tb - k[0]) > p.blink_min_gap for k in kept):
            kept.append((tb, float(rng.uniform(0.85, 1.0)), 1.0))
    kept.sort()
    # Partial blinks: some blinks after the first stop short. Own generator, so adding this
    # left every other draw of the track where it was.
    rng_part = np.random.default_rng([int(seed), 1])
    # A slow blink always closes: the draw is still made so the others stay where they were.
    for i, (tb0, amp, slow) in enumerate(kept):
        roll, a = rng_part.uniform(), rng_part.uniform(*p.blink_partial_amp)
        if i > 0 and roll < p.blink_partial_rate and slow == 1.0:
            kept[i] = (tb0, a, slow)
    blink_L, blink_R = np.zeros(n), np.zeros(n)
    for tb0, amp, slow in kept:
        j = rng.uniform(0.88, 1.12) * slow
        c, h, o = p.blink_close * j, p.blink_hold * j, p.blink_open * j
        lag = rng.uniform(-0.004, 0.004)
        for arr, shift, a in ((blink_L, 0.0, amp), (blink_R, lag, amp * rng.uniform(0.97, 1.0))):
            x = t - (tb0 + shift)
            shape = np.where(x < c, minjerk(x / c),
                             np.where(x < c + h, 1.0, 1.0 - minjerk((x - c - h) / o)))
            shape = np.where((x < 0) | (x > c + h + o), 0.0, shape)
            np.maximum(arr, a * shape, out=arr)
    # Under the closing lid the eyes roll down and in (toward the nose), back as it opens. Down
    # goes into gaze pitch here; in is a vergence change, so it goes into gaze_dist in step 6.
    lid = np.maximum(blink_L, blink_R)
    gaze[:, 1] -= p.blink_eye_dip * lid

    # -- 5. eye-in-head, clamped to the oculomotor range --------------------------------------
    eye_yaw = np.clip(gaze[:, 0] - head_yaw, -p.eye_yaw_max, p.eye_yaw_max)
    eye_pitch = np.clip(gaze[:, 1] - head_pitch, -p.eye_pitch_down, p.eye_pitch_up)
    gaze_yaw, gaze_pitch = head_yaw + eye_yaw, head_pitch + eye_pitch

    # -- 6. vergence distance -----------------------------------------------------------------
    fix_dist = 1.0 / _lowpass(dist_cmd, p.verg_tau, dt)     # what the eyes fixate (accommodation)
    half = np.arctan(p.eye_half_ipd / fix_dist) + math.radians(p.blink_eye_nasal) * lid
    gaze_dist = p.eye_half_ipd / np.tan(half)                # plus the nasal turn under a blink

    # -- 7. brows and lids --------------------------------------------------------------------
    b0, b1, bamt = p.brow_from_pitch
    brow_base = bamt * np.clip((eye_pitch - b0) / (b1 - b0), 0.0, 1.0)
    # The pitch-driven raise leans to one side for the whole clip; every brow event (a large
    # shift's effort, a scripted Brow) gets its own side difference in amplitude and timing.
    lean = rng.uniform(0.86, 0.96)
    if rng.uniform() < 0.5:
        brow_L, brow_R = brow_base * lean, brow_base.copy()
    else:
        brow_L, brow_R = brow_base.copy(), brow_base * lean
    rng_brow = np.random.default_rng([int(seed), 2])

    def sides():
        """(gain, delay) for L and R: one side weaker, one side later, drawn per event."""
        weak = 1.0 - rng_brow.uniform(0.0, p.brow_side_amp)
        lag = rng_brow.uniform(*p.brow_side_lag)
        gain = (weak, 1.0) if rng_brow.uniform() < 0.5 else (1.0, weak)
        delay = (lag, 0.0) if rng_brow.uniform() < 0.5 else (0.0, lag)
        return tuple(zip(gain, delay))

    def effort_curve(x, a):
        rise = 0.5 * (1 - np.cos(math.pi * np.clip(x / p.shift_rise, 0.0, 1.0)))
        relax = np.exp(-np.maximum(x - p.shift_rise, 0.0) / p.shift_relax)
        return np.where(x < 0, 0.0, a * rise * relax)

    widen, squint = np.zeros(n), np.zeros(n)
    effort = np.zeros(n)
    for onset, amp in shifts:
        a = np.clip((amp - p.shift_from) / (p.shift_full - p.shift_from), 0.0, 1.0)
        if a <= 0.0:
            continue
        effort = np.maximum(effort, effort_curve(t - onset, a))
        (gl, dl), (gr, dr) = sides()
        brow_L = np.maximum(brow_L, p.shift_brow * gl * effort_curve(t - onset - dl, a))
        brow_R = np.maximum(brow_R, p.shift_brow * gr * effort_curve(t - onset - dr, a))
    squint = np.maximum(squint, p.shift_squint * effort)
    for e in script.events:
        if isinstance(e, Brow):
            (gl, dl), (gr, dr) = sides()
            if e.side == "both":
                brow_L = np.maximum(brow_L, e.amp * gl * _envelope(t, e.t + dl, e.dur))
                brow_R = np.maximum(brow_R, e.amp * gr * _envelope(t, e.t + dr, e.dur))
            elif e.side == "L":
                brow_L = np.maximum(brow_L, e.amp * _envelope(t, e.t, e.dur))
            else:
                brow_R = np.maximum(brow_R, e.amp * _envelope(t, e.t, e.dur))
        elif isinstance(e, Lids):
            env = _envelope(t, e.t, e.dur, attack=0.14, release=0.3)
            widen = np.maximum(widen, e.widen * env)
            squint = np.maximum(squint, e.squint * env)
    brow_L = np.clip(_lowpass(brow_L, p.brow_tau, dt), 0.0, 1.0)
    brow_R = np.clip(_lowpass(brow_R, p.brow_tau, dt), 0.0, 1.0)
    widen = np.clip(_lowpass(np.maximum(widen, 0.3 * np.maximum(brow_L, brow_R)), 0.06, dt), 0, 1)
    squint = np.clip(_lowpass(squint, 0.08, dt), 0.0, 1.0)

    # -- 8. pupil: near response (constricts as the eyes converge) plus a slow wander ----------
    # Reads fix_dist, not gaze_dist: the nasal turn under a blink must leave the pupil alone.
    near = -p.near_gain * np.clip(1.0 / fix_dist - 1.0 / 0.6, -1.0, 2.0)
    pupil = _lowpass(near, p.pupil_tau, dt) + p.hippus * _smooth_noise(rng, t, *p.hippus_band)

    channels = dict(
        gaze_yaw=gaze_yaw, gaze_pitch=gaze_pitch, gaze_dist=gaze_dist,
        head_yaw=head_yaw, head_pitch=head_pitch, head_roll=head_roll,
        eye_yaw=eye_yaw, eye_pitch=eye_pitch,
        blink_L=blink_L, blink_R=blink_R, brow_L=brow_L, brow_R=brow_R,
        widen=widen, squint=squint, pupil=pupil,
    )
    meta = dict(duration=T, seed=int(seed), dt=dt,
                saccades=[(round(a, 4), round(b, 4), round(c, 3)) for a, b, c in saccades],
                blinks=[(round(a, 4), round(b, 3)) for a, b, _ in kept],
                blink_slow=[round(c, 3) for _, _, c in kept])
    return Track(t, channels, meta)
