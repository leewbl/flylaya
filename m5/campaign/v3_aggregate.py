"""V3 aggregation: paired Laya-vs-yoked z-metric differences with stratified
bootstrap CIs (vertical plan §0 V3; interval-based reporting, no hard gate).

Metrics per run: z_mean, z_std, vertical activity = mean|vz|.
Pairs keyed (scene, seed) across policies; seeds-within-scene resampling
via metrics.stratified_bootstrap_ci (same machinery as H1).
Usage: python m5/campaign/v3_aggregate.py  → m5/runs_confirm_v/v3-analysis.json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
import metrics as M  # noqa: E402

RUNS = os.path.join(ROOT, "m5", "runs_confirm_v")
CONFIRM_SEEDS = json.load(open(os.path.join(
    ROOT, "m5", "research", "confirmation_seeds_v.json")))["seeds"][0:20]


def zmetrics(run):
    fr = run["frames"]
    zs = np.array([f["pos_m"][2] for f in fr])
    vz = np.abs([(b["pos_m"][2] - a["pos_m"][2]) / max(b["t_s"] - a["t_s"], 1e-6)
                 for a, b in zip(fr, fr[1:])])
    return {"z_mean": float(zs.mean()), "z_std": float(zs.std()),
            "v_act": float(np.mean(vz))}


def collect(scene, pol, seeds):
    out = {}
    for seed in seeds:
        rd = os.path.join(RUNS, scene, pol, str(seed))
        if os.path.exists(os.path.join(rd, "trajectory.jsonl")):
            out[int(seed)] = zmetrics(M.load_run(rd))
    return out


def paired(scene, metric):
    a = collect(scene, "P_laya", CONFIRM_SEEDS)
    b = collect(scene, "P_yoked", CONFIRM_SEEDS)
    common = sorted(set(a) & set(b))
    diffs = [a[s][metric] - b[s][metric] for s in common]
    return {f"{scene}": diffs}, len(common)


def main():
    report = {"n_pairs": {}, "V3": {}}
    for metric in ("z_mean", "z_std", "v_act"):
        by_scene = {}
        for scene in ("S0v_neutral", "S4v_vertical"):
            d, n = paired(scene, metric)
            by_scene.update(d)
            report["n_pairs"].setdefault(scene, n)
        ci = M.stratified_bootstrap_ci(by_scene)
        report["V3"][metric] = {
            "per_scene": {k: {"mean_diff": float(np.mean(v)), "n": len(v)}
                          for k, v in by_scene.items()},
            "pooled_ci95": ci,
        }
    out = os.path.join(RUNS, "v3-analysis.json")
    json.dump(report, open(out, "w"), indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
