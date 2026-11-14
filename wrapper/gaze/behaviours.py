"""The three inputs the rubric asks for, written as short scripts of intentions.

The engine turns each script into motion; the seed only changes the performance
(timing, amplitudes, which side goes first), never the meaning of the input.
"""

import numpy as np

from .engine import Blink, Brow, Lids, Look, Script, Sweep

CAMERA = 0.40      # metres, where the render camera sits
FAR = 1.60         # metres, something across the room


GLANCE_HEAD = 0.5   # the head takes half of a held side glance; the eyes lead, then it catches up


def _glance(rng, side, duration=9.0):
    """Look to one side (side = -1 image-left, +1 image-right), study it, come back.

    The eyes go first and are seen going: no blink on the way out. Blinks are spread over the
    clip (in the hold, on the way back, at the viewer), about 2.5 s apart."""
    u = rng.uniform
    ev = []
    t = u(0.9, 1.2)
    yaw = side * u(25.0, 29.0)
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
    """A small performance: a glance, an eye roll, a look down, a thought, back to the viewer."""
    rng = np.random.default_rng(seed + 2000)
    u = rng.uniform
    side = -1 if rng.uniform() < 0.5 else 1
    ev = []
    t = u(0.8, 1.1)

    # glance to one side
    ev.append(Look(t, side * u(17.0, 22.0), u(2.0, 5.0), dist=FAR))
    t += u(1.0, 1.3)

    # eye roll: up and over to the other side, brows up, lids wide, blink on the way out
    roll = u(0.80, 0.95)
    arc = [(side * u(12.0, 15.0), u(19.0, 22.0)), (side * u(-2.0, 2.0), u(24.0, 26.0)),
           (-side * u(11.0, 14.0), u(18.0, 21.0)), (-side * u(16.0, 19.0), u(5.0, 8.0))]
    ev.append(Sweep(t, roll, arc, head=0.22))
    ev.append(Brow(t - 0.05, roll * 0.7, u(0.6, 0.8)))
    ev.append(Lids(t, roll * 0.6, widen=u(0.5, 0.7)))
    t += roll + u(0.25, 0.4)
    ev.append(Look(t, 0.0, 0.0, dist=CAMERA, blink=True))
    t += u(1.0, 1.3)

    blocks = ["down", "think"]
    if rng.uniform() < 0.5:
        blocks.reverse()
    for block in blocks:
        if block == "down":                              # look down at something close
            ev.append(Look(t, u(-4.0, 4.0), -u(19.0, 23.0), dist=0.30, blink=False))
            t += u(0.5, 0.7)
            ev.append(Look(t, u(-6.0, 6.0), -u(15.0, 18.0), blink=False))
            t += u(0.6, 0.8)
            ev.append(Look(t, 0.0, 0.0, dist=CAMERA, blink=True))
            t += u(0.9, 1.2)
        else:                                            # look up and aside, thinking
            ty, tp = -side * u(12.0, 16.0), u(13.0, 17.0)
            ev.append(Look(t, ty, tp, dist=FAR, blink=False))
            ev.append(Brow(t + 0.1, 0.9, u(0.25, 0.4), side="L" if side < 0 else "R"))
            ev.append(Lids(t + 0.2, 0.7, squint=u(0.15, 0.3)))
            t += u(1.1, 1.4)
            ev.append(Look(t, 0.0, 0.0, dist=CAMERA, blink=None))
            t += u(0.9, 1.2)

    ev.append(Blink(t))                                  # a soft closing blink at the viewer
    ev.append(Look(t + 0.5, u(-1.5, 1.5), u(-0.5, 0.5), blink=False))
    return Script(duration=round(min(t + 1.6, 14.5), 1), events=ev)


MODES = {"left": left, "right": right, "generate": generate}
