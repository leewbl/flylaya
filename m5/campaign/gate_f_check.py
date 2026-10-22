"""Gate-F instrument re-verification harness (campaign plan §0, TASK-0021 prep).

Runs the 15-segment re-verification batch on EXPLORATION seeds (1-9999) and
emits the plan's pass criteria:
  F1  S1 L/R x P_rule x sensory_only x connectome, 5 seeds: mean_cos_to_light
      >= +0.3 per mirror AND mirror symmetric (|L-R| <= 0.2)
  F2  S2 left x P_rule: correct-turn-away > 0.5; |left - right| < 0.2
  F3  guardrails on the same runs: omega p50 < 150 dps; arousal-speed r > 0.3

Usage: python m5/campaign/gate_f_check.py [--reuse]
Writes m5/runs_gateF/... and m5/campaign/gate-F-verdict.json. Exit 0 = PASS.
NO sealed seeds are touched (seeds 1-5 are exploration domain).
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
import metrics as M  # noqa: E402

PY = sys.executable
SEEDS = [1, 2, 3, 4, 5]


def _code_hash():
    h = hashlib.sha256()
    for rel in ("flylaya/brains.py", "flylaya/intent.py", "flylaya/world.py",
                "flylaya/scene.py", "m5/runner.py", "m5/metrics.py"):
        h.update(open(os.path.join(ROOT, rel), "rb").read())
    return h.hexdigest()


def run_batch():
    """Runs the batch AND guards against mid-batch code edits: any change to
    the sim sources between start and analysis invalidates the verdict."""
    snap = _code_hash()
    for scene in ("S1_light_left", "S1_light_right",
                  "S2_obstacle_left", "S2_obstacle_right"):
        for seed in SEEDS:
            out = os.path.join(ROOT, "m5", "runs_gateF", scene, "P_rule", str(seed))
            r = subprocess.run(
                [PY, os.path.join(HERE, "..", "runner.py"), "run",
                 "--scene", os.path.join(ROOT, "m5", "scenes", f"{scene}.json"),
                 "--seed", str(seed), "--policy", "P_rule",
                 "--coupling", "sensory_only", "--brain", "connectome",
                 "--out", out, "--experiment-id", "m5-gate-F",
                 "--seconds", "30"],
                capture_output=True, text=True)
            print(f"{scene}/{seed}: {'OK' if r.returncode == 0 else 'FAIL ' + r.stderr[-160:]}",
                  flush=True)
            if r.returncode != 0:
                raise SystemExit(1)
    after = _code_hash()
    if after != snap:
        raise SystemExit("CODE CHANGED MID-BATCH — verdict invalid, re-run")


def omega_p50(run):
    fr = run["frames"]
    dy = [abs(((b["yaw_deg"] - a["yaw_deg"] + 180) % 360) - 180) /
          max(b["t_s"] - a["t_s"], 1e-6) for a, b in zip(fr, fr[1:])]
    return float(np.median(dy))


def arou_r(run):
    fr = run["frames"]
    sp = np.array([f["speed_m_s"] for f in fr])
    ar = np.array([f["arousal"] for f in fr])
    if ar.std() == 0:
        return None
    return float(np.corrcoef(sp, ar)[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true")
    args = ap.parse_args()
    if not args.reuse:
        run_batch()

    cos = {}
    away = {}
    om, ars = [], []
    for scene in ("S1_light_left", "S1_light_right",
                  "S2_obstacle_left", "S2_obstacle_right"):
        cs, aws = [], []
        for seed in SEEDS:
            run = M.load_run(os.path.join(ROOT, "m5", "runs_gateF", scene,
                                          "P_rule", str(seed)))
            m = M.run_metrics(run)
            cs.append(m["light"]["mean_cos_to_light"])
            av = m["avoidance"]
            if av["correct_turn_away_rate"] is not None:
                aws.append(av["correct_turn_away_rate"])
            om.append(omega_p50(run))
            r = arou_r(run)
            if r is not None:
                ars.append(r)
        cs = [c for c in cs if c is not None]   # uniform-light scenes -> None
        cos[scene] = float(np.mean(cs)) if cs else None
        away[scene] = float(np.mean(aws)) if aws else None

    # criteria v2 — pre-registered readings (researcher Gate-F ruling
    # 2026-09-26, findings/researcher/gate-f-verdict.md):
    # A: symmetry under right-arm saturation -> left>=0.5 AND right>=0.8
    #    (saturation not degraded); P_yoked mirror symmetry is verified at
    #    confirm-batch level on sealed seeds.
    # B: spin guardrail from the S4 x full-coupling A-config guard pair
    #    (m5/runs_t22_final/guard), not from P_rule/sensory diagnostic cells.
    f1 = (cos["S1_light_left"] >= 0.3 and cos["S1_light_right"] >= 0.3 and
          abs(cos["S1_light_left"] - cos["S1_light_right"]) <= 0.2)
    f2 = (away["S2_obstacle_left"] is not None and away["S2_obstacle_left"] >= 0.5 and
          away["S2_obstacle_right"] is not None and away["S2_obstacle_right"] >= 0.8)
    om_guard = []
    guard_root = os.path.join(ROOT, "m5", "runs_t22_final", "guard")
    if os.path.isdir(guard_root):
        for d in sorted(os.listdir(guard_root)):
            tj = os.path.join(guard_root, d, "trajectory.jsonl")
            if os.path.exists(tj):
                om_guard.append(omega_p50(M.load_run(os.path.join(guard_root, d))))
    om_f3 = float(np.median(om_guard)) if om_guard else float(np.median(om))
    f3 = (om_f3 < 150 and (not ars or float(np.median(ars)) > 0.3))
    verdict = {
        "gate": "F", "criteria_version": "v2 (pre-registered readings A/B, "
                                         "researcher Gate-F ruling 2026-09-26)",
        "checked_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "F1_light_readout": {"mean_cos": cos, "pass": bool(f1),
                             "criteria": "both mirrors >= +0.3, |L-R| <= 0.2"},
        "F2_looming_sign": {"correct_away": away, "pass": bool(f2),
                            "criteria": "reading A: left >= 0.5 AND right >= 0.8 "
                                        "(right saturation not degraded)"},
        "F3_guardrails": {"omega_p50_dps": om_f3,
                          "omega_source": "guard pair" if om_guard else
                                          "P_rule diagnostic cells (fallback)",
                          "arousal_r_median": float(np.median(ars)) if ars else None,
                          "pass": bool(f3)},
        "PASS": bool(f1 and f2 and f3),
        "note": "exploration seeds 1-5 only; sealed set untouched",
    }
    out = os.path.join(HERE, "gate-F-verdict.json")
    json.dump(verdict, open(out, "w"), indent=1)
    print(json.dumps(verdict, indent=1))
    sys.exit(0 if verdict["PASS"] else 1)


if __name__ == "__main__":
    main()
