"""TASK-0008 (M5-G0): freeze batch directories into traceable manifests.

Usage: python make_manifest.py RUN_DIR --exp-id ID [--tau X --eps Y] [--note "..."]
Writes RUN_DIR/manifest.json with per-file sha256/line counts, scene-meta hashes,
code/decision-service fingerprints, and a completeness verdict (content-based,
not filename-based).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

EXPECTED_HZ = 10  # bio frames per second; +1 meta line per file


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def code_fingerprint():
    """Hash every file that shapes trajectories: sim code + configs + baselines."""
    rels = []
    for sub, exts in (("flylaya", (".py",)), ("m3", (".py", ".json")),
                      ("m3/ablation", (".json", ".md"))):
        d = os.path.join(ROOT, sub)
        for fn in sorted(os.listdir(d)):
            if os.path.isfile(os.path.join(d, fn)) and fn.endswith(exts):
                rels.append(os.path.join(sub, fn))
    rels.append("m4/run_batch.py")
    rels.append("m4/trajectory_stats.py" if os.path.exists(os.path.join(ROOT, "m4", "trajectory_stats.py"))
                else None)
    rels = [r for r in rels if r and os.path.exists(os.path.join(ROOT, r))]
    return {r: sha256_file(os.path.join(ROOT, r)) for r in sorted(rels)}


PROBES = [
    ("center_calm",
     "Fly zone: center. No obstacle near. Sun to the left, 30 deg left ahead. "
     "Flight speed 12 cm/s, level. Current intent explore for 3.0 s. "
     "Wall status: far from walls. Recent bump: no."),
    ("edge_bump",
     "Fly zone: right-back. Obstacle near ahead, 8 deg left, in the flight path. "
     "Sun behind, not in the flight path. Flight speed 18 cm/s, descending. "
     "Current intent phototaxis for 1.2 s. Wall status: near wall right, 6 cm. "
     "Recent bump: yes."),
]


def decision_service_fingerprint():
    import urllib.request

    url = "http://127.0.0.1:8000/v1/systemone"
    out = {"url": url, "reachable": False}
    try:
        health = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5).read()
        out["health_sha256"] = sha256_text(health.decode())
    except Exception as e:
        out["health_error"] = str(e)
        return out
    out["reachable"] = True
    out["serve_py_sha256"] = sha256_file(os.path.join(ROOT, "laya-mlx-serve", "serve.py"))
    probes = {}
    body_q = {"intent": {"type": "choice", "instructions": "pick",
                         "criteria": {"phototaxis": "a", "avoid_obstacle": "b", "explore": "c",
                                      "center_in_arena": "d", "rest_hover": "e"}},
              "arousal": {"type": "score", "instructions": "q", "criteria": ["1", "2", "3"]}}
    for name, text in PROBES:
        payload = json.dumps({"state": {"body": text}, "questions": body_q}).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10).read().decode()
        probes[name] = {"state_sha256": sha256_text(text), "response_sha256": sha256_text(resp),
                        "model": json.loads(resp).get("model")}
    out["deterministic_probes"] = probes
    out["note"] = ("weights served in-process (model id above); on-disk checkpoint not "
                   "located — probe response hashes are the behavioral fingerprint of the "
                   "exact decision function this batch consumed")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--exp-id", required=True)
    ap.add_argument("--seconds", type=int, default=300)
    ap.add_argument("--tau", type=float)
    ap.add_argument("--eps", type=float)
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    run_dir = os.path.abspath(args.run_dir)
    entries, bad = [], []
    mtimes = []
    for fn in sorted(os.listdir(run_dir)):
        if not fn.endswith(".jsonl"):
            continue
        path = os.path.join(run_dir, fn)
        with open(path) as f:
            first = f.readline().strip()
            n_lines = 1 + sum(1 for _ in f)
        meta = json.loads(first)
        stem = fn[: -len(".jsonl")]
        config = meta.get("config", stem.rsplit("_", 1)[0])
        seed = meta.get("seed")
        mt = os.path.getmtime(path)
        mtimes.append(mt)
        ok = (n_lines == args.seconds * EXPECTED_HZ + 1 and seed is not None)
        if not ok:
            bad.append(fn)
        entries.append({"file": fn, "config": config, "seed": seed, "lines": n_lines,
                        "frames": n_lines - 1, "sha256": sha256_file(path),
                        "scene_meta_sha256": sha256_text(first),
                        "mtime": dt.datetime.fromtimestamp(mt).isoformat(timespec="seconds"),
                        "status": "ok" if ok else "short_or_malformed"})

    stats_json = os.path.join(run_dir, "stats_metrics.json")
    stats_n = len(json.load(open(stats_json))) if os.path.exists(stats_json) else 0
    by_cfg = {}
    for e in entries:
        by_cfg.setdefault(e["config"], set()).add(e["seed"])

    manifest = {
        "experiment_id": args.exp_id,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "schema": "flylaya-m4-batch-manifest/1",
        "batch": {
            "driver": "m4/run_batch.py", "seconds": args.seconds, "frame_hz": 10,
            "env": {"FLYLAYA_INTENT_TAU": args.tau, "FLYLAYA_INTENT_EPS": args.eps},
            "configs": {c: sorted(s) for c, s in sorted(by_cfg.items())},
            "window": {"start": dt.datetime.fromtimestamp(min(mtimes)).isoformat(timespec="seconds"),
                       "end": dt.datetime.fromtimestamp(max(mtimes)).isoformat(timespec="seconds")}
            if mtimes else None,
        },
        "code_tree_at_freeze": code_fingerprint(),
        "decision_service": decision_service_fingerprint(),
        "runs": entries,
        "completeness": {
            "jsonl_files": len(entries), "ok": sum(1 for e in entries if e["status"] == "ok"),
            "bad": bad, "stats_metrics_entries": stats_n,
            "stats_matches_files": stats_n == len(entries),
        },
        "notes": args.note,
    }
    out_path = os.path.join(run_dir, "manifest.json")
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"{out_path}: {len(entries)} files, ok={manifest['completeness']['ok']}, "
          f"stats_entries={stats_n}, bad={bad or 'none'}")


if __name__ == "__main__":
    main()
