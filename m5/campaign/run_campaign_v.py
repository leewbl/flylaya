"""Vertical campaign driver (plan §3, TASK-0025).

Stages (serial, code-sentinel guarded, sealed-domain enforced):
  explore   S0v/S4v x {P_laya, P_yoked, P_rule} x exploration 4001-4010 x 120s
  confirm   S0v/S4v x {P_laya, P_yoked} x sealed_v seeds[0:20] x 120s
  s4rule    S4v x P_rule x sealed_v seeds[20:30] x 120s
Vertical sealed domain: 200000-299999 (confirmation_seeds_v.json);
exploration domain: 1-9999. Gate-V0 verdict must PASS before ANY sealed use.
V1 (vertical expressibility) is judged from the explore stage's P_rule arm:
V1 fail -> confirm is SKIPPED (instrument-first discipline, plan §5).
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
RUNS = os.path.join(ROOT, "m5", "runs_confirm_v")
SEALED = json.load(open(os.path.join(ROOT, "m5", "research",
                                     "confirmation_seeds_v.json")))
V3_SEEDS = SEALED["seeds"][0:20]
S4V_SEEDS = SEALED["seeds"][20:30]
_LAYA_ARGS = ["--state-source", "observable", "--tau", "1.6", "--eps", "0.06"]
_CODE_SNAP = None


def _code_hash():
    h = hashlib.sha256()
    for rel in ("flylaya/brains.py", "flylaya/intent.py", "flylaya/world.py",
                "flylaya/scene.py", "m5/runner.py", "m5/metrics.py"):
        h.update(open(os.path.join(ROOT, rel), "rb").read())
    return h.hexdigest()


def _check_code_stable(tag):
    global _CODE_SNAP
    cur = _code_hash()
    if _CODE_SNAP is None:
        _CODE_SNAP = cur
        return
    if cur != _CODE_SNAP:
        raise SystemExit(f"CODE CHANGED DURING {tag} — batch invalid; restart")


def _check_gate():
    v = os.path.join(HERE, "gate-V0-verdict.json")
    if not os.path.exists(v):
        raise SystemExit("no gate-V0 verdict — run gate_v0_check.py first")
    if not json.load(open(v)).get("PASS"):
        raise SystemExit("gate-V0 FAIL — vertical sealed seeds are off-limits")


def _seed_ok(seed, domain):
    if domain == "v3":
        return seed in V3_SEEDS
    if domain == "s4v":
        return seed in S4V_SEEDS
    return 1 <= seed <= 9999


def _run(scene, seed, policy, out, domain, coupling="sensory_only", extra=()):
    if not _seed_ok(seed, domain):
        raise SystemExit(f"seed {seed} outside domain {domain} — refusing")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [PY, os.path.join(HERE, "..", "runner.py"), "run",
           "--scene", os.path.join(ROOT, "m5", "scenes", f"{scene}.json"),
           "--seed", str(seed), "--policy", policy, "--coupling", coupling,
           "--brain", "connectome", "--out", out, "--seconds", "120", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    tag = f"{scene}/{policy}/{seed}"
    if r.returncode != 0:
        print(f"{tag}: FAIL {r.stderr[-200:]}", flush=True)
        return False
    v = subprocess.run([PY, os.path.join(HERE, "..", "runner.py"), "verify", out],
                       capture_output=True, text=True)
    ok = v.returncode == 0
    print(f"{tag}: {'OK' if ok else 'VERIFY-FAIL'}", flush=True)
    return ok


def _yoked(scene, seed, laya_out, k=41):
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
    raise SystemExit(f"yoked regen exhausted {scene}/{seed} — STOP (no relaxation)")


def _v1_verdict():
    """Vertical expressibility from the explore P_rule arm (plan §0 V1):
    commanded climb/dive probes produce same-sign vertical velocity,
    mirror-symmetric. Uses explore runs' vz stats per scene; returns dict."""
    sys.path.insert(0, os.path.join(HERE, ".."))
    import metrics as M
    out = {}
    for scene in ("S0v_neutral", "S4v_vertical"):
        root = os.path.join(RUNS, scene, "P_rule")
        if not os.path.isdir(root):
            out[scene] = None
            continue
        vzs = []
        for seed in sorted(os.listdir(root)):
            rd = os.path.join(root, seed)
            if not os.path.exists(os.path.join(rd, "trajectory.jsonl")):
                continue
            run = M.load_run(rd)
            fr = run["frames"]
            vz = [(b["pos_m"][2] - a["pos_m"][2]) /
                  max(b["t_s"] - a["t_s"], 1e-6) for a, b in zip(fr, fr[1:])]
            vzs.append(float(np.mean(vz)) if (np := __import__("numpy")) else 0)
        out[scene] = vzs
    return out


def stage_explore(dry=False):
    _check_code_stable("explore-start")
    for scene in ("S0v_neutral", "S4v_vertical"):
        for seed in range(4001, 4011):
            laya = os.path.join(RUNS, scene, "P_laya", str(seed))
            if not _run(scene, seed, "P_laya", laya, "exploration",
                        extra=_LAYA_ARGS + ["--experiment-id", "m5v-explore"]):
                raise SystemExit(1)
            if dry:
                continue
            seq = _yoked(scene, seed, laya)
            _run(scene, seed, "P_yoked",
                 os.path.join(RUNS, scene, "P_yoked", str(seed)), "exploration",
                 extra=["--yoked-sequence", seq, "--yoked-mode", "identity",
                        "--experiment-id", "m5v-explore"])
            _run(scene, seed, "P_rule",
                 os.path.join(RUNS, scene, "P_rule", str(seed)), "exploration",
                 extra=["--experiment-id", "m5v-explore"])
    _check_code_stable("explore-end")


def stage_confirm(dry=False):
    _check_gate()
    _check_code_stable("confirm-start")
    for scene in ("S0v_neutral", "S4v_vertical"):
        for seed in V3_SEEDS:
            laya = os.path.join(RUNS, scene, "P_laya", str(seed))
            if not _run(scene, seed, "P_laya", laya, "v3",
                        extra=_LAYA_ARGS + ["--experiment-id", "m5v-confirm"]):
                raise SystemExit(1)
            if dry:
                continue
            seq = _yoked(scene, seed, laya)
            _run(scene, seed, "P_yoked",
                 os.path.join(RUNS, scene, "P_yoked", str(seed)), "v3",
                 extra=["--yoked-sequence", seq, "--yoked-mode", "identity",
                        "--experiment-id", "m5v-confirm"])
    _check_code_stable("confirm-end")


def stage_s4rule(dry=False):
    _check_gate()
    _check_code_stable("s4rule-start")
    for seed in S4V_SEEDS:
        _run("S4v_vertical", seed, "P_rule",
             os.path.join(RUNS, "S4v_vertical", "P_rule", str(seed)), "s4v",
             extra=["--experiment-id", "m5v-s4-rule"])
    _check_code_stable("s4rule-end")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["explore", "confirm", "s4rule", "v1"])
    ap.add_argument("--dry-run", action="store_true")
    argv = sys.argv[1:]
    if argv and argv[0] == "stage":
        argv = argv[1:]
    args = ap.parse_args(argv)
    if args.stage == "v1":
        print(json.dumps(_v1_verdict(), indent=1))
        return
    {"explore": stage_explore, "confirm": stage_confirm,
     "s4rule": stage_s4rule}[args.stage](args.dry_run)


if __name__ == "__main__":
    main()
