"""FlyLaya blind-rating agreement & significance (final report §1.2 recompute).

Usage:
  python3 consistency.py rater1.json rater2.json [rater3.json ...]
  python3 consistency.py 'flylaya_rating3d_*.json'   # glob ok

Computes, on forced_choice mapped to binary chose-A / chose-notA
(A = truth config A_full; prevalence-robust main metric = Gwet AC1):
  - per-config pick rate / mean rating, per-rater A-pick & A-rating
  - unanimous trials, raw pairwise agreement
  - Fleiss kappa, Gwet AC1, pairwise Cohen kappa
  - exact binomial (one/two-sided) for A picks
  - A-B paired rating diff, one-sample t

Conventions:
  - truth fields store 'A_full' for the A side but run names for others
    ('B_no_laya_22'); config family = name minus trailing seed.
  - Cohen kappa is 1.0 by definition when two raters agree perfectly
    (degenerate marginals make the classic formula 0/0).
  - AC1 chance term uses the q=2 form 2*p*(1-p).
"""
import glob
import json
import math
import re
import sys
from collections import Counter

SEED_RE = re.compile(r"_\d+$")


def norm_cfg(name):
    return SEED_RE.sub("", name)


def load(paths):
    raters = []
    for p in paths:
        d = json.load(open(p))
        rs = sorted(d["results"], key=lambda r: r["trial"])
        raters.append((d.get("rater", p), rs))
    n = len(raters[0][1])
    for name, rs in raters:
        assert len(rs) == n, f"{name}: {len(rs)} != {n} trials"
    return raters


def cfg_of(rec, side):
    return norm_cfg(rec["truth"][side])


def picked_cfg(rec):
    return cfg_of(rec, rec["forced_choice"])


def main(paths):
    raters = load(paths)
    n_trials = len(raters[0][1])
    R = len(raters)
    names = [name for name, _ in raters]

    # per-trial matrices
    binm = [[1 if picked_cfg(r) == "A_full" else 0 for r in rs]  # chose-A
            for _, rs in raters]
    raw_choice = [[picked_cfg(r) for r in rs] for _, rs in raters]

    a_picks = sum(sum(row) for row in binm)
    total = n_trials * R

    # ---- per-config (aggregated by family) ----
    picks, apps, ratings = Counter(), Counter(), {}
    for _, rs in raters:
        for r in rs:
            for side in ("left", "right"):
                c = cfg_of(r, side)
                apps[c] += 1
                ratings.setdefault(c, []).append(r[f"rating_{side}"])
            picks[picked_cfg(r)] += 1
    print("== per-config (merged over raters) ==")
    for c in sorted(apps):
        m = sum(ratings[c]) / len(ratings[c])
        pk = f"{picks.get(c, 0)}/{apps[c]}" if c != "A_full" else f"{a_picks}/{total}"
        print(f"  {c:18s} picked {pk:>9s}   mean rating {m:.2f} (n={apps[c]})")

    # ---- per rater (A-side mean rating over ALL trials) ----
    print("== per rater ==")
    for (name, rs), row in zip(raters, binm):
        ar = [r[f"rating_{r['forced_choice']}"] if row[i] == 1 else
              r[f"rating_{'right' if r['forced_choice'] == 'left' else 'left'}"]
              for i, r in enumerate(rs)]
        print(f"  {name:6s} A picks {sum(row)}/{n_trials}   "
              f"mean A rating {sum(ar) / len(ar):.2f}")

    # ---- unanimity ----
    unan = sum(1 for t in range(n_trials)
               if len({raw_choice[r][t] for r in range(R)}) == 1)
    print(f"== unanimity == {unan}/{n_trials} trials all-same-run")

    # ---- Fleiss kappa (binary) ----
    po = sum((sum(row[t] for row in binm) ** 2
              + (R - sum(row[t] for row in binm)) ** 2 - R)
             for t in range(n_trials)) / (n_trials * R * (R - 1))
    p_a = a_picks / total
    pe = p_a ** 2 + (1 - p_a) ** 2
    fleiss = float("nan") if pe >= 1.0 else (po - pe) / (1 - pe)
    print("== agreement (binary chose-A) ==")
    print(f"  P_o={po:.4f}  P_e={pe:.4f}")
    print(f"  Fleiss kappa = {fleiss:.3f}")

    # ---- Gwet AC1 (q=2) ----
    pe_ac1 = 2 * p_a * (1 - p_a)
    ac1 = (po - pe_ac1) / (1 - pe_ac1)
    print(f"  Gwet AC1     = {ac1:.3f}   (P_e(AC1)={pe_ac1:.4f})")

    # ---- pairwise Cohen kappa + raw agreement ----
    print("== pairwise ==")
    for i in range(R):
        for j in range(i + 1, R):
            a = sum(binm[i][t] == binm[j][t] for t in range(n_trials)) / n_trials
            pi, pj = sum(binm[i]) / n_trials, sum(binm[j]) / n_trials
            peij = pi * pj + (1 - pi) * (1 - pj)
            if a >= 1.0:
                k = 1.0  # perfect agreement convention (degenerate marginals)
            elif peij >= 1.0:
                k = float("nan")
            else:
                k = (a - peij) / (1 - peij)
            print(f"  {names[i]}-{names[j]}: agree {a:.3f}  Cohen kappa {k:.3f}")

    # ---- binomial on A picks ----
    pmf = lambda kk: math.comb(total, kk) * 0.5 ** total
    p_obs = pmf(a_picks)
    p1 = sum(pmf(kk) for kk in range(a_picks, total + 1))
    p2 = min(1.0, sum(pmf(kk) for kk in range(total + 1)
                      if pmf(kk) <= p_obs * (1 + 1e-12)))
    print("== significance ==")
    print(f"  A picked {a_picks}/{total}: binomial one-sided p={p1:.2e}, "
          f"two-sided p={p2:.2e}")

    # ---- A-B paired rating diff ----
    diffs = []
    for _, rs in raters:
        for r in rs:
            cl, cr = cfg_of(r, "left"), cfg_of(r, "right")
            if {cl, cr} == {"A_full", "B_no_laya"}:
                ra = r["rating_left"] if cl == "A_full" else r["rating_right"]
                rb = r["rating_right"] if cl == "A_full" else r["rating_left"]
                diffs.append(ra - rb)
    if diffs:
        nn = len(diffs)
        mean = sum(diffs) / nn
        var = sum((d - mean) ** 2 for d in diffs) / (nn - 1)
        print(f"  A-B rating diff: mean {mean:.2f}, n={nn}, "
              f"t({nn - 1})={mean / math.sqrt(var / nn):.1f}")
    else:
        print("  A-B rating diff: no A-B pairs present")


if __name__ == "__main__":
    args = sys.argv[1:]
    files = []
    for a in args:
        files.extend(sorted(glob.glob(a)) if any(c in a for c in "*?") else [a])
    if len(files) < 2:
        raise SystemExit("need >= 2 rater JSONs")
    main(files)
