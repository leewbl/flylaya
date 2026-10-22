"""m5/metrics.py — W4 evaluation/statistics contract (design doc §7; TASK-0012).

Statistical unit: seed-within-scene (never frames, never rating clicks).
H1/H2 are co-primary endpoints; multiplicity controlled via Bonferroni
(one-sided 2.5% bounds each) alongside plain two-sided 95% CIs.

DATA CONTRACT v1 (SI units) — consumed per run directory (design §6).
Field names are the m5 contract; the W3 runner must emit exactly these.

trajectory.jsonl — first line meta, then one row per neural frame:
  {"type":"meta", "schema":"flylaya.m5.traj.v1", "scene_id": str, "seed": int,
   "policy": str, "coupling": str, "brain": str, "dt_s": float, ...}
  {"t_s": float, "pos_m": [x,y,z], "yaw_deg": float, "speed_m_s": float,
   "min_gap_m": float,                      # clearance BEFORE any clamping
   "intent_raw": str|null, "intent_applied": str, "arousal": float,
   "yaw_bias_direct": float,                # rad/s direct path this frame
   "gains_pre": {...}, "gains_post": {...}, # sensory & motor gain dicts
   "dn": {name: rate_Hz},                   # must include the DN_PAIRS below
   "stim": [str, ...]}                      # active stimulus tags

decisions.jsonl — one row per Laya call:
  {"t_s": float, "state_source": "oracle"|"observable",
   "state_text_sha256": str, "raw_choice": str,
   "raw_probabilities": {intent: p},        # model output, NOT post-temperature
   "arousal_score": float, "sampled": str, "applied": str,
   "dwell_guard": bool, "latency_ms": float, "timeout": bool,
   "fallback_reason": null|"consecutive_failures"|"timeout"|...}

events.jsonl — one row per event (detector version embedded):
  {"t_s": float, "kind": "approach_start"|"approach_end"|"contact"|
    "wall_contact"|"turn_start"|"turn_end"|"sun_lost"|
    "stimulus_on"|"stimulus_off", "target": str|null,
   "detector": "flylaya.m5.events.v1", ...kind-specific fields}

scene JSON (flylaya.scene.v1, W1): light {"mode", "azimuth_deg"},
obstacles [{"id","center_xy_m","radius_m",...}] — read for H1 target direction
and stimulus context. No scene file → light/avoid context metrics return None
with "scene_missing" reason instead of guessing.

sun_R (circular concentration) is ALWAYS co-reported with mean direction and
is never a phototaxis direction metric (design §1/§7).
"""
import argparse
import hashlib
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))          # repo root (m3 reuse)
sys.path.insert(0, os.path.join(HERE, "..", "m3"))
import trajectory_stats as ts  # noqa: E402  (pooled KS, descriptive only)

EVENTS_VERSION = "flylaya.m5.events.v1"

# Prespecified DN left/right readout pairs (design §7 神经中介; brains.py pools).
DN_PAIRS = [("DNp20_L", "DNp20_R"), ("MDN_L", "MDN_R"),
            ("DNa02_L", "DNa02_R"), ("DNpe017_L", "DNpe017_R")]
DN_LR = [n for pair in DN_PAIRS for n in pair]

# Engineering thresholds (declared; NOT biological constants — design §2).
APPROACH = {"max_dist_m": 0.25, "frontal_cone_deg": 45.0, "min_closing_m_s": 0.02}
TURN = {"yaw_rate_dps": 150.0, "min_gap_for_wall_m": 0.05}
HF_DT_S = 0.02          # only median dt <= this may report turn duration/peak
HIGHFREQ_GATE = "median_dt<=0.02s"

YOKED_TOL = {"class_share_abs": 0.02, "dwell_rel": 0.10, "arousal_mean_abs": None}

H1_MIN_DIFF = 0.15       # paired mean_cos_to_light advantage (design §2)
H2_MIN_REDUCTION = 0.25  # contact-risk reduction vs yoked (design §2)
N_PRIMARY = 2            # H1, H2 co-primary → Bonferroni one-sided 2.5% each


# ----------------------------------------------------------------- IO
def _jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_run(run_dir, scene=None):
    """Load one contract run dir. scene: dict or path to scene json."""
    run = {"dir": run_dir}
    traj_path = os.path.join(run_dir, "trajectory.jsonl")
    if not os.path.exists(traj_path):
        raise FileNotFoundError(f"{traj_path} missing — not a contract run dir")
    rows = _jsonl(traj_path)
    run["meta"], run["frames"] = rows[0], rows[1:]
    for name in ("decisions", "events"):
        p = os.path.join(run_dir, f"{name}.jsonl")
        run[name] = _jsonl(p) if os.path.exists(p) else []
    if scene is None:
        for cand in (os.path.join(run_dir, "scene.json"),
                     os.path.join(run_dir, "..", "..", "..", "scenes",
                                  f"{run['meta'].get('scene_id')}.json")):
            if os.path.exists(cand):
                scene = cand
                break
    run["scene"] = json.load(open(scene)) if isinstance(scene, str) else scene
    return run


# ------------------------------------------------- event detector v1
def _bearing_deg(dx, dz):
    return math.degrees(math.atan2(dz, dx))


def _heading_deg(yaw_deg):
    return yaw_deg  # contract: yaw_deg is compass/math heading of h_xy


def _enable_timeline(scene):
    """Obstacle id -> [(t, enabled)] switch points (initial state first),
    replayed from the scene clock events. Frames outside their stimulus
    window must not produce approaches to a not-yet-materialized obstacle."""
    tl = {ob.get("id"): [(0.0, ob.get("enabled", True))]
          for ob in scene.get("obstacles", [])}
    for ev in scene.get("events", []):
        tgt, kind = ev.get("target"), ev.get("kind")
        if tgt in tl and kind in ("stimulus_on", "stimulus_off"):
            tl[tgt].append((float(ev["t_s"]), kind == "stimulus_on"))
    return tl


def _enabled_at(switches, t):
    state = switches[0][1]
    for tt, en in switches:
        if tt <= t + 1e-9:
            state = en
        else:
            break
    return state


def detect_events(frames, scene=None):
    """Reference detector v1. Emits the events.jsonl row kinds the metrics
    consume, so the runner and metrics share one implementation."""
    ev = []
    n = len(frames)
    approaching = False
    turning = False
    timeline = _enable_timeline(scene) if scene else {}
    for i, fr in enumerate(frames):
        t = fr["t_s"]
        yaw = fr["yaw_deg"]
        # ---- obstacle approach: distance + frontal cone + closing speed
        hit = None
        if scene:
            for ob in scene.get("obstacles", []):
                if not _enabled_at(timeline[ob.get("id")], t):
                    continue
                ox, oz = ob["center_xy_m"]
                dx, dz = ox - fr["pos_m"][0], oz - fr["pos_m"][1]
                dist = math.hypot(dx, dz) - ob.get("radius_m", 0.0)
                brg = _bearing_deg(dx, dz)
                rel = (brg - _heading_deg(yaw)) % 360.0
                if rel > 180.0:
                    rel -= 360.0
                if abs(rel) > APPROACH["frontal_cone_deg"] or dist > APPROACH["max_dist_m"]:
                    continue
                closing = 0.0
                if i > 0:
                    p0 = frames[i - 1]["pos_m"]
                    d0 = math.hypot(ox - p0[0], oz - p0[1]) - ob.get("radius_m", 0.0)
                    closing = (d0 - dist) / max(frames[i]["t_s"] - frames[i - 1]["t_s"], 1e-6)
                if closing >= APPROACH["min_closing_m_s"]:
                    hit = {"target": ob["id"], "bearing_deg": brg, "dist_m": dist}
                    break
        if hit and not approaching:
            approaching = True
            ev.append({"t_s": t, "kind": "approach_start", "detector": EVENTS_VERSION,
                       "target": hit["target"], "bearing_deg": round(hit["bearing_deg"], 2),
                       "dist_m": round(hit["dist_m"], 4)})
        elif not hit and approaching:
            approaching = False
            ev.append({"t_s": t, "kind": "approach_end", "detector": EVENTS_VERSION,
                       "target": None})
        # ---- turns from yaw rate
        if i > 0:
            dyaw = ((yaw - frames[i - 1]["yaw_deg"] + 180.0) % 360.0) - 180.0
            rate = dyaw / max(t - frames[i - 1]["t_s"], 1e-6)
            if abs(rate) >= TURN["yaw_rate_dps"] and not turning:
                turning = True
                ev.append({"t_s": t, "kind": "turn_start", "detector": EVENTS_VERSION,
                           "sign": 1 if rate > 0 else -1})
            elif abs(rate) < TURN["yaw_rate_dps"] and turning:
                turning = False
                ev.append({"t_s": t, "kind": "turn_end", "detector": EVENTS_VERSION,
                           "sign": 0})
    return ev


def run_events(run):
    """events.jsonl rows, falling back to the reference detector over frames."""
    if run["events"]:
        return run["events"]
    return detect_events(run["frames"], run.get("scene"))


# --------------------------------------------------------- per-run metrics
def _angles_to_xy(azimuth_deg):
    a = math.radians(azimuth_deg)
    return math.cos(a), math.sin(a)


def light_metrics(run):
    """H1 family. mean_cos_to_light is THE signed direction metric;
    sun_R co-reported with mean direction only."""
    scene = run.get("scene")
    frames = run["frames"]
    light = (scene or {}).get("light") or {}
    if light.get("mode") not in ("directional", "single"):
        return {"mean_cos_to_light": None, "reason": "scene_missing_or_not_directional"}
    tx, tz = _angles_to_xy(light.get("azimuth_deg", 0.0))
    cosines, sun_rel = [], []
    for fr in frames:
        h = math.radians(fr["yaw_deg"])
        hx, hz = math.cos(h), math.sin(h)
        cosines.append(hx * tx + hz * tz)
        sun_rel.append(math.degrees(math.atan2(hz * tx - hx * tz, hx * tx + hz * tz)))
    net = np.array(frames[-1]["pos_m"][:2]) - np.array(frames[0]["pos_m"][:2])
    out = {
        "mean_cos_to_light": float(np.mean(cosines)),
        "displacement_toward_target_m": float(net[0] * tx + net[1] * tz),
        "net_displacement_m": float(np.linalg.norm(net)),
    }
    # first correct turn: heading error toward target reduced >=15 deg from the
    # value at first stimulus_on (else run start), sustained >= 0.3 s
    evs = run_events(run)
    t0 = next((e["t_s"] for e in evs if e["kind"] == "stimulus_on"), frames[0]["t_s"])
    base = None
    lat = None
    for fr in frames:
        if fr["t_s"] < t0:
            continue
        err = math.degrees(math.acos(max(-1.0, min(1.0,
                math.cos(math.radians(fr["yaw_deg"])) * tx +
                math.sin(math.radians(fr["yaw_deg"])) * tz))))
        if base is None:
            base = err
        if lat is None and base - err >= 15.0:
            lat = fr["t_s"] - t0
    out["first_correct_turn_latency_s"] = lat
    # concentration co-report (never standalone phototaxis)
    a = np.radians(np.asarray(sun_rel))
    Rbar = abs(np.mean(np.exp(1j * a)))
    meandir = math.degrees(np.angle(np.mean(np.exp(1j * a))))
    out["sun_R_with_mean_dir"] = {"R": float(Rbar), "mean_dir_deg": float(meandir),
                                  "note": "concentration only; direction is the "
                                          "mean_cos_to_light field"}
    return out


def _approach_windows(events):
    wins, cur = [], None
    for e in events:
        if e["kind"] == "approach_start":
            cur = {"t0": e["t_s"], "target": e.get("target"),
                   "bearing_deg": e.get("bearing_deg"), "t1": None}
        elif e["kind"] == "approach_end" and cur is not None:
            cur["t1"] = e["t_s"]
            wins.append(cur)
            cur = None
    if cur is not None:                      # still open at run end
        cur["t1"] = float("inf")
        wins.append(cur)
    return wins


def avoidance_metrics(run):
    """H2 family. Denominator = valid approaches (distance+frontal+closing);
    empty denominator returns None fields with the count — never success."""
    frames, events = run["frames"], run_events(run)
    wins = _approach_windows(events)
    contacts = [e for e in events if e["kind"] == "contact"]
    rows = []
    for w in wins:
        t1f = w["t1"] if w["t1"] != float("inf") else frames[-1]["t_s"]
        fwin = [f for f in frames if w["t0"] <= f["t_s"] <= t1f]
        if not fwin:
            continue
        contact = any(w["t0"] <= c["t_s"] <= t1f + 1e-9 for c in contacts)
        gaps = [f["min_gap_m"] for f in fwin if f.get("min_gap_m") is not None]
        dyaw = 0.0
        if len(fwin) > 1:
            dyaw = ((fwin[-1]["yaw_deg"] - fwin[0]["yaw_deg"] + 180.0) % 360.0) - 180.0
        brg = w.get("bearing_deg")
        correct = None
        if brg is not None and dyaw != 0.0:
            correct = bool((brg > 0) != (dyaw > 0))   # turned opposite the bearing
        turn0 = next((e["t_s"] for e in events
                      if e["kind"] == "turn_start" and w["t0"] <= e["t_s"] <= t1f), None)
        rows.append({"contact": contact,
                     "min_gap_m": float(min(gaps)) if gaps else None,
                     "turned_away_correctly": correct,
                     "reaction_latency_s": (turn0 - w["t0"]) if turn0 is not None else None})
    n = len(rows)
    n_contact = sum(1 for r in rows if r["contact"])
    corr = [r["turned_away_correctly"] for r in rows if r["turned_away_correctly"] is not None]
    lat = [r["reaction_latency_s"] for r in rows if r["reaction_latency_s"] is not None]
    gaps = [r["min_gap_m"] for r in rows if r["min_gap_m"] is not None]
    return {
        "n_valid_approaches": n,
        "n_contact": n_contact,
        "contact_rate": (n_contact / n) if n else None,      # empty denom ≠ success
        "min_gap_m_p50": float(np.median(gaps)) if gaps else None,
        "correct_turn_away_rate": (float(np.mean(corr)) if corr else None),
        "reaction_latency_s_p50": float(np.median(lat)) if lat else None,
        "approaches": rows,
    }


def decision_metrics(run):
    """Decision family: rates, shares, dwell, fallback, and stimulus-conditional
    hit / false-positive (needs scene context; None when denominators empty)."""
    dec = run["decisions"]
    frames = run["frames"]
    out = {}
    seq = [f["intent_applied"] for f in frames]
    switches = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    span = frames[-1]["t_s"] - frames[0]["t_s"] if len(frames) > 1 else None
    out["switch_rate_hz"] = (switches / span) if span else None
    shares = defaultdict(float)
    for s in seq:
        shares[s] += 1
    out["class_shares"] = {k: v / len(seq) for k, v in shares.items()} if seq else {}
    dwells, cur, t0 = [], seq[0] if seq else None, frames[0]["t_s"] if frames else 0
    for f in frames[1:]:
        if f["intent_applied"] != cur:
            dwells.append(f["t_s"] - t0)
            cur, t0 = f["intent_applied"], f["t_s"]
    if frames:
        dwells.append(frames[-1]["t_s"] - t0)
    out["mean_dwell_s"] = float(np.mean(dwells)) if dwells else None
    if dec:
        out["n_decisions"] = len(dec)
        out["timeout_rate"] = sum(1 for d in dec if d.get("timeout")) / len(dec)
        out["fallback_rate"] = sum(1 for d in dec if d.get("fallback_reason")) / len(dec)
    else:
        out["n_decisions"] = 0
        out["timeout_rate"] = out["fallback_rate"] = None

    # stimulus-conditional rates (scene + frames' stim tags)
    ctx = {"frontal_obstacle": [], "rear_obstacle": [], "light_side": []}
    scene = run.get("scene")
    for f in frames:
        tags = set(f.get("stim") or [])
        obs = (scene or {}).get("obstacles", [])
        front = rear = False
        for ob in obs:
            if not ob.get("enabled", True):
                continue
            tag = f"obstacle_{ob['id']}"
            if tag in tags:
                front = ob.get("frontal", True)
                rear = ob.get("rear", False)
        ctx["frontal_obstacle"].append(front)
        ctx["rear_obstacle"].append(rear)
        ctx["light_side"].append("light_on" in tags)
    seqf = seq

    def _cond(flags, predicate):
        idx = [i for i, b in enumerate(flags) if b]
        if not idx:
            return {"n": 0, "rate": None}
        hits = sum(1 for i in idx if predicate(seqf[i]))
        return {"n": len(idx), "rate": hits / len(idx)}

    out["hit_avoid_given_frontal_obstacle"] = _cond(
        ctx["frontal_obstacle"], lambda s: s == "avoid_obstacle")
    out["false_avoid_given_rear_obstacle"] = _cond(
        ctx["rear_obstacle"], lambda s: s == "avoid_obstacle")
    out["hit_phototaxis_given_light"] = _cond(
        ctx["light_side"], lambda s: s == "phototaxis")
    return out


def neural_metrics(run):
    """Neural mediation family. Prespecified DN pairs only."""
    frames = run["frames"]
    events = run_events(run)
    out = {"dn_pairs": [list(p) for p in DN_PAIRS]}

    def _asym(fr):
        dn = fr.get("dn") or {}
        return [dn.get(r, 0.0) - dn.get(l, 0.0) for l, r in DN_PAIRS]

    # per-turn: DN asymmetry shift in ±0.3 s window vs pre-window, sign match
    matches, total = 0, 0
    for e in events:
        if e["kind"] != "turn_start":
            continue
        pre = [_asym(f) for f in frames if e["t_s"] - 0.3 <= f["t_s"] < e["t_s"]]
        post = [_asym(f) for f in frames if e["t_s"] < f["t_s"] <= e["t_s"] + 0.3]
        if not pre or not post:
            continue
        d = np.mean(post, axis=0) - np.mean(pre, axis=0)
        sgn = e.get("sign") or (1 if d[0] >= 0 else -1)
        total += 1
        if np.sign(d[0]) == np.sign(sgn):
            matches += 1
    out["dn_turn_sign_consistency"] = (matches / total) if total else None
    out["n_turns_for_dn"] = total

    # neural precedes turn: |ΔDN| reaches 10% of window max before yaw rate does
    prec, tot = 0, 0
    for e in events:
        if e["kind"] != "turn_start":
            continue
        w = [f for f in frames if e["t_s"] - 0.1 <= f["t_s"] <= e["t_s"] + 0.3]
        if len(w) < 5:
            continue
        a = np.abs([_asym(f)[0] for f in w])
        yr = []
        for i in range(1, len(w)):
            dy = ((w[i]["yaw_deg"] - w[i - 1]["yaw_deg"] + 180) % 360) - 180
            yr.append(abs(dy) / max(w[i]["t_s"] - w[i - 1]["t_s"], 1e-6))
        yr = np.abs(yr)
        if a.max() <= 0 or yr.max() <= 0:
            continue
        ta = next((i for i in range(len(w)) if a[i] >= 0.1 * a.max()), None)
        tr = next((i for i in range(len(yr)) if yr[i] >= 0.1 * yr.max()), None)
        if ta is None or tr is None:
            continue
        tot += 1
        if ta <= tr:
            prec += 1
    out["dn_precedes_turn_frac"] = (prec / tot) if tot else None

    # direct-path action share within avoid windows
    wins = _approach_windows(events)
    num = den = 0.0
    for wgt in wins:
        t1 = wgt["t1"] if wgt["t1"] != float("inf") else frames[-1]["t_s"]
        for i, f in enumerate(frames):
            if wgt["t0"] <= f["t_s"] <= t1 and i > 0:
                dy = abs(((f["yaw_deg"] - frames[i - 1]["yaw_deg"] + 180) % 360) - 180)
                den += dy
                num += abs(math.degrees(f.get("yaw_bias_direct", 0.0) *
                                        max(f["t_s"] - frames[i - 1]["t_s"], 1e-6)))
    out["direct_path_yaw_share_in_approach"] = (num / den) if den > 0 else None
    return out


def flight_metrics(run):
    """Flight family. Turn duration/peak gated on high-frequency dt."""
    frames = run["frames"]
    events = run_events(run)
    dts = np.diff([f["t_s"] for f in frames]) if len(frames) > 1 else np.array([1.0])
    med_dt = float(np.median(dts))
    hi = med_dt <= HF_DT_S
    speeds = np.array([f["speed_m_s"] for f in frames])
    zs = np.array([f["pos_m"][2] for f in frames])
    turns = []
    cur = None
    for e in events:
        if e["kind"] == "turn_start":
            cur = e["t_s"]
        elif e["kind"] == "turn_end" and cur is not None:
            turns.append((cur, e["t_s"]))
            cur = None
    span = frames[-1]["t_s"] - frames[0]["t_s"] if len(frames) > 1 else 0.0
    rates = []
    for t0, t1 in turns:
        w = [f for f in frames if t0 <= f["t_s"] <= t1]
        if len(w) > 1:
            dy = ((w[-1]["yaw_deg"] - w[0]["yaw_deg"] + 180) % 360) - 180
            rates.append(dy)
    rest = float(np.mean(speeds < 0.02))
    wall = float(np.mean([f.get("min_gap_m", 1.0) is not None and
                          f.get("min_gap_m", 1.0) <= TURN["min_gap_for_wall_m"]
                          for f in frames]))
    out = {
        "turn_rate_hz": (len(turns) / span) if span > 0 else None,
        "turn_amplitude_deg_p50": float(np.median(np.abs(rates))) if rates else None,
        "speed_m_s_p50": float(np.median(speeds)),
        "z_m_p50": float(np.median(zs)),
        "rest_frac": rest,
        "near_wall_frac": wall,
        "high_freq_gate": hi,
        "turn_duration_s_p50": None,
        "turn_peak_dps_p50": None,
    }
    if hi and turns:  # ONLY at neural_dt <= 20 ms (design §3.3/§7)
        durs, peaks = [], []
        for t0, t1 in turns:
            w = [f for f in frames if t0 <= f["t_s"] <= t1]
            if len(w) < 3:
                continue
            durs.append(t1 - t0)
            yr = []
            for i in range(1, len(w)):
                dy = ((w[i]["yaw_deg"] - w[i - 1]["yaw_deg"] + 180) % 360) - 180
                yr.append(abs(dy) / max(w[i]["t_s"] - w[i - 1]["t_s"], 1e-6))
            peaks.append(max(yr))
        out["turn_duration_s_p50"] = float(np.median(durs)) if durs else None
        out["turn_peak_dps_p50"] = float(np.median(peaks)) if peaks else None
    else:
        out["gate_note"] = (f"turn duration/peak suppressed: median dt "
                            f"{med_dt:.4f}s > {HF_DT_S}s ({HIGHFREQ_GATE})")
    return out


def run_metrics(run):
    return {"meta": {k: run["meta"].get(k) for k in
                     ("scene_id", "seed", "policy", "coupling", "brain", "dt_s")},
            "decision": decision_metrics(run),
            "light": light_metrics(run),
            "avoidance": avoidance_metrics(run),
            "neural": neural_metrics(run),
            "flight": flight_metrics(run)}


# ------------------------------------------------------------ statistics
def paired_diffs(pairs, value):
    """pairs: {(scene,seed): (runA, runB)}; value: run -> float.
    Returns {(scene,seed): a-b} dropping None sides (counted)."""
    out, dropped = {}, 0
    for key, (a, b) in pairs.items():
        va, vb = value(a), value(b)
        if va is None or vb is None:
            dropped += 1
            continue
        out[key] = va - vb
    return out, dropped


def stratified_bootstrap_ci(diffs_by_scene, ci=95.0, n_boot=10000, rng_seed=7):
    """Hierarchical bootstrap: resample scenes with replacement, then seeds
    within each resampled scene (design §7). Independent unit = seed-in-scene."""
    rng = np.random.default_rng(rng_seed)
    scenes = [s for s, d in diffs_by_scene.items() if len(d) > 0]
    if not scenes:
        return None
    arrs = {s: np.asarray(diffs_by_scene[s], dtype=float) for s in scenes}
    means = []
    for _ in range(n_boot):
        pick = rng.choice(len(scenes), size=len(scenes), replace=True)
        vals = []
        for i in pick:
            s = scenes[i]
            vals.extend(rng.choice(arrs[s], size=len(arrs[s]), replace=True))
        means.append(float(np.mean(vals)))
    lo, hi = np.percentile(means, [(100 - ci) / 2, 100 - (100 - ci) / 2])
    point = float(np.mean([v for s in scenes for v in arrs[s]]))
    return {"point": point, "lo": float(lo), "hi": float(hi),
            "n_seeds": int(sum(len(arrs[s]) for s in scenes)),
            "n_scenes": len(scenes), "n_boot": n_boot, "ci": ci}


def bonferroni_lower_bound(diffs_by_scene, n_primary=N_PRIMARY, n_boot=10000,
                           rng_seed=7):
    """One-sided (1 - 0.05/n_primary) lower bound for co-primary endpoints."""
    alpha = 0.05 / n_primary
    rng = np.random.default_rng(rng_seed)
    scenes = [s for s, d in diffs_by_scene.items() if len(d) > 0]
    if not scenes:
        return None
    arrs = {s: np.asarray(diffs_by_scene[s], dtype=float) for s in scenes}
    means = []
    for _ in range(n_boot):
        pick = rng.choice(len(scenes), size=len(scenes), replace=True)
        vals = []
        for i in pick:
            s = scenes[i]
            vals.extend(rng.choice(arrs[s], size=len(arrs[s]), replace=True))
        means.append(float(np.mean(vals)))
    return float(np.percentile(means, 100 * alpha))


def _prep(run):
    """Accept a loaded run (has 'frames') or an already-computed metrics dict."""
    return run_metrics(run) if run.get("frames") else run


def h1_verdict(pairs_by_mirror):
    """pairs_by_mirror: {mirror_label: {(scene,seed): (laya_run, yoked_run)}}.
    H1 (design §2): paired diff >= +0.15 AND CI lower bound > 0 on BOTH mirrors."""
    detail = {}
    ok_all = True
    for label, pairs in pairs_by_mirror.items():
        pairs = {k: (_prep(a), _prep(b)) for k, (a, b) in pairs.items()}
        diffs, dropped = paired_diffs(pairs,
                                      lambda r: r.get("light", {}).get("mean_cos_to_light"))
        by_scene = defaultdict(list)
        for (sc, sd), v in diffs.items():
            by_scene[sc].append(v)
        ci = stratified_bootstrap_ci(by_scene)
        lb = bonferroni_lower_bound(by_scene)
        point = ci["point"] if ci else None
        ok = (point is not None and point >= H1_MIN_DIFF and lb is not None and lb > 0)
        ok_all &= ok
        detail[label] = {"mean_paired_diff": point, "ci95": ci,
                         "bonferroni_lower": lb, "thresholds":
                         {"min_diff": H1_MIN_DIFF, "one_sided_alpha": 0.05 / N_PRIMARY},
                         "n_dropped_none": dropped, "pass": ok}
    return {"H1_pass": ok_all, "per_mirror": detail,
            "note": "co-primary with H2; both must hold for the L1 claim"}


def h2_verdict(pairs):
    """H2 (design §2): contact-risk reduction >= 25% AND CI upper bound < 1
    (risk ratio laya/yoked). Seeds with zero valid approaches in either arm
    are excluded and counted — empty denominators are never success."""
    by_scene = defaultdict(list)
    excluded = 0
    agg = {"laya": [0, 0], "yoked": [0, 0]}   # [contacts, approaches]
    zero_zero = 0
    for (sc, sd), (a, b) in pairs.items():
        ma, mb = _prep(a).get("avoidance", {}), _prep(b).get("avoidance", {})
        if not ma.get("n_valid_approaches") or not mb.get("n_valid_approaches"):
            excluded += 1
            continue
        agg["laya"][0] += ma["n_contact"]
        agg["laya"][1] += ma["n_valid_approaches"]
        agg["yoked"][0] += mb["n_contact"]
        agg["yoked"][1] += mb["n_valid_approaches"]
        r_a = ma["n_contact"] / ma["n_valid_approaches"]
        r_b = mb["n_contact"] / mb["n_valid_approaches"]
        if r_a == 0.0 and r_b == 0.0:
            zero_zero += 1               # undefined ratio; excluded, counted
            continue
        rr = r_a / r_b
        by_scene[sc].append(rr)
    if not by_scene:
        reason = ("no_seed_with_valid_approaches_both_arms" if excluded and not zero_zero
                  else "all_paired_seeds_zero_contact_both_arms")
        return {"H2_pass": False, "reason": reason,
                "n_excluded_zero_denominator": excluded,
                "n_zero_contact_both_arms": zero_zero,
                "aggregates": {k: {"contacts": v[0], "approaches": v[1]}
                               for k, v in agg.items()},
                "fallback": "report turn-away rate, min gap, approach counts "
                            "(design §2) — do NOT read as success"}
    rng = np.random.default_rng(7)
    scenes = list(by_scene)
    arrs = {s: np.asarray(by_scene[s]) for s in scenes}
    ratios = []
    for _ in range(10000):
        pick = rng.choice(len(scenes), size=len(scenes), replace=True)
        vals = []
        for i in pick:
            s = scenes[i]
            vals.extend(rng.choice(arrs[s], size=len(arrs[s]), replace=True))
        ratios.append(float(np.mean(vals)))
    point = float(np.mean([v for s in scenes for v in arrs[s]]))
    ub = float(np.percentile(ratios, 100 * (1 - 0.05 / N_PRIMARY)))
    ci = stratified_bootstrap_ci(by_scene)
    ok = point <= (1 - H2_MIN_REDUCTION) and ub < 1.0
    return {"H2_pass": ok, "risk_ratio_point": point, "ci95": ci,
            "bonferroni_upper": ub, "reduction": 1 - point,
            "n_excluded_zero_denominator": excluded,
            "thresholds": {"min_reduction": H2_MIN_REDUCTION,
                           "one_sided_alpha": 0.05 / N_PRIMARY}}


def pooled_ks_descriptive(runs_a, runs_b, field="speed_m_s"):
    """Pooled-frame KS D — distribution description only (design §7)."""
    da = [f[field] for r in runs_a for f in r["frames"] if f.get(field) is not None]
    db = [f[field] for r in runs_b for f in r["frames"] if f.get(field) is not None]
    if not da or not db:
        return None
    d, p = ts.ks2samp(da, db)
    return {"D": d, "p": p, "note": "descriptive only; frames are not the "
                                    "independent unit"}


# ------------------------------------------------------- yoked matching
def yoked_match_check(laya_run, yoked_run, tol=YOKED_TOL):
    """Design §5.1/§7: a yoked pair may only enter the primary analysis when
    class shares, dwell and arousal match within tolerance."""
    a = decision_metrics(laya_run)
    b = decision_metrics(yoked_run)
    shares_a, shares_b = a["class_shares"], b["class_shares"]
    keys = sorted(set(shares_a) | set(shares_b))
    share_diff = {k: abs(shares_a.get(k, 0.0) - shares_b.get(k, 0.0)) for k in keys}
    da, db = a.get("mean_dwell_s"), b.get("mean_dwell_s")
    dwell_rel = (abs(da - db) / da) if (da and db) else None
    ar_a = [f["arousal"] for f in laya_run["frames"] if f.get("arousal") is not None]
    ar_b = [f["arousal"] for f in yoked_run["frames"] if f.get("arousal") is not None]
    ar_diff = (abs(float(np.mean(ar_a)) - float(np.mean(ar_b)))
               if ar_a and ar_b else None)
    share_ok = all(v <= tol["class_share_abs"] for v in share_diff.values())
    dwell_ok = dwell_rel is not None and dwell_rel <= tol["dwell_rel"]
    arousal_ok = True if tol["arousal_mean_abs"] is None else (
        ar_diff is not None and ar_diff <= tol["arousal_mean_abs"])
    return {"pass": bool(share_ok and dwell_ok and arousal_ok),
            "class_share_abs_diff": share_diff, "dwell_rel_diff": dwell_rel,
            "arousal_mean_abs_diff": ar_diff,
            "tolerances": dict(tol),
            "arousal_note": "report-only by default (tolerance None)"}


# ---------------------------------------------------------- seed sealing
def seal_seeds(n, out_path, rng_seed=None, pool_hint=None):
    """Seal n confirmation seeds BEFORE the confirmatory batch (design §7.1).
    File is content-addressed; verify_seals() detects any later mutation."""
    rng_seed = rng_seed if rng_seed is not None else int(__import__("time").time())
    rng = np.random.default_rng(rng_seed)
    picked = set()
    while len(picked) < n:  # integers() draws; never materialize the pool
        picked.add(int(rng.integers(1, 1 << 30)))
    seeds = sorted(picked)
    body = {"schema": "flylaya.m5.sealedseeds.v1", "n": n, "rng_seed": rng_seed,
            "sealed_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
            "pool_hint": pool_hint, "seeds": seeds}
    body["sha256"] = hashlib.sha256(
        json.dumps({"n": n, "rng_seed": rng_seed, "seeds": seeds},
                   sort_keys=True).encode()).hexdigest()
    with open(out_path, "w") as f:
        json.dump(body, f, indent=1)
    os.chmod(out_path, 0o444)  # read-only: sealing is a one-way operation
    return body


def verify_seals(sealed_path, exploration_run_dirs=()):
    body = json.load(open(sealed_path))
    expect = hashlib.sha256(json.dumps(
        {"n": body["n"], "rng_seed": body["rng_seed"], "seeds": body["seeds"]},
        sort_keys=True).encode()).hexdigest()
    intact = expect == body["sha256"]
    sealed = set(body["seeds"])
    overlaps = {}
    for d in exploration_run_dirs:
        try:
            meta = _jsonl(os.path.join(d, "trajectory.jsonl"))[0]
        except Exception:
            continue
        if meta.get("seed") in sealed:
            overlaps[d] = meta["seed"]
    return {"intact": intact, "n_seeds": body["n"],
            "overlaps_with_exploration": overlaps,
            "usable_for_confirmation": intact and not overlaps}


# ----------------------------------------------------------------- CLI
def _collect_pairs(root, policy_a, policy_b):
    """RUNS_ROOT/<scene>/<policy>/<seed>/ → {(scene,seed): (runA, runB)}."""
    pairs = {}
    for scene in sorted(os.listdir(root)):
        sp = os.path.join(root, scene)
        if not os.path.isdir(sp):
            continue
        pa, pb = os.path.join(sp, policy_a), os.path.join(sp, policy_b)
        if not (os.path.isdir(pa) and os.path.isdir(pb)):
            continue
        for seed in sorted(set(os.listdir(pa)) & set(os.listdir(pb))):
            ra, rb = os.path.join(pa, seed), os.path.join(pb, seed)
            if os.path.exists(os.path.join(ra, "trajectory.jsonl")) and \
               os.path.exists(os.path.join(rb, "trajectory.jsonl")):
                pairs[(scene, int(seed) if seed.isdigit() else seed)] = \
                    (load_run(ra), load_run(rb))
    return pairs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="per-run metrics → metrics.json")
    p.add_argument("run_dir")

    p = sub.add_parser("pair-batch", help="paired H1/H2 analysis over a batch root")
    p.add_argument("root")
    p.add_argument("--laya", default="P_laya")
    p.add_argument("--yoked", default="P_yoked")
    p.add_argument("--h1-scenes", nargs="+", default=["S1_light_left", "S1_light_right"])
    p.add_argument("--h2-scenes", nargs="+", default=["S2_obstacle_left",
                                                      "S2_obstacle_right"])
    p.add_argument("--out", default=None)

    p = sub.add_parser("yoked-check", help="matching tolerance check for one pair")
    p.add_argument("laya_dir")
    p.add_argument("yoked_dir")

    p = sub.add_parser("seal-seeds", help="seal confirmation seeds (one-way)")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--out", default=os.path.join(HERE, "confirm_seeds.json"))
    p.add_argument("--rng-seed", type=int, default=None)

    p = sub.add_parser("verify-seals", help="verify sealed seeds + exploration overlap")
    p.add_argument("sealed_path")
    p.add_argument("--exploration", nargs="*", default=[])

    args = ap.parse_args()
    if args.cmd == "run":
        m = run_metrics(load_run(args.run_dir))
        out = os.path.join(args.run_dir, "metrics.json")
        json.dump(m, open(out, "w"), indent=1)
        print(json.dumps(m, indent=1)[:2000])
        print(f"wrote {out}")
    elif args.cmd == "pair-batch":
        all_pairs = _collect_pairs(args.root, args.laya, args.yoked)
        h1p = {k: v for k, v in all_pairs.items() if k[0] in args.h1_scenes}
        h2p = {k: v for k, v in all_pairs.items() if k[0] in args.h2_scenes}
        by_mirror = defaultdict(dict)
        for (sc, sd), v in h1p.items():
            by_mirror[sc].update({(sc, sd): v})
        rep = {"n_pairs_total": len(all_pairs),
               "h1": h1_verdict(by_mirror) if h1p else {"H1_pass": None,
                                                        "reason": "no h1 scene pairs"},
               "h2": h2_verdict(h2p) if h2p else {"H2_pass": None,
                                                  "reason": "no h2 scene pairs"}}
        out = args.out or os.path.join(args.root, "analysis.json")
        json.dump(rep, open(out, "w"), indent=1)
        print(json.dumps(rep, indent=1)[:3000])
        print(f"wrote {out}")
    elif args.cmd == "yoked-check":
        print(json.dumps(yoked_match_check(load_run(args.laya_dir),
                                           load_run(args.yoked_dir)), indent=1))
    elif args.cmd == "seal-seeds":
        body = seal_seeds(args.n, args.out, args.rng_seed)
        print(f"sealed {body['n']} seeds → {args.out} (read-only, sha256 {body['sha256'][:12]}…)")
    elif args.cmd == "verify-seals":
        print(json.dumps(verify_seals(args.sealed_path, args.exploration), indent=1))


if __name__ == "__main__":
    main()
