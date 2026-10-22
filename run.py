"""FlyLaya entry point: uvicorn on FLYLAYA_PORT (default 8900)."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("flylaya.server:app", host="127.0.0.1",
                port=int(os.environ.get("FLYLAYA_PORT", "8900")), log_level="warning")
