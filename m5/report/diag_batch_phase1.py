"""TASK-0013 phase-1 diagnostic batch: S0-S3 x P_fixed x {connectome,skeleton}
x {sensory_only,motor_only}, 30 s, seed 1, serial (16 GB safe).

Lays down contract runs under m5/runs_diag/<scene>/<brain>/<coupling>/ and
derives the per-scene transfer-function table (pre/post-stimulus DN asymmetry,
heading-to-target, approach/turn events) into m5/report/diag-phase1.md.
No Laya calls — this batch makes NO Laya-superiority claims (design §5.2).
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))
import metrics as M  # noqa: E402

PY = sys.executable
SCENES = [
    ("S0_neutral", "explore"),
    ("S1_light_left", "phototaxis"),
    ("S1_light_right", "phototaxis"),
    ("S2_obstacle_left", "avoid_obstacle"),
    ("S2_obstacle_right", "avoid_obstacle"),
    ("S2_obstacle_rear_negctrl", "avoid_obstacle"),
    ("S3_wall", "center_in_arena"),
]
T_STIM = 5.0


def run_matrix():
    for scene, intent in SCENES:
        for brain in ("skeleton", "connectome"):
            for cp in ("sensory_only", "motor_only"):
                out = os.path.join(ROOT, "m5", "runs_diag", scene, brain, cp)
                r = subprocess.run(
                    [PY, os.path.join(HERE, "..", "runner.py"), "run",
                     "--scene", os.path.join(ROOT, "m5", "scenes", f"{scene}.json"),
                     "--seed", "1", "--policy", "P_fixed", "--coupling", cp,
                     "--brain", brain, "--out", out,
                     "--experiment-id", "m5-diag-phase1", "--seconds", "30",
                     "--fixed-intent", intent],
                    capture_output=True, text=True)
                ok = r.returncode == 0
                print(f"{scene}/{brain}/{cp}: {'OK' if ok else 'FAIL ' + r.stderr[-200:]}",
                      flush=True)
                if not ok:
                    raise SystemExit(1)


def _dn_asym(row):
    dn = row["dn"]
    return dn["DNp20_R"] - dn["DNp20_L"]


def transfer_row(scene, brain, cp):
    run_dir = os.path.join(ROOT, "m5", "runs_diag", scene, brain, cp)
    run = M.load_run(run_dir)
    frames = run["frames"]
    meta = run["meta"]
    scene_spec = run.get("scene") or {}
    pre = [f for f in frames if f["t_s"] < T_STIM]
    post = [f for f in frames if f["t_s"] >= T_STIM]
    dn_pre = float(np.mean([_dn_asym(f) for f in pre])) if pre else None
    dn_post = float(np.mean([_dn_asym(f) for f in post])) if post else None

    # heading-to-target: light azimuth for S1, obstacle bearing for S2,
    # arena center for S3/S0
    def cos_target(f):
        h = math.radians(f["yaw_deg"])
        hx, hz = math.cos(h), math.sin(h)
        if scene.startswith("S1"):
            az = math.radians(scene_spec["light"]["azimuth_deg"])
            tx, tz = math.cos(az), math.sin(az)
        elif scene.startswith("S2"):
            ob = scene_spec["obstacles"][0]
            dx = ob["center_xy_m"][0] - f["pos_m"][0]
            dz = ob["center_xy_m"][1] - f["pos_m"][1]
            n = math.hypot(dx, dz) or 1e-9
            tx, tz = -dx / n, -dz / n          # AWAY from obstacle (avoidance target)
        else:
            dx, dz = 0.5 - f["pos_m"][0], 0.5 - f["pos_m"][1]
            n = math.hypot(dx, dz) or 1e-9
            tx, tz = dx / n, dz / n            # toward arena center
        return hx * tx + hz * tz

    def _m(xs):
        xs = [x for x in xs if x is not None]
        return float(np.mean(xs)) if xs else None

    c_pre, c_post = _m([cos_target(f) for f in pre]), _m([cos_target(f) for f in post])
    ev = run_events_or_detect(run)
    turns = [e for e in ev if e["kind"] == "turn_start"]
    appr = [e for e in ev if e["kind"] == "approach_start"]
    m = M.run_metrics(run)
    av = m["avoidance"]
    return {"scene": scene, "brain": brain, "coupling": cp,
            "intent": meta.get("intent_hint", ""),
            "dn_asym_pre": dn_pre, "dn_asym_post": dn_post,
            "dn_delta": (dn_post - dn_pre) if dn_pre is not None and dn_post is not None else None,
            "cos_target_pre": c_pre, "cos_target_post": c_post,
            "cos_delta": (c_post - c_pre) if c_pre is not None and c_post is not None else None,
            "turns": len(turns), "approaches": av["n_valid_approaches"],
            "contacts": av["n_contact"],
            "turn_away_rate": av["correct_turn_away_rate"],
            "speed_p50": m["flight"]["speed_m_s_p50"]}


def run_events_or_detect(run):
    if run["events"]:
        return run["events"]
    return M.detect_events(run["frames"], run.get("scene"))


def main():
    if "--reuse" not in sys.argv:
        run_matrix()
    rows = [transfer_row(s, b, c) for s, _ in SCENES
            for b in ("skeleton", "connectome") for c in ("sensory_only", "motor_only")]
    out = os.path.join(HERE, "diag-phase1.md")
    with open(out, "w") as f:
        f.write("# M5 接口诊断批 阶段1 传递函数表\n\n"
                "P_fixed × S0–S3 × 双脑 × 双耦合 × 30s × seed1（m5/runs_diag/，"
                "manifest 齐、无 Laya 调用、不作 Laya 优势统计）。\n"
                "t_stim=5s（S1 光/S2 柱在 t=5 开启；S0/S3 无事件，pre/post 仅作"
                "漂移对照）。cos_target：S1 朝光源、S2 朝离开柱方向、S3/S0 朝场地中心。\n\n")
        f.write("| scene | brain | coupling | ΔDN(R−L) | Δcos_target | turns | appr | contact | turn_away | speed_p50 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['scene']} | {r['brain']} | {r['coupling']} | "
                    f"{r['dn_delta']:+.2f} ({r['dn_asym_pre']:+.2f}→{r['dn_asym_post']:+.2f}) | "
                    f"{r['cos_delta']:+.3f} ({r['cos_target_pre']:+.3f}→{r['cos_target_post']:+.3f}) | "
                    f"{r['turns']} | {r['approaches']} | {r['contacts']} | "
                    f"{r['turn_away_rate'] if r['turn_away_rate'] is not None else '-'} | "
                    f"{r['speed_p50']:.3f} |\n")
    json.dump(rows, open(os.path.join(HERE, "diag-phase1.json"), "w"), indent=1)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
