"""Plot the gaze channels dumped by xr/tests/dump.mjs.  python3 xr/tests/plot_curves.py <dir>"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/tmp/m14/xr")
TITLES = {"still": "1. wearer still at 0.7 m", "step": "2. 0.5 m step to the side at 3 s, 1 s long",
          "walk": "3. walk round 0 -> 150 deg at 20 deg/s, wait, back to 30 deg at 40 deg/s"}
for f in sorted(out.glob("curves_*.json")):
    d = json.loads(f.read_text())
    c, log = d["channels"], d["log"]
    t = c["time"]
    fig, ax = plt.subplots(5, 1, figsize=(14, 13), sharex=True)
    def shade(a):
        for i in range(1, len(t)):
            m = c["mode"][i]
            col = {"glance": "#ffe9a8", "lostHold": "#f4c7c3", "search": "#d9d2e9"}.get(m)
            if col:
                a.axvspan(t[i - 1], t[i], color=col, lw=0)
    for a in ax:
        shade(a)
    ax[0].plot(t, c["desired_yaw"], color="#bbbbbb", lw=3, label="target (fixated point)")
    ax[0].plot(t, c["gaze_yaw"], color="#1f77b4", lw=1.2, label="gaze")
    ax[0].plot(t, c["head_yaw"], color="#d62728", lw=1.4, label="head")
    ax[0].plot(t, c["eye_yaw"], color="#2ca02c", lw=1.0, label="eye in head")
    ax[0].set_ylabel("yaw, deg")
    ax[1].plot(t, c["desired_pitch"], color="#bbbbbb", lw=3, label="target")
    ax[1].plot(t, c["gaze_pitch"], color="#1f77b4", lw=1.2, label="gaze")
    ax[1].plot(t, c["head_pitch"], color="#d62728", lw=1.4, label="head")
    ax[1].plot(t, c["head_roll"], color="#9467bd", lw=1.0, label="head roll")
    ax[1].plot(t, c["eye_pitch"], color="#2ca02c", lw=1.0, label="eye in head")
    ax[1].set_ylabel("pitch, deg")
    ax[2].plot(t, c["blink_L"], color="#333333", lw=1.2, label="blink L")
    ax[2].plot(t, c["blink_R"], color="#888888", lw=1.0, ls="--", label="blink R")
    ax[2].set_ylabel("lid")
    ax[3].plot(t, c["brow_L"], color="#8c564b", lw=1.2, label="brow L")
    ax[3].plot(t, c["brow_R"], color="#e377c2", lw=1.0, label="brow R")
    ax[3].plot(t, c["squint"], color="#17becf", lw=1.0, label="squint")
    ax[3].plot(t, c["widen"], color="#bcbd22", lw=1.0, label="widen")
    ax[3].set_ylabel("0..1")
    ax[4].plot(t, c["pupil"], color="#555555", lw=1.0, label="pupil offset")
    ax[4].plot(t, [x / 10 for x in c["gaze_dist"]], color="#ff7f0e", lw=1.0, label="gaze distance / 10, m")
    ax[4].set_ylabel("pupil")
    ax[4].set_xlabel("time, s")
    for s_ in log["saccades"]:
        ax[0].axvline(s_["t"], color="#1f77b4", alpha=0.18, lw=0.8)
    for g in log["greets"]:
        for a in ax:
            a.axvline(g["t"], color="#2ca02c", lw=1.5, ls=":")
    for a in ax:
        a.legend(loc="upper right", fontsize=8, ncol=5)
        a.grid(alpha=0.25)
    kinds = {}
    for s_ in log["saccades"]:
        kinds[s_["kind"]] = kinds.get(s_["kind"], 0) + 1
    ax[0].set_title(f"{TITLES.get(d['path'], d['path'])}, seed {d['seed']}, {d['hz']} Hz  |  saccades {kinds}  "
                    f"blinks {len(log['blinks'])}  glances {len(log['glances'])}  (yellow glance, red lost, violet search, "
                    f"green dotted greet)", fontsize=9)
    fig.tight_layout()
    png = out / f"curves_{d['path']}.png"
    fig.savefig(png, dpi=90)
    plt.close(fig)
    print("wrote", png)
