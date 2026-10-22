"""R3: functional accuracy baseline for laya-mlx-serve on eval_v1 (120 labeled cases).

One POST /v1/systemone per case (state={body}, single question), rows written in
score_eval.py `accuracy` format. Starts the service itself; fully offline.

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python run_eval.py r3
Output: /Users/leewbl/aiworld/flylaya/laya-testbench/results/r3-eval-v1-results.jsonl (+ scorer stdout)
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
OUT_DIR = "/Users/leewbl/aiworld/flylaya/laya-testbench/results"
ROUNDS = {
    "r3": ("/Users/leewbl/aiworld/flylaya/laya-testbench/data/eval_v1.jsonl", "r3-eval-v1-results.jsonl", "8251"),
    "r9": ("/Users/leewbl/aiworld/flylaya/laya-testbench/data/eval_multi_v1.jsonl", "r9-eval-multi-v1-results.jsonl", "8281"),
}
ROUND = ROUNDS.get(sys.argv[1] if len(sys.argv) > 1 else "r3")
DATA, OUT_NAME, _PORT = ROUND
OUT = os.path.join(OUT_DIR, OUT_NAME)
PORT = int(os.environ.get("EVAL_PORT", _PORT))
BASE = f"http://127.0.0.1:{PORT}"


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
    os.makedirs(OUT_DIR, exist_ok=True)
    cases = [json.loads(l) for l in open(DATA) if l.strip()]
    print(f"{DATA}: {len(cases)} cases", flush=True)

    proc = start_service()
    out_path = OUT
    n_err = 0
    t0 = time.perf_counter()
    with open(out_path, "w") as out:
        for c in cases:
            s, res = req("POST", "/v1/systemone",
                         {"state": {"body": c["body"]}, "questions": {"q": c["question"]}})
            if s != 200:
                n_err += 1
                print(f"  [ERROR] {c['id']}: status={s} {res}", flush=True)
                continue
            out.write(json.dumps({
                "id": c["id"],
                "lang": c["lang"],
                "group": c["question"]["type"],
                "expected": c["expected"],
                "actual": res["answers"]["q"],
                "routing_model": res["routing"]["model"],
            }, ensure_ascii=False) + "\n")
    dt = time.perf_counter() - t0
    stop = lambda: (proc.send_signal(signal.SIGINT), proc.wait(timeout=15))
    try:
        stop()
    except Exception:
        proc.kill()

    print(f"ran {len(cases)} cases in {dt:.1f}s ({len(cases)/dt:.1f} req/s), HTTP errors: {n_err}", flush=True)
    print(f"results: {out_path}", flush=True)

    print("\n== score_eval.py accuracy ==", flush=True)
    subprocess.run(["python3", "/Users/leewbl/aiworld/flylaya/laya-testbench/score_eval.py", "accuracy", out_path])

    # routing sanity per case (r3: en->english, zh->multilingual; r9: everything -> multilingual)
    rows = [json.loads(l) for l in open(out_path)]
    want = ({"en": "english", "zh": "multilingual"} if "eval_v1" in out_path
            else {r["lang"]: "multilingual" for r in rows})
    mism = [f'{r["id"]}({r["lang"]}->{r["routing_model"]})' for r in rows
            if want.get(r["lang"]) and r["routing_model"] != want[r["lang"]]]
    print(f"\nrouting: {len(rows)-len(mism)}/{len(rows)} lang-consistent"
          + (f" (misrouted: {mism})" if mism else ""), flush=True)
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
