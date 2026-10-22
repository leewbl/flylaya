# laya-mlx-serve

Jev-compatible HTTP service (`/v1/systemone`) backed by `laya_mlx` (MLX, Apple
Silicon) instead of torch. Ported from `laya/serve.py` 0.3.10; wire protocol,
env config and error contract are identical, so a Jev/laya-serve client swaps
only its `baseUrl`.

## Run

```bash
LAYA_HOST=127.0.0.1 LAYA_PORT=8000 /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python serve.py
```

Weights: english (`convaiinnovations/laya`) and multilingual
(`aac6fef/laya-multilingual-mlx`, pre-converted FP16) — both already in the HF
cache; the service runs with `HF_HUB_OFFLINE=1`. A cold cache needs
`HF_ENDPOINT=https://hf-mirror.com` (HF direct is unreachable in this network).

## Config

| env | default | meaning |
|---|---|---|
| `LAYA_HOST` / `LAYA_PORT` | `0.0.0.0` / `8000` | bind |
| `LAYA_PRELOAD` | `1` | build checkpoints at startup |
| `LAYA_MODELS` | `english,multilingual` | comma list to preload; empty = all three |
| `LAYA_AUTO_TASK` | `0` | auto-route typed-decisions workflows |
| `LAYA_API_KEY` | (none) | require `Authorization: Bearer <key>` |
| `LAYA_DTYPE` | `float16` | MLX weights dtype |
| `LAYA_LOG_LEVEL` | `info` | uvicorn log level |

Deviations from laya-serve: no `LAYA_DEVICE`/`LAYA_THREADS` (MLX-specific);
default preload set is english+multilingual instead of all three (typed-
decisions costs ~800MB download+RAM and is only reachable via explicit `model`
or `LAYA_AUTO_TASK`); `/health` reports the actual MLX device.

## Verify

```bash
/Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python smoke_serve.py
```

Self-contained acceptance: starts the service twice (plain, then with
`LAYA_API_KEY`), checks health/routing/answers/auth/error paths, measures warm
p50/p95 over 35 requests. Exits non-zero on failure.
