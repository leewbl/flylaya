"""TASK-0013 phase-2 semantic confirmation, exploratory stage (design §5.2.2).

S1/S2 mirrors x {P_laya(observable, tau=1.6/eps=0.06), P_yoked(cycle_shift
k=17 from the SAME seed's P_laya run), P_rule(sensory)} x connectome x
sensory_only x 30s x seeds 101-105 (exploration seeds; confirmatory seeds
stay sealed). Serial. Yoked pairs are frozen laya-first per (scene, seed).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
PY = sys.executable

SCENES = ["S1_light_left", "S1_light_right", "S2_obstacle_left", "S2_obstacle_right"]
SEEDS = [101, 102, 103, 104, 105]
YOKED_K = 17   # >> max dwell (~2s); preserves marginals exactly, kills state tie


def run(scene, seed, policy, out, extra=()):
    cmd = [PY, os.path.join(HERE, "..", "runner.py"), "run",
           "--scene", os.path.join(ROOT, "m5", "scenes", f"{scene}.json"),
           "--seed", str(seed), "--policy", policy, "--coupling", "sensory_only",
           "--brain", "connectome", "--out", out,
           "--experiment-id", "m5-sem-explore", "--seconds", "30", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(f"{scene}/{seed}/{policy}: {'OK' if r.returncode == 0 else 'FAIL ' + r.stderr[-200:]}",
          flush=True)
    return r.returncode == 0


def main():
    root = os.path.join(ROOT, "m5", "runs_sem")
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
                print("yoked gen FAIL:", g.stderr[-200:])
                raise SystemExit(1)
            verdict = json.load(open(os.path.join(yok_gen, "yoked_verdict.json")))
            if not verdict.get("ok"):
                print(f"YOKED MISMATCH {scene}/{seed}: {verdict}")
                raise SystemExit(1)
            run(scene, seed, "P_yoked",
                os.path.join(root, scene, "P_yoked", str(seed)),
                ["--yoked-sequence", os.path.join(yok_gen, "yoked_sequence.jsonl"),
                 "--yoked-mode", "identity"])
            run(scene, seed, "P_rule",
                os.path.join(root, scene, "P_rule", str(seed)))
    print("batch complete")


if __name__ == "__main__":
    main()
