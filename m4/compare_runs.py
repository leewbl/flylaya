"""TASK-0001: compare old baseline (m4/runs) vs rerun under iteration-1 params.

Usage: python compare_runs.py OLD_DIR NEW_DIR
Prints a markdown report: per-config medians, guardrail verdicts (new run),
pooled KS separations for A-B / A-C / A-D / B-D, literature in-range counts.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "m3"))
import trajectory_stats as ts  # noqa: E402

KS_KEYS = ("speed", "omega_dps", "saccade_amp", "heading_sun_deg")
PAIRS = [("A_full", "B_no_laya"), ("A_full", "C_no_connectome"),
         ("A_full", "D_random_intent"), ("B_no_laya", "D_random_intent")]

MEDIAN_ROWS = [
    ("speed_p50 cm/s", "kinematics.speed_cm_s.p50"),
    ("sacc_rate Hz", "saccades.rate_hz"),
    ("sacc_amp_p50 deg", "saccades.amplitude_deg.p50"),
    ("rest_frac", "rest_bouts.frac_time"),
    ("sun_R", "phototaxis.heading_sun_angle_deg.circular_R"),
    ("occ_util", "occupancy.xy_top.utilization_frac"),
    ("switch_hz", "intent.switch_rate_hz"),
    ("arou_r", "intent.arousal_speed_pearson"),
    ("n_intents", "intent.n_unique_intents"),
]


def load(run_dir):
    reps, skipped = [], []
    for fn in sorted(os.listdir(run_dir)):
        if not fn.endswith(".jsonl"):
            continue
        try:
            reps.append(ts.analyze(os.path.join(run_dir, fn)))
        except Exception as e:  # truncated/in-flight file
            skipped.append(f"{fn}: {e}")
    return reps, skipped


def by_cfg(reps):
    d = {}
    for r in reps:
        d.setdefault(r["config"], []).append(r)
    return d


def dig(rep, dotted):
    v = rep
    for p in dotted.split("."):
        if not isinstance(v, dict) or p not in v:
            return None
        v = v[p]
    return v


def med(reps, dotted):
    vals = [v for v in (dig(r, dotted) for r in reps) if v is not None]
    return float(np.median(vals)) if vals else None


def omega_stats(reps):
    pooled = [x for r in reps for x in r["_dists"]["omega_dps"]]
    if not pooled:
        return None, None
    a = np.abs(np.asarray(pooled))
    return float(np.median(a)), float(np.mean(a > 300))


def fmt(v):
    return "-" if v is None else f"{v:.3g}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old_dir")
    ap.add_argument("new_dir")
    args = ap.parse_args()

    old, sk_o = load(args.old_dir)
    new, sk_n = load(args.new_dir)
    for tag, sk in (("old", sk_o), ("new", sk_n)):
        if sk:
            print(f">> WARN {tag} skipped {len(sk)} file(s): {'; '.join(sk)}")

    oc, nc = by_cfg(old), by_cfg(new)
    baselines = json.load(open(os.path.join(HERE, "..", "m3", "literature_baselines.json")))

    hdr = (["metric"] + [f"{c} old" for c in sorted(oc)] + [f"{c} new" for c in sorted(nc)])
    print("| " + " | ".join(hdr) + " |")
    print("|" + "---|" * len(hdr))

    def cells(pick):
        row = []
        for src in (oc, nc):
            for cfg in sorted(src):
                row.append(fmt(pick(src[cfg])))
        return row

    for label, dotted in MEDIAN_ROWS:
        print("| " + " | ".join([label] + cells(lambda r: med(r, dotted))) + " |")
    print("| " + " | ".join(["omega_p50 dps"] + cells(lambda r: omega_stats(r)[0])) + " |")
    print("| " + " | ".join(["omega>300dps frac"] + cells(lambda r: omega_stats(r)[1])) + " |")
    print("| " + " | ".join(["intent top-class share"] + cells(
        lambda r: float(np.median([max(x["intent"]["distribution"].values())
                                   for x in r])) if r else None)) + " |")

    print("\n## guardrails (new run)")
    print("| config | omega_p50<150 | omega>300 frac~0 | arou_r>0.3 | switch 0.1-1 | "
          "intents>=4 | top-class<80% |")
    print("|---|---|---|---|---|---|---|")
    for cfg in sorted(nc):
        reps = nc[cfg]
        p50, f300 = omega_stats(reps)
        ar = med(reps, "intent.arousal_speed_pearson")
        sw = med(reps, "intent.switch_rate_hz")
        ni = med(reps, "intent.n_unique_intents")
        shares = [max(r["intent"]["distribution"].values()) for r in reps
                  if dig(r, "intent.distribution")]
        ts_ = float(np.median(shares)) if shares else None
        print(f"| {cfg} | {'PASS' if p50 is not None and p50 < 150 else 'FAIL'} ({fmt(p50)}) | "
              f"{fmt(f300)} | {'PASS' if ar and ar > 0.3 else 'FAIL'} ({fmt(ar)}) | "
              f"{'PASS' if sw and 0.1 <= sw <= 1 else 'FAIL'} ({fmt(sw)}) | "
              f"{'PASS' if ni and ni >= 4 else 'FAIL'} ({fmt(ni)}) | "
              f"{'PASS' if ts_ is not None and ts_ < 0.8 else 'FAIL'} ({fmt(ts_)}) |")

    print("\n## pooled KS separations old -> new (D, p)")
    for a, b in PAIRS:
        for key in KS_KEYS:
            line = f"- {a}-{b} {key}: "
            for src in (oc, nc):
                if a in src and b in src:
                    da = [x for r in src[a] for x in r["_dists"][key]]
                    db = [x for r in src[b] for x in r["_dists"][key]]
                    if da and db:
                        d, p = ts.ks2samp(da, db)
                        line += f"D={d:.3f} p={p:.1e} "
                else:
                    line += "MISSING "
            print(line)

    print("\n## literature in-range (median of per-seed counts)")
    n_checks = None
    for tag, src in (("old", oc), ("new", nc)):
        for cfg in sorted(src):
            counts = []
            for r in src[cfg]:
                verdicts = ts.check_baselines(r, baselines)
                n_checks = len(verdicts)
                counts.append(sum(1 for v in verdicts.values() if v["in_range"]))
            print(f"- {tag} {cfg}: {int(np.median(counts))}/{n_checks} "
                  f"(per-seed {min(counts)}-{max(counts)})")


if __name__ == "__main__":
    main()
