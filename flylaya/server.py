"""FlyLaya M1 server: FastAPI + websocket sim loop + static three.js viewer.

Loop (10 Hz bio frames, matches the connectome frame budget):
  luminance = world.render_luminance()
  dn_rates = brain.step(luminance, dt)
  world.step_motor(dn_rates, dt)
  intent = intent_source.poll(...)          # M1: fixed rotation stub
  broadcast state + HUD to all viewers

Controls (inbound ws json): pause/resume, speed in {0.25,0.5,1,2}, reseed.

Run: FLYLAYA_PORT=8900 python run.py   (skeleton brain, no connectome)
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .brains import FixedIntentSource, make_brain
from .world import World

STATIC = Path(__file__).resolve().parent.parent / "static"
FRAME_S = 0.1  # bio frame, seconds


class Session:
    # (bio frames per tick, wall seconds per tick) per speed multiplier
    SPEEDS = {0.25: (1, 0.4), 0.5: (1, 0.2), 1.0: (1, 0.1), 2.0: (2, 0.1)}

    def __init__(self, seed=0, brain_kind="skeleton", intent_kind="fixed",
                 laya_url="http://127.0.0.1:8000/v1/systemone"):
        self.brain_kind = brain_kind
        self.intent_kind = intent_kind
        self.laya_url = laya_url
        self.paused = False
        self.speed = 1.0
        self.clients = set()
        self.rt_factor = 1.0
        self.reset(seed)

    def reset(self, seed):
        self.seed = int(seed)
        self.world = World(seed=self.seed)
        # Rebuild cheap brains; the 892MB connectome persists across resets
        # (Sim has no rewind -- documented: connectome reseed resets world
        # and intent state, not neural state; full replay = process restart).
        if self.brain_kind != "connectome" or not hasattr(self, "brain"):
            self.brain = make_brain(self.brain_kind, seed=self.seed)
        if self.intent_kind == "laya":
            from .intent import LayaIntentSource

            self.intent_src = LayaIntentSource(
                url=self.laya_url,
                log_path=os.environ.get("FLYLAYA_INTENT_LOG") or None)
        else:
            if self.intent_kind != "fixed":
                logging.warning(
                    "FLYLAYA_INTENT=%r unknown; falling back to fixed rotation "
                    "(expected 'laya' or 'fixed')", self.intent_kind)
            self.intent_src = FixedIntentSource(
                log_path=os.environ.get("FLYLAYA_INTENT_LOG") or None)
        self.frame = 0
        self.last_intent, self.last_conf = "explore", 1.0
        self.last_gains = {"light": 1.0, "looming": 1.0, "wall": 1.0,
                           "thrust": 1.0, "yaw_noise": 1.0, "arousal": 1}

    async def broadcast(self, msg):
        dead = []
        for ws in self.clients:
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def run(self):
        last = time.perf_counter()
        while True:
            t0 = time.perf_counter()
            n_frames, interval = self.SPEEDS[self.speed]
            if not self.paused and self.clients:
                from .intent import modulation_for

                for _ in range(n_frames):
                    self.last_intent, self.last_conf = self.intent_src.poll(
                        self.frame, self.world, self.brain)
                    mod = modulation_for(self.last_intent,
                                         getattr(self.intent_src, "arousal", 1))
                    self.last_gains = mod
                    lum = self.world.render_luminance(mod)
                    rates = self.brain.step(lum, FRAME_S)
                    bias = self.intent_src.consume_yaw_bias() if hasattr(
                        self.intent_src, "consume_yaw_bias") else 0.0
                    self.world.step_motor(rates, FRAME_S,
                                          gains={"thrust": mod["thrust"]},
                                          yaw_noise=mod["yaw_noise"],
                                          rng=self.world.rng, yaw_bias=bias)
                    self.frame += 1
                await self.broadcast(self.state_msg())
            elapsed = time.perf_counter() - t0
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self.rt_factor = FRAME_S * n_frames / max(time.perf_counter() - last, 1e-6)
            last = time.perf_counter()

    def state_msg(self):
        snap = self.world.snapshot()
        hud = self.brain.hud()
        if hasattr(self.brain, "dn_snapshot"):
            dn = self.brain.dn_snapshot()
        elif hasattr(self.brain, "pools"):
            dn = {k: round(v, 2) for k, v in self.brain.pools.items()}
        else:
            dn = {}
        hud.update({
            "intent": self.last_intent,
            "intent_kind": self.intent_kind,
            "gains": self.last_gains,
            "intent_hud": getattr(self.intent_src, "hud", dict)(),
            "intent_confidence": self.last_conf,
            "dn": dn,
            "frame": self.frame,
            "rt_factor": round(self.rt_factor, 2),
            "paused": self.paused,
            "speed": self.speed,
            "seed": self.seed,
            "brain": self.brain_kind,
        })
        trail_pt = [round(float(v), 4) for v in self.world.pos]
        return {"type": "state", "t": round(self.frame * FRAME_S, 2),
                "fly": snap, "hud": hud, "trail": trail_pt}


app = FastAPI(title="flylaya")
SESSION = Session(seed=int(os.environ.get("FLYLAYA_SEED", "0")),
                  brain_kind=os.environ.get("FLYLAYA_BRAIN", "skeleton"),
                  intent_kind=os.environ.get("FLYLAYA_INTENT", "fixed"),
                  laya_url=os.environ.get("FLYLAYA_LAYA_URL",
                                          "http://127.0.0.1:8000/v1/systemone"))
@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/{name}")
async def static_file(name: str):
    p = STATIC / name
    if p.exists() and p.parent == STATIC:
        return FileResponse(p)
    return {"error": "not found"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    SESSION.clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "scene", **SESSION.world.scene(),
                                       "brain": SESSION.brain_kind}))
        await ws.send_text(json.dumps(SESSION.state_msg()))
        while True:
            data = json.loads(await ws.receive_text())
            cmd = data.get("cmd")
            if cmd == "pause":
                SESSION.paused = True
            elif cmd == "resume":
                SESSION.paused = False
            elif cmd == "speed":
                v = float(data.get("value", 1.0))
                SESSION.speed = v if v in (0.25, 0.5, 1.0, 2.0) else 1.0
            elif cmd == "reseed":
                SESSION.reset(int(data.get("value", 0)) or
                              int(np.random.default_rng().integers(0, 10 ** 9)))
            elif cmd == "reset":
                SESSION.reset(SESSION.seed)
            if cmd in ("pause", "resume", "speed", "reseed", "reset"):
                await ws.send_text(json.dumps(SESSION.state_msg()))
    except WebSocketDisconnect:
        pass
    finally:
        SESSION.clients.discard(ws)


@app.on_event("startup")
async def _start():
    asyncio.create_task(SESSION.run())
