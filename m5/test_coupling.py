"""Self-test for TASK-0010 (M5-W2): dual state source + three-pathway gating.

G2 acceptance (design §9): sensory_only has no motor shortcut, motor_only
does not touch the sensory gains, direct is default-off; state source and
DN provenance are auditable; no silent fallback. Plus the policy-group
implementations (P_laya raw-vs-sampled, P_yoked tolerance validation,
P_rule both modes, P_fixed).

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python m5/test_coupling.py
"""
import copy
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "m5", "scenes"))

from flylaya import intent as I
from flylaya.brains import make_brain
from flylaya.world import World

FAIL = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAIL.append(name)


# ---------------------------------------------------------------- coupling
full = I.modulation_for("phototaxis", 2, "full")
so = I.modulation_for("phototaxis", 2, "sensory_only")
mo = I.modulation_for("phototaxis", 2, "motor_only")
check("sensory_only: no motor shortcut (thrust 1.0, yaw_noise 0, no arousal scale)",
      so["thrust"] == 1.0 and so["yaw_noise"] == 0.0 and so["arousal"] == 2)
check("sensory_only: sensory gains intact",
      (so["light"], so["looming"], so["wall"]) == (2.0, 0.6, 0.5))
check("motor_only: sensory gains neutralized",
      mo["light"] == mo["looming"] == mo["wall"] == 1.0)
check("motor_only: motor path active with arousal scale",
      mo["thrust"] == 1.1 * I.arousal_thrust_scale(2) and mo["yaw_noise"] == 0.8)
check("full: legacy M2 values preserved",
      full["thrust"] == 1.1 * I.arousal_thrust_scale(2) and full["light"] == 2.0
      and full["yaw_noise"] == 0.8)
dflt = I.modulation_for("explore", 1)
check("default coupling is full and equals legacy formula",
      dflt["coupling"] == "full" and dflt["thrust"] == 1.0 * I.arousal_thrust_scale(1)
      and dflt["light"] == 1.0 and dflt["yaw_noise"] == 1.5)
row = I.audit_row(so, 1.5, 3.0)
check("audit row carries source paths, values, times",
      row["source_paths"] == {"sensory": True, "motor": False}
      and row["t_start_s"] == 1.5 and row["t_end_s"] == 3.0
      and row["intent_gains"]["thrust"] == 1.0)
row_mo = I.audit_row(mo, 0.0)
check("audit row: motor_only flags motor-only paths",
      row_mo["source_paths"] == {"sensory": False, "motor": True})

# ---------------------------------------------------------------- direct
os.environ.pop("FLYLAYA_DIRECT", None)
src = I.LayaIntentSource(every_frames=1, rng_seed=1)
check("direct pathway default off", src.direct is False)
w2 = World.from_scene(os.path.join(ROOT, "m5", "scenes", "S2_obstacle_left.json"), seed=1)
w2.advance_clock(5.0)
w2.pos = np.array([0.45, 0.42, 0.5])  # ~7 cm from the column, in path
src_direct = I.LayaIntentSource(every_frames=1, rng_seed=1, direct=True)
src_direct._arm_escape(w2)
check("direct on: escape bias armed and consumed",
      src_direct.consume_yaw_bias() != 0.0)
src._arm_escape(w2)  # default-off source: _arm_escape is inert via poll gating
check("direct off: consume_yaw_bias stays zero after arming attempt via poll path",
      all(src.consume_yaw_bias() == 0.0 for _ in range(6)))

# ------------------------------------------------- observable vs oracle
class _FrozenTime:
    @staticmethod
    def time():
        return 1_000_000.0
_real_time = I.time
I.time = _FrozenTime  # freeze dwell text for exact comparison
try:
    w = World(seed=5)
    b = make_brain("skeleton", seed=5)
    w.render_luminance()
    oracle1 = I.state_text(w, "explore", w and 999_999.0, False)
    sum1, obs1 = I.observable_state(w, b, "explore", 999_999.0)
    # corrupt every ground-truth channel the oracle reads
    w.obstacles = np.array([[0.5, 0.5, 0.06, 0.9]] * 7)
    w.sun = np.array([0.0, 0.99, 0.1])
    w.pos = np.array([0.1, 0.9, 0.2])
    oracle2 = I.state_text(w, "explore", 999_999.0, False)
    sum2, obs2 = I.observable_state(w, b, "explore", 999_999.0)
    check("oracle state reads ground truth (changes with it)", oracle1 != oracle2)
    check("observable state is blind to ground-truth corruption",
          obs1 == obs2 and sum1 == sum2)
    check("observable summary keys == OBS_FIELDS provenance registry",
          set(sum1) == set(I.OBS_FIELDS))
    check("every observable field declares source + latency",
          all(set(v) >= {"source", "latency_s"} for v in I.OBS_FIELDS.values()))
    check("observable text contains no obstacle/sun/zone truth tokens",
          not any(tok in obs1 for tok in
                  ["obstacle ahead", "sun ", "cm)", "zone", "wall", "bearing"]))
finally:
    I.time = _real_time

# ------------------------------------------------- decisions contract
def fake_post_factory(probs, arousal=1):
    resp = {"answers": {"intent": {"choice": max(probs, key=probs.get),
                                   "probabilities": probs, "confidence": 0.9},
                        "arousal": {"score": arousal}}}
    return lambda payload: resp

src = I.LayaIntentSource(every_frames=1, rng_seed=7, eps=1.0, tau=1.0)
src._post = fake_post_factory({"phototaxis": 0.998, "explore": 0.001,
                               "avoid_obstacle": 0.0003, "center_in_arena": 0.0003,
                               "rest_hover": 0.0004})
src.intent_since = time.time() - 10
w = World(seed=5)
b = make_brain("skeleton", seed=5)
src.poll(0, w, b)
d = src.last_decision
need = {"t_s", "state_source", "state_text_sha256", "raw_choice",
        "raw_probabilities", "sampled", "applied", "dwell_guard",
        "arousal_score", "latency_ms", "timeout", "fallback_reason"}
check("decisions contract fields present", set(d) >= need, str(sorted(d)))
check("raw argmax recorded separately from eps-sampled pick",
      d["raw_choice"] == "phototaxis" and d["sampled"] == "explore"
      and d["applied"] == "explore")
check("sha256 matches state text", d["state_text_sha256"] ==
      __import__("hashlib").sha256(src.last_state_text.encode()).hexdigest())

# failover: no silent fallback
class Boom(Exception):
    pass
src2 = I.LayaIntentSource(every_frames=1, rng_seed=7)
src2._post = lambda payload: (_ for _ in ()).throw(Boom("timeout"))
for f in range(3):
    src2.poll(f, w, b)
check("3 consecutive errors -> rest_hover with recorded reason",
      src2.last_intent == "rest_hover"
      and src2.last_decision["fallback_reason"] == "consecutive_failures"
      and src2.last_decision["timeout"] is False)

# ---------------------------------------------------------------- yoked
seq = [{"t_s": round(0.3 * k, 3), "intent": I.INTENTS[k % 5],
        "arousal": 1 + (k % 2)} for k in range(60)]
cyc = I.permute_sequence(seq, mode="cycle_shift", k=7)
blk = I.permute_sequence(seq, mode="block_perm", block_s=5.0, seed=1)
check("permutations keep the exact t_s grid",
      [s["t_s"] for s in cyc] == [s["t_s"] for s in seq]
      and [s["t_s"] for s in blk] == [s["t_s"] for s in seq])
check("permutations preserve the intent multiset exactly",
      sorted(s["intent"] for s in cyc) == sorted(s["intent"] for s in seq)
      and sorted(s["intent"] for s in blk) == sorted(s["intent"] for s in seq))
rep_id = I.validate_yoked(seq, seq)
rep_cyc = I.validate_yoked(seq, cyc)
rep_blk = I.validate_yoked(seq, blk)
check("yoked tolerance: identity/cycle/block all pass",
      rep_id["ok"] and rep_cyc["ok"] and rep_blk["ok"],
      f"share={rep_blk['max_share_diff']:.4f} dwell={rep_blk['dwell_rel_diff']:.4f}")
bad = [{"t_s": s["t_s"], "intent": "explore", "arousal": 1} for s in seq]
rep_bad = I.validate_yoked(seq, bad)
check("yoked tolerance: degenerate sequence rejected",
      not rep_bad["ok"], f"share_diff={rep_bad['max_share_diff']:.3f}")
yk = I.YokedIntentSource(seq, mode="block_perm", seed=2)
w.reset()
seen = [yk.poll(f, w, b)[0] for f in range(0, 180, 3)]
check("YokedIntentSource replays its sequence in sim time",
      len(set(seen)) > 1 and all(s in I.INTENTS for s in seen))
try:
    I.load_sequence([{"t_s": 1.0, "intent": "phototaxis"},
                     {"t_s": 1.0, "intent": "explore"}])
    check("load_sequence rejects non-increasing t_s", False)
except ValueError:
    check("load_sequence rejects non-increasing t_s", True)

# ---------------------------------------------------------------- rule / fixed
wr = World.from_scene(os.path.join(ROOT, "m5", "scenes", "S2_obstacle_left.json"), seed=1)
wr.advance_clock(5.0)
wr.pos = np.array([0.45, 0.42, 0.5])
rule_t = I.RuleIntentSource(use_truth=True)
check("P_rule truth mode: in-path column -> avoid_obstacle",
      rule_t.poll(0, wr, b)[0] == "avoid_obstacle")
wr.pos = np.array([0.05, 0.5, 0.5])
check("P_rule truth mode: near wall -> center_in_arena",
      rule_t.poll(1, wr, b)[0] == "center_in_arena")
wr.pos = np.array([0.5, 0.5, 0.5])
check("P_rule truth mode: open space -> explore",
      rule_t.poll(2, wr, b)[0] == "explore")
sens_rule = I.RuleIntentSource(use_truth=False)
out = sens_rule.poll(0, World(seed=2), b)[0]
check("P_rule sensory mode returns valid intents", out in I.INTENTS, out)
check("P_rule sensory branch rules behave",
      I.RuleIntentSource._rule_sensory({"frontal_dark_frac": 0.5,
                                        "front_dark_side": "left",
                                        "lateral_contrast": 0.9,
                                        "mean_brightness": 0.45}) == "avoid_obstacle"
      and I.RuleIntentSource._rule_sensory({"frontal_dark_frac": 0.0,
                                            "front_dark_side": "even",
                                            "lateral_contrast": 0.2,
                                            "mean_brightness": 0.45}) == "phototaxis"
      and I.RuleIntentSource._rule_sensory({"frontal_dark_frac": 0.0,
                                            "front_dark_side": "even",
                                            "lateral_contrast": 0.0,
                                            "mean_brightness": 0.12}) == "center_in_arena")
fg = I.FixedGoalSource("phototaxis")
check("P_fixed constant goal", fg.poll(0, wr, b) == ("phototaxis", 1.0))
try:
    I.FixedGoalSource("fly_to_moon")
    check("P_fixed rejects unknown intent", False)
except ValueError:
    check("P_fixed rejects unknown intent", True)

# ---------------------------------------------------------------- DN parity
sk = make_brain("skeleton", seed=1)
lum = np.full(3335, 0.4, np.float32)
sk.step(lum, 0.1)
check("SkeletonBrain.dn_snapshot parity with connectome contract",
      set(sk.dn_snapshot()) == set(sk.pools)
      and sk.dn_snapshot()["DNp20_R"] == round(sk.pools["DNp20_R"], 2))

# ------------------------------------------- skeleton light->DN sign (0017)
sk2 = make_brain("skeleton", seed=0)
lum_left = np.zeros(3335, np.float32)
lum_left[sk2.dirs[:, 1] > 0.25] = 0.9   # geometric LEFT bright
out_l = sk2.step(lum_left, 0.1)
sk2b = make_brain("skeleton", seed=0)
lum_right = np.zeros(3335, np.float32)
lum_right[sk2b.dirs[:, 1] < -0.25] = 0.9
out_r = sk2b.step(lum_right, 0.1)
check("skeleton sign: left-bright retina -> DNp20_R-L > 0 (turn-left command)",
      (out_l["DNp20_R"] - out_l["DNp20_L"]) > 0)
check("skeleton sign: right-bright retina -> DNp20_R-L < 0 (mirror)",
      (out_r["DNp20_R"] - out_r["DNp20_L"]) < 0)

# --------------------------------------------- vertical channel sign (0023)
sk3 = make_brain("skeleton", seed=0)
lum_up = np.full(3335, 0.3, np.float32)
lum_up[sk3.dirs[:, 2] > 0.3] = 0.95          # dorsal bright
out_up = sk3.step(lum_up, 0.1)
sk3b = make_brain("skeleton", seed=0)
lum_dn = np.full(3335, 0.3, np.float32)
lum_dn[sk3b.dirs[:, 2] < -0.3] = 0.95        # ventral bright
out_dn = sk3b.step(lum_dn, 0.1)
check("vertical sign: dorsal-bright -> DNa02_R-L > 0 (climb command)",
      (out_up["DNa02_R"] - out_up["DNa02_L"]) > 0)
check("vertical sign: ventral-bright -> DNa02_R-L < 0 (descend, mirror)",
      (out_dn["DNa02_R"] - out_dn["DNa02_L"]) < 0)


def _s1_z_spread(seconds=15.0):
    """S1 with a sun above must leave the start altitude (TASK-0023;
    pre-fix z stayed at 0.500 to four decimals)."""
    w = World.from_scene(os.path.join(ROOT, "m5", "scenes", "S1_light_left.json"),
                         seed=1)
    brain = make_brain("skeleton", seed=1)
    pol = I.FixedGoalSource("phototaxis")
    zs = []
    for f in range(int(seconds / 0.1)):
        w.advance_clock(f * 0.1)
        mod = I.modulation_for(pol.poll(f, w, brain)[0], 1, "sensory_only")
        rates = brain.step(w.render_luminance(mod), 0.1)
        w.step_motor(rates, 0.1, gains={"thrust": mod["thrust"]},
                     yaw_noise=mod["yaw_noise"], rng=w.rng)
        zs.append(float(w.pos[2]))
    return float(np.std(zs)), max(zs) - min(zs)


_zstd, _zrange = _s1_z_spread()
check("z unpin: S1 skeleton leaves start altitude (std>0.05, range>0.15)",
      _zstd > 0.05 and _zrange > 0.15, f"std={_zstd:.3f} range={_zrange:.3f}")


def _s1_toward_light(scene, seconds=15.0):
    """Both S1 mirrors under sensory_only + fixed phototaxis: the heading
    must move TOWARD the light (regression for the TASK-0017 sign fix;
    pre-fix behavior drifted +0.50 -> -0.84)."""
    w = World.from_scene(os.path.join(ROOT, "m5", "scenes", f"{scene}.json"),
                         seed=1)
    brain = make_brain("skeleton", seed=1)
    pol = I.FixedGoalSource("phototaxis")
    light_xy = w.sun[:2] / np.linalg.norm(w.sun[:2])
    c0, cs = None, []
    for f in range(int(seconds / 0.1)):
        w.advance_clock(f * 0.1)
        mod = I.modulation_for(pol.poll(f, w, brain)[0], 1, "sensory_only")
        rates = brain.step(w.render_luminance(mod), 0.1)
        w.step_motor(rates, 0.1, gains={"thrust": mod["thrust"]},
                     yaw_noise=mod["yaw_noise"], rng=w.rng)
        if w.light_on:
            h = w._heading()[:2]
            c = float(h @ light_xy)
            c0 = c if c0 is None else c0
            cs.append(c)
    return c0, float(np.mean(cs[-50:]))


for _scene in ("S1_light_left", "S1_light_right"):
    _c0, _c1 = _s1_toward_light(_scene)
    check(f"{_scene}: heading turns TOWARD the light (sensory_only)",
          _c1 > _c0 and _c1 > 0.8, f"{_c0:+.3f} -> {_c1:+.3f}")

print()
if FAIL:
    print(f"FAILED: {len(FAIL)} -> {FAIL}")
    sys.exit(1)
print("ALL PASS")
