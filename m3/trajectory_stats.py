"""FlyLaya M3 (1/3): trajectory statistics module.

Computes the trajectory-metric suite used to judge fly-likeness of the four
ablation configs against literature baselines (plan §4, criterion 1):

  kinematics        path length, net displacement, straightness, speed percentiles
  saccades          yaw-rate peak detection -> amplitude/peak/duration dists + rate
  segments          straight-flight segments between saccades / rest bouts
  rest_bouts        low-speed hovering episodes
  speed_psd         Welch power spectrum of speed & yaw rate
  phototaxis        heading-to-sun angular distribution (circular stats)
  margins           min distance to obstacle columns and walls over time
  occupancy         xy + xz heatmaps, utilization, entropy
  intent            distribution, switch rate, dwell, arousal-speed correlation
  ks2 / baseline    two-sample KS + literature-range checking (cross-config)

Input contract (trajectory jsonl; first line optional meta):
  {"type":"meta","config":"A_full","seed":11,"brain":"connectome",
   "intent_source":"laya","arena":{"size_cm":100},
   "obstacles":[{"x":20,"y":30,"r":3,"h":60}],
   "sun":{"azimuth_deg":120,"elevation_deg":35},"dt":0.1}
  {"t":0.0,"pos":[50,50,50],"yaw":10.0,"pitch":0.0,"speed":30.0,
   "intent":"explore","intent_conf":0.62,"arousal":1.2}

pos in cm within [0,size]; yaw/pitch in deg (yaw: heading in xy-plane,
0 = +x, CCW positive); speed cm/s. Missing intent/arousal fields tolerated.
Run with /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python (numpy).

CLI:
  trajectory_stats.py run   traj.jsonl [-o metrics.json]
  trajectory_stats.py compare a.json b.json [...] [-o table.md]
  trajectory_stats.py baseline metrics.json literature_baselines.json
"""
import json
import math
import sys

import numpy as np

# ----------------------------------------------------------------- loading


def load_trajectory(path):
    meta, rows = {}, []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("type") == "meta":
                meta = d
            else:
                rows.append(d)
    if not rows:
        raise ValueError(f"no frames in {path}")
    return meta, rows


def _cols(rows, key, n=3):
    out = []
    for r in rows:
        v = r.get(key)
        out.append(v if isinstance(v, (list, tuple)) else [None] * n)
    return np.array(out, dtype=float)


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


# ----------------------------------------------------------------- metrics


def kinematics(pos, speed, dt):
    step = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    path = float(step.sum())
    net = float(np.linalg.norm(pos[-1] - pos[0]))
    return {
        "duration_s": float(len(pos) * dt),
        "path_length_cm": path,
        "net_displacement_cm": net,
        "straightness_index": net / path if path > 0 else 0.0,
        "speed_cm_s": {
            "mean": float(np.mean(speed)), "p10": float(np.percentile(speed, 10)),
            "p50": float(np.percentile(speed, 50)), "p90": float(np.percentile(speed, 90)),
        },
    }


def yaw_series(yaw_deg, dt):
    """Unwrapped yaw (rad) and its rate omega (rad/s)."""
    y = np.unwrap(np.deg2rad(np.asarray(yaw_deg, dtype=float)))
    omega = np.diff(y) / dt
    return y, omega


def detect_saccades(omega, dt, thresh_dps=300.0, refractory_s=0.10):
    """Peak detection on yaw rate; classic saccade criterion |omega|>thresh.

    Returns list of dicts (peak_dps signed, amplitude_deg, duration_s, sign).
    """
    thresh = math.radians(thresh_dps)
    events, i, n = [], 0, len(omega)
    refractory = max(1, int(round(refractory_s / dt)))
    while i < n:
        if abs(omega[i]) > thresh:
            j = i
            while j < n and abs(omega[j]) > thresh * 0.5:  # event tail at half-threshold
                j += 1
            seg = omega[i:j]
            peak = float(seg[np.argmax(np.abs(seg))])
            events.append({
                "peak_dps": float(math.degrees(peak)),
                "amplitude_deg": float(math.degrees(sum(seg) * dt)),
                "duration_s": float(len(seg) * dt),
                "sign": 1 if peak > 0 else -1,
            })
            i = j + refractory
        else:
            i += 1
    return events


def saccade_stats(events, duration_s):
    amps = np.array([abs(e["amplitude_deg"]) for e in events]) if events else np.array([])
    peaks = np.array([abs(e["peak_dps"]) for e in events]) if events else np.array([])
    durs = np.array([e["duration_s"] for e in events]) if events else np.array([])
    return {
        "n": len(events),
        "rate_hz": len(events) / duration_s if duration_s > 0 else 0.0,
        "amplitude_deg": {"p10": _p(amps, 10), "p50": _p(amps, 50), "p90": _p(amps, 90)},
        "peak_angular_velocity_dps": {"p50": _p(peaks, 50), "p90": _p(peaks, 90)},
        "duration_ms": {"p50": 1000 * _p(durs, 50) if len(durs) else None},
        "left_right_balance": (sum(e["sign"] > 0 for e in events) / len(events)) if events else None,
    }


def _p(a, q):
    return float(np.percentile(a, q)) if len(a) else None


def rest_bouts(speed, dt, thresh=5.0, min_s=0.5):
    """Low-speed episodes >= min_s; returns list of durations."""
    slow = speed < thresh
    bouts, i, n = [], 0, len(slow)
    while i < n:
        if slow[i]:
            j = i
            while j < n and slow[j]:
                j += 1
            d = (j - i) * dt
            if d >= min_s:
                bouts.append(d)
            i = j
        else:
            i += 1
    return bouts


def segments(pos, omega, dt, omega_thresh_dps=100.0):
    """Straight-flight segments: split where |omega| exceeds a low threshold."""
    big = np.abs(omega) > math.radians(omega_thresh_dps)
    cuts = [0] + [i + 1 for i in range(len(big)) if big[i]] + [len(pos)]
    segs = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 3:
            continue
        pts = pos[a:b + 1]
        arc = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
        straight = float(np.linalg.norm(pts[-1] - pts[0]))
        segs.append({"arc_cm": arc, "straight_cm": straight,
                     "duration_s": float((b - a) * dt)})
    return segs


def welch_psd(x, dt, nseg=256, overlap=0.5):
    """Minimal Welch (hann window, 50% overlap); returns (freqs, psd)."""
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    hop = max(1, int(nseg * (1 - overlap)))
    win = np.hanning(nseg)
    nfft = 1 << int(math.ceil(math.log2(nseg)))
    acc, cnt = np.zeros(nfft // 2 + 1), 0
    for start in range(0, len(x) - nseg + 1, hop):
        seg = x[start:start + nseg] * win
        acc += abs(np.fft.rfft(seg, nfft)) ** 2
        cnt += 1
    if cnt == 0:
        return None
    psd = acc / cnt / (dt * (win ** 2).sum())
    freqs = np.fft.rfftfreq(nfft, dt)
    return freqs, psd


def phototaxis(yaw_deg, pitch_deg, speed, pos, sun):
    """Angular distribution of heading relative to sun azimuth + climb coupling."""
    az = math.radians(sun["azimuth_deg"])
    rel = wrap180(yaw_deg - sun["azimuth_deg"])
    rel_rad = np.deg2rad(rel)
    # circular stats (heading weighted uniformly over frames)
    C, S = np.cos(rel_rad).mean(), np.sin(rel_rad).mean()
    R = float(math.hypot(C, S))
    mean_dir = float(math.degrees(math.atan2(S, C)))
    dz = np.diff(pos[:, 2]) if pos.shape[1] == 3 else np.zeros(1)
    climb = np.concatenate([[0.0], dz])
    sun_up = sun.get("elevation_deg", 0) > 0
    r_climb = (float(np.corrcoef(climb, np.cos(rel_rad))[0, 1])
               if pos.shape[1] == 3 and np.std(climb) > 0 else None)
    return {
        "heading_sun_angle_deg": {
            "mean_dir": mean_dir, "circular_R": R,
            "frac_within_30deg_of_sun": float(np.mean(np.abs(rel) <= 30)),
            "frac_within_30deg_of_antisun": float(np.mean(np.abs(np.abs(rel) - 180) <= 30)),
            "p10": _p(rel, 10), "p50": _p(rel, 50), "p90": _p(rel, 90),
        },
        "climb_vs_sun_elevation": {
            "sun_elevation_deg": sun.get("elevation_deg"),
            "sun_above_horizon": bool(sun_up),
            "pearson_climb_vs_cos_relheading": r_climb,
            "mean_climb_cm_per_s": float(np.mean(climb)) if len(climb) > 1 else None,
        },
        "_az_rad": az,
    }


def margins(pos, meta):
    """Per-frame min clearance to obstacle cylinders (xy, z-span aware) and walls."""
    size = float(meta.get("arena", {}).get("size_cm", 100.0))
    half = size / 2.0
    cx = pos[:, 0] - half
    cy = pos[:, 1] - half
    cz = pos[:, 2] - half if pos.shape[1] == 3 else np.zeros(len(pos))
    obs = meta.get("obstacles", [])
    min_obs = np.full(len(pos), np.inf)
    for o in obs:
        d = np.hypot(cx - (o["x"] - half), cy - (o["y"] - half)) - float(o["r"])
        in_span = (cz >= 0) & (cz <= float(o.get("h", size)))
        d = np.where(in_span, d, np.inf)
        min_obs = np.minimum(min_obs, d)
    wall = np.minimum(np.minimum(half - np.abs(cx), half - np.abs(cy)),
                      (half - np.abs(cz)) if pos.shape[1] == 3 else np.inf)
    total = np.minimum(min_obs, wall)
    return {
        "obstacle_margin_cm": {
            "p05": _p(min_obs[np.isfinite(min_obs)], 5) if np.isfinite(min_obs).any() else None,
            "p50": _p(min_obs[np.isfinite(min_obs)], 50) if np.isfinite(min_obs).any() else None,
        },
        "min_any_margin_cm": {"p05": _p(total, 5), "p50": _p(total, 50),
                              "frac_below_5cm": float(np.mean(total < 5.0))},
        "n_obstacles": len(obs),
    }


def occupancy(pos, size_cm=100.0, bins=10):
    """xy (top) and xz (side) occupancy heatmaps; utilization + normalized entropy."""
    half = size_cm / 2.0
    def grid(a, b):
        h, _, _ = np.histogram2d(a, b, bins=bins, range=[(-half, half)] * 2)
        return h
    xy = grid(pos[:, 0] - half, pos[:, 1] - half)
    xz = grid(pos[:, 0] - half, (pos[:, 2] - half) if pos.shape[1] == 3 else np.zeros(len(pos)))
    def stats(h):
        p = h.flatten().astype(float)
        p = p / p.sum() if p.sum() else p
        used = float(np.mean(p >= 0.01))
        nz = p[p > 0]
        ent = float(-(nz * np.log(nz)).sum() / math.log(len(p))) if len(nz) else 0.0
        return {"utilization_frac": used, "entropy_norm": ent,
                "max_bin_frac": float(p.max()) if len(p) else 0.0}
    return {"xy_top": stats(xy), "xz_side": stats(xz),
            "grid": {"bins": bins, "cm_per_bin": size_cm / bins}}


def intent_stats(rows, duration_s, dt=0.1):
    intents = [r.get("intent") for r in rows]
    arousal = np.array([r.get("arousal", np.nan) for r in rows], dtype=float)
    speed = np.array([r.get("speed", np.nan) for r in rows], dtype=float)
    dist = {}
    for it in intents:
        if it is not None:
            dist[it] = dist.get(it, 0) + 1
    n = len(intents)
    switches = sum(1 for a, b in zip(intents, intents[1:]) if a != b)
    dwell, cur = [], 1
    for a, b in zip(intents, intents[1:] + [None]):
        if a == b:
            cur += 1
        else:
            dwell.append(cur)
            cur = 1
    m = np.isnan(arousal) | np.isnan(speed)
    r = (float(np.corrcoef(arousal[~m], speed[~m])[0, 1])
         if (~m).sum() > 2 and np.std(arousal[~m]) > 0 else None)
    return {
        "distribution": {k: v / n for k, v in dist.items()} if n else {},
        "switch_rate_hz": switches / duration_s if duration_s > 0 else None,
        "mean_dwell_s": float(np.mean(dwell)) * dt if dwell else None,
        "arousal_speed_pearson": r,
        "n_unique_intents": len(dist),
    }

# ----------------------------------------------------------------- statistics


def ks2samp(a, b):
    """Two-sample Kolmogorov-Smirnov statistic and asymptotic p-value."""
    a, b = np.sort(np.asarray(a, float)), np.sort(np.asarray(b, float))
    if not len(a) or not len(b):
        return None, None
    allv = np.concatenate([a, b])
    cdf1 = np.searchsorted(a, allv, side="right") / len(a)
    cdf2 = np.searchsorted(b, allv, side="right") / len(b)
    d = float(np.max(np.abs(cdf1 - cdf2)))
    if d == 0.0:
        return 0.0, 1.0
    en = len(a) * len(b) / (len(a) + len(b))
    lam = (math.sqrt(en) + 0.12 + 0.11 / math.sqrt(en)) * d
    if lam <= 0.4:  # alternating series diverges for small lambda; p>0.97 there
        return d, 1.0
    p = 0.0
    for j in range(1, 101):
        p += 2 * (-1) ** (j - 1) * math.exp(-2 * j * j * lam * lam)
    return d, max(0.0, min(1.0, p))


def analyze(path):
    meta, rows = load_trajectory(path)
    dt = float(meta.get("dt", 0.1))
    pos = _cols(rows, "pos")
    yaw = np.array([r.get("yaw", np.nan) for r in rows], dtype=float)
    pitch = np.array([r.get("pitch", 0.0) for r in rows], dtype=float)
    speed = np.array([r.get("speed", np.nan) for r in rows], dtype=float)
    if np.isnan(yaw).any():  # derive from positions if yaw unlogged
        d = np.diff(pos[:, :2], axis=0)
        yaw = np.rad2deg(np.unwrap(np.arctan2(d[:, 1], d[:, 0])))
        yaw = np.concatenate([[yaw[0] if len(yaw) else 0.0], yaw])
    if np.isnan(speed).any():
        sp = np.linalg.norm(np.diff(pos, axis=0), axis=1) / dt
        speed = np.concatenate([[sp[0] if len(sp) else 0.0], sp])

    _, omega = yaw_series(yaw, dt)
    kin = kinematics(pos, speed, dt)
    dur = kin["duration_s"]
    events = detect_saccades(omega, dt)
    segs = segments(pos, omega, dt)
    rests = rest_bouts(speed, dt)
    spec = welch_psd(speed, dt)
    dom_hz = None
    if spec is not None and len(spec[1]) > 2:
        freqs, psd = spec
        dom_hz = float(freqs[int(np.argmax(psd[1:])) + 1])
    sun = meta.get("sun", {"azimuth_deg": 0.0, "elevation_deg": 0.0})
    photo = phototaxis(yaw, pitch, speed, pos, sun)
    photo.pop("_az_rad", None)
    seg_arc = np.array([s["arc_cm"] for s in segs]) if segs else np.array([])

    rep = {
        "source": path,
        "config": meta.get("config"), "seed": meta.get("seed"),
        "brain": meta.get("brain"), "intent_source": meta.get("intent_source"),
        "n_frames": len(rows), "dt": dt,
        "kinematics": kin,
        "saccades": saccade_stats(events, dur),
        "segments": {"n": len(segs),
                     "arc_cm": {"p50": _p(seg_arc, 50), "p90": _p(seg_arc, 90)},
                     "mean_straightness": (float(np.mean([s["straight_cm"] / s["arc_cm"]
                                                          for s in segs if s["arc_cm"] > 0]))
                                           if segs else None)},
        "rest_bouts": {"n": len(rests),
                       "total_s": float(sum(rests)),
                       "frac_time": float(sum(rests) / dur) if dur else 0.0},
        "speed_spectrum": {"dominant_hz": dom_hz},
        "phototaxis": photo,
        "margins": margins(pos, meta),
        "occupancy": occupancy(pos, float(meta.get("arena", {}).get("size_cm", 100.0))),
        "intent": intent_stats(rows, dur, dt),
        "_dists": {  # raw distributions for cross-config KS (not for the report table)
            "speed": speed.tolist(), "omega_dps": np.rad2deg(omega).tolist(),
            "saccade_amp": [abs(e["amplitude_deg"]) for e in events],
            "heading_sun_deg": wrap180(yaw - sun.get("azimuth_deg", 0.0)).tolist(),
        },
    }
    return rep




def compare(reports, out_md=None):
    """Pairwise KS on key distributions + summary markdown across configs."""
    rows, dists = [], {}
    for rep in reports:
        dists[rep["config"]] = rep["_dists"]
        s = rep["saccades"]
        rows.append({
            "config": rep["config"], "seed": rep.get("seed"),
            "speed_p50": rep["kinematics"]["speed_cm_s"]["p50"],
            "straightness": rep["kinematics"]["straightness_index"],
            "saccade_rate_hz": s["rate_hz"],
            "saccade_amp_p50": s["amplitude_deg"]["p50"],
            "rest_frac": rep["rest_bouts"]["frac_time"],
            "sun_R": rep["phototaxis"]["heading_sun_angle_deg"]["circular_R"],
            "sun_frac30": rep["phototaxis"]["heading_sun_angle_deg"]["frac_within_30deg_of_sun"],
            "margin_p05": rep["margins"]["min_any_margin_cm"]["p05"],
            "occ_util": rep["occupancy"]["xy_top"]["utilization_frac"],
            "intent_switch_hz": rep["intent"]["switch_rate_hz"],
            "arousal_speed_r": rep["intent"]["arousal_speed_pearson"],
        })
    ks = {}
    keys = list(dists)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            for dist_key in ("speed", "omega_dps", "heading_sun_deg", "saccade_amp"):
                d, p = ks2samp(dists[a][dist_key], dists[b][dist_key])
                if d is not None:
                    ks[f"{a}|{b}|{dist_key}"] = {"D": d, "p": p}
    lines = ["| config | seed | speed_p50 | straight | sacc_rate | sacc_amp_p50 | rest_frac | sun_R | sun_frac30 | margin_p05 | occ_util | switch_hz | arou_r |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| " + " | ".join(
            str(r[k]) if r[k] is not None else "-" for k in
            ("config", "seed", "speed_p50", "straightness", "saccade_rate_hz",
             "saccade_amp_p50", "rest_frac", "sun_R", "sun_frac30", "margin_p05",
             "occ_util", "intent_switch_hz", "arousal_speed_r")) + " |")
    lines.append("")
    lines.append("## pairwise KS (D, p) — config|config|distribution")
    for k, v in sorted(ks.items()):
        lines.append(f"- {k}: D={v['D']:.3f} p={v['p']:.2e}")
    md = "\n".join(lines)
    if out_md:
        with open(out_md, "w") as f:
            f.write(md + "\n")
    return {"summary": rows, "ks": ks, "markdown": md}


def check_baselines(metrics, baselines):
    """baselines.json: {"metric.path": [lo, hi] or {"range":[lo,hi], "note":...}}
    using dotted paths into the metrics report; returns per-metric verdicts."""
    def get(d, path):
        for part in path.split("."):
            if not isinstance(d, dict) or part not in d:
                return None
            d = d[part]
        return d
    out = {}
    for path, spec in baselines.items():
        rng = spec["range"] if isinstance(spec, dict) else spec
        v = get(metrics, path)
        out[path] = {
            "value": v, "range": rng,
            "in_range": (v is not None and rng[0] <= v <= rng[1]),
            "note": spec.get("note") if isinstance(spec, dict) else None,
        }
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode = argv[1]
    if mode == "run":
        rep = analyze(argv[2])
        out = argv[argv.index("-o") + 1] if "-o" in argv else None
        if out:
            with open(out, "w") as f:
                json.dump(rep, f, indent=2)
            print(f"wrote {out}")
        else:
            rep.pop("_dists", None)
            print(json.dumps(rep, indent=2))
    elif mode == "compare":
        files, i = [], 2
        while i < len(argv) and argv[i] != "-o":
            files.append(argv[i])
            i += 1
        reports = [json.load(open(p)) for p in files]
        out = argv[argv.index("-o") + 1] if "-o" in argv else None
        res = compare(reports, out)
        print(res["markdown"])
    elif mode == "baseline":
        metrics = json.load(open(argv[2]))
        baselines = json.load(open(argv[3]))
        print(json.dumps(check_baselines(metrics, baselines), indent=2))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
