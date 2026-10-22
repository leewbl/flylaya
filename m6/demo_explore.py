"""m6/demo_explore.py — M6-W1 free-exploration demo (TASK-0027).

Runs the fixed natural-terrain map (mountains/trees/water/sun) with a
fly freely exploring, and writes an m5-contract trajectory.jsonl (plus a
terrain meta header) so the M5 bench (TASK-0024) can replay it. The
brain is skeleton by default; --brain connectome for the full circuit.

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python m6/demo_explore.py \
        [--seed 11] [--seconds 120] [--brain skeleton] [--out m6/runs_demo/explore_11]
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from flylaya.brains import make_brain          # noqa: E402
from flylaya.intent import FixedGoalSource, modulation_for  # noqa: E402
from flylaya.terrain import Terrain            # noqa: E402
from flylaya.world import World                # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--brain", default="skeleton", choices=("skeleton", "connectome"))
    ap.add_argument("--intent", default="explore",
                    help="fixed intent for the demo (default explore)")
    ap.add_argument("--terrain-seed", type=int, default=20260926)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = args.out or os.path.join(HERE, "runs_demo", f"explore_{args.seed}")
    os.makedirs(out, exist_ok=True)

    terrain = Terrain(args.terrain_seed)
    world = World.from_terrain(terrain_seed=args.terrain_seed, seed=args.seed)
    brain = make_brain(args.brain, seed=args.seed)
    pol = FixedGoalSource(args.intent)
    dt = 0.1
    n = int(args.seconds / dt)

    meta = {
        "type": "meta", "schema": "flylaya.m6.explore.v1",
        "scene_id": f"terrain_{args.terrain_seed}", "seed": args.seed,
        "brain": args.brain, "intent": args.intent,
        "dt_s": dt,
        "terrain": {"seed": args.terrain_seed, "half_m": terrain.half,
                    "max_h_m": 14.0, "water_level_m": terrain.water_level,
                    "n_trees": len(terrain.trees),
                    "sun_az_deg": 205.0, "sun_el_deg": 50.0},
        "trees": [{"x": round(x, 2), "z": round(z, 2),
                   "r": round(r, 2), "h": round(h, 2)}
                  for x, z, r, h in terrain.trees],
        "start_m": [round(float(v), 3) for v in world.pos],
    }
    with open(os.path.join(out, "trajectory.jsonl"), "w") as f:
        f.write(json.dumps(meta) + "\n")
        for fr in range(n):
            intent, _ = pol.poll(fr, world, brain)
            mod = modulation_for(intent, 1, "full")
            lum = world.render_luminance(mod)
            rates = brain.step(lum, dt)
            world.step_motor(rates, dt, gains={"thrust": mod["thrust"]},
                             yaw_noise=mod["yaw_noise"], rng=world.rng)
            h = terrain.height_at(world.pos[0], world.pos[1])
            f.write(json.dumps({
                "t_s": round(fr * dt, 2),
                "pos_m": [round(float(v), 3) for v in world.pos],
                "ground_h_m": round(float(h), 3),
                "over_water": bool(h < terrain.water_level),
                "yaw_deg": round(math.degrees(world.yaw), 2),
                "pitch_deg": round(math.degrees(world.pitch), 2),
                "speed_m_s": round(float(np.linalg.norm(world.vel)), 3),
                "intent_applied": intent,
                "arousal": 1.0,
            }) + "\n")
    print(json.dumps({"out": out, "frames": n,
                      "end_pos": [round(float(v), 2) for v in world.pos]}))


if __name__ == "__main__":
    main()
