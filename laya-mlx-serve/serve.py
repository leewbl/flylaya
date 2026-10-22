"""HTTP server exposing Laya-MLX over TypeSafe Jev's ``/v1/systemone`` wire protocol.

Port of laya's torch ``serve.py`` to the laya_mlx backend (Apple Silicon, MLX).
Wire behaviour is identical to laya-serve, so a client written against Jev or
laya-serve only swaps its baseUrl:

- ``GET /health`` -> ``{"status": "ok", "loaded": [...], "device": "gpu(0)"}``
- ``POST /v1/systemone`` ``{state, questions, model?}`` ->
  ``{model, answers, usage, routing}``  (laya_mlx's ``Router.predict`` output is
  already Jev-shaped)
- optional bearer auth (``LAYA_API_KEY``) -> 401 without/with a wrong token
- 400 when the body lacks ``questions`` (or is not valid JSON)
- 422 when the model/tokenizer rejects the request (unknown question type, too
  many options for the token budget, ...)

Configuration (env vars, same contract as laya-serve):

======================  ==============================================  =========
env var                 meaning                                          default
======================  ==============================================  =========
``LAYA_HOST``           bind address                                     0.0.0.0
``LAYA_PORT``           bind port                                        8000
``LAYA_PRELOAD``        build checkpoints at startup, not lazily         1
``LAYA_MODELS``         comma list to preload (english,multilingual,     english,
                        typed-decisions); empty = every checkpoint      multilingual
``LAYA_AUTO_TASK``      auto-route to the typed-decisions checkpoint    0
``LAYA_API_KEY``        if set, require ``Authorization: Bearer <it>``   (none)
``LAYA_DTYPE``          MLX weights dtype (float16/float32/bfloat16)    float16
``LAYA_LOG_LEVEL``      uvicorn log level                                info
======================  ==============================================  =========

Deviations from laya-serve, both deliberate:

- ``LAYA_DEVICE``/``LAYA_THREADS`` do not apply (MLX always runs through
  ``mx.default_device()``; there is no torch intra-op pool to cap). ``/health``
  reports the actual MLX device instead of the configured one.
- The default preload set is english+multilingual -- the two checkpoints the
  router actually chooses between -- instead of all three. Preloading
  typed-decisions too costs a ~800MB download and resident memory while it is
  only reachable via an explicit ``model`` field or ``LAYA_AUTO_TASK``; opt in
  with ``LAYA_MODELS=""`` (all) or an explicit list.

The multilingual checkpoint is mounted from the pre-converted FP16 MLX mirror
(``aac6fef/laya-multilingual-mlx``, weight-parity verified 63/63 against
upstream) so a warm cache starts fully offline; the bundle subfolder works too.

Heavy imports (fastapi, uvicorn, mlx via Router) are deferred exactly like the
torch original, so importing this module stays cheap.
"""
import os
from typing import Any, Dict, List, Optional

_KNOWN_MODELS = {"english", "multilingual", "typed-decisions"}

# laya_mlx Router accepts hub ids directly via Router(models=...): value is a
# repo (optionally "repo/subfolder"). Published ids map onto checkpoint keys so
# a Jev/laya client can name a checkpoint in the `model` field.
_PUBLISHED_MODEL_IDS = {
    "convaiinnovations/laya-multilingual": "multilingual",
    "convaiinnovations/laya-typed-decisions": "typed-decisions",
    "aac6fef/laya-multilingual-mlx": "multilingual",
}

# Checkpoint specs the router mounts (same layout as laya_mlx.STANDALONE_MODELS,
# with multilingual pointed at the pre-converted FP16 MLX mirror).
_MODEL_SPECS = {
    "english": "convaiinnovations/laya",
    "multilingual": "aac6fef/laya-multilingual-mlx",
    "typed-decisions": "convaiinnovations/laya/typed-decisions",
}

_DEFAULT_PRELOAD = ["english", "multilingual"]


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _resolve_model(model: Optional[str]) -> Optional[str]:
    """Map a client's `model` field onto a Laya checkpoint, or None to auto-route."""
    if not model:
        return None
    published = _PUBLISHED_MODEL_IDS.get(str(model).strip().lower())
    if published is not None:
        return published
    from laya_mlx.router import normalise_name

    # normalise_name raises ValueError on anything that is not a known checkpoint
    # or alias. A Jev client's `model` field (e.g. "jev-1") is expected to miss;
    # treat that as "no explicit checkpoint" and let the router auto-select.
    try:
        key = normalise_name(model)
    except Exception:
        return None
    return key if key in _KNOWN_MODELS else None


def _preload_names() -> Optional[List[str]]:
    """LAYA_MODELS -> list of checkpoint keys; empty/absent means the default set."""
    models_env = os.environ.get("LAYA_MODELS")
    if models_env is None:
        return list(_DEFAULT_PRELOAD)
    names = [m.strip() for m in models_env.split(",") if m.strip()]
    return names or None  # explicit empty = every checkpoint, like laya-serve


def build_router():
    """Build a laya_mlx Router from the environment, preloading unless told otherwise."""
    from laya_mlx import Router

    router = Router(
        models=_MODEL_SPECS,
        dtype=os.environ.get("LAYA_DTYPE", "float16"),
        auto_task_detection=_env_bool("LAYA_AUTO_TASK", False),
    )
    if _env_bool("LAYA_PRELOAD", True):
        router.preload(_preload_names())
    return router


def _mlx_device() -> str:
    import mlx.core as mx

    return str(mx.default_device())


def create_app(router: Optional[Any] = None):
    """Build the FastAPI app. Pass a Router to inject one (tests); otherwise one
    is built from the environment (and preloaded) at app-creation time."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import FastAPI, Header, HTTPException, Request

    if router is None:
        router = build_router()
    api_key = os.environ.get("LAYA_API_KEY") or None

    # MLX forward passes are synchronous (mx.eval blocks on the GPU) and the MLX
    # runtime is safest driven from one thread at a time, so requests funnel
    # through a single executor worker behind an asyncio gate: the event loop
    # stays free (`GET /health` included) while predictions serialise. Same
    # shape as laya-serve, minus the CPU-thread-pool tuning.
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="laya-mlx-infer")
    # Created on first request, not here: an `asyncio.Lock` binds to the loop
    # running when it is first awaited, and `create_app` may run before any
    # loop exists (module scope, TestClient startup, a preload script).
    gate: Optional[asyncio.Lock] = None

    app = FastAPI(
        title="laya-mlx-serve",
        summary="Laya System-1 decisions on Apple Silicon (MLX) over the TypeSafe Jev /v1/systemone protocol",
    )

    def _check_auth(authorization: Optional[str]) -> None:
        if api_key is None:
            return
        if authorization != "Bearer " + api_key:
            raise HTTPException(status_code=401, detail="invalid or missing bearer token")

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "loaded": router.loaded,
            "device": _mlx_device(),
        }

    @app.post("/v1/systemone")
    async def systemone(request: Request, authorization: Optional[str] = Header(default=None)):
        nonlocal gate
        _check_auth(authorization)
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="request body must be valid JSON")
        if not isinstance(body, dict) or "questions" not in body:
            raise HTTPException(status_code=400, detail="request body must be an object with a 'questions' field")
        state = body.get("state")
        questions = body["questions"]
        model = _resolve_model(body.get("model"))
        if gate is None:
            gate = asyncio.Lock()
        try:
            # laya_mlx's result is already Jev-shaped: {model, answers, usage,
            # routing}. hs-jev decodes `answers` and `usage` and ignores the rest.
            async with gate:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    pool, lambda: router.predict(state, questions, model=model))
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 -- surface model/tokenizer errors as 422
            raise HTTPException(status_code=422, detail=str(e))

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        create_app(),
        host=os.environ.get("LAYA_HOST", "0.0.0.0"),
        port=int(os.environ.get("LAYA_PORT", "8000")),
        log_level=os.environ.get("LAYA_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
