"""M5 8-hour campaign batch driver (plan §2, TASK-0021).

Stage-serial execution with seed-domain enforcement:
  h1  S1 L/R x {P_laya, P_yoked} x sealed seeds[0:20] x 30s
  h2  S2 L/R x {P_laya, P_yoked} x sealed seeds[0:20] + rear negctrl
      (P_laya x exploration 2001-2010)
  h3  S1 L/R x P_laya x {sensory_only, motor_only, full} x exploration
      3001-3010, direct off (mediation; plan takes the effective scene from
      H1 — S1 default, override by editing SCENES_H3)
  s4  S4_mixed_holdout x {P_laya, P_yoked, P_rule} x sealed seeds[20:30] x 300s

Iron rules enforced here (plan §5铁律 1/3/4):
  - sealed seeds only inside their window; exploration runs confined to 1-9999;
  - yoked mismatch regenerates (max 2 attempts, then abort — never relax);
  - every run manifest-verified (content gate, not filename).

Usage: python m5/campaign/run_campaign.py stage h1|h2|h3|s4 [--dry-run]
Prerequisite: m5/campaign/gate-F-verdict.json PASS before ANY sealed seed use.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
PY = sys.executable
RUNS = os.path.join(ROOT, "m5", "runs_confirm")
SEALED = json.load(open(os.path.join(ROOT, "m5", "research",
                                     "confirmation_seeds.json")))
H1H2_SEEDS = SEALED["seeds"][0:20]
S4_SEEDS = SEALED["seeds"][20:30]
SCENES_H3 = ("S1_light_left", "S1_light_right")   # effective scene from H1


_CODE_SNAP = None


def _code_hash():
    h = hashlib.sha256()
    for rel in ("flylaya/brains.py", "flylaya/intent.py", "flylaya/world.py",
                "flylaya/scene.py", "m5/runner.py", "m5/metrics.py"):
        h.update(open(os.path.join(ROOT, rel), "rb").read())
    return h.hexdigest()


def _check_code_stable(stage_name):
    """Called after each stage: mid-batch sim-source edits invalidate the
    whole confirmatory batch (design §6: every change = new version)."""
    global _CODE_SNAP
    cur = _code_hash()
    if _CODE_SNAP is None:
        _CODE_SNAP = cur
        return
    if cur != _CODE_SNAP:
        raise SystemExit(f"CODE CHANGED DURING {stage_name} — batch invalid; "
                         "restart stage on the new code version")
    v = os.path.join(HERE, "gate-F-verdict.json")
    if not os.path.exists(v):
        raise SystemExit("no gate-F verdict — run gate_f_check.py first")
    if not json.load(open(v)).get("PASS"):
        raise SystemExit("gate-F FAIL — sealed seeds are off-limits (plan §0)")


def _check_gate():
    v = os.path.join(HERE, "gate-F-verdict.json")
    if not os.path.exists(v):
        raise SystemExit("no gate-F verdict — run gate_f_check.py first")
    if not json.load(open(v)).get("PASS"):
        raise SystemExit("gate-F FAIL — sealed seeds are off-limits (plan §0)")


def _seed_ok(seed, domain):
    if domain == "h1h2":
        return seed in H1H2_SEEDS
    if domain == "s4":
        return seed in S4_SEEDS
    return 1 <= seed <= 9999


def _run(scene, seed, policy, out, seconds, domain, coupling="sensory_only",
         extra=()):
    if not _seed_ok(seed, domain):
        raise SystemExit(f"seed {seed} outside domain {domain} — refusing")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [PY, os.path.join(HERE, "..", "runner.py"), "run",
           "--scene", os.path.join(ROOT, "m5", "scenes", f"{scene}.json"),
           "--seed", str(seed), "--policy", policy, "--coupling", coupling,
           "--brain", "connectome", "--out", out, "--seconds", str(seconds),
           *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    tag = f"{scene}/{policy}/{seed}"
    if r.returncode != 0:
        print(f"{tag}: FAIL {r.stderr[-200:]}", flush=True)
        return False
    v = subprocess.run([PY, os.path.join(HERE, "..", "runner.py"), "verify", out],
                       capture_output=True, text=True)
    ok = v.returncode == 0
    print(f"{tag}: {'OK' if ok else 'VERIFY-FAIL ' + v.stdout[-200:]}", flush=True)
    return ok


def _yoked(scene, seed, laya_out, k=17):
    gen = os.path.join(RUNS, scene, "yoked_src", str(seed))
    for attempt in (1, 2):
        g = subprocess.run([PY, os.path.join(HERE, "..", "runner.py"), "yoked",
                            laya_out, gen, "--mode", "cycle_shift",
                            "--k", str(k + attempt - 1)],
                           capture_output=True, text=True)
        if g.returncode != 0:
            continue
        verdict = json.load(open(os.path.join(gen, "yoked_verdict.json")))
        if verdict.get("ok"):
            return os.path.join(gen, "yoked_sequence.jsonl")
        print(f"yoked mismatch {scene}/{seed} attempt {attempt}: "
              f"share={verdict['max_share_diff']:.4f} "
              f"dwell={verdict['dwell_rel_diff']:.3f}", flush=True)
    raise SystemExit(f"yoked regen exhausted for {scene}/{seed} — STOP BATCH "
                     "(plan iron rule 3: no tolerance relaxation)")


_LAYA_ARGS = ["--state-source", "observable", "--tau", "1.6", "--eps", "0.06"]


def stage_h1(dry=False):
    _check_gate()
    _check_code_stable("h1-start")
    for scene in ("S1_light_left", "S1_light_right"):
        for seed in H1H2_SEEDS:
            laya = os.path.join(RUNS, scene, "P_laya", str(seed))
            if not _run(scene, seed, "P_laya", laya, 30, "h1h2",
                        extra=_LAYA_ARGS + ["--experiment-id", "m5-confirm-h1h2"]):
                raise SystemExit(1)
            if dry:
                continue
            seq = _yoked(scene, seed, laya)
            _run(scene, seed, "P_yoked",
                 os.path.join(RUNS, scene, "P_yoked", str(seed)), 30, "h1h2",
                 extra=["--yoked-sequence", seq, "--yoked-mode", "identity",
                        "--experiment-id", "m5-confirm-h1h2"])
    _check_code_stable("h1-end")


def stage_h2(dry=False):
    _check_gate()
    _check_code_stable("h2-start")
    for scene in ("S2_obstacle_left", "S2_obstacle_right"):
        for seed in H1H2_SEEDS:
            laya = os.path.join(RUNS, scene, "P_laya", str(seed))
            if not _run(scene, seed, "P_laya", laya, 30, "h1h2",
                        extra=_LAYA_ARGS + ["--experiment-id", "m5-confirm-h1h2"]):
                raise SystemExit(1)
            if dry:
                continue
            seq = _yoked(scene, seed, laya)
            _run(scene, seed, "P_yoked",
                 os.path.join(RUNS, scene, "P_yoked", str(seed)), 30, "h1h2",
                 extra=["--yoked-sequence", seq, "--yoked-mode", "identity",
                        "--experiment-id", "m5-confirm-h1h2"])
    for seed in range(2001, 2011):   # rear negative control, exploration domain
        _run("S2_obstacle_rear_negctrl", seed, "P_laya",
             os.path.join(RUNS, "S2_obstacle_rear_negctrl", "P_laya", str(seed)),
             30, "exploration",
             extra=_LAYA_ARGS + ["--experiment-id", "m5-confirm-h2-negctrl"])
    _check_code_stable("h2-end")


def stage_h3(dry=False):
    _check_gate()
    _check_code_stable("h3-start")
    for scene in SCENES_H3:
        for cp in ("sensory_only", "motor_only", "full"):
            for seed in range(3001, 3011):
                _run(scene, seed, "P_laya",
                     os.path.join(RUNS, scene, f"P_laya_{cp}", str(seed)),
                     30, "exploration", coupling=cp,
                     extra=_LAYA_ARGS + ["--experiment-id", "m5-h3-mediation"])
    _check_code_stable("h3-end")


def stage_s4(dry=False):
    _check_gate()
    _check_code_stable("s4-start")
    for seed in S4_SEEDS:
        laya = os.path.join(RUNS, "S4_mixed_holdout", "P_laya", str(seed))
        if not _run("S4_mixed_holdout", seed, "P_laya", laya, 300, "s4",
                    extra=_LAYA_ARGS + ["--experiment-id", "m5-s4-open"]):
            raise SystemExit(1)
        if dry:
            continue
        seq = _yoked("S4_mixed_holdout", seed, laya)
        _run("S4_mixed_holdout", seed, "P_yoked",
             os.path.join(RUNS, "S4_mixed_holdout", "P_yoked", str(seed)),
             300, "s4",
             extra=["--yoked-sequence", seq, "--yoked-mode", "identity",
                    "--experiment-id", "m5-s4-open"])
        _run("S4_mixed_holdout", seed, "P_rule",
             os.path.join(RUNS, "S4_mixed_holdout", "P_rule", str(seed)),
             300, "s4", extra=["--experiment-id", "m5-s4-open"])

    _check_code_stable("stage-end")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["h1", "h2", "h3", "s4"])
    ap.add_argument("--dry-run", action="store_true")
    argv = sys.argv[1:]
    if argv and argv[0] == "stage":
        argv = argv[1:]
    args = ap.parse_args(argv)
    {"h1": stage_h1, "h2": stage_h2, "h3": stage_h3, "s4": stage_s4}[args.stage](
        args.dry_run)


if __name__ == "__main__":
    main()
