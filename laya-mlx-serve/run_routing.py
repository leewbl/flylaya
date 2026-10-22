"""R4: routing matrix for laya-mlx-serve — script/language edge cases vs expected.

Each routing_matrix_v1.jsonl row is sent through the real HTTP path
(state={"body": text}); the router decision comes back in `routing`.
`expected_model: "default"` maps to the Router default (english).

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python run_routing.py
Output: /Users/leewbl/aiworld/flylaya/laya-testbench/results/r4-routing-results.jsonl (+ scorer stdout)
"""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MLX_PY = "/Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python"
DATA = "/Users/leewbl/aiworld/flylaya/laya-testbench/data/routing_matrix_v1.jsonl"
OUT = "/Users/leewbl/aiworld/flylaya/laya-testbench/results/r4-routing-results.jsonl"
PORT = int(os.environ.get("R4_PORT", "8261"))
BASE = f"http://127.0.0.1:{PORT}"

PROBE_Q = {"probe": {"type": "noul", "instructions": "Does this mention a billing problem?"}}


def req(method, path, body=None, timeout=180):
    r = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def start_service():
    env = dict(os.environ, HF_HUB_OFFLINE="1", LAYA_HOST="127.0.0.1", LAYA_PORT=str(PORT))
    proc = subprocess.Popen([MLX_PY, os.path.join(HERE, "serve.py")], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 300
    while time.time() < deadline:
        if proc.poll() is not None:
            print(proc.stdout.read()[-3000:], flush=True)
            raise RuntimeError("mlx-serve exited during startup")
        try:
            s, _ = req("GET", "/health", timeout=5)
            if s == 200:
                return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("mlx-serve not healthy in 300s")


def main():
    cases = [json.loads(l) for l in open(DATA) if l.strip()]
    print(f"routing_matrix_v1: {len(cases)} cases", flush=True)

    proc = start_service()
    rows, diag = [], []
    n_err = 0
    for c in cases:
        s, res = req("POST", "/v1/systemone", {"state": {"body": c["text"]}, "questions": PROBE_Q})
        if s != 200:
            n_err += 1
            print(f"  [ERROR] {c['id']}: status={s} {res}", flush=True)
            continue
        actual = res["routing"]["model"]
        expected = "english" if c["expected_model"] == "default" else c["expected_model"]
        rows.append({"id": c["id"], "expected_model": expected, "actual_model": actual})
        if actual != expected:
            diag.append((c["id"], expected, actual, c.get("rationale", ""), res["routing"].get("reason", "")))
    try:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=15)
    except Exception:
        proc.kill()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"results: {OUT} (HTTP errors: {n_err})", flush=True)

    print("\n== score_eval.py routing ==", flush=True)
    subprocess.run(["python3", "/Users/leewbl/aiworld/flylaya/laya-testbench/score_eval.py", "routing", OUT])

    print("\n== misroute diagnostics (expected -> actual | dataset rationale | router reason) ==", flush=True)
    for cid, exp, act, why, reason in diag:
        print(f"  {cid}: {exp} -> {act}\n    dataset: {why}\n    router:  {reason}", flush=True)
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
