"""When the video camera glides between its framings, from a gaze track. Pure numpy, no bpy.

The videos are shot by one moving camera (cam_move in scene.blend) with three framings:
`eye` (the subject's left eye, close, three-quarter from the nose side), `eyes` (both eyes,
straight on) and `face` (the whole head). Each video holds one framing, glides to the next,
holds, glides to the last and holds to the end:

    left, right   eyes ~3 s  ->  face ~3 s  ->  eye to the end   (the first gaze shift is seen
                                                                  with both eyes in frame)
    generate      eye ~2 s   ->  eyes ~2 s  ->  face to the end

The camera never moves while the eyes do: it moves only inside fixations (no saccade, no blink,
no sweep). A glide takes GLIDE seconds of motion, 1.5 s when it goes to or from the eye framing
(the longest way), 1 s otherwise. Fixations in these tracks last 0.5 to 1 s, so a glide that
does not fit one fixation is split over the next ones: each piece is eased to a stop and the
camera stands still through the saccade or blink between pieces. In the eye framing the camera
rides on the head bone; that follow is blended in or out over the glide next to it
(wrapper/eyes.py does the geometry).
"""

import math

import numpy as np

ORDER = {"left": ("eyes", "face", "eye"), "right": ("eyes", "face", "eye"),
         "generate": ("eye", "eyes", "face")}
HOLD = {"left": (3.0, 3.0), "right": (3.0, 3.0), "generate": (2.0, 2.0)}   # s, first two holds
GLIDE = {"eye": 1.5, "other": 1.0}   # s of camera motion in a glide (to or from `eye`, other)
MIN_PIECE = 0.3         # s; a fixation shorter than this is sat out, and no piece is shorter
MAX_PIECES = 3          # a glide moves in at most this many fixations
SPAN = 2.0              # a glide, pauses included, lasts at most this many times its motion
MIN_HOLD = 1.0          # s, the shortest hold, the last one included
LAST_HOLD = 1.5         # s; a shorter last hold costs extra
# The nominal holds and glides add up to more than a 9 s clip, so something gives. The first hold
# counts double: in left and right it is the both-eyes shot the rubric's "both eyes move left"
# is judged on, so the face hold gives way first.
FIRST_HOLD_WEIGHT = 2.0
SHIFT_DEG = 5.0         # deg; left and right: the first gaze shift at least this large ...
SHIFT_SEEN = 0.5        # s ... has landed this long before the first glide starts
SACCADE_PAD = (0.03, 0.06)    # s kept still before a saccade onset and after its end (glissade)
BLINK_FROM = 0.01       # lid closure above which a blink is under way
BLINK_PAD = 0.03        # s around it
GAZE_STILL = 12.0       # deg/s; gaze faster than this for MICRO_MAX or longer is a sweep
MICRO_MAX = 0.04        # s; shorter bursts are microsaccades, part of a fixation


def busy_mask(track):
    """True at every track sample where the eyes move: saccades (with their glissades), sweeps
    and blinks. Microsaccades and drift are part of a fixation and do not count."""
    t, c = track.t, track.channels
    dt = float(t[1] - t[0])
    speed = np.hypot(np.gradient(c["gaze_yaw"], dt), np.gradient(c["gaze_pitch"], dt))
    fast = speed > GAZE_STILL
    busy = np.zeros_like(fast)
    i = 0
    while i < len(fast):                 # fast gaze that lasts (a sweep), not a microsaccade
        if fast[i]:
            j = i
            while j < len(fast) and fast[j]:
                j += 1
            if (j - i) * dt >= MICRO_MAX:
                busy[i:j] = True
            i = j
        else:
            i += 1
    for t0, dur, _ in track.meta["saccades"]:
        busy |= (t >= t0 - SACCADE_PAD[0]) & (t <= t0 + dur + SACCADE_PAD[1])
    blink = np.maximum(c["blink_L"], c["blink_R"]) > BLINK_FROM
    pad = int(math.ceil(BLINK_PAD / dt))
    if pad and blink.any():
        blink = np.convolve(blink.astype(float), np.ones(2 * pad + 1), "same") > 0
    return busy | blink


def fixations(track):
    """[(t0, t1)] of every interval in which the eyes hold still (complement of busy_mask)."""
    t, busy = track.t, busy_mask(track)
    out, start = [], None
    for i, b in enumerate(busy):
        if not b and start is None:
            start = t[i]
        elif b and start is not None:
            out.append((float(start), float(t[i - 1])))
            start = None
    if start is not None:
        out.append((float(start), float(t[-1])))
    return out


def glide_time(a, b):
    return GLIDE["eye"] if "eye" in (a, b) else GLIDE["other"]


def _candidates(windows, need, step):
    """Every way to fit `need` seconds of motion into fixations: (pieces, motion) per start on a
    `step` grid. From the start the camera moves to the end of that fixation, sits out the next
    saccade or blink, moves on in the next fixation long enough, and so on until it has moved
    `need` (or MAX_PIECES are used). Each piece is at least MIN_PIECE long."""
    usable = [(a, b) for a, b in windows if b - a >= MIN_PIECE - 1e-9]
    out = []
    for i, (w0, w1) in enumerate(usable):
        start = math.ceil(w0 / step) * step
        while w1 - start >= MIN_PIECE - 1e-9:
            pieces, left = [], need
            for a, b in [(start, w1)] + usable[i + 1:]:
                if len(pieces) == MAX_PIECES or left < MIN_PIECE / 2:
                    break
                length = min(b - a, max(left, MIN_PIECE))
                pieces.append((a, a + length))
                left -= length
                if pieces[-1][1] - pieces[0][0] > SPAN * need:
                    pieces.pop()
                    break
            if pieces:
                out.append((tuple(pieces), sum(b - a for a, b in pieces)))
            start += step
    return out


def plan(track, mode, step=1.0 / 30.0):
    """The two glides: [(t0, t1, from_framing, to_framing, pieces)], pieces [(t0, t1)] each
    inside a fixation, t0 / t1 the start of the first and the end of the last.

    Searched jointly over every pair of glides. Cost: how far each of the first two holds is
    from its nominal length (the first counts FIRST_HOLD_WEIGHT times), plus two for every
    second of motion missing, a quarter for every
    pause, and a last hold shorter than LAST_HOLD. In left and right the first glide waits until
    the first gaze shift has landed (SHIFT_DEG or more) and SHIFT_SEEN has passed.
    """
    order, (h1, h2) = ORDER[mode], HOLD[mode]
    T = track.duration
    windows = fixations(track)
    earliest = MIN_HOLD
    if mode in ("left", "right"):
        big = [(t0, d) for t0, d, amp in track.meta["saccades"] if amp >= SHIFT_DEG]
        if big:
            earliest = max(earliest, big[0][0] + big[0][1] + SHIFT_SEEN)
    need1, need2 = glide_time(order[0], order[1]), glide_time(order[1], order[2])
    first = [c for c in _candidates(windows, need1, step) if c[0][0][0] >= earliest]
    second = _candidates(windows, need2, step)
    best = None
    for p1, m1 in first:
        s1, e1 = p1[0][0], p1[-1][1]
        c1 = FIRST_HOLD_WEIGHT * abs(s1 - h1) + 2.0 * (need1 - m1) + 0.25 * (len(p1) - 1)
        if best is not None and c1 >= best[0]:
            continue
        for p2, m2 in second:
            s2, e2 = p2[0][0], p2[-1][1]
            hold2, last = s2 - e1, T - e2
            if hold2 < MIN_HOLD or last < MIN_HOLD:
                continue
            cost = (c1 + abs(hold2 - h2) + 2.0 * (need2 - m2) + 0.25 * (len(p2) - 1)
                    + 2.0 * max(0.0, LAST_HOLD - last))
            if best is None or cost < best[0] - 1e-9:
                best = (cost, p1, p2)
    if best is None:
        raise RuntimeError(f"no fixations in `{mode}` hold the camera glides")
    _, p1, p2 = best
    return [(p1[0][0], p1[-1][1], order[0], order[1], list(p1)),
            (p2[0][0], p2[-1][1], order[1], order[2], list(p2))]


def ease(u):
    """Smootherstep: zero speed and acceleration at both ends."""
    u = np.clip(u, 0.0, 1.0)
    return u * u * u * (u * (6.0 * u - 15.0) + 10.0)


def gentle(u):
    """Smoothstep: zero speed at both ends, a lower peak speed than smootherstep (1.5 x the
    mean against 1.875 x). Each piece of a glide runs on it."""
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def frames(track, mode, fps=30):
    """Per video frame (frame numbers from 1, sampled like Track.frames): which two framings
    are blended, how far (s, 0 = the first), and how much of the head follow is on.

    Each piece is snapped inward to whole frames, so every pair of camera keys that differ (and
    the linear in-betweens motion blur samples) lies inside a fixation. A piece carries its share
    of the glide in proportion to its length; between pieces the camera holds."""
    glides = plan(track, mode)
    n = int(round(track.duration * fps))
    snapped = []
    for _, _, a, b, pieces in glides:
        fr = [(math.ceil(p0 * fps - 1e-9), math.floor(p1 * fps + 1e-9)) for p0, p1 in pieces]
        fr = [(f0, f1) for f0, f1 in fr if f1 > f0]
        total = sum(f1 - f0 for f0, f1 in fr)
        snapped.append((a, b, fr, total))
    out = []
    for f in range(n):
        row = dict(a=glides[-1][3], b=glides[-1][3], s=0.0)
        for a, b, fr, total in snapped:
            if f <= fr[0][0]:
                row = dict(a=a, b=a, s=0.0)
                break
            if f < fr[-1][1]:
                done = 0.0
                for f0, f1 in fr:
                    if f >= f1:
                        done += f1 - f0
                    elif f > f0:
                        done += (f1 - f0) * float(gentle((f - f0) / (f1 - f0)))
                row = dict(a=a, b=b, s=done / total)
                break
        w = 0.0
        if row["a"] == "eye":
            w = 1.0 - row["s"]
        elif row["b"] == "eye":
            w = row["s"]
        row.update(frame=f + 1, time=f / fps, follow=w)
        out.append(row)
    return out, glides
