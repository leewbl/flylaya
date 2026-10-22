"""m5/test_metrics.py — W4 acceptance: metric formula unit samples with
hand-computed cases (design §7; TASK-0012 deliverable 4).

Run: python m5/test_metrics.py   (exit 0 = all pass)
No pytest dependency; plain asserts so the 16GB box can run it anywhere.
Coordinate convention (matches metrics.py contract): pos_m = [x, y, z] with
x/y horizontal, z height; yaw_deg is the math heading of h_xy.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import metrics as M  # noqa: E402


def approx(a, b, tol=1e-9):
    return a is not None and b is not None and abs(a - b) <= tol


# ---------------------------------------------------------------- helpers
def mkrun(frames, scene=None, decisions=None, events=None, meta=None):
    return {"meta": meta or {"scene_id": "T", "seed": 1, "policy": "P",
                             "coupling": "sensory_only", "brain": "skeleton",
                             "dt_s": 0.1},
            "frames": frames, "decisions": decisions or [], "events": events or [],
            "scene": scene, "dir": "/synthetic"}


def fr(t, x=0.0, y=0.0, z=0.0, yaw=0.0, speed=0.1, gap=0.5, intent="explore",
       arousal=1.0, dn=None, bias=0.0, stim=()):
    return {"t_s": t, "pos_m": [x, y, z], "yaw_deg": yaw, "speed_m_s": speed,
            "min_gap_m": gap, "intent_raw": intent, "intent_applied": intent,
            "arousal": arousal, "yaw_bias_direct": bias,
            "gains_pre": {}, "gains_post": {},
            "dn": dn if dn is not None else {n: 10.0 for n in M.DN_LR},
            "stim": list(stim)}


# ================================================================ light
def test_mean_cos_to_light():
    # HAND: yaw 0° → heading (1,0). light az 0° → target (1,0): cos=1.
    #       az 90° → target (0,1): cos=0. az 180° → target (−1,0): cos=−1.
    # mean over the three = (1+0−1)/3 = 0.
    scene = {"light": {"mode": "directional", "azimuth_deg": 0.0}}
    run = mkrun([fr(0.0, yaw=0), fr(0.1, yaw=90), fr(0.2, yaw=180)], scene)
    m = M.light_metrics(run)
    assert approx(m["mean_cos_to_light"], 0.0, 1e-12), m
    # az 90°, yaws 0/90/180 → cos = 0/1/0 → mean = 1/3  (HAND: 0.3333…)
    scene90 = {"light": {"mode": "directional", "azimuth_deg": 90.0}}
    run90 = mkrun([fr(0.0, yaw=0), fr(0.1, yaw=90), fr(0.2, yaw=180)], scene90)
    m90 = M.light_metrics(run90)
    assert approx(m90["mean_cos_to_light"], 1.0 / 3.0, 1e-12), m90
    print("ok mean_cos_to_light (hand: 0 and 1/3)")


def test_displacement_toward_target():
    # HAND: horizontal displacement (0.3, 0.4); target az = atan2(0.8, 0.6)
    # ≈ 53.13°; projection = 0.3*0.6 + 0.4*0.8 = 0.5
    az = math.degrees(math.atan2(0.8, 0.6))
    scene = {"light": {"mode": "directional", "azimuth_deg": az}}
    run = mkrun([fr(0.0), fr(1.0, x=0.3, y=0.4)], scene)
    m = M.light_metrics(run)
    assert approx(m["displacement_toward_target_m"], 0.5, 1e-9), m
    assert approx(m["net_displacement_m"], 0.5, 1e-9), m
    print("ok displacement_toward_target (hand: 0.5 m)")


def test_sun_R_paired_with_direction():
    # HAND: sun-relative angles [0°, 0°, 180°] → resultant = (2−1)/3 = 1/3,
    # mean direction 0°.
    scene = {"light": {"mode": "directional", "azimuth_deg": 0.0}}
    run = mkrun([fr(0.0, yaw=0), fr(0.1, yaw=0), fr(0.2, yaw=180)], scene)
    m = M.light_metrics(run)
    r = m["sun_R_with_mean_dir"]
    assert approx(r["R"], 1.0 / 3.0, 1e-9), r
    assert abs(r["mean_dir_deg"]) < 1e-6, r
    print("ok sun_R co-report (hand: R=1/3, dir=0°)")


def test_first_correct_turn_latency():
    # stimulus_on at t=5; heading error starts 60° (az 60, yaw 0);
    # reaches ≤45° (−15°) at t=5.4 (yaw 15) → latency 0.4 s (HAND)
    scene = {"light": {"mode": "directional", "azimuth_deg": 60.0}}
    frames = [fr(t, yaw=0.0 if t < 5.4 else 15.0) for t in
              [4.8, 4.9, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5]]
    events = [{"t_s": 5.0, "kind": "stimulus_on", "target": "light",
               "detector": M.EVENTS_VERSION}]
    run = mkrun(frames, scene, events=events)
    m = M.light_metrics(run)
    assert approx(m["first_correct_turn_latency_s"], 0.4, 1e-9), m
    print("ok first_correct_turn_latency (hand: 0.4 s)")


# ============================================================ avoidance
def test_contact_rate_and_denominator():
    # HAND: 2 valid approaches, 1 contact → rate 0.5; zero approaches → None
    events = [
        {"t_s": 1.0, "kind": "approach_start", "target": "o1", "bearing_deg": 30.0,
         "detector": M.EVENTS_VERSION},
        {"t_s": 2.0, "kind": "contact", "target": "o1", "detector": M.EVENTS_VERSION},
        {"t_s": 2.5, "kind": "approach_end", "detector": M.EVENTS_VERSION},
        {"t_s": 4.0, "kind": "approach_start", "target": "o1", "bearing_deg": -10.0,
         "detector": M.EVENTS_VERSION},
        {"t_s": 5.0, "kind": "approach_end", "detector": M.EVENTS_VERSION},
    ]
    frames = [fr(t, gap=0.05 if 1.0 <= t <= 2.5 else 0.2) for t in
              [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 4.5, 5.0]]
    run = mkrun(frames, events=events)
    m = M.avoidance_metrics(run)
    assert m["n_valid_approaches"] == 2
    assert m["n_contact"] == 1
    assert approx(m["contact_rate"], 0.5), m
    empty = M.avoidance_metrics(mkrun([fr(0.0), fr(0.1)]))
    assert empty["n_valid_approaches"] == 0 and empty["contact_rate"] is None
    print("ok contact_rate (hand: 0.5; empty denominator = None)")


def test_correct_turn_away():
    # HAND: obstacle bearing +30° (left of heading); yaw change −40° (right)
    # → turned opposite side → correct=True. Same sign → False.
    events = [
        {"t_s": 1.0, "kind": "approach_start", "target": "o1", "bearing_deg": 30.0,
         "detector": M.EVENTS_VERSION},
        {"t_s": 2.0, "kind": "approach_end", "detector": M.EVENTS_VERSION},
    ]
    frames = [fr(1.0, yaw=0.0), fr(1.5, yaw=-20.0), fr(2.0, yaw=-40.0)]
    m = M.avoidance_metrics(mkrun(frames, events=events))
    assert m["approaches"][0]["turned_away_correctly"] is True, m
    frames_same = [fr(1.0, yaw=0.0), fr(1.5, yaw=20.0), fr(2.0, yaw=40.0)]
    m2 = M.avoidance_metrics(mkrun(frames_same, events=events))
    assert m2["approaches"][0]["turned_away_correctly"] is False, m2
    print("ok correct_turn_away (hand: opposite sign true / same sign false)")


def test_reaction_latency():
    # HAND: approach_start t=2.0; turn_start t=2.4 → 0.4 s
    events = [
        {"t_s": 2.0, "kind": "approach_start", "target": "o1", "bearing_deg": 0.0,
         "detector": M.EVENTS_VERSION},
        {"t_s": 2.4, "kind": "turn_start", "sign": -1, "detector": M.EVENTS_VERSION},
        {"t_s": 2.6, "kind": "turn_end", "detector": M.EVENTS_VERSION},
        {"t_s": 3.0, "kind": "approach_end", "detector": M.EVENTS_VERSION},
    ]
    frames = [fr(t) for t in [1.9, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0]]
    m = M.avoidance_metrics(mkrun(frames, events=events))
    assert approx(m["reaction_latency_s_p50"], 0.4, 1e-9), m
    print("ok reaction_latency (hand: 0.4 s)")


# ============================================================= decision
def test_switch_rate_and_shares():
    # HAND: intents e,e,a,a,e over 0.0..1.2 s (dt 0.3) → 2 switches / 1.2 s
    # = 1.6667 Hz; shares e=0.6 a=0.4; dwells 0.6, 0.6, 0.0 → mean 0.4 s
    frames = [fr(0.0, intent="explore"), fr(0.3, intent="explore"),
              fr(0.6, intent="avoid_obstacle"), fr(0.9, intent="avoid_obstacle"),
              fr(1.2, intent="explore")]
    m = M.decision_metrics(mkrun(frames))
    assert approx(m["switch_rate_hz"], 2 / 1.2, 1e-9), m
    assert approx(m["class_shares"]["explore"], 0.6) and \
        approx(m["class_shares"]["avoid_obstacle"], 0.4), m
    assert approx(m["mean_dwell_s"], 0.4, 1e-9), m
    print("ok switch/shares/dwell (hand: 1.667 Hz, 0.6/0.4, 0.4 s)")


def test_conditional_hit_and_rear_fp():
    # Frontal obstacle o1 (frontal=True, rear=False), stim-tagged at t=0.3/0.6
    # with applied avoid → HAND: hit = 2/2 = 1.0.
    # Rear negative-control obstacle o2 (rear=True, frontal=False), stim-tagged
    # at t=0.9 (avoid) and t=1.2 (explore) → HAND: FP = 1/2 = 0.5.
    scene = {"obstacles": [
        {"id": "o1", "center_xy_m": [0.6, 0.0], "radius_m": 0.04,
         "frontal": True, "rear": False, "enabled": True},
        {"id": "o2", "center_xy_m": [0.4, 0.0], "radius_m": 0.04,
         "frontal": False, "rear": True, "enabled": True}]}
    frames = [fr(0.0, intent="explore"),
              fr(0.3, intent="avoid_obstacle", stim=("obstacle_o1",)),
              fr(0.6, intent="avoid_obstacle", stim=("obstacle_o1",)),
              fr(0.9, intent="avoid_obstacle", stim=("obstacle_o2",)),
              fr(1.2, intent="explore", stim=("obstacle_o2",))]
    m = M.decision_metrics(mkrun(frames, scene))
    assert m["hit_avoid_given_frontal_obstacle"] == {"n": 2, "rate": 1.0}, m
    assert m["false_avoid_given_rear_obstacle"] == {"n": 2, "rate": 0.5}, m
    print("ok conditional hit / rear FP (hand: 1.0 / 0.5)")


# =============================================================== neural
def test_dn_sign_consistency():
    # HAND: turn sign +1 at t=1.0; DN asymmetry R−L shifts +4 in the post
    # window → sign(DN)==sign(turn) → consistency 1.0.
    def dnfr(t, asym, yaw):
        dn = {n: 10.0 for n in M.DN_LR}
        dn["DNp20_L"] = 10.0 - asym / 2
        dn["DNp20_R"] = 10.0 + asym / 2
        return fr(t, yaw=yaw, dn=dn)

    frames = ([dnfr(t, 0.0, 0.0) for t in [0.6, 0.7, 0.8, 0.9]] +
              [dnfr(t, 4.0, 5.0 * (t - 1.0)) for t in [1.0, 1.1, 1.2, 1.3]])
    events = [{"t_s": 1.0, "kind": "turn_start", "sign": 1,
               "detector": M.EVENTS_VERSION}]
    m = M.neural_metrics(mkrun(frames, events=events))
    assert approx(m["dn_turn_sign_consistency"], 1.0), m
    print("ok dn_turn_sign_consistency (hand: 1.0)")


def test_direct_path_share():
    # HAND: one approach window 1.0→2.0 (10 steps × 0.1 s). yaw step 3.6° →
    # total |Δyaw| = 36°; direct bias 30°/s × 1.0 s = 30° → share = 30/36.
    events = [{"t_s": 1.0, "kind": "approach_start", "target": "o1",
               "bearing_deg": 0.0, "detector": M.EVENTS_VERSION},
              {"t_s": 2.0, "kind": "approach_end", "detector": M.EVENTS_VERSION}]
    ts = [round(0.1 * i, 1) for i in range(10, 21)]
    frames = [fr(t, yaw=3.6 * (i - 10), bias=math.radians(30.0))
              for i, t in enumerate(ts)]
    m = M.neural_metrics(mkrun(frames, events=events))
    assert approx(m["direct_path_yaw_share_in_approach"], 30.0 / 36.0, 1e-6), m
    print("ok direct_path_yaw_share (hand: 30/36 = 0.8333)")


# =============================================================== flight
def test_hf_gate():
    # 10 Hz frames: turn duration/peak MUST be suppressed even with turns.
    events = [{"t_s": 1.0, "kind": "turn_start", "sign": 1,
               "detector": M.EVENTS_VERSION},
              {"t_s": 1.2, "kind": "turn_end", "detector": M.EVENTS_VERSION}]
    ts = [round(0.1 * i, 1) for i in range(31)]
    frames = [fr(t, yaw=(60.0 if 1.0 < t <= 1.2 else 0.0)) for t in ts]
    m = M.flight_metrics(mkrun(frames, events=events))
    assert m["high_freq_gate"] is False
    assert m["turn_duration_s_p50"] is None and m["turn_peak_dps_p50"] is None
    assert "gate_note" in m
    # 100 Hz frames: duration/peak allowed; duration = 0.2 s (HAND)
    ts2 = [round(0.01 * i, 3) for i in range(301)]
    frames2 = [fr(t, yaw=(60.0 if 1.0 < t <= 1.2 else 0.0)) for t in ts2]
    m2 = M.flight_metrics(mkrun(frames2, events=events))
    assert m2["high_freq_gate"] is True
    assert approx(m2["turn_duration_s_p50"], 0.2, 1e-6), m2
    assert m2["turn_peak_dps_p50"] is not None and m2["turn_peak_dps_p50"] > 0
    print("ok hf gate (10Hz suppressed / 100Hz reports duration 0.2 s)")


# =========================================================== statistics
def test_paired_bootstrap_ci():
    # HAND: all diffs equal 0.10 → degenerate bootstrap: CI collapses to 0.10
    diffs = {"S1L": [0.10, 0.10], "S1R": [0.10, 0.10]}
    ci = M.stratified_bootstrap_ci(diffs, n_boot=100, rng_seed=1)
    assert approx(ci["point"], 0.10) and approx(ci["lo"], 0.10) and approx(ci["hi"], 0.10)
    # mixed: S1L [0.2, 0.2], S1R [0.0, 0.0] → point 0.1, CI straddles
    ci2 = M.stratified_bootstrap_ci({"S1L": [0.2, 0.2], "S1R": [0.0, 0.0]},
                                    n_boot=1000, rng_seed=1)
    assert approx(ci2["point"], 0.1) and ci2["lo"] <= 0.1 <= ci2["hi"]
    assert ci2["n_seeds"] == 4 and ci2["n_scenes"] == 2
    print("ok stratified bootstrap (hand: degenerate CI collapses to point)")


def test_h1_verdict_logic():
    def run_with(cos):
        return {"light": {"mean_cos_to_light": cos}, "frames": [], "scene": None,
                "meta": {}, "decisions": [], "events": [], "dir": "/s"}

    # HAND: diffs = 0.3 on both mirrors ≥ 0.15, degenerate CI > 0 → pass
    strong = {"S1_light_left": {("S1_light_left", 1): (run_with(0.5), run_with(0.2)),
                                ("S1_light_left", 2): (run_with(0.6), run_with(0.3))},
              "S1_light_right": {("S1_light_right", 1): (run_with(0.55), run_with(0.25)),
                                 ("S1_light_right", 2): (run_with(0.65), run_with(0.35))}}
    v = M.h1_verdict(strong)
    assert v["H1_pass"] is True, v
    assert v["per_mirror"]["S1_light_left"]["mean_paired_diff"] == 0.3
    # HAND: right mirror diffs 0.02/0.04 < 0.15 → that mirror fails → H1 fail
    weak = {"S1_light_left": strong["S1_light_left"],
            "S1_light_right": {("S1_light_right", 1): (run_with(0.22), run_with(0.2)),
                               ("S1_light_right", 2): (run_with(0.24), run_with(0.2))}}
    v2 = M.h1_verdict(weak)
    assert v2["H1_pass"] is False, v2
    print("ok H1 verdict (both-mirror rule; weak mirror fails)")


def test_h2_verdict_and_empty_denominator():
    def av_run(napp, ncon):
        return {"avoidance": {"n_valid_approaches": napp, "n_contact": ncon}}

    # HAND: laya 2/20 vs yoked 10/20 → RR 0.2, reduction 0.8 ≥ 0.25
    pairs = {("S2_obstacle_left", 1): (av_run(20, 2), av_run(20, 10)),
             ("S2_obstacle_right", 1): (av_run(20, 2), av_run(20, 10))}
    v = M.h2_verdict(pairs)
    assert approx(v["risk_ratio_point"], 0.2), v
    assert approx(v["reduction"], 0.8), v
    assert v["H2_pass"] in (True, False)  # CI from bootstrap; point passes
    # empty denominators: excluded, never success
    empty = {("S2_obstacle_rear", 1): (av_run(0, 0), av_run(0, 0))}
    v2 = M.h2_verdict(empty)
    assert v2["H2_pass"] is False and "no_seed_with_valid" in v2["reason"]
    print("ok H2 verdict (hand RR 0.2/red 0.8; empty denom → explicit failure)")


def test_yoked_match_check():
    # laya: perfect alternation [e,a]*100 at 0.5 s frame dwell → shares
    # 0.5/0.5, mean dwell 0.5 s.
    # ok: alternation + 4 extra explore → HAND: 102 e / 98 a of 200 → share
    # diff 0.01 per class (≤0.02 pass); dwell ≈0.5153 s → rel 3.1% ≤10% pass.
    # bad: pure alternation at 0.575 s → dwell rel 15% → pair fails.
    def seq_run(intents, dwell):
        return mkrun([fr(round(i * dwell, 3), intent=s) for i, s in enumerate(intents)])

    laya = seq_run(["explore", "avoid_obstacle"] * 100, 0.5)
    ok = seq_run(["explore", "avoid_obstacle"] * 98 + ["explore"] * 4, 0.5)
    c = M.yoked_match_check(laya, ok)
    assert approx(max(c["class_share_abs_diff"].values()), 0.01, 1e-9), c
    assert c["pass"] is True, c
    bad = seq_run(["explore", "avoid_obstacle"] * 100, 0.575)
    c2 = M.yoked_match_check(laya, bad)
    assert c2["dwell_rel_diff"] > 0.10 and c2["pass"] is False, c2
    print("ok yoked match (hand: share diff 0.01 pass / dwell 15% fail)")


# =============================================================== sealing
def test_seed_sealing_roundtrip():
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "sealed.json")
        body = M.seal_seeds(20, path, rng_seed=42)
        assert len(body["seeds"]) == 20 and len(set(body["seeds"])) == 20
        v = M.verify_seals(path)
        assert v["intact"] is True and v["usable_for_confirmation"] is True
        # exploration run overlapping a sealed seed must fail verification
        exp = os.path.join(tmp, "explore", "run1")
        os.makedirs(exp)
        with open(os.path.join(exp, "trajectory.jsonl"), "w") as f:
            f.write(json.dumps({"type": "meta", "seed": body["seeds"][0]}) + "\n")
        v2 = M.verify_seals(path, [exp])
        assert v2["usable_for_confirmation"] is False and v2["overlaps_with_exploration"]
        # mutation must break integrity
        doc2 = dict(body, seeds=body["seeds"][:-1] + [999999999])
        p2 = os.path.join(tmp, "mutated.json")
        json.dump(doc2, open(p2, "w"))
        assert M.verify_seals(p2)["intact"] is False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ok seed sealing (roundtrip / overlap / mutation detection)")


# ======================================================= detector + CLI
def test_detector_approach():
    # obstacle dead ahead (center x=0.6, r=0.04), fly at yaw 0.
    # slow: x step 1 mm per 0.1 s → closing 0.01 m/s < 0.02 → NO approach.
    # fast: x step 3 cm per 0.1 s → closing 0.3 ≥ 0.02, first qualifying
    # frame x=0.53 → HAND dist = |0.6−0.53| − 0.04 = 0.03 m.
    scene = {"obstacles": [{"id": "o1", "center_xy_m": [0.6, 0.0],
                            "radius_m": 0.04, "enabled": True}]}
    slow = [fr(round(0.1 * i, 1), x=0.5 + 0.001 * i) for i in range(5)]
    assert not any(e["kind"] == "approach_start" for e in M.detect_events(slow, scene))
    fast = [fr(round(0.1 * i, 1), x=0.5 + 0.03 * i) for i in range(5)]
    starts = [e for e in M.detect_events(fast, scene) if e["kind"] == "approach_start"]
    assert len(starts) == 1 and starts[0]["target"] == "o1", starts
    assert approx(starts[0]["dist_m"], 0.03, 1e-6), starts
    print("ok detector v1 (closing gate + hand distance 0.03 m)")


def test_run_cli_end_to_end():
    # contract run dir → CLI `run` → metrics.json
    tmp = tempfile.mkdtemp()
    try:
        rd = os.path.join(tmp, "S1_light_left", "P_laya", "1")
        os.makedirs(rd)
        scene = {"light": {"mode": "directional", "azimuth_deg": 0.0}}
        with open(os.path.join(rd, "scene.json"), "w") as f:
            json.dump(scene, f)
        with open(os.path.join(rd, "trajectory.jsonl"), "w") as f:
            f.write(json.dumps({"type": "meta", "schema": "flylaya.m5.traj.v1",
                                "scene_id": "S1_light_left", "seed": 1,
                                "policy": "P_laya", "coupling": "sensory_only",
                                "brain": "skeleton", "dt_s": 0.1}) + "\n")
            for i in range(30):
                f.write(json.dumps(fr(round(0.1 * i, 1), yaw=10.0 * i)) + "\n")
        run = M.load_run(rd)
        m = M.run_metrics(run)
        assert m["meta"]["scene_id"] == "S1_light_left"
        assert m["light"]["mean_cos_to_light"] is not None
        r = subprocess.run([sys.executable, os.path.join(HERE, "metrics.py"),
                            "run", rd], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert os.path.exists(os.path.join(rd, "metrics.json"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ok CLI end-to-end (contract dir → metrics.json)")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
