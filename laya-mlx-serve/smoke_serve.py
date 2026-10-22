"""Acceptance smoke for laya-mlx-serve: protocol parity, auth, errors, latency.

Starts the service itself (two runs: unauthenticated, then LAYA_API_KEY set),
exercises the Jev /v1/systemone wire contract, and measures warm p50/p95 over
>=30 requests. Exits non-zero on any failure.

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python smoke_serve.py
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
VENV_PY = "/Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python"
PORT = int(os.environ.get("SMOKE_PORT", "8231"))
BASE = f"http://127.0.0.1:{PORT}"

QUESTIONS = {
    "department": {
        "type": "choice",
        "instructions": "Which department should handle this request?",
        "criteria": {
            "billing": "invoices, payments, refunds",
            "technical": "bugs, outages, system errors",
            "sales": "pricing, new contracts",
            "other": "everything else",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this request?",
        "criteria": ["not urgent", "soon", "critical deadline or blocking issue"],
    },
    "churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel or leave?"},
}
EN_STATE = {"body": "Hi, we were billed twice for March. Please refund the duplicate today or we will cancel our plan."}
ZH_STATE = {"body": "发票被重复扣款，请立即退款，否则我们取消合同。"}

failures = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        failures.append(name)


def req(method, path, body=None, headers=None, timeout=120):
    r = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers or {},
        method=method,
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read()), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read())
        except Exception:
            payload = None
        return e.code, payload, (time.perf_counter() - t0) * 1000


def start_service(extra_env=None):
    env = dict(os.environ)
    env.setdefault("HF_HUB_OFFLINE", "1")  # weights are cached; fail fast if not
    env["LAYA_PORT"] = str(PORT)
    env["LAYA_HOST"] = "127.0.0.1"
    env.update(extra_env or {})
    proc = subprocess.Popen(
        [VENV_PY, os.path.join(HERE, "serve.py")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.time() + 300
    while time.time() < deadline:
        if proc.poll() is not None:
            print(proc.stdout.read(), flush=True)
            raise RuntimeError("service exited during startup")
        try:
            status, body, _ = req("GET", "/health", timeout=5)
            if status == 200:
                return proc, body
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("service did not become healthy in 300s")


def stop_service(proc):
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate(timeout=30)
        print(out[-2000:], flush=True)


def verify_answers(tag, res, expect_model):
    a = res["answers"]
    check(f"{tag}: response has model/answers/usage/routing",
          all(k in res for k in ("model", "answers", "usage", "routing")))
    check(f"{tag}: routed to {expect_model}", res["routing"]["model"] == expect_model,
          f"got {res['routing']['model']} ({res['routing']['reason']})")
    check(f"{tag}: department=billing", a["department"].get("choice") == "billing",
          f"got {a['department'].get('choice')} @ {a['department'].get('confidence')}")
    check(f"{tag}: department has probabilities over 4 options",
          isinstance(a["department"].get("probabilities"), dict)
          and len(a["department"]["probabilities"]) == 4)
    u = a["urgency"]
    check(f"{tag}: urgency score in [0,2]", isinstance(u.get("score"), (int, float)) and 0.0 <= u["score"] <= 2.0,
          f"score={u.get('score')}")
    check(f"{tag}: urgency has legend+probabilities(3)",
          isinstance(u.get("legend"), dict) and len(u.get("probabilities", {})) == 3)
    c = a["churn_risk"]
    check(f"{tag}: churn noul in [0,1]", isinstance(c.get("noul"), (int, float)) and 0.0 <= c["noul"] <= 1.0,
          f"noul={c.get('noul')}")
    check(f"{tag}: usage block present", isinstance(res["usage"].get("input_tokens"), int)
          and res["usage"].get("output_tokens") == 0, str(res.get("usage")))
    return a


def main():
    print(f"== starting laya-mlx-serve on :{PORT} (no auth) ==", flush=True)
    t0 = time.perf_counter()
    proc, health = start_service()
    startup = time.perf_counter() - t0
    print(f"startup (preload english+multilingual): {startup:.1f}s | /health: {health}", flush=True)

    print("== /health ==", flush=True)
    check("health status ok", health.get("status") == "ok")
    check("health loaded checkpoints", set(health.get("loaded", [])) >= {"english", "multilingual"},
          str(health.get("loaded")))
    check("health device reported", isinstance(health.get("device"), str) and health["device"], str(health.get("device")))

    print("== predictions (smoke_mlx.py questions) ==", flush=True)
    s, res, ms = req("POST", "/v1/systemone", {"state": EN_STATE, "questions": QUESTIONS})
    check("en POST 200", s == 200, f"status={s} {res if s != 200 else ''}")
    en_answers = verify_answers("en", res, "english")
    check("en: churn threat detected (noul >= 0.5, playbook en-ckpt range 0.82-0.97)",
          en_answers["churn_risk"]["noul"] >= 0.5, f"noul={en_answers['churn_risk']['noul']}")

    s, res, _ = req("POST", "/v1/systemone", {"state": ZH_STATE, "questions": QUESTIONS})
    check("zh POST 200", s == 200, f"status={s}")
    verify_answers("zh", res, "multilingual")

    s, res, _ = req("POST", "/v1/systemone",
                    {"state": EN_STATE, "questions": QUESTIONS, "model": "multilingual"})
    check("explicit model=multilingual honoured",
          s == 200 and res["routing"]["model"] == "multilingual",
          f"status={s} routing={res.get('routing', {}).get('model') if s == 200 else res}")

    s, res, _ = req("POST", "/v1/systemone",
                    {"state": EN_STATE, "questions": QUESTIONS, "model": "jev-1"})
    check("foreign model id (jev-1) falls back to auto-route",
          s == 200 and res["routing"]["model"] == "english",
          f"status={s} routing={res.get('routing', {}).get('model') if s == 200 else res}")

    print("== error contract (no auth configured) ==", flush=True)
    s, body, _ = req("POST", "/v1/systemone", {"state": EN_STATE})
    check("400 on body without questions", s == 400, f"status={s}")
    s, body, _ = req("POST", "/v1/systemone", {"questions": QUESTIONS})
    check("state omitted tolerated (routes to default checkpoint)", s == 200, f"status={s}")
    bad_q = {"q1": {"type": "telepathy", "instructions": "?", "criteria": ["a"]}}
    s, body, _ = req("POST", "/v1/systemone", {"state": EN_STATE, "questions": bad_q})
    check("422 on unknown question type", s == 422, f"status={s} detail={body}")

    print("== warm latency (>=30 requests, en state) ==", flush=True)
    lat = []
    for _ in range(35):
        _, _, ms = req("POST", "/v1/systemone", {"state": EN_STATE, "questions": QUESTIONS})
        lat.append(ms)
    lat.sort()
    p50, p95 = lat[len(lat) // 2], lat[int(len(lat) * 0.95)]
    print(f"  n={len(lat)} p50={p50:.1f}ms p95={p95:.1f}ms min={lat[0]:.1f}ms max={lat[-1]:.1f}ms", flush=True)
    check("warm p50 under 30ms (torch laya-serve baseline 22-24ms)", p50 < 30.0, f"p50={p50:.1f}ms")

    print("== concurrent health during inference ==", flush=True)
    import threading
    stop = threading.Event()
    def hammer():
        while not stop.is_set():
            req("POST", "/v1/systemone", {"state": EN_STATE, "questions": QUESTIONS})
    threads = [threading.Thread(target=hammer) for _ in range(3)]
    for t in threads:
        t.start()
    t0 = time.perf_counter()
    s, h, _ = req("GET", "/health", timeout=10)
    health_ms = (time.perf_counter() - t0) * 1000
    stop.set()
    for t in threads:
        t.join()
    check("GET /health responsive while 3 predicts in flight", s == 200 and health_ms < 250,
          f"status={s} {health_ms:.0f}ms")

    stop_service(proc)

    print("== restart with LAYA_API_KEY=test-secret-1 ==", flush=True)
    proc, health = start_service({"LAYA_API_KEY": "test-secret-1"})
    check("health needs no auth", health.get("status") == "ok")
    s, _, _ = req("POST", "/v1/systemone", {"state": EN_STATE, "questions": QUESTIONS})
    check("401 without bearer when API key set", s == 401, f"status={s}")
    s, _, _ = req("POST", "/v1/systemone", {"state": EN_STATE, "questions": QUESTIONS},
                  headers={"Authorization": "Bearer wrong-key"})
    check("401 with wrong bearer", s == 401, f"status={s}")
    s, res, _ = req("POST", "/v1/systemone", {"state": EN_STATE, "questions": QUESTIONS},
                    headers={"Authorization": "Bearer test-secret-1"})
    check("200 with correct bearer", s == 200 and res["routing"]["model"] == "english", f"status={s}")
    stop_service(proc)

    print(f"\n{'SMOKE OK' if not failures else 'SMOKE FAILED: ' + ', '.join(failures)}", flush=True)
    print(f"SUMMARY latency: warm p50={p50:.1f}ms p95={p95:.1f}ms (n={len(lat)}, http end-to-end)", flush=True)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
