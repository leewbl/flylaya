"""迭代①验收: v1.1 state(±采样旋钮) vs 基线 A_full_11.

指标: switch_rate_hz (目标 0.1–1), 意图分布 (≥4/5 类且无单类>80%),
回归护栏: rest_frac / speed_p50 / omega_p50 不劣化到 B 档。
"""
import json
import sys

sys.path.insert(0, "../m3")
import trajectory_stats as ts

NEW = sys.argv[1] if len(sys.argv) > 1 else "iter1_smoke/A_full_11.jsonl"
BASE = sys.argv[2] if len(sys.argv) > 2 else "runs/A_full_11.jsonl"


def report(path, label):
    r = ts.analyze(path)
    frames = [json.loads(l) for l in open(path) if '"type"' not in l]
    from collections import Counter
    dist = Counter(f["intent"] for f in frames)
    n = len(frames)
    dur = frames[-1]["t"] - frames[0]["t"]
    print(f"\n== {label} ({path}, {dur:.0f}s) ==")
    print(f"switch_hz   : {r['intent']['switch_rate_hz']:.4f}   (目标 0.1–1)")
    import numpy as np
    yaws = [f["yaw"] for f in frames]
    om = [abs((yaws[i+1] - yaws[i] + 180) % 360 - 180) / 0.1 for i in range(len(yaws) - 1)]
    print(f"omega_p50   : {np.percentile(om, 50):.0f} dps")
    print(f"rest_frac   : {r['rest_bouts']['frac_time']:.3f}")
    print(f"sacc_rate   : {r['saccades']['rate_hz']:.3f} Hz")
    print(f"occ_util    : {r['occupancy']['xy_top']['utilization_frac']:.3f}")
    print(f"arou_r      : {r['intent']['arousal_speed_pearson']:.3f}")
    for k, v in dist.most_common():
        flag = " <-- >80%" if v / n > 0.8 else ""
        print(f"  {k:<16} {v/n*100:5.1f}%{flag}")
    n_cls = len(dist)
    print(f"classes     : {n_cls}/5 (验收 ≥4)")
    return r


report(BASE, "基线 (v1 state)")
report(NEW, "迭代① (v1.1 state)")
