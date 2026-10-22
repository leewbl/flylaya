"""flylaya.scene — flylaya.scene.v1 contract: parse, validate, mirror, clock.

TASK-0009 / design doc §4 (flylaya-next-experiment-system-design.md is the
sole spec). Scene files are JSON in m5/scenes/<scene_id>.json.

Contract points implemented here:
- Strict parse: unknown keys are rejected (dimensional keys must carry
  their unit suffix, e.g. radius_m — a unitless "radius" is an unknown
  key, which is how "missing unit" surfaces); arena out-of-bounds
  cylinders, duplicate obstacle ids, contradictory sampling periods
  (duration/decision vs neural dt) and contradictory stimulus event
  sequences are all hard errors.
- mirror_scene(): reflects geometry + start pose + expected action sign
  (and light azimuth) about the arena mid-plane. It transforms the scene
  the sim will run — never just the replay camera.
- SceneClock: t_s event delivery for stimulus_on/stimulus_off, plus the
  diagnostic windows (baseline -> stimulus -> observe).
- stream_rngs(): four independent RNG streams (scene/controller/neural/
  motor) keyed by scene_id + version + seed. They share no state with the
  Laya sampler (intent.py owns its RNG) or with legacy World layouts.
- Scene.display(): the single m->cm / az-el conversion used by trajectory
  meta and the viewer (m4 world_meta contract: obstacles x/z/r/h in cm,
  sun azimuth_deg/elevation_deg).
"""
import json
import math
import os

import numpy as np

SCHEMA_VERSION = "flylaya.scene.v1"
# v1.1 (TASK-0026): adds light.floor_texture {contrast} + the
# 'floor_texture' stimulus target. v1 files stay fully valid.
SCHEMA_VERSIONS = (SCHEMA_VERSION, "flylaya.scene.v1.1")
STREAM_NAMES = ("scene", "controller", "neural", "motor")
EVENT_KINDS = ("stimulus_on", "stimulus_off")
MAX_SPEED_M_S = 0.5  # world.MAX_SPEED; import cycle avoided by restating


class SceneError(ValueError):
    """Scene file violates the flylaya.scene.v1 contract."""


# ---------------------------------------------------------------- validate

def _req(d, key, where):
    if key not in d:
        raise SceneError(f"{where}: missing required key {key!r}")
    return d[key]


def _num(v, where, lo=None, hi=None, lo_inc=True, hi_inc=True):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise SceneError(f"{where}: expected a number, got {v!r}")
    v = float(v)
    if not math.isfinite(v):
        raise SceneError(f"{where}: non-finite value {v!r}")
    if lo is not None and (v >= lo if lo_inc else v > lo):
        pass
    elif lo is not None:
        raise SceneError(f"{where}: {v} out of range (< {lo})")
    if hi is not None and (v <= hi if hi_inc else v < hi):
        pass
    elif hi is not None:
        raise SceneError(f"{where}: {v} out of range (> {hi})")
    return v


def _vec3(v, where):
    if not isinstance(v, list) or len(v) != 3:
        raise SceneError(f"{where}: expected [x, y, z], got {v!r}")
    return [_num(x, where) for x in v]


def _unknown(d, allowed, where):
    bad = sorted(set(d) - set(allowed))
    if bad:
        hint = (" (dimensional keys carry unit suffixes, e.g. radius_m / "
                "center_xy_m / t_s — a bare unitless name is unknown)"
                if any(k in ("radius", "height", "center_xy", "t", "position",
                             "speed", "duration", "arena") for k in bad) else "")
        raise SceneError(f"{where}: unknown key(s) {bad}{hint}")


class Scene:
    """Validated scene. Attributes are SI (m, s, deg) throughout."""

    def __init__(self, raw, source=None):
        if not isinstance(raw, dict):
            raise SceneError("scene root must be a JSON object")
        _unknown(raw, {"schema_version", "scene_id", "version", "arena_m",
                       "duration_s", "decision_dt_s", "neural_dt_s", "start",
                       "light", "obstacles", "events", "mirror_axis",
                       "random_streams", "windows", "expect"}, "scene")
        if _req(raw, "schema_version", "scene") not in SCHEMA_VERSIONS:
            raise SceneError(f"scene: schema_version must be one of {SCHEMA_VERSIONS}, "
                             f"got {raw['schema_version']!r}")
        self.schema = raw["schema_version"]
        self.source = source
        sid = _req(raw, "scene_id", "scene")
        if not isinstance(sid, str) or not sid or "/" in sid or ".." in sid:
            raise SceneError(f"scene: bad scene_id {sid!r}")
        self.scene_id = sid
        self.version = int(raw.get("version", 1))
        if self.version < 1:
            raise SceneError("scene: version must be >= 1")

        self.arena = _vec3(_req(raw, "arena_m", "scene"), "arena_m")
        if not all(0.1 < a <= 5.0 for a in self.arena):
            raise SceneError(f"arena_m: unreasonable arena {self.arena}")

        self.duration_s = _num(_req(raw, "duration_s", "scene"), "duration_s", lo=0)
        self.decision_dt_s = _num(_req(raw, "decision_dt_s", "scene"),
                                  "decision_dt_s", lo=0)
        self.neural_dt_s = _num(_req(raw, "neural_dt_s", "scene"),
                                "neural_dt_s", lo=0)
        for name, dt in (("duration_s", self.duration_s),
                         ("decision_dt_s", self.decision_dt_s)):
            n = dt / self.neural_dt_s
            if abs(n - round(n)) > 1e-9:
                raise SceneError(
                    f"contradictory sampling periods: {name}={dt} is not an "
                    f"integer multiple of neural_dt_s={self.neural_dt_s}")

        st = _req(raw, "start", "scene")
        _unknown(st, {"position_m", "yaw_deg", "speed_m_s"}, "start")
        self.start_pos = _vec3(_req(st, "position_m", "start"), "start.position_m")
        ax, ay, az = self.arena
        for i, (v, hi) in enumerate(zip(self.start_pos, (ax, ay, az))):
            if not (0.01 <= v <= hi - 0.01):
                raise SceneError(f"start.position_m[{i}]={v} outside arena "
                                 f"(0.01, {hi - 0.01:.2f})")
        self.start_yaw_deg = _num(_req(st, "yaw_deg", "start"), "start.yaw_deg")
        self.start_speed = _num(_req(st, "speed_m_s", "start"), "start.speed_m_s",
                                lo=0, hi=MAX_SPEED_M_S, hi_inc=True)

        self.light = self._validate_light(_req(raw, "light", "scene"))
        self.obstacles = self._validate_obstacles(raw.get("obstacles", []))
        self.events = self._validate_events(raw.get("events", []))
        ma = _req(raw, "mirror_axis", "scene")
        if ma not in ("x", "y"):
            raise SceneError(f"mirror_axis must be 'x' or 'y', got {ma!r}")
        self.mirror_axis = ma
        streams = _req(raw, "random_streams", "scene")
        if not isinstance(streams, list) or set(streams) != set(STREAM_NAMES):
            raise SceneError(f"random_streams must be exactly {list(STREAM_NAMES)}, "
                             f"got {streams!r}")
        self.streams = tuple(STREAM_NAMES)
        self.windows = self._validate_windows(raw.get("windows", []))
        self.expect = self._validate_expect(raw.get("expect"))

    # ------------------------------------------------------------ light
    def _validate_light(self, li):
        _unknown(li, {"mode", "level", "azimuth_deg", "elevation_deg",
                      "intensity", "initially_on", "floor_texture"}, "light")
        mode = _req(li, "mode", "light")
        out = {"mode": mode}
        if mode == "uniform":
            out["level"] = _num(li.get("level", 0.45), "light.level", lo=0, hi=1)
        elif mode == "directional":
            out["azimuth_deg"] = _num(_req(li, "azimuth_deg", "light.directional"),
                                      "light.azimuth_deg", lo=0, hi=360, hi_inc=False)
            out["elevation_deg"] = _num(li.get("elevation_deg", 45.0),
                                        "light.elevation_deg", lo=-90, hi=90,
                                        lo_inc=False, hi_inc=False)
            out["intensity"] = _num(li.get("intensity", 1.0), "light.intensity",
                                    lo=0, hi=1, hi_inc=True)
            io = li.get("initially_on", True)
            if not isinstance(io, bool):
                raise SceneError("light.initially_on must be a boolean")
            out["initially_on"] = io
        else:
            raise SceneError(f"light.mode must be 'uniform' or 'directional', "
                             f"got {mode!r}")
        # v1.1: floor texture (Straw optic-flow setpoint test V2-2). Texture
        # modulates the VENTRAL floor-glow statistics by `contrast`; it
        # carries no vertical-position information by construction (fixed
        # receptor-space pattern, mean-preserving).
        if "floor_texture" in li:
            ft = li["floor_texture"]
            if not isinstance(ft, dict):
                raise SceneError("light.floor_texture must be an object")
            _unknown(ft, {"contrast"}, "light.floor_texture")
            out["floor_texture"] = {
                "contrast": _num(_req(ft, "contrast", "light.floor_texture"),
                                 "light.floor_texture.contrast", lo=0, hi=1)}
        return out

    # ------------------------------------------------------------ obstacles
    def _validate_obstacles(self, obs):
        if not isinstance(obs, list):
            raise SceneError("obstacles must be a list")
        ax, ay, az = self.arena
        seen = set()
        out = []
        for i, ob in enumerate(obs):
            where = f"obstacles[{i}]"
            _unknown(ob, {"id", "shape", "center_xy_m", "radius_m",
                          "height_m", "enabled"}, where)
            oid = _req(ob, "id", where)
            if not isinstance(oid, str) or not oid or oid == "light":
                raise SceneError(f"{where}: bad id {oid!r} ('light' is reserved)")
            if oid in seen:
                raise SceneError(f"{where}: duplicate obstacle id {oid!r}")
            seen.add(oid)
            if _req(ob, "shape", where) != "cylinder":
                raise SceneError(f"{where}: only shape 'cylinder' is supported")
            cx, cy = _req(ob, "center_xy_m", where)
            cx = _num(cx, f"{where}.center_xy_m[0]")
            cy = _num(cy, f"{where}.center_xy_m[1]")
            r = _num(_req(ob, "radius_m", where), f"{where}.radius_m", lo=0, hi=0.25)
            h = _num(_req(ob, "height_m", where), f"{where}.height_m", lo=0, hi=az)
            if not (r <= cx <= ax - r and r <= cy <= ay - r):
                raise SceneError(
                    f"{where}: cylinder id {oid!r} [{cx:.3f},{cy:.3f}] r={r:.3f} "
                    f"is not fully inside the arena footprint {ax:.1f}x{ay:.1f}")
            en = ob.get("enabled", True)
            if not isinstance(en, bool):
                raise SceneError(f"{where}.enabled must be a boolean")
            out.append({"id": oid, "shape": "cylinder",
                        "center_xy_m": [cx, cy], "radius_m": r,
                        "height_m": h, "enabled": en})
        return out

    # ------------------------------------------------------------ events
    def _validate_events(self, evs):
        if not isinstance(evs, list):
            raise SceneError("events must be a list")
        state = {ob["id"]: ob["enabled"] for ob in self.obstacles}
        state["light"] = self.light.get("initially_on", True)
        state["floor_texture"] = False   # texture starts off; events toggle
        seen = set()
        out = []
        for i, ev in enumerate(evs):
            where = f"events[{i}]"
            _unknown(ev, {"t_s", "kind", "target"}, where)
            t = _num(_req(ev, "t_s", where), f"{where}.t_s", lo=0,
                     hi=self.duration_s, lo_inc=False, hi_inc=True)
            kind = _req(ev, "kind", where)
            if kind not in EVENT_KINDS:
                raise SceneError(f"{where}: kind must be one of {EVENT_KINDS}, "
                                 f"got {kind!r}")
            tgt = _req(ev, "target", where)
            if tgt not in state:
                raise SceneError(f"{where}: target {tgt!r} is not a known "
                                 f"obstacle id, 'light' or 'floor_texture'")
            key = (t, tgt)
            if key in seen:
                raise SceneError(f"{where}: duplicate event at t={t}s on {tgt!r}")
            seen.add(key)
            on = kind == "stimulus_on"
            if state[tgt] == on:
                raise SceneError(
                    f"{where}: contradictory stimulus — {tgt!r} is already "
                    f"{'on' if on else 'off'} at t={t}s")
            state[tgt] = on
            out.append({"t_s": t, "kind": kind, "target": tgt})
        out.sort(key=lambda e: e["t_s"])
        return out

    # ------------------------------------------------------------ windows
    def _validate_windows(self, wins):
        if not isinstance(wins, list):
            raise SceneError("windows must be a list")
        out = []
        for i, w in enumerate(wins):
            where = f"windows[{i}]"
            _unknown(w, {"name", "t_s"}, where)
            name = _req(w, "name", where)
            if not isinstance(name, str) or not name:
                raise SceneError(f"{where}: bad name {name!r}")
            ts = _req(w, "t_s", where)
            if not isinstance(ts, list) or len(ts) != 2:
                raise SceneError(f"{where}: t_s must be [start, end]")
            a = _num(ts[0], f"{where}.t_s[0]", lo=0, hi=self.duration_s)
            b = _num(ts[1], f"{where}.t_s[1]", lo=0, hi=self.duration_s)
            if a >= b:
                raise SceneError(f"{where}: window must have start < end")
            out.append({"name": name, "t_s": [a, b]})
        return out

    def _validate_expect(self, ex):
        if ex is None:
            return None
        _unknown(ex, {"initial_turn", "bearing_deg", "note"}, "expect")
        out = dict(ex)
        if "initial_turn" in ex:
            if ex["initial_turn"] not in ("left", "right", "none"):
                raise SceneError("expect.initial_turn must be left|right|none")
        if "bearing_deg" in ex:
            out["bearing_deg"] = _num(ex["bearing_deg"], "expect.bearing_deg",
                                      lo=-180, hi=180, hi_inc=False)
        return out

    # ------------------------------------------------------------ views
    def sun_vector(self):
        """Unit vector of the directional light, or None for uniform mode."""
        if self.light["mode"] != "directional":
            return None
        az = math.radians(self.light["azimuth_deg"])
        el = math.radians(self.light["elevation_deg"])
        return np.array([math.cos(el) * math.cos(az),
                         math.cos(el) * math.sin(az),
                         math.sin(el)])

    def obstacle_array(self):
        """(N,4) float array [cx, cy, r, h] for World (row i = obstacles[i])."""
        if not self.obstacles:
            return np.zeros((0, 4))
        return np.array([[*ob["center_xy_m"], ob["radius_m"], ob["height_m"]]
                         for ob in self.obstacles])

    def display(self):
        """Single unit conversion for trajectory meta / viewer (cm, deg).

        Same contract as m4 run_batch.world_meta: obstacles x/z/r/h in cm,
        sun as azimuth_deg/elevation_deg. All scene-mode consumers route
        through this one function (design §4).
        """
        return {
            "scene_id": self.scene_id, "version": self.version,
            "schema": SCHEMA_VERSION,
            "arena_cm": [round(a * 100.0, 2) for a in self.arena],
            "obstacles": [{"id": ob["id"],
                           "x": round(ob["center_xy_m"][0] * 100.0, 2),
                           "z": round(ob["center_xy_m"][1] * 100.0, 2),
                           "r": round(ob["radius_m"] * 100.0, 2),
                           "h": round(ob["height_m"] * 100.0, 2),
                           "enabled": ob["enabled"]}
                          for ob in self.obstacles],
            "sun": ({"azimuth_deg": round(self.light["azimuth_deg"], 2),
                     "elevation_deg": round(self.light["elevation_deg"], 2),
                     "intensity": round(self.light["intensity"], 3)}
                    if self.light["mode"] == "directional" else None),
            "windows": [dict(w) for w in self.windows],
        }

    def to_dict(self):
        """Canonical JSON dict (round-trips through Scene unchanged)."""
        d = {"schema_version": self.schema, "scene_id": self.scene_id,
             "version": self.version,
             "arena_m": list(self.arena), "duration_s": self.duration_s,
             "decision_dt_s": self.decision_dt_s,
             "neural_dt_s": self.neural_dt_s,
             "start": {"position_m": list(self.start_pos),
                       "yaw_deg": self.start_yaw_deg,
                       "speed_m_s": self.start_speed},
             "light": dict(self.light),
             "obstacles": [dict(o) for o in self.obstacles],
             "events": [dict(e) for e in self.events],
             "mirror_axis": self.mirror_axis,
             "random_streams": list(self.streams)}
        if self.windows:
            d["windows"] = [dict(w) for w in self.windows]
        if self.expect is not None:
            d["expect"] = dict(self.expect)
        return d


def load_scene(src):
    """From a path (m5/scenes/<id>.json) or an already-parsed dict."""
    if isinstance(src, Scene):
        return src
    if isinstance(src, dict):
        return Scene(src)
    with open(src) as f:
        return Scene(json.load(f), source=os.path.abspath(src))


# ---------------------------------------------------------------- mirror

def mirror_scene(src, axis=None, scene_id=None):
    """Reflect a scene about an arena mid-plane — the sim input itself.

    axis 'x': reflect across the plane y = arena_y/2 (left/right flip):
    y -> ay - y, yaw -> -yaw, azimuth -> (360 - az) % 360.
    axis 'y': x -> ax - x, yaw -> 180 - yaw, azimuth -> (180 - az) % 360.
    Both are orientation-reversing: geometry, start pose, light azimuth
    and the expected action sign (expect.initial_turn / bearing_deg)
    transform together. scene_id gets its left/right token swapped unless
    given explicitly.
    """
    scene = load_scene(src)
    axis = axis or scene.mirror_axis
    if axis not in ("x", "y"):
        raise SceneError(f"mirror axis must be 'x' or 'y', got {axis!r}")
    d = scene.to_dict()
    ax, ay, _ = scene.arena
    if axis == "x":
        flip = lambda x, y: (x, ay - y)  # noqa: E731
    else:
        flip = lambda x, y: (ax - x, y)  # noqa: E731

    px, py, pz = d["start"]["position_m"]
    d["start"]["position_m"] = [round(v, 12) for v in (*flip(px, py), pz)]
    d["start"]["yaw_deg"] = round((-d["start"]["yaw_deg"] if axis == "x"
                                   else 180.0 - d["start"]["yaw_deg"]) % 360.0, 12)
    for ob in d["obstacles"]:
        ob["center_xy_m"] = [round(v, 12) for v in flip(*ob["center_xy_m"])]
    if d["light"]["mode"] == "directional":
        az = d["light"]["azimuth_deg"]
        d["light"]["azimuth_deg"] = round((360.0 - az if axis == "x"
                                           else 180.0 - az) % 360.0, 12)
    if d.get("expect"):
        if d["expect"].get("initial_turn") in ("left", "right"):
            d["expect"]["initial_turn"] = ("right"
                                           if d["expect"]["initial_turn"] == "left"
                                           else "left")
        if "bearing_deg" in d["expect"]:
            d["expect"]["bearing_deg"] = round(-d["expect"]["bearing_deg"], 12)
    new_id = scene_id
    if new_id is None:
        sid = scene.scene_id
        if "_left" in sid:
            new_id = sid.replace("_left", "_right")
        elif "_right" in sid:
            new_id = sid.replace("_right", "_left")
        else:
            raise SceneError(f"scene_id {sid!r} has no _left/_right token; "
                             "pass scene_id= explicitly")
    d["scene_id"] = new_id
    return Scene(d)  # full re-validation on the mirrored content


# ---------------------------------------------------------------- clock

class SceneClock:
    """Monotonic t_s delivery of scene events (stimulus switches)."""

    def __init__(self, scene):
        self.events = [dict(e) for e in scene.events]
        self.i = 0

    def due(self, t_s):
        """Events with t_s <= now, in time order; each delivered once."""
        out = []
        while self.i < len(self.events) and self.events[self.i]["t_s"] <= t_s + 1e-9:
            out.append(self.events[self.i])
            self.i += 1
        return out


# ---------------------------------------------------------------- streams

def _fnv32(data):
    h = 0x811C9DC5
    for b in data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def stream_rngs(scene, seed):
    """Four independent PCG64 streams keyed by (seed, scene identity, name).

    Independent of the Laya sampler (LayaIntentSource owns its RNG) and of
    legacy World layout RNG. Same scene_id+version+seed -> same streams.
    """
    scene = load_scene(scene)
    tag = f"{scene.scene_id}|v{scene.version}".encode()
    return {name: np.random.default_rng(
                np.random.SeedSequence([int(seed) & 0xFFFFFFFF, _fnv32(tag)],
                                       spawn_key=(_fnv32(name.encode()),)))
            for name in scene.streams}
