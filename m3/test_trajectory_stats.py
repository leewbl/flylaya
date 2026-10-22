"""Self-test for trajectory_stats.py on synthetic trajectories with known answers.

Deterministic (no RNG beyond seeded generators). Validates:
  saccade detector recovers injected amplitudes/rate
  segment split, rest-bout detection, straightness, kinematics
  phototaxis circular stats against a fixed sun
  margins against known obstacle geometry
  occupancy utilization/entropy on a confined box walk
  KS two-sample sanity (identical vs shifted distributions)
  end-to-end CLI run/compare on generated jsonl files

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python test_trajectory_stats.py
"""
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trajectory_stats as ts

DT = 0.1
FAIL = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAIL.append(name)


def write_traj(path, meta, rows):
    with open(path, "w") as f:
        if meta is not None:
            f.write(json.dumps({"type": "meta", **meta}) + "\n")
        for r in rows:
            f.write(json.dumps(r) + "\n")


def traj_rows(t, pos, yaw, speed, intent="explore", arousal=None):
    arousal = np.full(len(t), 1.0) if arousal is None else arousal
    return [{"t": float(ti), "pos": [float(p[0]), float(p[1]), float(p[2])],
             "yaw": float(yi), "pitch": 0.0, "speed": float(si),
             "intent": intent, "intent_conf": 0.5, "arousal": float(ai)}
            for ti, p, yi, si, ai in zip(t, pos, yaw, speed, arousal)]


# ---------------------------------------------------------------- 1. saccades
n = 600
t = np.arange(n) * DT
yaw = np.zeros(n)
# inject a 90 deg saccade every 3 s: constant yaw-rate burst of 900 dps for 0.1 s
amp_deg, rate_dps = 90.0, 900.0
burst_len = int(amp_deg / rate_dps / DT)  # 1 frame at 900 dps -> 90 deg in 0.1s
per = int(3.0 / DT)
n_sac = 0
for start in range(per, n - burst_len, per):
    yaw[start:start + burst_len] += rate_dps * DT
    n_sac += 1
yaw = np.cumsum(yaw)
pos = np.column_stack([np.cumsum(np.cos(np.deg2rad(yaw))) * 30 * DT,
                       np.cumsum(np.sin(np.deg2rad(yaw))) * 30 * DT,
                       np.zeros(n)])
rows = traj_rows(t, pos, yaw, np.full(n, 30.0))
meta = {"config": "T_saccade", "seed": 1, "arena": {"size_cm": 100},
        "obstacles": [], "sun": {"azimuth_deg": 0.0, "elevation_deg": 30}, "dt": DT}
p1 = os.path.join(tempfile.mkdtemp(), "sac.jsonl")
write_traj(p1, meta, rows)
rep = ts.analyze(p1)
s = rep["saccades"]
check("saccade count recovered", s["n"] == n_sac, f"{s['n']} vs {n_sac}")
check("saccade amplitude ~90deg", abs((s["amplitude_deg"]["p50"] or 0) - 90.0) < 12,
      f"p50={s['amplitude_deg']['p50']}")
check("saccade rate ~1/3s", abs(s["rate_hz"] - 1 / 3) < 0.1, f"{s['rate_hz']:.3f}")
check("peak angular velocity ~900dps", abs((s["peak_angular_velocity_dps"]["p50"] or 0) - 900) < 120,
      f"p50={s['peak_angular_velocity_dps']['p50']}")

# ---------------------------------------------------------------- 2. straight line + rest
n2 = 400
yaw2 = np.zeros(n2)
pos2 = np.column_stack([np.arange(n2) * 30 * DT, np.zeros(n2), np.zeros(n2)])
speed2 = np.full(n2, 30.0)
speed2[300:340] = 1.0  # 4 s rest bout (>=0.5s)
rows2 = traj_rows(np.arange(n2) * DT, pos2, yaw2, speed2)
p2 = os.path.join(os.path.dirname(p1), "line.jsonl")
write_traj(p2, {**meta, "config": "T_line"}, rows2)
rep2 = ts.analyze(p2)
check("straightness ~1.0", rep2["kinematics"]["straightness_index"] > 0.99,
      f"{rep2['kinematics']['straightness_index']:.4f}")
check("rest bout detected ~4s", rep2["rest_bouts"]["n"] == 1
      and abs(rep2["rest_bouts"]["total_s"] - 4.0) < 0.2,
      f"n={rep2['rest_bouts']['n']} total={rep2['rest_bouts']['total_s']}")
check("segments >=1 long straight", (rep2["segments"]["arc_cm"]["p90"] or 0) > 100,
      f"p90={rep2['segments']['arc_cm']['p90']}")

# ---------------------------------------------------------------- 3. phototaxis (orbit at fixed rel angle)
n3 = 1000
sun_az = 120.0
heading = np.full(n3, sun_az + 45.0)  # constant 45 deg off-sun
pos3 = np.column_stack([50 + 20 * np.cos(np.arange(n3) * 0.02),
                        50 + 20 * np.sin(np.arange(n3) * 0.02),
                        50 + 5 * np.sin(np.arange(n3) * 0.01)])
rows3 = traj_rows(np.arange(n3) * DT, pos3, heading, np.full(n3, 40.0))
p3 = os.path.join(os.path.dirname(p1), "orbit.jsonl")
write_traj(p3, {**meta, "config": "T_orbit", "sun": {"azimuth_deg": sun_az, "elevation_deg": 30}}, rows3)
rep3 = ts.analyze(p3)
h = rep3["phototaxis"]["heading_sun_angle_deg"]
check("circular R ~1 (constant rel angle)", h["circular_R"] > 0.99, f"R={h['circular_R']:.4f}")
check("mean dir ~45deg", abs(h["mean_dir"] - 45.0) < 1.0, f"{h['mean_dir']:.2f}")
check("frac within 30deg = 0 at 45 off-sun", h["frac_within_30deg_of_sun"] == 0.0,
      f"{h['frac_within_30deg_of_sun']}")

# ---------------------------------------------------------------- 4. margins
meta4 = {**meta, "config": "T_margin",
         "obstacles": [{"x": 70, "y": 50, "r": 5, "h": 100}]}  # center (70,50) r5
n4 = 100
pos4 = np.column_stack([np.full(n4, 50.0), np.full(n4, 50.0), np.full(n4, 50.0)])  # 20cm from axis
rows4 = traj_rows(np.arange(n4) * DT, pos4, np.zeros(n4), np.full(n4, 0.5))
p4 = os.path.join(os.path.dirname(p1), "margin.jsonl")
write_traj(p4, meta4, rows4)
rep4 = ts.analyze(p4)
m = rep4["margins"]
check("obstacle margin = 20-5 = 15cm", abs((m["obstacle_margin_cm"]["p50"] or 0) - 15.0) < 0.6,
      f"p50={m['obstacle_margin_cm']['p50']}")
check("wall margin = 50 (min axis dist at center)", abs((m["min_any_margin_cm"]["p50"] or 0) - 15.0) < 0.6,
      f"p50={m['min_any_margin_cm']['p50']}")

# ---------------------------------------------------------------- 5. occupancy
n5 = 500
pos5 = np.column_stack([25 + 50 * (np.arange(n5) % 2), 50 + np.zeros(n5), 50 + np.zeros(n5)])
rows5 = traj_rows(np.arange(n5) * DT, pos5, np.zeros(n5), np.full(n5, 10.0))
p5 = os.path.join(os.path.dirname(p1), "occ.jsonl")
write_traj(p5, {**meta, "config": "T_occ"}, rows5)
rep5 = ts.analyze(p5)
occ = rep5["occupancy"]["xy_top"]
check("occupancy: 2 of 100 bins used -> utilization 0.02", abs(occ["utilization_frac"] - 0.02) < 1e-9,
      f"{occ['utilization_frac']}")
check("occupancy entropy max = ln2/ln100", abs(occ["entropy_norm"] - math.log(2) / math.log(100)) < 1e-9,
      f"{occ['entropy_norm']:.6f}")

# ---------------------------------------------------------------- 6. intent stats + KS
d1, p1ks = ts.ks2samp(rep["_dists"]["speed"], rep["_dists"]["speed"])
d2, p2ks = ts.ks2samp(rep["_dists"]["speed"], rep4["_dists"]["speed"])  # 30 vs 0.5 cm/s: disjoint
check("KS identical -> D=0 p=1", d1 == 0.0 and p1ks > 0.99, f"D={d1} p={p1ks}")
check("KS disjoint -> D=1 p~0", d2 == 1.0 and p2ks < 1e-6, f"D={d2} p={p2ks:.1e}")
check("KS small-D regime -> p=1", ts.ks2samp(rep2["_dists"]["speed"], rep["_dists"]["speed"])[0] - 0.1 < 1e-9,
      f"D={ts.ks2samp(rep2['_dists']['speed'], rep['_dists']['speed'])[0]} (rest-bout overlap)")
intents = ["explore"] * 50 + ["phototaxis"] * 50
rows6 = traj_rows(np.arange(100) * DT, pos5[:100], np.zeros(100), np.full(100, 10.0))
for r, it in zip(rows6, intents):
    r["intent"] = it
p6 = os.path.join(os.path.dirname(p1), "intent.jsonl")
write_traj(p6, {**meta, "config": "T_intent"}, rows6)
rep6 = ts.analyze(p6)
check("intent dist 50/50", abs(rep6["intent"]["distribution"]["explore"] - 0.5) < 1e-9)
check("switch rate = 1 switch / 10 s = 0.1Hz", abs(rep6["intent"]["switch_rate_hz"] - 0.1) < 1e-9,
      f"{rep6['intent']['switch_rate_hz']}")

# ---------------------------------------------------------------- 7. CLI end-to-end
out_metrics = os.path.join(os.path.dirname(p1), "m.json")
out_md = os.path.join(os.path.dirname(p1), "t.md")
env = dict(os.environ)
r_run = subprocess.run([sys.executable, os.path.abspath("trajectory_stats.py"), "run", p1,
                        "-o", out_metrics], capture_output=True, text=True, cwd=os.path.dirname(
                            os.path.abspath(__file__)))
check("CLI run exits 0", r_run.returncode == 0, r_run.stderr[-200:])
check("CLI run writes metrics json", os.path.exists(out_metrics) and
      json.load(open(out_metrics))["saccades"]["n"] == n_sac)
r_cmp = subprocess.run([sys.executable, os.path.abspath("trajectory_stats.py"), "compare",
                        out_metrics, out_metrics, "-o", out_md], capture_output=True, text=True)
check("CLI compare exits 0 and writes md", r_cmp.returncode == 0 and os.path.exists(out_md),
      r_cmp.stderr[-200:])

print(f"\n{'SELF-TEST OK' if not FAIL else 'SELF-TEST FAILED: ' + ', '.join(FAIL)}")
sys.exit(1 if FAIL else 0)
