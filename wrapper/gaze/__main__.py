import argparse
import json

from . import MODES, generate


def plot(track, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t, c = track.t, track.channels
    fig, ax = plt.subplots(5, 1, figsize=(12, 11), sharex=True)
    ax[0].plot(t, c["gaze_yaw"], label="gaze yaw")
    ax[0].plot(t, c["head_yaw"], label="head yaw")
    ax[0].plot(t, c["eye_yaw"], label="eye-in-head yaw", lw=0.8)
    ax[0].set_ylabel("deg (+ image-right)")
    ax[1].plot(t, c["gaze_pitch"], label="gaze pitch")
    ax[1].plot(t, c["head_pitch"], label="head pitch")
    ax[1].plot(t, c["eye_pitch"], label="eye-in-head pitch", lw=0.8)
    ax[1].plot(t, c["head_roll"], label="head roll", lw=0.8)
    ax[1].set_ylabel("deg (+ up)")
    ax[2].plot(t, c["blink_L"], label="blink L")
    ax[2].plot(t, c["blink_R"], label="blink R", lw=0.8)
    ax[2].plot(t, c["widen"], label="widen")
    ax[2].plot(t, c["squint"], label="squint")
    ax[2].set_ylabel("0..1")
    ax[3].plot(t, c["brow_L"], label="brow L")
    ax[3].plot(t, c["brow_R"], label="brow R")
    ax[3].plot(t, c["pupil"], label="pupil offset")
    ax[3].set_ylabel("0..1 / coeff")
    ax[4].plot(t, c["gaze_dist"], label="fixation distance")
    ax[4].set_ylabel("m")
    ax[4].set_xlabel("s")
    for a in ax:
        a.legend(loc="upper right", ncol=4, fontsize=8)
        a.grid(alpha=0.3)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def main():
    ap = argparse.ArgumentParser(prog="python -m wrapper.gaze")
    ap.add_argument("--mode", choices=sorted(MODES), default="generate")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--json")
    ap.add_argument("--plot")
    a = ap.parse_args()
    track = generate(a.mode, a.seed)
    print("%s seed %d: %.1f s, %d saccades, %d blinks" % (
        a.mode, a.seed, track.duration, len(track.meta["saccades"]), len(track.meta["blinks"])))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(track.to_dict(a.fps), f)
    if a.plot:
        plot(track, a.plot, "%s, seed %d" % (a.mode, a.seed))


if __name__ == "__main__":
    main()
