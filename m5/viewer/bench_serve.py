"""M5 W5 test bench server (TASK-0024) — scene/render + live sim + replay bridge.

Serves m5/viewer/bench.html and a small JSON API over the M5 workspace:
  GET /api/scenes                     -> [{id, path}...] from m5/scenes/*.json
  GET /api/runs                       -> run index under allowed roots
  GET /api/run?dir=<rel>              -> {scene, meta, frames, events, decisions}
  GET /api/live?scene=&policy=&coupling=&brain=&seed=&seconds=
        -> streams trajectory.jsonl lines as they are written (NDJSON chunks),
           final line {"_done": run_dir}. Spawns m5/runner.py run.

Security: local dev only; run dirs restricted to m5/runs_*; live writes to
m5/runs_bench_live/ (kept, verifiable by runner verify).
"""
import argparse
import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
M5 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(M5, ".."))
SCENES = os.path.join(M5, "scenes")
RUN_ROOTS = [os.path.join(M5, d) for d in sorted(os.listdir(M5))
             if d.startswith("runs_") and os.path.isdir(os.path.join(M5, d))]
LIVE_OUT = os.path.join(M5, "runs_bench_live")
PY = os.path.abspath(os.path.join(REPO, "laya-mlx-deploy", ".venv", "bin", "python"))


def read_jsonl(path, limit=None):
    rows = []
    with open(path) as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def index_runs():
    out = []
    for root in RUN_ROOTS:
        root_name = os.path.basename(root)
        for dirpath, dirnames, filenames in os.walk(root):
            if "trajectory.jsonl" in filenames:
                rel = os.path.relpath(dirpath, M5)
                parts = rel.split(os.sep)
                out.append({"root": root_name, "rel": rel,
                            "scene": parts[1] if len(parts) > 2 else "",
                            "policy": parts[2] if len(parts) > 3 else "",
                            "seed": parts[3] if len(parts) > 4 else ""})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _file(self, path, ctype):
        b = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _safe_run_dir(self, rel):
        p = os.path.normpath(os.path.join(M5, rel))
        if not p.startswith(M5 + os.sep) or "trajectory.jsonl" not in os.listdir(p):
            return None
        return p

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/" or u.path == "/bench.html":
                return self._file(os.path.join(HERE, "bench.html"), "text/html; charset=utf-8")
            if u.path == "/api/scene":
                sid = q.get("id", [""])[0]
                p = os.path.join(SCENES, sid + ".json")
                if not sid.replace("_", "").isalnum() or not os.path.exists(p):
                    return self._json({"error": "bad scene id"}, 400)
                return self._file(p, "application/json")
            if u.path == "/api/scenes":
                scenes = sorted(f for f in os.listdir(SCENES) if f.endswith(".json"))
                return self._json([{"id": s[:-5], "path": f"scenes/{s}"} for s in scenes])
            if u.path == "/api/runs":
                return self._json(index_runs())
            if u.path == "/api/run":
                p = self._safe_run_dir(q["dir"][0])
                if not p:
                    return self._json({"error": "bad dir"}, 400)
                return self._json({
                    "dir": q["dir"][0],
                    "scene": read_jsonl_or_none(os.path.join(p, "scene.json")),
                    "meta": read_jsonl(os.path.join(p, "trajectory.jsonl"), 1)[0],
                    "frames": read_jsonl(os.path.join(p, "trajectory.jsonl"))[1:],
                    "events": read_jsonl_or_none(os.path.join(p, "events.jsonl")) or [],
                    "decisions": read_jsonl_or_none(os.path.join(p, "decisions.jsonl")) or [],
                })
            if u.path == "/api/live":
                return self.do_live(q)
            return self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e)}, 500)

    def do_live(self, q):
        scene = q.get("scene", ["S0_neutral"])[0]
        policy = q.get("policy", ["P_fixed"])[0]
        coupling = q.get("coupling", ["sensory_only"])[0]
        brain = q.get("brain", ["skeleton"])[0]
        seed = int(q.get("seed", ["42"])[0])
        seconds = float(q.get("seconds", ["30"])[0])
        state_source = q.get("state_source", ["observable"])[0]

        out_dir = os.path.join(LIVE_OUT, f"{scene}_{policy}_{seed}_{int(time.time())}")
        os.makedirs(out_dir, exist_ok=True)
        scene_path = os.path.join(SCENES, scene + ".json")
        cmd = [PY, os.path.join(M5, "runner.py"), "run",
               "--scene", scene_path, "--seed", str(seed), "--policy", policy,
               "--coupling", coupling, "--brain", brain, "--out", out_dir,
               "--seconds", str(seconds), "--experiment-id", "m5-bench-live",
               "--state-source", state_source]
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        traj = os.path.join(out_dir, "trajectory.jsonl")
        sent = 0
        # poll-growing-file loop; runner flushes per frame (streaming contract §6)
        while proc.poll() is None or os.path.exists(traj) and sent < _count_lines(traj):
            if os.path.exists(traj):
                with open(traj) as f:
                    lines = f.readlines()
                for line in lines[sent:]:
                    if line.strip():
                        try:
                            self.wfile.write(line.encode())
                            self.wfile.flush()
                        except BrokenPipeError:
                            proc.kill()
                            return
                sent = len(lines)
            time.sleep(0.05)
        rc = proc.returncode
        log = proc.stdout.read()[-2000:] if proc.stdout else ""
        tail = json.dumps({"_done": True, "run_dir": os.path.relpath(out_dir, M5),
                           "returncode": rc, "log_tail": log})
        try:
            self.wfile.write(tail.encode() + b"\n")
            self.wfile.flush()
        except BrokenPipeError:
            pass


def read_jsonl_or_none(path):
    if not os.path.exists(path):
        return None
    if path.endswith("scene.json"):
        return json.load(open(path))
    return read_jsonl(path)


def _count_lines(path):
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8964)
    args = ap.parse_args()
    print(f"bench server on http://127.0.0.1:{args.port}/  (m5={M5})")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
