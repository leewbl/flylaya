"""m5/runner.py — W3 batch/logging runner (design §6; TASK-0011).

Policy and coupling layers consume the W2 canonical sources in
flylaya/intent.py (TASK-0010): FixedGoalSource / RuleIntentSource /
YokedIntentSource / LayaIntentSource(state_source, coupling, direct),
modulation_for(coupling=...) and audit_row. This module owns the batch
plumbing only: streaming contract writers, §6 manifests, content-based
resume, the yoked freeze step, and the scene×policy×seed driver.

RNG audit (Gate-F ruling addendum 2): ConnectomeBrain's dead-axis
symmetry-breaking entropy consumes the brain-internal stream seeded by
the run seed; it is accounted under the "neural" stream family of
scene.stream_rngs.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import shutil
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import metrics as M  # noqa: E402  (event detector v1, single implementation)
from flylaya.intent import (FixedGoalSource, LayaIntentSource,  # noqa: E402
                            RuleIntentSource, YokedIntentSource, audit_row,
                            load_sequence, modulation_for, permute_sequence,
                            validate_yoked)

SCENES_DIR = os.path.join(HERE, "scenes")
COUPLINGS = ("full", "sensory_only", "motor_only")   # W2 canonical set


# ------------------------------------------------------------- §6 manifest
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(run_dir, *, experiment_id, scene_id, seed, policy, coupling,
                   brain, dt_s, rng_streams, status, t_start, t_end,
                   scene_path=None, extra_code_files=(), source_batch=None,
                   state_source=None, direct=None):
    files = {}
    for fn in ("trajectory.jsonl", "decisions.jsonl", "events.jsonl",
               "audit.jsonl"):
        p = os.path.join(run_dir, fn)
        if os.path.exists(p):
            with open(p) as f:
                n = sum(1 for _ in f)
            files[fn] = {"sha256": sha256_file(p), "bytes": os.path.getsize(p),
                         "lines": n}
    manifest = {
        "schema": "flylaya.m5.manifest.v1",
        "experiment_id": experiment_id,
        "scene_id": scene_id,
        "seed": seed,
        "policy": policy,
        "coupling": coupling,
        "brain": brain,
        "dt_s": dt_s,
        "state_source": state_source,
        "direct": direct,
        "rng_streams": rng_streams,
        "device": platform.machine() + "/" + platform.system(),
        "python": platform.python_version(),
        "t_start": t_start, "t_end": t_end,
        "status": status,
        "files": files,
        "scene_sha256": sha256_file(scene_path) if scene_path else None,
        "code": {rel: sha256_file(os.path.join(HERE, "..", rel))
                 for rel in ("flylaya/world.py", "flylaya/brains.py",
                             "flylaya/intent.py", "flylaya/scene.py",
                             "m5/metrics.py", "m5/runner.py",
                             *extra_code_files)},
        "detector_version": M.EVENTS_VERSION,
        "source_batch": source_batch,
    }
    with open(os.path.join(run_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    return manifest


def verify_run(run_dir, expected_frames=None):
    """Content-based resume gate: hash + line count + status + required
    fields, never mere filename existence (design §6)."""
    mp = os.path.join(run_dir, "manifest.json")
    if not os.path.exists(mp):
        return {"ok": False, "reason": "no_manifest"}
    m = json.load(open(mp))
    problems = []
    if m.get("status") != "ok":
        problems.append(f"status={m.get('status')}")
    for fn, meta in (m.get("files") or {}).items():
        p = os.path.join(run_dir, fn)
        if not os.path.exists(p):
            problems.append(f"{fn}:missing")
            continue
        if sha256_file(p) != meta["sha256"]:
            problems.append(f"{fn}:hash_mismatch")
        with open(p) as f:
            n = sum(1 for _ in f)
        if expected_frames is not None and fn == "trajectory.jsonl":
            want = expected_frames + 1          # +1 meta line
        else:
            want = meta.get("lines")
        if want is not None and n != want:
            problems.append(f"{fn}:lines={n}!={want}")
    for field in ("experiment_id", "scene_id", "seed", "policy", "coupling",
                  "rng_streams", "t_start", "t_end", "status", "scene_sha256"):
        if m.get(field) in (None, "", []):
            problems.append(f"field_missing:{field}")
    return {"ok": not problems, "problems": problems, "manifest": m}


# ------------------------------------------------------------- helpers
def _min_gap(world):
    """Clearance BEFORE any clamping (contract: 碰撞前的间隙)."""
    gaps = []
    for k, (x, z, r, h) in enumerate(world.obstacles):
        if world.obstacle_enabled[k] and world.pos[2] < h:
            gaps.append(math.hypot(world.pos[0] - x, world.pos[1] - z) - r)
    for i in range(3):
        gaps.append(world.pos[i] - world.arena_min[i])
        gaps.append(world.arena_max[i] - world.pos[i])
    return max(min(gaps), 0.0) if gaps else None


def make_policy(policy, scene, laya_url, yoked_sequence=None, yoked_mode="identity",
                yoked_seed=0, fixed_intent="explore", rule_truth=False,
                state_source="oracle", coupling="sensory_only", direct=False,
                tau=None, eps=None):
    every = max(1, round(scene.decision_dt_s / scene.neural_dt_s))
    if policy == "P_fixed":
        return FixedGoalSource(fixed_intent)
    if policy == "P_rule":
        return RuleIntentSource(use_truth=rule_truth)
    if policy == "P_yoked":
        if not yoked_sequence:
            raise ValueError("P_yoked needs --yoked-sequence")
        return YokedIntentSource(yoked_sequence, dt=scene.neural_dt_s,
                                 mode=yoked_mode, seed=yoked_seed)
    if policy == "P_laya":
        return LayaIntentSource(url=laya_url, every_frames=every,
                                state_source=state_source, coupling=coupling,
                                direct=direct, tau=tau, eps=eps)
    raise ValueError(f"unknown policy {policy!r}")


# ------------------------------------------------------------- run_one
def run_one(scene_path, seed, policy, coupling, brain_kind, out_dir,
            experiment_id, seconds=None,
            laya_url="http://127.0.0.1:8000/v1/systemone",
            yoked_sequence=None, yoked_mode="identity", yoked_seed=0,
            fixed_intent="explore", rule_truth=False, state_source="oracle",
            direct=False, tau=None, eps=None):
    from flylaya.brains import make_brain
    from flylaya.world import World

    os.makedirs(out_dir, exist_ok=True)
    t_start = dt.datetime.now().isoformat(timespec="seconds")
    world = World.from_scene(scene_path, seed=seed)
    scene = world.scene_obj
    if scene.source and os.path.exists(scene.source):
        shutil.copyfile(scene.source, os.path.join(out_dir, "scene.json"))
    dt_s = scene.neural_dt_s
    n_frames = int(round((seconds if seconds is not None else scene.duration_s) / dt_s))
    brain = make_brain(brain_kind, seed=seed)
    src = make_policy(policy, scene, laya_url, yoked_sequence, yoked_mode,
                      yoked_seed, fixed_intent, rule_truth, state_source,
                      coupling, direct, tau, eps)
    state_source_eff = getattr(src, "state_source",
                               "scripted" if policy != "P_laya" else "oracle")
    rng_streams = ({name: seed for name in scene.streams}
                   if world.streams else {"legacy": seed})
    status = "ok"

    traj_path = os.path.join(out_dir, "trajectory.jsonl")
    decisions = []
    audits = []
    try:
        with open(traj_path, "w") as ftraj, \
                open(os.path.join(out_dir, "events.jsonl"), "w") as fev, \
                open(os.path.join(out_dir, "audit.jsonl"), "w") as faudit:
            ftraj.write(json.dumps({
                "type": "meta", "schema": "flylaya.m5.traj.v1",
                "scene_id": scene.scene_id, "seed": seed, "policy": policy,
                "coupling": coupling, "brain": brain_kind, "dt_s": dt_s,
                "n_frames": n_frames, "state_source": state_source_eff,
                "truth_assisted_policy": bool(getattr(src, "use_truth", False)),
                "experiment_id": experiment_id}) + "\n")
            frames = []
            seg_intent, seg_t0 = None, None
            last_dec_id = None
            for frame in range(n_frames):
                t = round(frame * dt_s, 4)
                for ev in world.advance_clock(t):
                    fev.write(json.dumps({"t_s": t, "kind": ev["kind"],
                                          "target": ev.get("target"),
                                          "detector": "scene.clock"}) + "\n")
                intent, conf = src.poll(frame, world, brain)
                arousal = float(getattr(src, "arousal", 1) or 1)
                if policy == "P_laya" and getattr(src, "last_decision", None) \
                        and id(src.last_decision) != last_dec_id:
                    decisions.append(dict(src.last_decision))
                    last_dec_id = id(src.last_decision)
                mod_full = modulation_for(intent, arousal, "full")
                mod = modulation_for(intent, arousal, coupling)
                if intent != seg_intent:                 # modulation audit segment
                    if seg_intent is not None:
                        audits.append(audit_row(modulation_for(
                            seg_intent, arousal, coupling), seg_t0, t))
                    seg_intent, seg_t0 = intent, t
                gap = _min_gap(world)
                lum = world.render_luminance(
                    {k: mod[k] for k in ("light", "looming", "wall")})
                rates = brain.step(lum, dt_s)
                bias = src.consume_yaw_bias() if hasattr(src, "consume_yaw_bias") else 0.0
                world.step_motor(rates, dt_s,
                                 gains={"thrust": mod["thrust"]},
                                 yaw_noise=mod["yaw_noise"], rng=world.rng,
                                 yaw_bias=bias)
                row = {"t_s": t,
                       "pos_m": [round(float(v), 5) for v in world.pos],
                       "yaw_deg": round(math.degrees(world.yaw), 3),
                       "speed_m_s": round(float(np.linalg.norm(world.vel)), 4),
                       "min_gap_m": round(gap, 5) if gap is not None else None,
                       "intent_raw": intent, "intent_applied": intent,
                       "arousal": arousal,
                       "yaw_bias_direct": round(float(bias), 5),
                       "gains_pre": {k: round(float(v), 4) for k, v in
                                     mod_full.items() if isinstance(v, (int, float))},
                       "gains_post": audit_row(mod, t),
                       "dn": {k: round(float(rates.get(k, 0.0)), 3) for k in M.DN_LR},
                       "stim": (["light_on"] if getattr(world, "light_on", True)
                                else ["light_off"])}
                ftraj.write(json.dumps(row) + "\n")
                frames.append(row)
            if seg_intent is not None:
                audits.append(audit_row(modulation_for(seg_intent, arousal, coupling),
                                        seg_t0, frames[-1]["t_s"]))
            for a in audits:
                faudit.write(json.dumps(a) + "\n")
            # obstacle enable timing comes from the scene clock; the static
            # scene file keeps initial flags and detect_events replays the
            # stimulus_on/off timeline itself (passing the run-end state
            # produced phantom pre-stimulus approaches — TASK-0020)
            det_scene = ({"obstacles": [dict(ob) for ob in scene.obstacles],
                          "events": [dict(e) for e in scene.events]}
                         if scene is not None else None)
            for ev in M.detect_events(frames, det_scene):
                fev.write(json.dumps(ev) + "\n")
    except Exception as e:                       # explicit failed status (design §6)
        status = "failed"
        t_end = dt.datetime.now().isoformat(timespec="seconds")
        write_manifest(out_dir, experiment_id=experiment_id,
                       scene_id=scene.scene_id, seed=seed, policy=policy,
                       coupling=coupling, brain=brain_kind, dt_s=dt_s,
                       rng_streams=rng_streams, status=status, t_start=t_start,
                       t_end=t_end, scene_path=scene.source,
                       state_source=state_source_eff, direct=direct,
                       source_batch=experiment_id)
        raise
    if decisions:
        with open(os.path.join(out_dir, "decisions.jsonl"), "w") as f:
            for r in decisions:
                f.write(json.dumps(r) + "\n")
    t_end = dt.datetime.now().isoformat(timespec="seconds")
    write_manifest(out_dir, experiment_id=experiment_id, scene_id=scene.scene_id,
                   seed=seed, policy=policy, coupling=coupling, brain=brain_kind,
                   dt_s=dt_s, rng_streams=rng_streams, status=status,
                   t_start=t_start, t_end=t_end, scene_path=scene.source,
                   state_source=state_source_eff, direct=direct,
                   source_batch=experiment_id)
    return {"dir": out_dir, "frames": n_frames, "status": status,
            "n_decisions": len(decisions)}


# ------------------------------------------------------------- yoked freeze
def freeze_sequence(laya_run_dir, out_path):
    """Freeze a P_laya run's applied (intent, arousal) stream at decision
    cadence into a W2 sequence file (t_s strictly increasing)."""
    rows = M._jsonl(os.path.join(laya_run_dir, "trajectory.jsonl"))
    frames = rows[1:]
    seq = [{"t_s": f["t_s"], "intent": f["intent_applied"],
            "arousal": f.get("arousal", 1.0)} for f in frames]
    load_sequence(seq)                            # validation (W2)
    with open(out_path, "w") as f:
        for r in seq:
            f.write(json.dumps(r) + "\n")
    return out_path


def build_yoked(laya_run_dir, out_dir, mode="cycle_shift", k=1, seed=0):
    """freeze → permute (W2 canonical modes) → tolerance verdict."""
    os.makedirs(out_dir, exist_ok=True)
    src_path = os.path.join(out_dir, "laya_sequence.jsonl")
    freeze_sequence(laya_run_dir, src_path)
    yoked = permute_sequence(src_path, mode=mode, k=k, seed=seed)
    yoked_path = os.path.join(out_dir, "yoked_sequence.jsonl")
    with open(yoked_path, "w") as f:
        for r in yoked:
            f.write(json.dumps(r) + "\n")
    verdict = validate_yoked(src_path, yoked_path)
    with open(os.path.join(out_dir, "yoked_verdict.json"), "w") as f:
        json.dump(verdict, f, indent=1)
    return {"sequence": yoked_path, "source": src_path, "verdict": verdict}


# ------------------------------------------------------------- driver
def plan_matrix(scenes, policies, seeds):
    return [(sc, pol, sd) for sc in scenes for pol in policies for sd in seeds]


def _run_cli(args):
    res = run_one(args.scene, args.seed, args.policy, args.coupling,
                  args.brain, args.out, args.experiment_id, seconds=args.seconds,
                  laya_url=args.laya_url,
                  yoked_sequence=args.yoked_sequence, yoked_mode=args.yoked_mode,
                  yoked_seed=args.yoked_seed, fixed_intent=args.fixed_intent,
                  rule_truth=args.rule_truth, state_source=args.state_source,
                  direct=args.direct, tau=args.tau, eps=args.eps)
    print(json.dumps(res))
    v = verify_run(args.out, expected_frames=res["frames"])
    print("verify:", json.dumps({k: v[k] for k in ("ok", "problems")}))
    sys.exit(0 if v["ok"] else 1)


def main():
    ap = argparse.ArgumentParser(description="M5 W3 runner (TASK-0011, W2-native)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("yoked", help="freeze+permute a P_laya run (W2 modes)")
    p.add_argument("laya_run_dir")
    p.add_argument("out_dir")
    p.add_argument("--mode", default="cycle_shift",
                   choices=["identity", "cycle_shift", "block_perm"])
    p.add_argument("--k", type=int, default=1)
    p.add_argument("--seed", type=int, default=0)
    p = sub.add_parser("verify", help="content-based run verification")
    p.add_argument("run_dir")
    p.add_argument("--frames", type=int, default=None)
    p = sub.add_parser("plan", help="print the scene×policy×seed matrix")
    p.add_argument("--scenes", nargs="+", required=True)
    p.add_argument("--policies", nargs="+", required=True)
    p.add_argument("--seeds", nargs="+", type=int, required=True)
    p = sub.add_parser("run", help="one contract run (scene×policy×seed×coupling)")
    p.add_argument("--scene", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--policy", default="P_fixed",
                   choices=["P_fixed", "P_yoked", "P_rule", "P_laya"])
    p.add_argument("--coupling", default="sensory_only", choices=list(COUPLINGS))
    p.add_argument("--brain", default="skeleton", choices=["skeleton", "connectome"])
    p.add_argument("--out", required=True)
    p.add_argument("--experiment-id", default="m5-dev")
    p.add_argument("--seconds", type=float, default=None)
    p.add_argument("--laya-url", default="http://127.0.0.1:8000/v1/systemone")
    p.add_argument("--yoked-sequence", default=None)
    p.add_argument("--yoked-mode", default="identity",
                   choices=["identity", "cycle_shift", "block_perm"])
    p.add_argument("--yoked-seed", type=int, default=0)
    p.add_argument("--fixed-intent", default="explore")
    p.add_argument("--rule-truth", action="store_true")
    p.add_argument("--state-source", default="oracle",
                   choices=["oracle", "observable"])
    p.add_argument("--direct", action="store_true")
    p.add_argument("--tau", type=float, default=None)
    p.add_argument("--eps", type=float, default=None)
    args = ap.parse_args()

    if args.cmd == "yoked":
        print(json.dumps(build_yoked(args.laya_run_dir, args.out_dir,
                                     args.mode, args.k, args.seed), indent=1))
    elif args.cmd == "verify":
        v = verify_run(args.run_dir, expected_frames=args.frames)
        print(json.dumps({k: v[k] for k in ("ok", "problems")}, indent=1))
        sys.exit(0 if v["ok"] else 1)
    elif args.cmd == "plan":
        for key in plan_matrix(args.scenes, args.policies, args.seeds):
            print("/".join(map(str, key)))
    elif args.cmd == "run":
        _run_cli(args)


if __name__ == "__main__":
    main()
