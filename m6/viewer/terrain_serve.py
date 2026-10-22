"""M6-W2 terrain viewer server (TASK-0028) — natural world render + replay/live.

API:
  GET /                      -> terrain.html
  GET /api/maps              -> [{id}] from m6/terrain/*.json
  GET /api/map?id=           -> terrain spec json (flylaya.m6.terrain.v1)
  GET /api/runs              -> run index under m6/runs* (trajectory.jsonl dirs)
  GET /api/run?dir=<rel>     -> {spec, meta, frames, events?}
  GET /api/live?...          -> if m6 runner present, stream like bench_serve;
                                else 501 {"error":"W1 runner 未就绪"} (page falls
                                back to client-side DEMO walk)

Contract (published, tolerant): run trajectory jsonl reuses flylaya traj schema
(t_s/pos_m/yaw_deg/speed_m_s/intent_applied/arousal/dn) with free coords in m;
terrain spec per m6/terrain/*.json v1.
"""
import argparse
import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
M6 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(M6, ".."))
TERRAIN = os.path.join(M6, "terrain")
PY = os.path.abspath(os.path.join(REPO, "laya-mlx-deploy", ".venv", "bin", "python"))
M6_RUNNER = os.path.join(M6, "runner.py")


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def index_runs():
    out = []
    if not os.path.isdir(M6):
        return out
    for d in sorted(os.listdir(M6)):
        root = os.path.join(M6, d)
        if not d.startswith("runs") or not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            if "trajectory.jsonl" in filenames:
                out.append({"root": d, "rel": os.path.relpath(dirpath, M6)})
    return out


def find_spec(run_dir):
    for cand in ("terrain.json", "scene.json", "map.json"):
        p = os.path.join(run_dir, cand)
        if os.path.exists(p):
            try:
                j = json.load(open(p))
                if "hills" in j or "schema_version" in j:
                    return j
            except (OSError, json.JSONDecodeError):
                pass
    return None


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

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/terrain.html"):
                return self._file(os.path.join(HERE, "terrain.html"),
                                  "text/html; charset=utf-8")
            if u.path == "/api/maps":
                ids = sorted(f[:-5] for f in os.listdir(TERRAIN)
                             if f.endswith(".json"))
                return self._json([{"id": i} for i in ids])
            if u.path == "/api/map":
                mid = q.get("id", [""])[0]
                p = os.path.join(TERRAIN, mid + ".json")
                if not mid.replace("_", "").isalnum() or not os.path.exists(p):
                    return self._json({"error": "bad map id"}, 400)
                return self._file(p, "application/json")
            if u.path == "/api/runs":
                return self._json(index_runs())
            if u.path == "/api/run":
                p = os.path.normpath(os.path.join(M6, q["dir"][0]))
                if not p.startswith(M6 + os.sep) or \
                        "trajectory.jsonl" not in os.listdir(p):
                    return self._json({"error": "bad dir"}, 400)
                rows = read_jsonl(os.path.join(p, "trajectory.jsonl"))
                return self._json({
                    "dir": q["dir"][0],
                    "spec": find_spec(p) or json.load(
                        open(os.path.join(TERRAIN, "default_hills.json"))),
                    "meta": rows[0] if rows else {},
                    "frames": rows[1:] if rows and rows[0].get("type") == "meta" else rows,
                })
            if u.path == "/api/live":
                if not os.path.exists(M6_RUNNER):
                    return self._json({"error": "W1 runner (m6/runner.py) 未就绪"}, 501)
                return self.do_live(q)
            return self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e)}, 500)

    def do_live(self, q):
        scene = q.get("scene", ["default_hills"])[0]
        seed = int(q.get("seed", ["42"])[0])
        seconds = float(q.get("seconds", ["30"])[0])
        out_dir = os.path.join(M6, "runs_bench_live",
                               f"{scene}_{seed}_{int(time.time())}")
        os.makedirs(out_dir, exist_ok=True)
        cmd = [PY, M6_RUNNER, "run", "--scene", os.path.join(TERRAIN, scene + ".json"),
               "--seed", str(seed), "--out", out_dir, "--seconds", str(seconds)]
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        traj = os.path.join(out_dir, "trajectory.jsonl")
        sent = 0
        while proc.poll() is None or (os.path.exists(traj)
                                      and sent < self._nlines(traj)):
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
        tail = json.dumps({"_done": True, "run_dir": os.path.relpath(out_dir, M6),
                           "returncode": proc.returncode,
                           "log_tail": (proc.stdout.read() or "")[-1500:]})
        try:
            self.wfile.write(tail.encode() + b"\n")
        except BrokenPipeError:
            pass

    @staticmethod
    def _nlines(path):
        try:
            with open(path) as f:
                return sum(1 for _ in f)
        except OSError:
            return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8965)
    args = ap.parse_args()
    print(f"m6 terrain viewer on http://127.0.0.1:{args.port}/")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
