"""FlyLaya M4: batch driver — ablation configs x seeds -> trajectory jsonl -> stats.

Consumes the M3 ablation configs (m3/ablation/*.json) and drives the M2
simulation loop directly (world + brain + intent source, no websocket), logging
each run as an M3-contract trajectory jsonl, then computes metrics per run and
aggregated tables (per-config summary, pooled pairwise KS, literature-baseline
verdicts).

Loop order mirrors flylaya.server.Session.run (M2): poll intent -> modulation
-> modulated luminance -> brain step -> motor step with thrust gain, yaw noise.
Units: world is meters with z up; logs are converted to cm (x100) to match the
M3 contract and the literature numbers (20-60 cm/s flight).

Usage:
  /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python run_batch.py --configs A_full B_no_laya \
      C_no_connectome D_random_intent --seeds 11 --seconds 300 --out runs/
  /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python run_batch.py --aggregate-only --out runs/
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))            # repo root (flylaya pkg)
sys.path.insert(0, os.path.join(HERE, "..", "m3"))      # trajectory_stats

from flylaya.world import World                          # noqa: E402
from flylaya.brains import make_brain, FixedIntentSource  # noqa: E402
from flylaya.intent import INTENTS, LayaIntentSource, modulation_for  # noqa: E402
import trajectory_stats as ts                            # noqa: E402

DT = 0.1  # bio frame, s
class FixedRotationSource:
    """B ablation: rotate through the researcher 5-intent set every hold_n frames.

    Replaces the library FixedIntentSource (M1 stub) whose hardcoded vocabulary
    no longer matches intent.MODULATION — that stub silently fell back to
    explore-default modulation for all four of its labels.
    """

    def __init__(self, hold_frames=30, arousal=1.0):
        self.hold = hold_frames
        self.i = 0
        self.arousal = arousal

    def poll(self, frame, world, brain):
        if frame % self.hold == 0:
            self.i = (self.i + 1) % len(INTENTS)
        return INTENTS[self.i], 1.0

    def hud(self):
        return {"source": "fixed_rotation", "intent": INTENTS[self.i]}


class RandomIntentSource:
    """D ablation: uniform random intent each decision epoch (same cadence as Laya)."""

    def __init__(self, seed, every_frames=3, arousal=1.0):
        self.rng = np.random.default_rng((seed ^ 0xD) & 0xFFFFFFFF)
        self.every = every_frames
        self.arousal = arousal
        self._current = INTENTS[int(self.rng.integers(0, len(INTENTS)))]

    def poll(self, frame, world, brain):
        if frame % self.every == 0:
            self._current = INTENTS[int(self.rng.integers(0, len(INTENTS)))]
        return self._current, 0.2

    def hud(self):
        return {"source": "random"}


def make_intent(kind, seed, laya_url):
    if kind == "laya":
        return LayaIntentSource(url=laya_url, rng_seed=seed)
    if kind == "random":
        return RandomIntentSource(seed)
    return FixedRotationSource()  # "fixed"


def world_meta(world, cfg, seed):
    az = math.degrees(math.atan2(world.sun[1], world.sun[0]))
    el = math.degrees(math.asin(max(-1.0, min(1.0, world.sun[2]))))
    return {
        "type": "meta", "config": cfg["config_id"], "seed": seed,
        "brain": cfg["brain"], "intent_source": cfg["intent_source"],
        "arena": {"size_cm": 100},
        "obstacles": [{"x": float(x) * 100, "y": float(y) * 100,
                       "r": float(r) * 100, "h": float(h) * 100}
                      for x, y, r, h in world.obstacles],
        "sun": {"azimuth_deg": round(az, 2), "elevation_deg": round(el, 2)},
        "dt": DT,
    }


def run_one(cfg_path, seed, seconds, out_path, laya_url):
    cfg = json.load(open(cfg_path))
    world = World(seed=seed)
    brain = make_brain(cfg["brain"], seed=seed)
    src = make_intent(cfg["intent_source"], seed, laya_url)
    n = int(round(seconds / DT))
    rows = []
    prev = world.pos.copy()
    t0 = time.perf_counter()
    for frame in range(n):
        intent, conf = src.poll(frame, world, brain)
        mod = modulation_for(intent, getattr(src, "arousal", 1))
        lum = world.render_luminance(mod)
        rates = brain.step(lum, DT)
        bias = src.consume_yaw_bias() if hasattr(src, "consume_yaw_bias") else 0.0
        world.step_motor(rates, DT, gains={"thrust": mod["thrust"]},
                         yaw_noise=mod["yaw_noise"], rng=world.rng, yaw_bias=bias)
        pos = world.pos * 100.0
        speed = float(np.linalg.norm(world.pos - prev)) / DT * 100.0
        prev = world.pos.copy()
        rows.append({
            "t": round(frame * DT, 2),
            "pos": [round(float(v), 3) for v in pos],
            "yaw": round(float(math.degrees(world.yaw)), 3),
            "pitch": round(float(math.degrees(world.pitch)), 3),
            "speed": round(speed, 2),
            "intent": intent, "intent_conf": float(conf),
            "arousal": float(getattr(src, "arousal", 1)),
        })
    wall = time.perf_counter() - t0
    with open(out_path, "w") as f:
        f.write(json.dumps(world_meta(world, cfg, seed)) + "\n")
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return {"out": out_path, "frames": n, "wall_s": round(wall, 1),
            "rt_factor": round(seconds / wall, 2) if wall else None}


PICKS = [
    ("speed_p50", lambda r: r["kinematics"]["speed_cm_s"]["p50"]),
    ("sacc_rate", lambda r: r["saccades"]["rate_hz"]),
    ("sacc_amp_p50", lambda r: r["saccades"]["amplitude_deg"]["p50"]),
    ("rest_frac", lambda r: r["rest_bouts"]["frac_time"]),
    ("sun_R", lambda r: r["phototaxis"]["heading_sun_angle_deg"]["circular_R"]),
    ("margin_p05", lambda r: r["margins"]["min_any_margin_cm"]["p05"]),
    ("occ_util", lambda r: r["occupancy"]["xy_top"]["utilization_frac"]),
    ("switch_hz", lambda r: r["intent"]["switch_rate_hz"]),
    ("arou_r", lambda r: r["intent"]["arousal_speed_pearson"]),
]


def _med(vals):
    vals = [v for v in vals if v is not None]
    return float(np.median(vals)) if vals else None


def _fmt(v):
    return "-" if v is None else f"{v:.3g}"


def aggregate(run_dir, out_prefix):
    full = [ts.analyze(os.path.join(run_dir, fn)) for fn in sorted(os.listdir(run_dir))
            if fn.endswith(".jsonl")]
    with open(out_prefix + "_metrics.json", "w") as f:
        json.dump({rep["source"]: {k: v for k, v in rep.items() if k != "_dists"}
                   for rep in full}, f, indent=2)

    by_cfg = {}
    for rep in full:
        by_cfg.setdefault(rep["config"], []).append(rep)

    lines = ["| config | n | speed_p50 | sacc_rate | sacc_amp_p50 | rest_frac | sun_R | "
             "margin_p05 | occ_util | switch_hz | arou_r |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for cfg, reps in sorted(by_cfg.items()):
        cells = [cfg, str(len(reps))] + [_fmt(_med([p(r) for r in reps])) for _, p in PICKS]
        lines.append("| " + " | ".join(cells) + " |")

    ks_lines = []
    names = sorted(by_cfg)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for key in ("speed", "omega_dps", "saccade_amp", "heading_sun_deg"):
                da = [x for rep in by_cfg[a] for x in rep["_dists"][key]]
                db = [x for rep in by_cfg[b] for x in rep["_dists"][key]]
                if da and db:
                    d, p = ts.ks2samp(da, db)
                    ks_lines.append(f"- {a}|{b}|{key}: D={d:.3f} p={p:.1e}")

    base_lines = []
    baselines = json.load(open(os.path.join(HERE, "..", "m3", "literature_baselines.json")))
    for cfg, reps in sorted(by_cfg.items()):
        verdicts = ts.check_baselines(reps[0], baselines)
        ok = sum(1 for v in verdicts.values() if v["in_range"])
        base_lines.append(f"- {cfg}: {ok}/{len(verdicts)} baseline metrics in literature range")

    md = "\n".join(lines + ["", "## pooled KS (D, p)"] + ks_lines +
                   ["", "## literature baselines (first seed; per-seed in metrics json)"] + base_lines)
    with open(out_prefix + "_tables.md", "w") as f:
        f.write(md + "\n")
    print(md)
    return out_prefix + "_tables.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=["A_full", "B_no_laya",
                                                     "C_no_connectome", "D_random_intent"])
    ap.add_argument("--seeds", nargs="+", type=int,
                    default=[11, 22, 33, 44, 55, 66, 77, 88, 99, 111])
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--out", default=os.path.join(HERE, "runs"))
    ap.add_argument("--laya-url", default="http://127.0.0.1:8000/v1/systemone")
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    if not args.aggregate_only:
        for cid in args.configs:
            cfg_path = os.path.join(HERE, "..", "m3", "ablation", f"{cid}.json")
            for seed in args.seeds:
                out = os.path.join(args.out, f"{cid}_{seed}.jsonl")
                if os.path.exists(out):
                    print(f"skip existing {out}")
                    continue
                info = run_one(cfg_path, seed, args.seconds, out, args.laya_url)
                print(f"{cid} seed={seed}: {info['frames']} frames in {info['wall_s']}s "
                      f"(rt x{info['rt_factor']})", flush=True)
    aggregate(args.out, os.path.join(args.out, "stats"))


if __name__ == "__main__":
    main()
