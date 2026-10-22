"""R8: Jev wire-contract regression for laya-mlx-serve (full schema + error paths).

Gate (test plan): contract deviations = 0.

Layers:
  A. Response schema, all three primitives, strict field/type/value checks
     (incl. k=1 confidence edge, 11+ option temperature bucket).
  B. Determinism: identical request -> byte-identical response.
  C. usage sanity: positive input_tokens, scales with state, output_tokens=0.
  D. Error contract: 400/401/422/404/405 matrix.
  E. model-override coverage: HTTP-level for loaded checkpoints; process-level
     (serve._resolve_model + Router.route) for typed-decisions / aliases / auto-task.
  F. Differential vs torch laya-serve (english): identical field sets & types,
     same argmax decisions; probability deltas recorded (fp16 vs fp32).

Runs fully offline (HF_HUB_OFFLINE=1) on the warm cache. Exits non-zero when
any contract deviation is found.

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python contract_regression.py
"""
import json
import math
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MLX_PY = "/Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python"
TORCH_SERVE = "/Users/leewbl/aiworld/flylaya/laya-deploy/.venv/bin/laya-serve"
MLX_PORT = int(os.environ.get("R8_PORT", "8241"))
TORCH_PORT = MLX_PORT + 1
MLX = f"http://127.0.0.1:{MLX_PORT}"
TORCH = f"http://127.0.0.1:{TORCH_PORT}"
API_KEY = "r8-secret"

deviations = []
passed = 0


def check(name, ok, detail=""):
    global passed
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)
    if ok:
        passed += 1
    else:
        deviations.append(f"{name}: {detail}")


def req(base, method, path, body=None, headers=None, raw=None, timeout=180):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(base + path, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, None


def start(cmd, env_extra, port, mark):
    env = dict(os.environ)
    env.update({"HF_HUB_OFFLINE": "1", "LAYA_HOST": "127.0.0.1", "LAYA_PORT": str(port), **env_extra})
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 300
    while time.time() < deadline:
        if proc.poll() is not None:
            print(proc.stdout.read()[-3000:], flush=True)
            raise RuntimeError(f"{mark} exited during startup")
        try:
            s, b = req(f"http://127.0.0.1:{port}", "GET", "/health", timeout=5)
            if s == 200:
                return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError(f"{mark} not healthy in 300s")


def stop(proc):
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------- schema layer

def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_common(answer, qid, qtype, where):
    ok = True
    if not isinstance(answer.get("type"), str) or answer["type"] != qtype:
        check(f"{where}/{qid}: answer.type == {qtype!r}", False, str(answer.get("type")))
        return False
    if not (is_num(answer.get("confidence")) and 0.0 <= answer["confidence"] <= 1.0):
        check(f"{where}/{qid}: confidence in [0,1]", False, str(answer.get("confidence")))
        ok = False
    act = answer.get("action")
    if not (isinstance(act, dict) and is_num(act.get("act_probability"))
            and 0.0 <= act["act_probability"] <= 1.0):
        check(f"{where}/{qid}: action.act_probability in [0,1]", False, str(act))
        ok = False
    keys = set(answer)
    expected = {"type", "confidence", "action"}
    if qtype == "choice":
        expected |= {"choice", "probabilities"}
    elif qtype == "score":
        expected |= {"score", "legend", "probabilities"}
    else:
        expected |= {"noul"}
    if keys != expected:
        check(f"{where}/{qid}: exact field set", False, f"extra={keys - expected} missing={expected - keys}")
        ok = False
    return ok


def probs_sum_ok(probs, tol=0.02):
    return abs(sum(probs.values()) - 1.0) <= tol


def validate_response(res, where, questions):
    """Full-schema validation of one /v1/systemone response against its questions."""
    top = set(res)
    check(f"{where}: top-level fields", top == {"model", "answers", "usage", "routing"},
          f"got {sorted(top)}")
    check(f"{where}: model is str", isinstance(res.get("model"), str), str(res.get("model")))
    u = res.get("usage", {})
    check(f"{where}: usage fields", set(u) == {"input_tokens", "output_tokens"}, str(u))
    check(f"{where}: usage.input_tokens positive int",
          isinstance(u.get("input_tokens"), int) and u["input_tokens"] > 0, str(u))
    check(f"{where}: usage.output_tokens == 0", u.get("output_tokens") == 0, str(u))
    r = res.get("routing", {})
    check(f"{where}: routing.model known",
          r.get("model") in ("english", "multilingual", "typed-decisions"), str(r.get("model")))
    check(f"{where}: routing.reason non-empty str",
          isinstance(r.get("reason"), str) and r["reason"], str(r.get("reason"))[:80])
    check(f"{where}: answers keys == questions keys",
          set(res.get("answers", {})) == set(questions), "")

    for qid, q in questions.items():
        a = res["answers"].get(qid, {})
        if not check_common(a, qid, q["type"], where):
            continue
        if q["type"] == "choice":
            labels = list(q["criteria"])
            p = a.get("probabilities", {})
            check(f"{where}/{qid}: probabilities keys == choice labels",
                  set(p) == set(labels), f"{sorted(p)} vs {labels}")
            check(f"{where}/{qid}: probabilities valid & sum~1",
                  all(is_num(v) and 0 <= v <= 1 for v in p.values()) and probs_sum_ok(p),
                  f"sum={sum(p.values()):.4f}")
            check(f"{where}/{qid}: choice in labels", a.get("choice") in labels, str(a.get("choice")))
            check(f"{where}/{qid}: choice == argmax(probabilities)",
                  a.get("choice") == max(p, key=p.get) if p else False, str(a.get("choice")))
        elif q["type"] == "score":
            k = len(q["criteria"])
            p = a.get("probabilities", {})
            legend = a.get("legend", {})
            check(f"{where}/{qid}: probabilities/legend keys == 0..{k-1}",
                  set(p) == set(legend) == {str(i) for i in range(k)},
                  f"p={sorted(p)} legend={sorted(legend)}")
            check(f"{where}/{qid}: probabilities valid & sum~1",
                  all(is_num(v) and 0 <= v <= 1 for v in p.values()) and probs_sum_ok(p),
                  f"sum={sum(p.values()):.4f}")
            check(f"{where}/{qid}: legend maps to criteria",
                  legend == {str(i): c for i, c in enumerate(q["criteria"])}, "")
            check(f"{where}/{qid}: score in [0,{k-1}]",
                  is_num(a.get("score")) and 0.0 <= a["score"] <= k - 1, str(a.get("score")))
            if p:
                exp = sum(i * p[str(i)] for i in range(k))
                check(f"{where}/{qid}: score == E[rank]",
                      abs(a["score"] - exp) <= 0.02, f"score={a['score']} E={exp:.4f}")
        else:
            n = a.get("noul")
            check(f"{where}/{qid}: noul in [0,1]", is_num(n) and 0.0 <= n <= 1.0, str(n))
            check(f"{where}/{qid}: noul confidence == max(noul,1-noul)",
                  abs(a["confidence"] - max(n, 1.0 - n)) <= 1e-4, f"c={a['confidence']} n={n}")


SMOKE_Q = {
    "department": {
        "type": "choice",
        "instructions": "Which department should handle this request?",
        "criteria": {"billing": "invoices, payments, refunds", "technical": "bugs, outages, system errors",
                     "sales": "pricing, new contracts", "other": "everything else"},
    },
    "urgency": {"type": "score", "instructions": "How urgent is this request?",
                "criteria": ["not urgent", "soon", "critical deadline or blocking issue"]},
    "churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel or leave?"},
}
EN = {"body": "Hi, we were billed twice for March. Please refund the duplicate today or we will cancel our plan."}
ZH = {"body": "发票被重复扣款，请立即退款，否则我们取消合同。"}

# Wide/edge question sets for schema layer.
CHOICE_1 = {"flag": {"type": "choice", "instructions": "Is this about billing at all?",
                     "criteria": {"billing": "about invoices and refunds"}}}
CHOICE_12 = {"bucket": {"type": "choice", "instructions": "Which bucket fits this message?",
                        "criteria": {f"c{i}": f"category number {i}" for i in range(12)}}}
SCORE_2 = {"binary": {"type": "score", "instructions": "How formal is the tone?",
                      "criteria": ["casual", "formal"]}}
SCORE_10 = {"scale10": {"type": "score", "instructions": "Rate business impact 1-10.",
                        "criteria": [f"level {i}" for i in range(10)]}}
NOUL_CRIT = {"tox": {"type": "noul", "instructions": "Is this message rude?",
                     "criteria": {"false": "polite or neutral", "true": "rude or aggressive"}}}
MULTI_Q = {**SMOKE_Q, **SCORE_2}


def main():
    print(f"== A/E/D: mlx-serve on :{MLX_PORT} (LAYA_API_KEY set) ==", flush=True)
    mlx_proc = start([MLX_PY, os.path.join(HERE, "serve.py")], {"LAYA_API_KEY": API_KEY}, MLX_PORT, "mlx-serve")
    auth = {"Authorization": f"Bearer {API_KEY}"}

    print("== A: response schema, all primitives ==", flush=True)
    for tag, state, qs in [
        ("smoke3(en)", EN, SMOKE_Q),
        ("smoke3(zh)", ZH, SMOKE_Q),
        ("choice1", EN, CHOICE_1),
        ("choice12", EN, CHOICE_12),
        ("score2+smoke", EN, MULTI_Q),
        ("score10", EN, SCORE_10),
        ("noul-criteria", EN, NOUL_CRIT),
    ]:
        s, res = req(MLX, "POST", "/v1/systemone", {"state": state, "questions": qs}, headers=auth)
        if s != 200:
            check(f"schema {tag}: 200", False, f"status={s} {res}")
            continue
        validate_response(res, f"schema {tag}", qs)
    # k=1 confidence edge: entropy confidence defined as 1.0
    s, res = req(MLX, "POST", "/v1/systemone", {"state": EN, "questions": CHOICE_1}, headers=auth)
    check("choice1: k=1 confidence == 1.0", s == 200 and res["answers"]["flag"]["confidence"] == 1.0,
          str(res.get("answers", {}).get("flag", {}).get("confidence")) if s == 200 else f"status={s}")

    print("== B: determinism (same request x3) ==", flush=True)
    payloads = []
    for _ in range(3):
        s, res = req(MLX, "POST", "/v1/systemone", {"state": EN, "questions": SMOKE_Q}, headers=auth)
        payloads.append(json.dumps(res, sort_keys=True))
    check("identical byte-for-byte across 3 calls", len(set(payloads)) == 1, "")

    print("== C: usage sanity ==", flush=True)
    short_state = {"body": "refund please"}
    long_state = {"body": "Hello, " + "we were billed twice for March and need a refund. " * 18}
    _, u_short = req(MLX, "POST", "/v1/systemone", {"state": short_state, "questions": SMOKE_Q}, headers=auth)
    _, u_long = req(MLX, "POST", "/v1/systemone", {"state": long_state, "questions": SMOKE_Q}, headers=auth)
    ts, tl = u_short["usage"]["input_tokens"], u_long["usage"]["input_tokens"]
    check("input_tokens grows with state size", tl > ts, f"short={ts} long={tl}")
    cap = 1024 * len(SMOKE_Q)
    check("input_tokens under per-question max_len cap", tl <= cap, f"long={tl} cap={cap}")

    print("== D: error contract matrix ==", flush=True)
    cases = [
        ("400 no questions", "POST", "/v1/systemone", {"state": EN}, 400),
        ("400 list body", "POST", "/v1/systemone", [1, 2, 3], 400),
        ("400 string body", "POST", "/v1/systemone", "hello", 400),
        ("400 null body", "POST", "/v1/systemone", None, 400),
    ]
    for name, m, p, b, want in cases:
        s, res = req(MLX, m, p, b, headers=auth)
        check(name, s == want, f"status={s} want={want} {res}")
    s, res = req(MLX, "POST", "/v1/systemone", raw=b"{not json", headers=auth)
    check("400 invalid JSON bytes", s == 400, f"status={s}")
    s, res = req(MLX, "POST", "/v1/systemone", raw=b"", headers=auth)
    check("400 empty body", s == 400, f"status={s}")

    unauth_cases = [
        ("401 no auth header", None),
        ("401 wrong key", {"Authorization": "Bearer nope"}),
        ("401 lowercase scheme", {"Authorization": f"bearer {API_KEY}"}),
        ("401 other scheme", {"Authorization": f"Token {API_KEY}"}),
        ("401 bare key no scheme", {"Authorization": API_KEY}),
    ]
    for name, h in unauth_cases:
        s, _ = req(MLX, "POST", "/v1/systemone", {"state": EN, "questions": SMOKE_Q}, headers=h)
        check(name, s == 401, f"status={s}")
    s, _ = req(MLX, "POST", "/v1/systemone", {"state": EN, "questions": SMOKE_Q},
               headers={"Authorization": f"Bearer {API_KEY} extra"})
    check("401 trailing token junk", s == 401, f"status={s}")

    model_errors = [
        ("422 unknown question type", {"q": {"type": "telepathy", "instructions": "?", "criteria": ["a"]}}),
        ("422 missing instructions", {"q": {"type": "noul"}}),
        ("422 choice criteria empty", {"q": {"type": "choice", "instructions": "?", "criteria": {}}}),
        ("422 choice dup labels", {"q": {"type": "choice", "instructions": "?",
                                          "criteria": ["a", "a"]}}),
        ("422 score criteria empty", {"q": {"type": "score", "instructions": "?", "criteria": []}}),
        ("422 noul criteria wrong type", {"q": {"type": "noul", "instructions": "?", "criteria": ["x"]}}),
        ("422 questions not a dict", "not-a-dict"),
        ("422 question not an object", {"q": "banana"}),
    ]
    for name, qs in model_errors:
        s, res = req(MLX, "POST", "/v1/systemone", {"state": EN, "questions": qs}, headers=auth)
        detail = (res or {}).get("detail")
        check(name, s == 422, f"status={s} detail={str(detail)[:70]}")

    s, _ = req(MLX, "GET", "/v1/systemone", headers=auth)
    check("405 GET /v1/systemone", s == 405, f"status={s}")
    s, _ = req(MLX, "DELETE", "/v1/systemone", headers=auth)
    check("405 DELETE /v1/systemone", s == 405, f"status={s}")
    s, _ = req(MLX, "GET", "/definitely-not-here", headers=auth)
    check("404 unknown path", s == 404, f"status={s}")
    s, res = req(MLX, "POST", "/v1/systemone", {"state": EN, "questions": {}}, headers=auth)
    check("empty questions {} still 200 (parity with laya-serve)",
          s == 200 and res["answers"] == {} and res["usage"]["input_tokens"] == 0,
          f"status={s}")  # observation, kept for parity; see write-up

    print("== E: model override coverage (HTTP, loaded checkpoints) ==", flush=True)
    for name, want in [("english", "english"), ("en", "english"), ("default", "english"),
                       ("multilingual", "multilingual"), ("multi", "multilingual"), ("ml", "multilingual"),
                       ("convaiinnovations/laya-multilingual", "multilingual"),
                       ("aac6fef/laya-multilingual-mlx", "multilingual"),
                       ("MULTILINGUAL", "multilingual"),
                       ("jev-1", "english"), ("gpt-4o", "english"), ("", "english")]:
        s, res = req(MLX, "POST", "/v1/systemone",
                     {"state": EN, "questions": SMOKE_Q, "model": name}, headers=auth)
        got = res.get("routing", {}).get("model") if s == 200 else f"status={s}"
        check(f"model={name!r} -> {want}", s == 200 and got == want, f"got {got}")
    stop(mlx_proc)

    print("== E(continued): model resolution + auto-task at process level ==", flush=True)
    sys.path.insert(0, HERE)
    os.environ.pop("LAYA_API_KEY", None)
    import serve as mlx_serve  # cheap import: no fastapi/mlx touched

    for name, want in [("typed-decisions", "typed-decisions"), ("typed", "typed-decisions"),
                       ("decisions", "typed-decisions"),
                       ("convaiinnovations/laya-typed-decisions", "typed-decisions"),
                       ("jev-1", None), (None, None), (12345, None)]:
        got = mlx_serve._resolve_model(name)
        check(f"_resolve_model({name!r}) == {want!r}", got == want, f"got {got!r}")

    from laya_mlx.router import Router
    r = Router(auto_task_detection=True)
    cs_q = {k: {"type": "noul", "instructions": "?"}
            for k in ("action", "needs_review", "outcome", "risk", "urgency")}
    d = r.route(EN, cs_q)
    check("auto_task_detection routes typed-decisions workflow", d["model"] == "typed-decisions",
          f"got {d['model']} ({d.get('workflow')})")
    d = r.route(EN, SMOKE_Q)
    check("auto_task_detection off for non-matching ids", d["model"] == "english", d["model"])
    d = r.route(EN, SMOKE_Q, model="typed-decisions")
    check("explicit model wins over detection", d["model"] == "typed-decisions", d["model"])

    print(f"== F: differential vs torch laya-serve on :{TORCH_PORT} (english) ==", flush=True)
    mlx_proc = start([MLX_PY, os.path.join(HERE, "serve.py")], {}, MLX_PORT, "mlx-serve")
    torch_proc = start([TORCH_SERVE], {"LAYA_MODELS": "english", "LAYA_PRELOAD": "1"},
                       TORCH_PORT, "torch-serve")
    try:
        worst = 0.0
        for tag, qs in [("smoke3", SMOKE_Q), ("score2", SCORE_2), ("noul-crit", NOUL_CRIT),
                        ("choice12", CHOICE_12)]:
            s1, r1 = req(TORCH, "POST", "/v1/systemone", {"state": EN, "questions": qs})
            s2, r2 = req(MLX, "POST", "/v1/systemone", {"state": EN, "questions": qs})
            if s1 != 200 or s2 != 200:
                check(f"diff {tag}: both 200", False, f"torch={s1} mlx={s2}")
                continue
            check(f"diff {tag}: top-level field sets equal",
                  set(r1) == set(r2), f"{sorted(r1)} vs {sorted(r2)}")
            check(f"diff {tag}: routing decision equal",
                  r1["routing"]["model"] == r2["routing"]["model"],
                  f"{r1['routing']['model']} vs {r2['routing']['model']}")
            for qid in qs:
                a1, a2 = r1["answers"][qid], r2["answers"][qid]
                check(f"diff {tag}/{qid}: field sets equal", set(a1) == set(a2),
                      f"{sorted(a1)} vs {sorted(a2)}")
                for fld in ("type", "choice"):
                    if fld in a1:
                        check(f"diff {tag}/{qid}: {fld} equal", a1[fld] == a2[fld],
                              f"{a1[fld]!r} vs {a2[fld]!r}")
                p1, p2 = a1.get("probabilities", {}), a2.get("probabilities", {})
                if p1 and set(p1) == set(p2):
                    worst = max(worst, sum(abs(p1[k] - p2[k]) for k in p1))
                for fld in ("score", "noul", "confidence"):
                    if fld in a1 and is_num(a1[fld]) and is_num(a2[fld]):
                        if abs(a1[fld] - a2[fld]) > 0.15:
                            check(f"diff {tag}/{qid}: {fld} within 0.15", False,
                                  f"torch={a1[fld]} mlx={a2[fld]}")
        print(f"  [INFO] worst per-question probability L1 delta torch(fp32) vs mlx(fp16): "
              f"{worst:.4f}", flush=True)
    finally:
        stop(torch_proc)
        stop(mlx_proc)

    print(f"\n{'R8 CONTRACT OK' if not deviations else 'R8 CONTRACT DEVIATIONS: ' + str(len(deviations))}"
          f" ({passed} checks passed)", flush=True)
    for d in deviations:
        print(f"  - {d}", flush=True)
    sys.exit(1 if deviations else 0)


if __name__ == "__main__":
    main()
