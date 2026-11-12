"""Human-like gaze, lid, brow and head motion for the three rubric inputs.

    from wrapper.gaze import generate
    track = generate("left", seed=0)
    for row in track.frames(fps=30):
        ...   # row["gaze_yaw"], row["blink_L"], ...

    python -m wrapper.gaze --mode generate --seed 7 --json out.json --plot out.png
"""

from .behaviours import MODES
from .engine import CHANNELS, GazeParams, Script, Track, simulate

__all__ = ["CHANNELS", "GazeParams", "MODES", "Script", "Track", "generate", "simulate"]


def generate(mode, seed=0, params=GazeParams()):
    """Return a Track for mode in {"left", "right", "generate"}. Same seed, same motion."""
    if mode not in MODES:
        raise ValueError("mode must be one of %s" % ", ".join(MODES))
    return simulate(MODES[mode](seed), seed=seed, params=params)
