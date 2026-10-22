"""Gate-V0 instrument re-verification harness (vertical campaign plan §1, TASK-0025 prep).

S0v x P_rule vertical probe x 5 exploration seeds x 30s (plan §1).
Probe history: the original absolute-brightness gate coupled with intent
light gains (P_rule z_std exactly 0.0); backend's structural criterion
(glare-core bu > 4*bd, gate-v0-precheck.md) fixed the instrument itself,
so the plan-native P_rule probe is correct again.
QA (frame-hash determinism of the frozen runs). V0 criteria (plan §0):
  z_std >= 0.03 m            (channel unpinned)
  floor/ceiling pin frames < 5%   (z outside [0.10, 0.90] m)
  horizontal guardrails hold (omega p50 < 150 dps; switch gate applies to
    sampled policies; the probe is deterministic P_fixed,
    not gated)
FAIL -> sealed vertical seeds (200000-299999) stay locked.

Usage: python m5/campaign/gate_v0_check.py [--reuse]
Exit 0 = PASS. Writes m5/campaign/gate-V0-verdict.json.
"""
import argparse
import hashlib
import json
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
S0V = os.path.join(ROOT, "m5", "scenes", "S0v_neutral.json")
Z_LO, Z_HI, Z_STD_MIN, PIN_MAX = 0.10, 0.90, 0.03, 0.05


def _code_hash():
    h = hashlib.sha256()
    for rel in ("flylaya/brains.py", "flylaya/intent.py", "flylaya/world.py",
                "flylaya/scene.py", "m5/runner.py", "m5/metrics.py"):
        h.update(open(os.path.join(ROOT, rel), "rb").read())
    return h.hexdigest()


def run_batch():
    if not os.path.exists(S0V):
        raise SystemExit("S0v scene missing — TASK-0023 deliverable not landed")
    snap = _code_hash()
    for seed in SEEDS:
        out = os.path.join(ROOT, "m5", "runs_gateV0", "S0v", "P_rule", str(seed))
        r = subprocess.run(
            [PY, os.path.join(HERE, "..", "runner.py"), "run",
             "--scene", S0V, "--seed", str(seed), "--policy", "P_rule",
             "--coupling", "sensory_only", "--brain", "connectome",
             "--out", out, "--experiment-id", "m5-gate-V0",
             "--seconds", "30"],
            capture_output=True, text=True)
        print(f"S0v/{seed}: {'OK' if r.returncode == 0 else 'FAIL ' + r.stderr[-160:]}",
              flush=True)
        if r.returncode != 0:
            raise SystemExit(1)
    if _code_hash() != snap:
        raise SystemExit("CODE CHANGED MID-BATCH — verdict invalid, re-run")


def omega_p50(run):
    fr = run["frames"]
    dy = [abs(((b["yaw_deg"] - a["yaw_deg"] + 180) % 360) - 180) /
          max(b["t_s"] - a["t_s"], 1e-6) for a, b in zip(fr, fr[1:])]
    return float(np.median(dy))


def frame_hash(run):
    h = hashlib.sha256()
    for f in run["frames"]:
        h.update(json.dumps(f, sort_keys=True).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true")
    args = ap.parse_args()
    if not args.reuse:
        run_batch()

    z_stds, pin_fracs, oms, hashes = [], [], [], []
    for seed in SEEDS:
        run = M.load_run(os.path.join(ROOT, "m5", "runs_gateV0", "S0v",
                                      "P_rule", str(seed)))
        zs = np.array([f["pos_m"][2] for f in run["frames"]])
        z_stds.append(float(zs.std()))
        pin_fracs.append(float(np.mean((zs < Z_LO) | (zs > Z_HI))))
        oms.append(omega_p50(run))
        hashes.append(frame_hash(run))

    v0a = float(np.median(z_stds)) >= Z_STD_MIN
    v0b = float(np.median(pin_fracs)) < PIN_MAX
    v0c = float(np.median(oms)) < 150
    verdict = {
        "gate": "V0", "criteria_version": "v1 (plan §0)",
        "checked_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "z_std_m": {"per_seed": [round(z, 4) for z in z_stds],
                    "median": float(np.median(z_stds)), "pass": bool(v0a)},
        "pin_frac": {"per_seed": [round(p, 4) for p in pin_fracs],
                     "median": float(np.median(pin_fracs)), "pass": bool(v0b)},
        "omega_p50_dps": {"median": float(np.median(oms)), "pass": bool(v0c)},
        "replay_frame_hashes": hashes,   # 0024 QA input: determinism cross-check
        "PASS": bool(v0a and v0b and v0c),
        "note": "exploration seeds 1-5; vertical sealed set untouched; "
                "0024 replay/coupling/permission QA runs separately",
    }
    json.dump(verdict, open(os.path.join(HERE, "gate-V0-verdict.json"), "w"),
              indent=1)
    print(json.dumps({k: verdict[k] for k in
                      ("z_std_m", "pin_frac", "omega_p50_dps", "PASS")}, indent=1))
    sys.exit(0 if verdict["PASS"] else 1)


if __name__ == "__main__":
    main()
