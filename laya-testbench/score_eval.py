#!/usr/bin/env python3
"""laya-testbench scorer: unified metrics for Laya test rounds.

Usage:
  score_eval.py accuracy <results.jsonl>     # R3/R9: rows {id, lang, group, expected{...}, actual{...}, routing_model?}
  score_eval.py routing  <results.jsonl>     # R4: rows {id, expected_model, actual_model, detected?}
  score_eval.py ece      <results.jsonl>     # R2: rows {id, type, confidence, correct}
"""
import json
import sys
from collections import defaultdict


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def accuracy(rows):
    by = defaultdict(lambda: {"n": 0, "ok": 0, "err": []})
    soft_err = defaultdict(list)
    for r in rows:
        key_lang, key_type = r.get("lang", "?"), r.get("group", "?")
        exp, act = r["expected"], r["actual"]
        t = next(iter(exp))
        ok, detail = False, ""
        if t == "choice":
            ok = act.get("choice") == exp["choice"]
            detail = f'exp={exp["choice"]} got={act.get("choice")} p={act.get("probabilities", {}).get(act.get("choice"), "?")}'
        elif t == "score":
            d = abs(float(act.get("score", -9)) - float(exp["score"]))
            ok = d <= 0.5
            detail = f"exp={exp['score']} got={act.get('score')} |d|={d:.2f}"
            soft_err[key_lang].append(d)
        elif t == "noul":
            v = float(act.get("noul", 0.5))
            ok = (v >= 0.5) == bool(exp["noul"])
            detail = f"exp={exp['noul']} p={v}"
        for key in (f"{key_lang}|{t}", f"all|{t}", f"{key_lang}|ALL"):
            by[key]["n"] += 1
            by[key]["ok"] += ok
        if not ok:
            by[f"{key_lang}|{t}"]["err"].append(f'{r["id"]}: {detail} conf={act.get("confidence")}')
    out = {}
    for k in sorted(by):
        v = by[k]
        out[k] = {"n": v["n"], "acc": round(v["ok"] / v["n"], 4), "errors": v["err"]}
    for lang, ds in soft_err.items():
        out[f"{lang}|score_mae"] = round(sum(ds) / len(ds), 4)
    return out


def routing(rows):
    bad = [(r["id"], r["expected_model"], r["actual_model"]) for r in rows if r["expected_model"] != r["actual_model"]]
    return {"n": len(rows), "misrouted": len(bad), "rate": round(len(bad) / len(rows), 4), "detail": bad}


def _ece_brier(pts, bins):
    """Equal-count binned ECE (points sorted by confidence) + Brier score."""
    pts = sorted(pts)
    n = len(pts)
    nb = max(1, min(bins, n))
    chunks = [pts[i * n // nb: (i + 1) * n // nb] for i in range(nb)]
    e = 0.0
    for c in chunks:
        if not c:
            continue
        mc = sum(p for p, _ in c) / len(c)
        acc = sum(1 for _, ok in c if ok) / len(c)
        e += len(c) / n * abs(mc - acc)
    brier = sum((p - (1.0 if ok else 0.0)) ** 2 for p, ok in pts) / n
    return round(e, 4), round(brier, 4)


def ece(rows, bins=10):
    per_type = defaultdict(list)
    for r in rows:
        per_type[r["type"]].append((float(r["confidence"]), bool(r["correct"])))
    out = {}
    for t, pts in per_type.items():
        e, brier = _ece_brier(pts, bins)
        out[t] = {"n": len(pts), "ece": e, "brier": brier}
    return out


if __name__ == "__main__":
    mode, path = sys.argv[1], sys.argv[2]
    rows = load(path)
    fn = {"accuracy": accuracy, "routing": routing, "ece": ece}[mode]
    print(json.dumps(fn(rows), indent=2, ensure_ascii=False))
