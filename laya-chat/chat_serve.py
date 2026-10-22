"""Chat wrapper: laya-mlx-serve app + CORS + static chat page at "/".

Reuses serve.py's router/app verbatim; adds only the browser-facing pieces.
"""
import os
from pathlib import Path

import sys
sys.path.insert(0, "/Users/leewbl/aiworld/flylaya/laya-mlx-serve")
from serve import build_router, create_app  # noqa: E402

from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

HERE = Path(__file__).parent

app = create_app(build_router())
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    return FileResponse(HERE / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("LAYA_HOST", "127.0.0.1"),
        port=int(os.environ.get("LAYA_PORT", "8000")),
        log_level=os.environ.get("LAYA_LOG_LEVEL", "info"),
    )
