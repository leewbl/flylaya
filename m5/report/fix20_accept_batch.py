"""TASK-0020 acceptance batch: S2 mirrors x {P_laya, P_yoked, P_rule} x
connectome x sensory_only x 30s x seeds 101-105, following the sem-phase2
protocol (observable state, tau=1.6/eps=0.06, yoked cycle_shift k=17 with
tolerance gate). Reports per-scene correct-turn-away and symmetry.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
PY = sys.executable
SCENES = ["S2_obstacle_left", "S2_obstacle_right"]
SEEDS = [101, 102, 103, 104, 105]
YOKED_K = 17


def run(scene, seed, policy, out, extra=()):
    cmd = [PY, os.path.join(HERE, "..", "runner.py"), "run",
           "--scene", os.path.join(ROOT, "m5", "scenes", f"{scene}.json"),
           "--seed", str(seed), "--policy", policy, "--coupling", "sensory_only",
           "--brain", "connectome", "--out", out,
           "--experiment-id", "m5-fix20-accept", "--seconds", "30", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(f"{scene}/{seed}/{policy}: {'OK' if r.returncode == 0 else 'FAIL ' + r.stderr[-160:]}", flush=True)
    return r.returncode == 0


def main():
    root = os.path.join(ROOT, "m5", "runs_fix20_accept")
    for scene in SCENES:
        for seed in SEEDS:
            laya = os.path.join(root, scene, "P_laya", str(seed))
            if not run(scene, seed, "P_laya", laya,
                       ["--state-source", "observable", "--tau", "1.6", "--eps", "0.06"]):
                raise SystemExit(1)
            yok_gen = os.path.join(root, scene, "yoked_src", str(seed))
            g = subprocess.run(
                [PY, os.path.join(HERE, "..", "runner.py"), "yoked", laya, yok_gen,
                 "--mode", "cycle_shift", "--k", str(YOKED_K)],
                capture_output=True, text=True)
            if g.returncode != 0:
                print("yoked gen FAIL:", g.stderr[-160:])
                raise SystemExit(1)
            v = json.load(open(os.path.join(yok_gen, "yoked_verdict.json")))
            if not v.get("ok"):
                print(f"YOKED MISMATCH {scene}/{seed}")
                raise SystemExit(1)
            run(scene, seed, "P_yoked",
                os.path.join(root, scene, "P_yoked", str(seed)),
                ["--yoked-sequence", os.path.join(yok_gen, "yoked_sequence.jsonl"),
                 "--yoked-mode", "identity"])
            run(scene, seed, "P_rule",
                os.path.join(root, scene, "P_rule", str(seed)))

    sys.path.insert(0, os.path.join(HERE, ".."))
    import numpy as np
    import metrics as M
    print()
    summary = {}
    for scene in SCENES:
        for pol in ("P_laya", "P_yoked", "P_rule"):
            tas, nappr, ncont = [], 0, 0
            for seed in SEEDS:
                a = M.avoidance_metrics(M.load_run(os.path.join(root, scene, pol, str(seed))))
                if a["correct_turn_away_rate"] is not None:
                    tas.append(a["correct_turn_away_rate"])
                nappr += a["n_valid_approaches"]
                ncont += a["n_contact"]
            pooled = (round(float(np.mean(tas)), 3) if tas else None)
            summary[(scene, pol)] = (pooled, nappr, ncont)
            print(f"{scene:20s} {pol:8s} turn_away_pooled={pooled} "
                  f"approaches={nappr} contacts={ncont}")
    for pol in ("P_laya", "P_yoked", "P_rule"):
        l, r = summary[("S2_obstacle_left", pol)], summary[("S2_obstacle_right", pol)]
        ok = l[0] is not None and r[0] is not None and l[0] > 0.5 and abs(l[0] - r[0]) < 0.2
        print(f"{pol}: left>0.5 & |diff|<0.2 -> {'PASS' if ok else 'FAIL/EMPTY'} "
              f"(left={l}, right={r})")


if __name__ == "__main__":
    main()
