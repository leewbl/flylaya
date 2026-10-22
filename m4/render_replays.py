"""FlyLaya M4: offline replay renderer — trajectory jsonl -> mp4 (top + side view).

Replaces the browser MediaRecorder path (headless tab state proved unreliable).
Renders every STRIDE-th bio frame at FPS (default: every 2nd frame at 5 fps =
realtime playback). Output mp4 via imageio-ffmpeg's bundled static ffmpeg.

Usage:
  /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python render_replays.py runs/A_full_11.jsonl ... \
      --out replays/ [--fps 5 --stride 2]
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.animation import FuncAnimation, FFMpegWriter  # noqa: E402
import imageio_ffmpeg  # noqa: E402

plt.rcParams["figure.facecolor"] = "#0d0d10"
plt.rcParams["axes.facecolor"] = "#0d0d10"
plt.rcParams["text.color"] = "#dddddd"
plt.rcParams["xtick.color"] = "#888888"
plt.rcParams["ytick.color"] = "#888888"

INTENT_COLORS = {
    "phototaxis": "#ffd27f",
    "avoid_obstacle": "#ff6a4a",
    "explore": "#6adf8a",
    "center_in_arena": "#4a9fe4",
    "rest_hover": "#8a8adf",
    # M1-era fallback labels (fixed-rotation stub) -> gray
}


def render(path, out, fps, stride):
    lines = [json.loads(l) for l in open(path)]
    meta = next((d for d in lines if d.get("type") == "meta"), {})
    frames = [d for d in lines if d.get("type") != "meta"]
    pos = np.array([f["pos"] for f in frames])
    yaw = np.array([f["yaw"] for f in frames])
    speed = np.array([f["speed"] for f in frames])
    intents = [f.get("intent", "?") for f in frames]
    matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    obs = meta.get("obstacles", [])
    sun = meta.get("sun", {})

    fig, (ax_t, ax_s) = plt.subplots(1, 2, figsize=(11, 6.2), dpi=100)
    fig.suptitle(f"{os.path.basename(path)}  brain={meta.get('brain')} intent={meta.get('intent_source')} "
                 f"seed={meta.get('seed')}  sun az {sun.get('azimuth_deg')}° el {sun.get('elevation_deg')}°",
                 fontsize=10, color="#9cf")

    for ax, (xl, yl) in ((ax_t, ("x cm", "y cm")), (ax_s, ("x cm", "z cm"))):
        ax.set_xlim(0, 100); ax.set_ylim(0, 100)
        ax.set_xlabel(xl, fontsize=8); ax.set_ylabel(yl, fontsize=8)
        ax.set_aspect("equal")
        ax.grid(color="#22262c", lw=0.5)
        for sp in ax.spines.values():
            sp.set_color("#333")
    # obstacles: circles on top view, rectangles on side view
    from matplotlib.patches import Circle, Rectangle
    for o in obs:
        ax_t.add_patch(Circle((o["x"], o["y"]), o["r"], color="#3a4a55", alpha=0.8))
        ax_s.add_patch(Rectangle((o["x"] - o["r"], 0), 2 * o["r"], o["h"],
                                 color="#3a4a55", alpha=0.8))
    # sun marker on top view (edge, azimuth direction)
    az = np.deg2rad(sun.get("azimuth_deg", 0))
    ax_t.plot([50 + 46 * np.cos(az)], [50 + 46 * np.sin(az)], marker="*",
              ms=14, color="#ffd27f", mec="none")

    (tr_t,) = ax_t.plot([], [], "-", lw=1.2, color="#88aaff", alpha=0.8)
    (fl_t,) = ax_t.plot([], [], "o", ms=7, color="#ffffff", mec="#000")
    (tr_s,) = ax_s.plot([], [], "-", lw=1.2, color="#88aaff", alpha=0.8)
    (fl_s,) = ax_s.plot([], [], "o", ms=7, color="#ffffff", mec="#000")
    txt = ax_t.text(2, 96, "", fontsize=9, color="#dddddd", va="top")

    n = len(frames)
    idxs = list(range(0, n, stride))
    trail_len = 400 // stride

    def update(k):
        i = idxs[k]
        lo = max(0, i - trail_len)
        tr_t.set_data(pos[lo:i + 1, 0], pos[lo:i + 1, 1])
        fl_t.set_data([pos[i, 0]], [pos[i, 1]])
        tr_s.set_data(pos[lo:i + 1, 0], pos[lo:i + 1, 2])
        fl_s.set_data([pos[i, 0]], [pos[i, 2]])
        col = INTENT_COLORS.get(intents[i], "#cccccc")
        fl_t.set_color(col); fl_s.set_color(col)
        txt.set_text(f"t={frames[i]['t']:.0f}s  intent={intents[i]}  "
                     f"conf={frames[i].get('intent_conf', 0):.2f}\n"
                     f"speed={speed[i]:.1f}cm/s  yaw={yaw[i] % 360:.0f}°")
        return tr_t, fl_t, tr_s, fl_s, txt

    anim = FuncAnimation(fig, update, frames=len(idxs), blit=False, interval=1000 / fps)
    writer = FFMpegWriter(fps=fps, bitrate=2400,
                          extra_args=["-fflags", "+genpts"])
    anim.save(out, writer=writer)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", default="replays")
    ap.add_argument("--fps", type=int, default=5)
    ap.add_argument("--stride", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for p in args.inputs:
        base = os.path.splitext(os.path.basename(p))[0]
        out = os.path.join(args.out, f"{base}_replay.mp4")
        if os.path.exists(out):
            print("skip existing", out)
            continue
        render(p, out, args.fps, args.stride)
        print("rendered", out, flush=True)


if __name__ == "__main__":
    main()
