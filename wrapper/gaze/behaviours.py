"""The three inputs the rubric asks for, written as short scripts of intentions.

The engine turns each script into motion; the seed only changes the performance
(timing, amplitudes, which side goes first), never the meaning of the input.
"""

import numpy as np

from .engine import Blink, Brow, GazeParams, Look, Script, Sweep

CAMERA = 0.40      # metres, where the render camera sits
FAR = 1.60         # metres, something across the room


GLANCE_HEAD = 0.22  # the eyes carry a held side glance; the head follows with about a fifth


def _glance(rng, side, duration=9.0):
    """Look to one side (side = -1 image-left, +1 image-right), study it, come back.

    The eyes go first and are seen going: no blink on the way out. Blinks are spread over the
    clip (in the hold, on the way back, at the viewer), about 2.5 s apart."""
    u = rng.uniform
    ev = []
    t = u(0.9, 1.2)
    yaw = side * u(22.0, 26.0)
    pitch = u(-3.0, 2.0)
    ev.append(Look(t, yaw, pitch, dist=FAR, blink=False, head=GLANCE_HEAD))
    t += u(1.3, 1.6)                                    # a second fixation on the same thing
    yaw2, pitch2 = yaw - side * u(4.0, 7.0), pitch + u(2.5, 5.0)
    ev.append(Look(t, yaw2, pitch2, blink=False, head=GLANCE_HEAD))
    ev.append(Blink(t + u(0.25, 0.45)))
    t += u(0.9, 1.2)
    ev.append(Look(t, yaw + side * u(1.5, 3.5), pitch - u(1.0, 3.0), blink=False, head=GLANCE_HEAD))
    t += u(1.5, 1.8)
    ev.append(Look(t, 0.0, 0.0, dist=CAMERA, blink=True))   # back to the viewer
    ev.append(Brow(t + 0.05, 0.35, u(0.12, 0.22)))
    ev.append(Blink(t + u(2.1, 2.5)))
    t += u(1.1, 1.4)                                    # settle: flick between the viewer's eyes
    ev.append(Look(t, -side * u(1.4, 2.4), u(-0.6, 0.8), blink=False))
    t += u(0.7, 1.0)
    ev.append(Look(t, 0.0, 0.0, blink=False))
    return Script(duration=duration, events=ev)


def left(seed=0):
    return _glance(np.random.default_rng(seed), -1)


def right(seed=0):
    return _glance(np.random.default_rng(seed + 1000), +1)


def generate(seed=0):
    """One beat: a look to one side, across to the other, back to the viewer, an eye roll up and
    over that drops under a slow blink, and a settle on the viewer. Left, right, up and down in
    one clip. The seed picks the first side and jitters every time and angle by about 10 %."""
    rng = np.random.default_rng(seed + 2000)
    u = rng.uniform

    def j(x):
        return x * u(0.9, 1.1)

    A = -1 if rng.uniform() < 0.5 else 1
    ev = []

    # 1. a look to side A, held, with one small refixation inside the hold
    t = j(0.9)
    yaw_a, pitch_a = A * u(18.0, 22.0), u(-2.0, 2.0)
    ev.append(Look(t, yaw_a, pitch_a, dist=FAR, blink=False, head=0.2))
    hold = u(1.0, 1.2)
    r, ang = u(3.0, 5.0), u(0.35, 1.2) * (1 if rng.uniform() < 0.5 else -1)
    ev.append(Look(t + hold * u(0.45, 0.6), yaw_a - A * r * np.cos(ang), pitch_a + r * np.sin(ang),
                   blink=False))
    t += hold

    # 2. across to side B: a 40 deg shift blinks
    ev.append(Look(t, -A * u(18.0, 22.0), u(-2.0, 2.0), dist=FAR, blink=True, head=0.2))
    t += u(0.9, 1.1)

    # 3. back to the viewer
    ev.append(Look(t, 0.0, 0.0, dist=CAMERA, blink=None))
    t += u(0.8, 1.0)

    # 4. the eye roll. Brows first; no widening (the lid follows pitch on its own).
    ev.append(Brow(t - j(0.12), j(0.75), u(0.35, 0.45)))
    ev.append(Look(t, A * u(10.0, 13.0), u(20.0, 23.0), blink=False, head=0.22))   # launch, fast
    t_sweep, d_sweep = t + j(0.16), u(0.45, 0.60)                                   # over, slow
    ev.append(Sweep(t_sweep, d_sweep, [(A * u(-2.0, 2.0), u(25.0, 27.0)),
                                       (-A * u(12.0, 15.0), u(17.0, 20.0))], head=0.22))
    # down and out under a slow blink: the lids close on the way down and open on the low gaze.
    # The engine holds a saccade min_isi after a sweep, so the drop starts there.
    t_down = t_sweep + d_sweep + GazeParams().min_isi
    ev.append(Look(t_down, -A * u(4.0, 8.0), -u(12.0, 15.0), dist=0.40, blink=False, head=0.15))
    t_slow, slow = t_down - 0.03, u(1.8, 2.2)
    ev.append(Blink(t_slow, slow=slow))

    # 5. hold low with the lids open (counted from when the slow blink is 85 % open again, so
    # the lowered gaze is seen), then back to the viewer; a flick between the viewer's eyes and
    # back; a soft closing blink at least 1.3 s after the slow one
    p = GazeParams()
    opened = t_slow + 0.85 * slow * (p.blink_close + p.blink_hold + p.blink_open)
    duration = round(u(10.0, 11.5), 1)
    t_view = opened + u(0.35, 0.5)
    ev.append(Look(t_view, 0.0, 0.0, dist=CAMERA, blink=False))
    t_close = max(duration - u(1.2, 1.5), t_slow + 1.4)
    t_flick = t_view + (t_close - t_view) * u(0.30, 0.45)
    side = 1 if rng.uniform() < 0.5 else -1
    ev.append(Look(t_flick, side * u(1.5, 2.5), u(-0.6, 0.6), blink=False))
    ev.append(Look(t_flick + u(0.6, 0.9), 0.0, 0.0, blink=False))
    ev.append(Blink(t_close, amp=u(0.9, 1.0)))
    return Script(duration=duration, events=ev)


MODES = {"left": left, "right": right, "generate": generate}
