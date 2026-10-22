"""M2 intent layer — implements researcher's intent spec v1 exactly.

Spec: blackboard/findings/flylaya-intent-spec.md
- State encoding: structured English phrases (zone, obstacle bearing+range+
  closing, sun bearing+elevation+angle-to-heading, flight speed+climb,
  current intent + dwell, wall phrase, recent bump)
- Question set: 5 mutually exclusive behavioral intents + 3-level arousal
- Modulation table v1: light gain / looming sensitivity / wall repulsion /
  base thrust / yaw noise, arousal thrust scale x(0.6+0.25s)
- Call discipline: every 3 frames, 50ms timeout, 3 consecutive failures ->
  rest_hover, <1s intent flapping treated as jitter (keep previous)
- Logging: every call -> jsonl {state, intent, probabilities, latency}
"""
import hashlib
import json
import logging
import math
import os
import time

import numpy as np

INTENTS = ["phototaxis", "avoid_obstacle", "explore", "center_in_arena", "rest_hover"]

QUESTIONS = {
    "intent": {
        "type": "choice",
        "instructions": "Given the fly's sensory state, which behavioral goal should dominate the next few seconds?",
        "criteria": {
            "phototaxis": "steer toward the sun light, climb toward brightness",
            "avoid_obstacle": "an obstacle is close ahead, turning away takes priority",
            "explore": "cruise across open space, vary heading to sample the arena",
            "center_in_arena": "too close to a wall or corner, steer back toward open middle",
            "rest_hover": "reduce speed and hold position, low arousal",
        },
    },
    "arousal": {
        "type": "score",
        "instructions": "How aroused or active should the fly be right now?",
        "criteria": ["sluggish, nearly hovering", "moderate cruising",
                     "highly active, fast agile flight"],
    },
}

# spec §3 modulation table v1 (JSON-tunable) + v1.1 配套: rest_hover 贴墙不回中
MODULATION = {
    "phototaxis":     {"light": 2.0, "looming": 0.6, "wall": 0.5, "thrust": 1.1, "yaw_noise": 0.8},
    "avoid_obstacle": {"light": 0.3, "looming": 2.5, "wall": 0.6, "thrust": 0.9, "yaw_noise": 1.2},
    "explore":        {"light": 1.0, "looming": 1.0, "wall": 0.7, "thrust": 1.0, "yaw_noise": 1.5},
    "center_in_arena": {"light": 0.5, "looming": 0.5, "wall": 2.5, "thrust": 1.0, "yaw_noise": 0.5},
    "rest_hover":     {"light": 0.2, "looming": 0.3, "wall": 0.5, "thrust": 0.35, "yaw_noise": 0.4},
}


def arousal_thrust_scale(score_0_2):
    return 0.6 + 0.25 * float(np.clip(score_0_2, 0, 2))


_UNKNOWN_INTENT_WARNED = set()


COUPLINGS = ("full", "sensory_only", "motor_only")


def _default_coupling():
    c = os.environ.get("FLYLAYA_COUPLING", "full")
    if c not in COUPLINGS:
        logging.warning("FLYLAYA_COUPLING=%r unknown; using 'full'", c)
        return "full"
    return c


def modulation_for(intent, arousal, coupling=None):
    """Intent gains, gated by coupling mode (design §3.2, TASK-0010):

    - full: sensory (light/looming/wall) + motor (thrust/yaw_noise) as in M2
    - sensory_only: motor path neutralized (thrust 1.0, yaw_noise 0.0, no
      arousal thrust scale) — no motor shortcut can fake a pathway effect
    - motor_only: sensory path neutralized (light/looming/wall 1.0), motor
      path active
    The direct yaw path (escape bias) is separate and default-off; see
    LayaIntentSource(direct=...).
    """
    coupling = coupling or _default_coupling()
    if intent not in MODULATION and intent not in _UNKNOWN_INTENT_WARNED:
        _UNKNOWN_INTENT_WARNED.add(intent)
        logging.warning("modulation_for: unknown intent %r -> explore gains", intent)
    m = dict(MODULATION.get(intent, MODULATION["explore"]))
    if coupling == "sensory_only":
        m["thrust"] = 1.0
        m["yaw_noise"] = 0.0
    else:
        m["thrust"] = m["thrust"] * arousal_thrust_scale(arousal)
        if coupling == "motor_only":
            m["light"] = m["looming"] = m["wall"] = 1.0
    m["arousal"] = arousal
    m["coupling"] = coupling
    return m


def audit_row(mod, t_start_s, t_end_s=None):
    """Modulation audit record (design §3.2): every applied change carries
    its source_path, values and start/end time. The W3 runner emits one
    row per applied modulation segment; direct-path activity is recorded
    by the intent source itself."""
    coupling = mod.get("coupling", "full")
    paths = {"sensory": coupling in ("full", "sensory_only"),
             "motor": coupling in ("full", "motor_only")}
    return {"t_start_s": t_start_s, "t_end_s": t_end_s,
            "coupling": coupling, "intent_gains": {
                "light": mod.get("light"), "looming": mod.get("looming"),
                "wall": mod.get("wall"), "thrust": mod.get("thrust"),
                "yaw_noise": mod.get("yaw_noise")},
            "arousal": mod.get("arousal"), "source_paths": paths}


# ---------------------------------------------------------------- state text
def _where_phrase(bearing_rad):
    """Spec v1.1 aheadness: 'ahead 30 deg left, in the flight path' /
    'abeam right, off the flight path' / 'behind, not in the flight path'."""
    deg = math.degrees(bearing_rad)
    side = "left" if deg > 0 else "right"
    a = abs(deg)
    if a < 45:
        d = f" {a:.0f} deg {side}" if a > 3 else ""
        return f"ahead{d}, in the flight path"
    if a <= 90:
        return f"abeam {side}, off the flight path"
    return "behind, not in the flight path"


def _in_flight_path(bearing_rad):
    return abs(math.degrees(bearing_rad)) < 45


def _phrase_bearing(angle_rad):
    """Degrees + quadrant phrase per spec: '30 deg left ahead'."""
    deg = math.degrees(angle_rad)
    side = "left" if deg > 0 else "right"
    deg = abs(deg)
    zone = ("ahead" if deg < 45 else "behind" if deg > 135 else "to the side")
    return f"{deg:.0f} deg {side} {zone}" if deg > 3 else "straight ahead"


def _range_bin(cm):
    return "near" if cm < 15 else "mid" if cm < 40 else "far"


def state_text(world, last_intent, intent_since, recent_bump):
    pos = world.pos
    x_bin = "left" if pos[0] < 0.33 else "right" if pos[0] > 0.66 else "center"
    y_bin = "front" if pos[1] < 0.33 else "back" if pos[1] > 0.66 else "center"
    z_bin = "low" if pos[2] < 0.33 else "high" if pos[2] > 0.66 else "mid"
    heading = world._heading()
    speed_cm = float(np.linalg.norm(world.vel)) * 100

    # vertical zone phrase (ceiling/floor vs walls are distinct per M4 review)
    if pos[2] > 0.85:
        vert = "very close to the ceiling"
    elif pos[2] < 0.15:
        vert = "very close to the floor"
    else:
        vert = f"at {z_bin} height"

    # nearest obstacle: v1.1 前置性短语 + >40cm 抑制 + closing 仅 in-path
    best, bd, bv = None, 1e9, None
    for x, z, r, h in world.obstacles:
        if pos[2] < h + 0.05:
            dx, dz = x - pos[0], z - pos[1]
            d = math.hypot(dx, dz) - r
            if d < bd:
                bd, best, bv = d, (dx, dz), (dx, dz)
    if best is None:
        obs = "no obstacle nearby below flight height"
    else:
        bearing = math.atan2(heading[0] * best[1] - heading[1] * best[0],
                             heading[0] * best[0] + heading[1] * best[1])
        cm = max(bd, 0.0) * 100
        if cm > 40:
            obs = "no obstacle within 40 cm"
        else:
            closing = bool(np.dot(np.array(best) / max(math.hypot(*best), 1e-6),
                                  heading[:2]) > 0.1)
            tail = ", closing" if (closing and _in_flight_path(bearing)) else ""
            obs = (f"nearest obstacle {_where_phrase(bearing)}, "
                   f"{_range_bin(cm)} ({cm:.0f} cm){tail}")

    # sun
    sun_b = math.atan2(heading[0] * world.sun[1] - heading[1] * world.sun[0],
                       heading[0] * world.sun[0] + heading[1] * world.sun[1])
    angle_to_heading = math.degrees(math.acos(max(-1, min(1,
        float(np.dot(heading, world.sun))))))
    sun = (f"sun {_phrase_bearing(sun_b)}, elevation "
           f"{math.degrees(math.asin(world.sun[2])):.0f} deg, "
           f"{angle_to_heading:.0f} deg from heading")
    # wall phrase (v1.1: 附前置性; nearest of 4 walls)
    walls = [("left", pos[0], (-1, 0)), ("right", 1 - pos[0], (1, 0)),
             ("front", pos[1], (0, -1)), ("back", 1 - pos[1], (0, 1))]
    wname, wdist, wdir = min(walls, key=lambda t: t[1])
    rel = math.atan2(heading[0] * wdir[1] - heading[1] * wdir[0],
                     heading[0] * wdir[0] + heading[1] * wdir[1])
    wall = (f"nearest wall {_where_phrase(rel)}, "
            f"{min(wdist, 0.99) * 100:.0f} cm" if wdist < 0.15 else "far from walls")

    climb = "climbing" if world.vel[2] > 0.05 else "descending" if world.vel[2] < -0.05 else "level"
    dwell = max(0.0, time.time() - intent_since)

    return (f"Fly zone: {x_bin}-{y_bin} of the arena, {vert}. "
            f"{obs}. {sun}. Flight speed {speed_cm:.0f} cm/s, {climb}. "
            f"Current intent {last_intent} for {dwell:.1f} s. "
            f"Wall status: {wall}. "
            f"Recent bump: {'yes' if recent_bump else 'no'}.")


# ---------------------------------------------------------------- source
class LayaIntentSource:
    """Spec-conformant intent loop against the Jev-compatible endpoint."""

    def __init__(self, url="http://127.0.0.1:8000/v1/systemone", every_frames=3,
                 log_path=None, tau=None, eps=None, rng_seed=None,
                 state_source=None, coupling=None, direct=None):
        self.url = url
        self.every = every_frames
        self.tau = float(tau if tau is not None else os.environ.get("FLYLAYA_INTENT_TAU", 1.0))
        self.eps = float(eps if eps is not None else os.environ.get("FLYLAYA_INTENT_EPS", 0.0))
        self.rng = np.random.default_rng(rng_seed)
        # TASK-0010 (design §3.1/§3.2): state source and pathway gating.
        self.state_source = state_source or os.environ.get("FLYLAYA_STATE_SOURCE", "oracle")
        if self.state_source not in ("oracle", "observable"):
            logging.warning("FLYLAYA_STATE_SOURCE=%r unknown; using 'oracle'",
                            self.state_source)
            self.state_source = "oracle"
        self.coupling = coupling or _default_coupling()
        self.direct = (direct if direct is not None
                       else os.environ.get("FLYLAYA_DIRECT", "off") == "on")
        self.last_intent = "explore"
        self.last_conf = 1.0
        self.arousal = 1
        self.intent_since = time.time()
        self.last_state_text = ""
        self.last_decision = {}  # m5 decisions.jsonl contract fields (W3 logs this)
        self.calls = 0
        self.errors = 0
        self._consec_errors = 0
        self._client = None
        self._log = open(log_path, "a") if log_path else None
        self.history = []  # (t, intent) for switch-rate stats
        # v1.1 配套: avoid 瞬时逃离偏置 (120°/s, ≤0.5s = 5 frames)。
        # direct 通路: 默认关 (design §3.2), 仅 direct=True 时武装。
        self._escape_frames = 0
        self._escape_sign = 0.0

    def _post(self, payload):
        import httpx

        if self._client is None:
            self._client = httpx.Client(timeout=0.05, trust_env=False)
        r = self._client.post(self.url, json=payload)
        r.raise_for_status()
        return r.json()

    def poll(self, frame, world, brain):
        if frame % self.every:
            return self.last_intent, self.last_conf
        if self.state_source == "observable":
            _, text = observable_state(world, brain, self.last_intent,
                                       self.intent_since)
        else:
            text = state_text(world, self.last_intent, self.intent_since,
                              getattr(world, "last_bump", False))
        self.last_state_text = text
        t0 = time.perf_counter()
        try:
            res = self._post({"state": {"body": text}, "questions": QUESTIONS})
            latency_ms = (time.perf_counter() - t0) * 1000
            a = res["answers"]
            new_intent = a["intent"]["choice"]
            probs = a["intent"].get("probabilities") or {}
            keys = [k for k in INTENTS if k in probs]
            # raw model argmax, recorded separately from the applied sample
            # (design §6: raw probabilities are never overwritten by sampling)
            raw_choice = (max(keys, key=lambda k: float(probs[k]))
                          if keys else new_intent)
            # 迭代①: 温度采样/ε-探索防 argmax 塌缩 (p=0.998 峰时 τ 效果弱,
            # eps 是兜底; 默认 tau=1/eps=0 保持 v1 行为, env/参数开启)
            if len(keys) >= 2 and (self.tau != 1.0 or self.eps > 0):
                pick = None
                if self.eps > 0 and self.rng.random() < self.eps:
                    # ε 只在非 rest 意图里探索: rest 由 Laya 自己判断,
                    # 均匀 ε 会把静止时间推过 B 档 (冒烟2: rest 26% > B 21%)
                    active = [k for k in INTENTS if k != "rest_hover"]
                    pick = active[int(self.rng.integers(len(active)))]
                elif self.tau != 1.0:
                    w = np.array([max(float(probs[k]), 1e-9) for k in keys]) ** (1.0 / self.tau)
                    w /= w.sum()
                    pick = keys[int(self.rng.choice(len(keys), p=w))]
                if pick is not None:
                    new_intent = pick
            self.last_conf = a["intent"].get("confidence", 1.0)
            # keep the FLOAT score (clamped 0-2): int-rounding collapsed
            # Laya's 1.3-1.5 range to a constant 1 under observable states,
            # zeroing arousal variance (Gate-F arou_r guardrail degenerate).
            # No effect under sensory_only (arousal thrust path is gated).
            self.arousal = float(np.clip(a["arousal"]["score"], 0.0, 2.0))
            self.calls += 1
            self._consec_errors = 0
            # spec: <1s dwell switches are jitter -> keep previous intent
            dwell = time.time() - self.intent_since
            dwell_guard = bool(new_intent != self.last_intent and dwell < 1.0)
            if new_intent != self.last_intent and dwell >= 1.0:
                self.last_intent = new_intent
                self.intent_since = time.time()
                self.history.append((time.time(), new_intent))
                if new_intent == "avoid_obstacle":
                    self._arm_escape(world)
            self.last_decision = {
                "t_s": round(frame * 0.1, 3),
                "state_source": self.state_source,
                "state_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "raw_choice": raw_choice,
                "raw_probabilities": {k: float(probs[k]) for k in keys},
                "sampled": new_intent,
                "applied": self.last_intent,
                "dwell_guard": dwell_guard,
                "arousal_score": self.arousal,
                "latency_ms": round(latency_ms, 1),
                "timeout": False,
                "fallback_reason": None,
            }
            if self._log:
                self._log.write(json.dumps({
                    "t": time.time(), "t_s": round(frame * 0.1, 3),
                    "state_source": self.state_source, "state": text,
                    "raw_choice": raw_choice, "intent": new_intent,
                    "applied": self.last_intent, "probabilities": probs,
                    "arousal": self.arousal, "latency_ms": round(latency_ms, 1),
                    "coupling": self.coupling, "direct": self.direct,
                }) + "\n")
                self._log.flush()
        except Exception as e:
            self.errors += 1
            self._consec_errors += 1
            if self._consec_errors >= 3:  # spec: fail over to rest_hover
                self.last_intent = "rest_hover"
                self.intent_since = time.time()
                # 无静默回退 (design §3.2/G2): 每次 failover 必须留痕
                logging.warning(
                    "LayaIntentSource: %d consecutive errors (last %s: %s); "
                    "failed over to rest_hover",
                    self._consec_errors, type(e).__name__, str(e)[:80])
                self.last_decision = {
                    "t_s": round(frame * 0.1, 3),
                    "state_source": self.state_source,
                    "state_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "raw_choice": None, "raw_probabilities": {},
                    "sampled": None, "applied": self.last_intent,
                    "dwell_guard": False, "arousal_score": self.arousal,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "timeout": "timeout" in type(e).__name__.lower(),
                    "fallback_reason": "consecutive_failures",
                }
        return self.last_intent, self.last_conf

    def _arm_escape(self, world):
        """v1.1 配套: 切入 avoid 时若有 in-path 障碍, 武装 0.5s 120°/s 逃离偏置.
        direct 通路默认关 (design §3.2): 未显式开启时本函数是硬 no-op,
        不存在绕过 poll 的武装路径."""
        if not self.direct:
            return
        heading = world._heading()
        pos = world.pos
        best, bd = None, 1e9
        for x, z, r, h in world.obstacles:
            if pos[2] < h + 0.05:
                dx, dz = x - pos[0], z - pos[1]
                d = math.hypot(dx, dz) - r
                if d < bd:
                    bd, best = d, (dx, dz)
        if best is None or bd * 100 > 40:
            return
        bearing = math.atan2(heading[0] * best[1] - heading[1] * best[0],
                             heading[0] * best[0] + heading[1] * best[1])
        if abs(math.degrees(bearing)) < 45:  # in the flight path
            self._escape_frames = 5   # 0.5s @ 10Hz
            self._escape_sign = -1.0 if bearing > 0 else 1.0  # yaw += 120°/s * sign(-bearing)

    def consume_yaw_bias(self):
        """每帧调用: 返回本帧附加 yaw 偏置 rad/s (逃离窗口递减)."""
        if self._escape_frames > 0:
            self._escape_frames -= 1
            return math.radians(120.0) * self._escape_sign
        return 0.0

    def hud(self):
        return {"intent_calls": self.calls, "intent_errors": self.errors,
                "arousal": self.arousal,
                "switches": len(self.history)}


# ------------------------------------------------------- observable state
OBS_FIELDS = {
    "lateral_contrast":  {"source": "retina", "latency_s": 0.1},
    "vertical_contrast": {"source": "retina", "latency_s": 0.1},
    "frontal_dark_frac": {"source": "retina", "latency_s": 0.1},
    "front_dark_side":   {"source": "retina", "latency_s": 0.1},
    "mean_brightness":   {"source": "retina", "latency_s": 0.1},
    "speed_cm_s":        {"source": "proprio (labeled estimate)", "latency_s": 0.0},
    "climb":             {"source": "proprio (labeled estimate)", "latency_s": 0.0},
    "dn_yaw_balance_hz": {"source": "dn_readout", "latency_s": 0.1},
    "intent_dwell_s":    {"source": "history", "latency_s": 0.0},
}


def observable_state(world, brain, last_intent, intent_since):
    """Sensory-observable state (design §3.1) — explicitly versioned
    'sensory-observable v1', NOT a pure-neural state.

    Built only from: the post-modulation retina vector cached by
    World.render_luminance (1 frame stale by construction), labeled
    proprioceptive estimates (speed/climb), the DN motor readout, and
    intent history. Never reads obstacle entities, the true sun vector,
    the arena seed or any scorer label. Returns (summary, text) where
    summary keys are exactly OBS_FIELDS.
    """
    lum = getattr(world, "last_luminance", None)
    if lum is None:
        lum = world.render_luminance()
    d = world.receptor_dirs
    left, right = d[:, 1] < -0.25, d[:, 1] > 0.25
    up, down = d[:, 2] > 0.3, d[:, 2] < -0.3
    frontal = d[:, 0] > 0.3
    lat = float(lum[left].mean() - lum[right].mean())
    vert = float(lum[up].mean() - lum[down].mean())
    bright = float(lum.mean())
    fr = lum[frontal]
    front_dark = float((fr < 0.5 * float(np.median(lum))).mean()) if len(fr) else 0.0
    dl = float(lum[frontal & left].mean())
    dr = float(lum[frontal & right].mean())
    dark_side = "left" if dl < dr else "right" if dr < dl else "even"
    speed_cm = float(np.linalg.norm(world.vel)) * 100
    climb = ("climbing" if world.vel[2] > 0.05
             else "descending" if world.vel[2] < -0.05 else "level")
    dn = brain.dn_snapshot() if hasattr(brain, "dn_snapshot") else {}
    dn_bal = float(dn.get("DNp20_R", 0.0) - dn.get("DNp20_L", 0.0))
    dwell = max(0.0, time.time() - intent_since)
    side = "left" if lat > 0.02 else "right" if lat < -0.02 else "even"
    vert_txt = ("brighter" if vert > 0.02
                else "dimmer" if vert < -0.02 else "level with")
    summary = {
        "lateral_contrast": lat, "vertical_contrast": vert,
        "frontal_dark_frac": front_dark, "front_dark_side": dark_side,
        "mean_brightness": bright, "speed_cm_s": speed_cm, "climb": climb,
        "dn_yaw_balance_hz": dn_bal, "intent_dwell_s": dwell,
    }
    text = (f"Vision: brightest on the {side} side (contrast {abs(lat):.2f}), "
            f"dorsal {vert_txt} ventral ({vert:+.2f}). Frontal dark fraction "
            f"{front_dark:.2f}, densest ahead-{dark_side} if dark. "
            f"Overall brightness {bright:.2f}. Body sense (labeled "
            f"proprioception): speed {speed_cm:.0f} cm/s, {climb}. "
            f"DN yaw balance {dn_bal:+.1f} Hz. Current intent {last_intent} "
            f"for {dwell:.1f} s.")
    return summary, text


# ------------------------------------------------------------ policy groups
class FixedGoalSource:
    """P_fixed (design §5.1): one fixed goal intent. Single-cue mechanism
    experiments only — measures the target-to-motor transfer function."""

    def __init__(self, intent="phototaxis"):
        if intent not in INTENTS:
            raise ValueError(f"FixedGoalSource: unknown intent {intent!r}")
        self.intent = intent
        self.arousal = 1
        self.last_intent = intent

    def poll(self, frame, world, brain):
        return self.intent, 1.0

    def hud(self):
        return {"source": "fixed_goal", "intent": self.intent}


class RuleIntentSource:
    """P_rule (design §5.1): interpretable rules. use_truth=True reads
    world ground truth (flagged as such — scenario solvability / ceiling);
    use_truth=False runs on the sensory-observable summary only."""

    def __init__(self, use_truth=False):
        self.use_truth = bool(use_truth)
        self.arousal = 1
        self.last_intent = "explore"
        self.calls = 0

    def poll(self, frame, world, brain):
        self.calls += 1
        if self.use_truth:
            intent = self._rule_truth(world)
        else:
            summary, _ = observable_state(world, brain, self.last_intent, 0.0)
            intent = self._rule_sensory(summary)
        self.last_intent = intent
        return intent, 1.0

    @staticmethod
    def _rule_truth(world):
        pos, heading = world.pos, world._heading()
        for x, z, r, h in world.obstacles:
            if pos[2] < h + 0.05:
                dx, dz = x - pos[0], z - pos[1]
                d = math.hypot(dx, dz) - r
                b = math.atan2(heading[0] * dz - heading[1] * dx,
                               heading[0] * dx + heading[1] * dz)
                if d < 0.25 and abs(b) < math.radians(60):
                    return "avoid_obstacle"
        dmin = min(pos[0], 1 - pos[0], pos[1], 1 - pos[1])
        if dmin < 0.12:
            return "center_in_arena"
        return "explore"

    @staticmethod
    def _rule_sensory(summary):
        if summary["frontal_dark_frac"] > 0.30 and summary["front_dark_side"] != "even":
            return "avoid_obstacle"
        # wall escape (TASK-0020 coverage): pressing against a wall dims
        # the whole visual field — sensorily indistinguishable from a
        # looming wall, and the remedy (steer back to open space) is the
        # centering intent, whose sensory wall gain does exactly that
        if summary["mean_brightness"] < 0.18:
            return "center_in_arena"
        if abs(summary["lateral_contrast"]) > 0.08:
            return "phototaxis"
        return "explore"

    def hud(self):
        return {"source": "rule", "use_truth": self.use_truth,
                "calls": self.calls}


def load_sequence(src):
    """Frozen intent sequence: list of {"t_s", "intent", "arousal"} dicts,
    or a path to a JSON array / JSONL file. Validates t_s strictly
    increasing and intents in the vocabulary."""
    if isinstance(src, (str, os.PathLike)):
        with open(src) as f:
            first = f.read(1)
            f.seek(0)
            seq = json.load(f) if first == "[" else [json.loads(ln)
                                                     for ln in f if ln.strip()]
    else:
        seq = list(src)
    out = []
    prev = -1.0
    for i, s in enumerate(seq):
        t = float(s["t_s"])
        if t <= prev:
            raise ValueError(f"sequence[{i}]: t_s {t} not strictly increasing")
        if s["intent"] not in INTENTS:
            raise ValueError(f"sequence[{i}]: unknown intent {s['intent']!r}")
        prev = t
        out.append({"t_s": t, "intent": s["intent"],
                    "arousal": float(s.get("arousal", 1.0))})
    if not out:
        raise ValueError("empty intent sequence")
    return out


def _time_stats(seq):
    """Time-weighted class shares and dwell list (last segment censored)."""
    dur = {}
    dwells = []
    for i, s in enumerate(seq):
        end = seq[i + 1]["t_s"] if i + 1 < len(seq) else s["t_s"] + 0.3
        dt = end - s["t_s"]
        dur[s["intent"]] = dur.get(s["intent"], 0.0) + dt
        if i + 1 < len(seq) and s["intent"] != seq[i + 1]["intent"]:
            dwells.append(dt)
    total = sum(dur.values())
    shares = {k: v / total for k, v in dur.items()}
    mean_dwell = float(np.mean(dwells)) if dwells else 0.0
    return shares, mean_dwell


def validate_yoked(src_seq, yoked_seq, share_tol=0.02, dwell_rtol=0.10):
    """Design §7: a yoked arm may only enter analysis if per-class share
    differs by <= share_tol (absolute) and mean dwell by <= dwell_rtol
    (relative) from its source sequence. Returns the match report."""
    a, b = load_sequence(src_seq), load_sequence(yoked_seq)
    sh_a, dw_a = _time_stats(a)
    sh_b, dw_b = _time_stats(b)
    share_diff = {k: abs(sh_b.get(k, 0.0) - sh_a.get(k, 0.0)) for k in sh_a}
    max_share = max(share_diff.values())
    dwell_rel = abs(dw_b - dw_a) / dw_a if dw_a > 0 else 0.0
    return {"ok": max_share <= share_tol and dwell_rel <= dwell_rtol,
            "max_share_diff": max_share, "dwell_rel_diff": dwell_rel,
            "share_diff": share_diff, "mean_dwell_s": {"src": dw_a, "yoked": dw_b},
            "tolerances": {"share_tol": share_tol, "dwell_rtol": dwell_rtol}}


def permute_sequence(src, mode="cycle_shift", k=1, block_s=5.0, seed=0):
    """Deterministic yoke permutations (design §5.1): cycle_shift rotates
    the (intent, arousal) pairs by k entries; block_perm permutes ~block_s
    blocks with a seeded rng. The t_s grid is kept identical, so cadence,
    shares and dwell structure survive while state correspondence dies."""
    seq = load_sequence(src)
    n = len(seq)
    ts = [s["t_s"] for s in seq]
    pairs = [(s["intent"], s["arousal"]) for s in seq]
    if mode == "cycle_shift":
        k = int(k) % n if n else 0
        pairs = pairs[k:] + pairs[:k]
    elif mode == "block_perm":
        size = max(1, int(round(block_s / max(np.median(np.diff(ts)), 1e-3))))
        blocks = [pairs[i:i + size] for i in range(0, n, size)]
        rng = np.random.default_rng(seed)
        order = rng.permutation(len(blocks))
        pairs = [p for j in order for p in blocks[j]]
        pairs = (pairs + pairs)[:n]
    else:
        raise ValueError(f"permute mode must be cycle_shift|block_perm, got {mode!r}")
    return [{"t_s": t, "intent": p[0], "arousal": p[1]}
            for t, p in zip(ts, pairs)]


class YokedIntentSource:
    """P_yoked (design §5.1): replay a frozen (t_s, intent, arousal)
    sequence recorded from a P_laya run — identity, cycle-shifted or
    block-permuted. Preserves class shares, dwell structure and arousal
    magnitudes; destroys the state correspondence (that is the point)."""

    def __init__(self, sequence, dt=0.1, mode="identity", seed=0, block_s=5.0):
        seq = load_sequence(sequence)
        if mode != "identity":
            seq = permute_sequence(seq, mode=mode, block_s=block_s, seed=seed)
        self.seq = seq
        self.dt = dt
        self.i = 0
        self.last_intent = seq[0]["intent"]
        self.arousal = seq[0]["arousal"]
        self.calls = 0

    def poll(self, frame, world, brain):
        t = frame * self.dt
        while self.i + 1 < len(self.seq) and self.seq[self.i + 1]["t_s"] <= t + 1e-9:
            self.i += 1
        s = self.seq[self.i]
        self.last_intent = s["intent"]
        self.arousal = s["arousal"]
        self.calls += 1
        return s["intent"], 1.0

    def hud(self):
        return {"source": "yoked", "i": self.i, "n": len(self.seq)}
