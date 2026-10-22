"""M5 W5 盲评聚合 — 导出可复算 + 泄漏审计.

用法:
  python3 aggregate.py --key m5/viewer/blind_key.json e1.json e2.json [e3.json ...]

  - 连接 blind_key.json 把匿名 clip id 还原成 config
  - 丢弃 training 记录
  - Q1(任务判断)/Q2(偏好) 分列: 各自一致率 + Gwet AC1(主) + Fleiss κ(附, 边际偏斜解释)
  - Q2 偏好映射 chose-A; 无真实参照时输出限定为『方案间人类偏好』
  - 聚类披露: 同一 clip 对被多名评分者重复评价, 按唯一对数与评分者分层报告,
    不把每次点击当独立样本
  - 审计导出文件本身不得含 truth/config/seed/文件名字段

与 consistency.py 的区别: 那是 m4 旧批(导出含 truth)的复算器; 本件面向 v2 盲评导出.
"""
import argparse
import glob
import json
import math
import sys
from collections import Counter, defaultdict


def load_export(path, key):
    d = json.load(open(path))
    leaks = [f for f in ("truth", "config", "seed", "run", "brain", "intent_source")
             if f in json.dumps(d)]
    recs = [r for r in d["records"] if not r.get("training")]
    return d.get("rater", path), recs, leaks


def ac1_fleiss(mat, R):
    """mat: [trial][rater] 0/1; returns po, fleiss, ac1."""
    n = len(mat)
    po = sum((sum(col) ** 2 + (R - sum(col)) ** 2 - R) for col in mat)
    po /= n * R * (R - 1)
    p = sum(sum(col) for col in mat) / (n * R)
    pe = p * p + (1 - p) * (1 - p)
    fleiss = float("nan") if pe >= 1 else (po - pe) / (1 - pe)
    pe1 = 2 * p * (1 - p)
    ac1 = (po - pe1) / (1 - pe1) if pe1 < 1 else float("nan")
    return po, fleiss, ac1


def agree_stats(trial_choice, raters, question):
    """trial_choice[(tid, side_key)][rater] = 0/1 (chose A for Q2 / chose L for Q1)."""
    keys = sorted(trial_choice.keys())
    mat = [[trial_choice[k].get(r, None) for r in raters] for k in keys]
    mat = [[c for c in col if c is not None] for col in mat if
           sum(c is not None for c in col) >= 2]
    if not mat:
        return None
    R = max(len(col) for col in mat)
    sub = [[c for c in col if c is not None] for col in mat]
    # Fleiss/AC1 need equal rater counts per trial; use trials where all raters present
    full = [col for col in mat if len(col) == R]
    out = {"n_trials_used": len(full), "R": R}
    if len(full) >= 2 and R >= 2:
        po, fl, ac = ac1_fleiss(full, R)
        out.update({"P_o": round(po, 4), "fleiss_kappa": round(fl, 3),
                    "gwet_AC1": round(ac, 3)})
    # pairwise raw agreement
    pa = {}
    for i in range(len(raters)):
        for j in range(i + 1, len(raters)):
            keys_ij = [k for k in keys
                       if raters[i] in trial_choice[k] and raters[j] in trial_choice[k]]
            if not keys_ij:
                continue
            a = sum(trial_choice[k][raters[i]] == trial_choice[k][raters[j]]
                    for k in keys_ij) / len(keys_ij)
            pa[f"{raters[i]}-{raters[j]}"] = round(a, 3)
    out["pairwise_agree"] = pa
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("exports", nargs="+")
    args = ap.parse_args()

    key = json.load(open(args.key))["clips"]
    files = []
    for a in args.exports:
        files.extend(sorted(glob.glob(a)) if any(c in a for c in "*?") else [a])
    if len(files) < 2:
        sys.exit("need >= 2 rater export files")

    raters, leaks_all = [], []
    # Q2: chose-A binary per (tid, unordered clip pair)
    q2_choice = defaultdict(dict)
    # Q1: task judgment — chosen SIDE of the *A clip* (does rater pick the A
    # segment as "clearer goal"?); report both chose-A rate and raw L-consistency
    q1_choice = defaultdict(dict)
    pair_raters = defaultdict(set)
    a_picks = a_total = 0
    pair_scores = defaultdict(list)  # (cidA, cidX) -> rating diffs

    for f in files:
        rater, recs, leaks = load_export(f, key)
        leaks_all += [f"{f}:{l}" for l in leaks]
        raters.append(rater)
        for r in recs:
            cl, cr = r["clip_l"], r["clip_r"]
            cfgL = key.get(cl, {}).get("config", "?")
            cfgR = key.get(cr, {}).get("config", "?")
            k = tuple(sorted([cl, cr]))
            pair_raters[k].add(rater)
            a_side = "L" if cfgL == "A_full" else ("R" if cfgR == "A_full" else None)
            # Q2 preference -> chose-A binary
            if r.get("q2_choice"):
                if a_side:
                    chose_a = 1 if r["q2_choice"] == a_side else 0
                    q2_choice[(r["tid"], k)][rater] = chose_a
                    a_picks += chose_a
                    a_total += 1
            # Q1 task judgment -> same binary basis (chose A segment as clearer)
            if r.get("q1_choice"):
                if a_side:
                    q1_choice[(r["tid"], k)][rater] = 1 if r["q1_choice"] == a_side else 0
            if a_side:
                ra = r["rating_l"] if a_side == "L" else r["rating_r"]
                rx = r["rating_r"] if a_side == "L" else r["rating_l"]
                pair_scores[k].append(ra - rx)

    print(f"raters: {raters}")
    print(f"audit: export-file truth leak -> {leaks_all or 'NONE (ok)'}")
    if a_total:
        pmf = lambda kk: math.comb(a_total, kk) * 0.5 ** a_total
        p1 = sum(pmf(kk) for kk in range(a_picks, a_total + 1))
        print(f"\n== Q2 方案间偏好(无真实参照口径) ==")
        print(f"A-side chosen {a_picks}/{a_total} = {a_picks / a_total:.1%}  "
              f"(binomial one-sided p={p1:.2e})")
    st2 = agree_stats(q2_choice, raters, "Q2")
    if st2:
        print("Q2 agreement:", json.dumps(st2))
    st1 = agree_stats(q1_choice, raters, "Q1")
    print("\n== Q1 任务判断(chose-A 侧一致性, 附) ==")
    if st1:
        print("Q1 agreement:", json.dumps(st1))

    # clustering disclosure
    n_pairs = len(pair_raters)
    multi = {k: v for k, v in pair_raters.items() if len(v) > 1}
    print(f"\n== 聚类披露 ==")
    print(f"unique clip pairs: {n_pairs}; evaluated by >1 rater: {len(multi)}; "
          f"总记录 {a_total} 不是 {n_pairs} 个独立样本")
    if pair_scores:
        diffs = [d for v in pair_scores.values() for d in v]
        mean = sum(diffs) / len(diffs)
        print(f"A-X rating diff: mean {mean:.2f} over {len(diffs)} ratings "
              f"(per-pair means 见下)")
        for k, v in sorted(pair_raters.items()):
            ms = pair_scores.get(k)
            if ms:
                print(f"  pair {'/'.join(k)}: raters {len(v)}, "
                      f"diff mean {sum(ms) / len(ms):.2f}")


if __name__ == "__main__":
    main()
