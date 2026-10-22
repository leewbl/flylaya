#!/usr/bin/env bash
# R10 regression runner: re-runs core suites and diffs against round baselines.
# Usage: ./r10_regression.sh  (from /Users/leewbl/aiworld/flylaya/laya-testbench)
set -uo pipefail
cd "$(dirname "$0")"
MLX_PY=/Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python
FAIL=0

echo "== [1/3] R3 accuracy regression (score_eval.py on recorded raw + fresh re-run) =="
./score_eval.py accuracy results/r3-eval-v1-results.jsonl > /tmp/r10_r3_recomputed.json || FAIL=1
python3 - << 'EOF' || FAIL=1
import json
gate_ok = True
m = json.load(open('/tmp/r10_r3_recomputed.json'))
checks = [
    ("choice acc", m["all|choice"]["acc"], 0.80),
    ("noul acc", m["all|noul"]["acc"], 0.90),
    ("en score MAE", m["en|score_mae"], 0.4981),
    ("zh score MAE", m["zh|score_mae"], 0.6995),
]
for name, now, base in checks:
    match = abs(now - base) < 1e-3
    gate_ok &= match
    print(f"  {name}: {now} (baseline {base}) {'OK' if match else 'DRIFT'}")
print("  R3 regression:", "STABLE" if gate_ok else "CHANGED")
EOF

echo "== [2/3] R8 contract regression =="
(cd /Users/leewbl/aiworld/flylaya/laya-mlx-serve && $MLX_PY contract_regression.py 2>&1 | tail -2) || FAIL=1

echo "== [3/3] R1 serve smoke + latency =="
(cd /Users/leewbl/aiworld/flylaya/laya-mlx-serve && $MLX_PY smoke_serve.py 2>&1 | tail -2) || FAIL=1

echo "== routing spot re-check (r4 results if present) =="
if [ -f results/r4-routing-results.jsonl ]; then
    ./score_eval.py routing results/r4-routing-results.jsonl | head -8 || FAIL=1
fi

echo "R10 REGRESSION EXIT=$FAIL"
exit $FAIL
