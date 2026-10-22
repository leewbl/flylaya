"""Self-test for flylaya.scene (TASK-0009 / design doc §4, gate G1).

Deterministic. Validates the flylaya.scene.v1 contract end to end:
- strict parse: unitless/unknown keys, out-of-bounds cylinders, duplicate
  ids, contradictory sampling periods and stimulus sequences all reject
- every shipped scene file loads and satisfies the spec table (S0-S4,
  single-cue geometry, rear negative control)
- mirror transform: geometry + start pose + light azimuth + expected
  action sign move together; the mirrored file on disk equals
  mirror_scene() of its pair
- event clock: stimulus_on/off delivery windows, obstacle enable toggles,
  light on/off changes the rendered retina, diagnostic windows parse
- G1 determinism: same scene_id + version + seed -> bit-identical world
  state and luminance over a driven rollout; different seed diverges
- mirror acts on real sensory data: S1_left vs S1_right retina vectors
  differ and the body-frame lateral glare centroid flips sign
- observer contract: World.scene() for scene worlds routes through the
  single m->cm conversion (display()), sun az/el consistent with the
  sun unit vector

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python m5/test_scene.py
"""
import copy
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from flylaya.scene import (Scene, SceneError, load_scene, mirror_scene,
                           stream_rngs)
from flylaya.world import World

SCENES = os.path.join(HERE, "scenes")
FAIL = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAIL.append(name)


def scene_dict(sid):
    return json.load(open(os.path.join(SCENES, f"{sid}.json")))


def expect_reject(name, mutate, msg_part=None):
    d = scene_dict("S2_obstacle_left")
    mutate(d)
    try:
        Scene(copy.deepcopy(d))
    except SceneError as e:
        ok = msg_part is None or msg_part in str(e)
        check(name, ok, str(e)[:110])
        return
    check(name, False, "no error raised")


# ---------------------------------------------------------------- parsing
check("all scene files load", all(
    load_scene(os.path.join(SCENES, f)).scene_id == f[:-5]
    for f in sorted(os.listdir(SCENES)) if f.endswith(".json")),
    ", ".join(sorted(f[:-5] for f in os.listdir(SCENES) if f.endswith(".json"))))

expect_reject("reject unitless key (radius)", lambda d: d["obstacles"][0].update(
    {"radius": 0.04}) or d["obstacles"][0].pop("radius_m"), "unit suffix")
expect_reject("reject out-of-bounds cylinder", lambda d: d["obstacles"][0].update(
    {"center_xy_m": [0.02, 0.54]}), "inside the arena")
expect_reject("reject duplicate obstacle ids", lambda d: d["obstacles"].append(
    dict(d["obstacles"][0])), "duplicate obstacle id")
expect_reject("reject contradictory decision_dt", lambda d: d.update(
    {"decision_dt_s": 0.35}), "integer multiple")
expect_reject("reject duration not multiple of neural_dt", lambda d: d.update(
    {"duration_s": 30.05}), "integer multiple")
expect_reject("reject wrong schema_version", lambda d: d.update(
    {"schema_version": "flylaya.scene.v2"}), "schema_version")
expect_reject("reject unknown top-level key", lambda d: d.update(
    {"obstacle_count": 1}), "unknown key")
expect_reject("reject stimulus off when already off", lambda d: d.update(
    {"events": [{"t_s": 5.0, "kind": "stimulus_off", "target": "o1"}]}),
    "contradictory stimulus")
expect_reject("reject double stimulus_on", lambda d: d.update(
    {"events": [{"t_s": 5.0, "kind": "stimulus_on", "target": "o1"},
                {"t_s": 9.0, "kind": "stimulus_on", "target": "o1"}]}),
    "contradictory stimulus")
expect_reject("reject event past duration", lambda d: d.update(
    {"events": [{"t_s": 31.0, "kind": "stimulus_on", "target": "o1"}]}),
    "t_s")
s2 = load_scene(os.path.join(SCENES, "S2_obstacle_left.json"))
ob = s2.obstacles[0]
dx = ob["center_xy_m"][0] - s2.start_pos[0]
dy = ob["center_xy_m"][1] - s2.start_pos[1]
dist = math.hypot(dx, dy)
cy, sy = math.cos(math.radians(s2.start_yaw_deg)), math.sin(math.radians(s2.start_yaw_deg))
# forward = delta . heading; left(CCW) = delta . heading rotated +90deg
bearing = math.degrees(math.atan2(-dx * sy + dy * cy, dx * cy + dy * sy))
check("S2 frontal distance in [0.20, 0.40] m", 0.20 <= dist <= 0.40, f"{dist:.3f}")
check("S2 frontal |bearing| in [20, 35] deg", 20 <= abs(bearing) <= 35, f"{bearing:.1f}")
rear = load_scene(os.path.join(SCENES, "S2_obstacle_rear_negctrl.json"))
rob = rear.obstacles[0]
rdx = rob["center_xy_m"][0] - rear.start_pos[0]
rdy = rob["center_xy_m"][1] - rear.start_pos[1]
rdist = math.hypot(rdx, rdy)
check("rear negative control: equal distance to frontal", abs(rdist - dist) < 0.005,
      f"{rdist:.3f} vs {dist:.3f}")
rcy, rsy = math.cos(math.radians(rear.start_yaw_deg)), math.sin(math.radians(rear.start_yaw_deg))
rbear = math.degrees(math.atan2(-rdx * rsy + rdy * rcy, rdx * rcy + rdy * rsy))
check("rear negative control: obstacle behind the fly", abs(rbear) > 155,
      f"{rbear:.1f} deg off heading")

# ---------------------------------------------------------------- mirror
for left, right in (("S1_light_left", "S1_light_right"),
                    ("S2_obstacle_left", "S2_obstacle_right")):
    m = mirror_scene(os.path.join(SCENES, f"{left}.json"))
    on_disk = Scene(scene_dict(right))
    check(f"mirror({left}) == {right} on disk",
          m.to_dict() == on_disk.to_dict(),
          "" if m.to_dict() == on_disk.to_dict() else
          f"diff: { {k: (m.to_dict()[k], on_disk.to_dict()[k]) for k in m.to_dict() if m.to_dict()[k] != on_disk.to_dict()[k]} }")

ml = mirror_scene(os.path.join(SCENES, "S1_light_left.json"))
sl, sr = load_scene(os.path.join(SCENES, "S1_light_left.json")), ml
check("mirror flips start y about mid-plane",
      abs(sl.start_pos[1] - (1.0 - sr.start_pos[1])) < 1e-12 and
      sl.start_pos[0] == sr.start_pos[0])
check("mirror negates start yaw", (sl.start_yaw_deg + sr.start_yaw_deg) % 360 == 0)
check("mirror reflects light azimuth", (sl.light["azimuth_deg"] +
      sr.light["azimuth_deg"]) % 360 == 0)
check("mirror swaps expected action sign",
      sl.expect["initial_turn"] == "left" and sr.expect["initial_turn"] == "right" and
      sl.expect["bearing_deg"] == -sr.expect["bearing_deg"])
my = mirror_scene(os.path.join(SCENES, "S3_wall.json"), scene_id="S3_wall_mir")
check("y-axis mirror maps S3_wall across x mid-plane",
      abs(my.start_pos[0] - 0.85) < 1e-12 and abs(my.start_yaw_deg - 0.0) < 1e-12,
      f"pos_x={my.start_pos[0]}, yaw={my.start_yaw_deg}")

# ---------------------------------------------------------------- clock
w2 = World.from_scene(os.path.join(SCENES, "S2_obstacle_left.json"), seed=7)
check("obstacle starts disabled", not w2.obstacle_enabled[0])
before = w2.render_luminance()
evs = w2.advance_clock(5.0)
check("event delivered at t=5", evs == [{"t_s": 5.0, "kind": "stimulus_on", "target": "o1"}])
check("obstacle enabled after event", w2.obstacle_enabled[0])
after = w2.render_luminance()
check("column stimulus changes the retina", float(np.abs(after - before).max()) > 0.01,
      f"max |dlum| = {float(np.abs(after - before).max()):.3f}")
check("clock is idempotent", w2.advance_clock(5.5) == [])

w1 = World.from_scene(os.path.join(SCENES, "S1_light_left.json"), seed=7)
flat = w1.render_luminance()
w1.advance_clock(5.0)
lit = w1.render_luminance()
check("uniform baseline before light event", float(flat.std()) < 0.06,
      f"std={float(flat.std()):.4f}")
check("directional light after event adds glare structure", float(lit.max() - flat.min()) > 0.3,
      f"range={float(lit.max() - lit.min()):.3f}")

# ---------------------------------------------------------------- G1 determinism
def rollout(scene_path, seed, frames=120):
    w = World.from_scene(scene_path, seed=seed)
    rows = []
    dn = {"DNp20_R": 1.5, "DNp20_L": 0.9, "MDN_R": 2.0, "MDN_L": 2.0,
          "DNa02_R": 0.2, "DNa02_L": 0.1, "DNpe017_R": 0.0, "DNpe017_L": 0.0}
    for i in range(frames):
        w.advance_clock(i * 0.1)
        lum = w.render_luminance()
        w.step_motor(dn, 0.1, yaw_noise=0.8, rng=w.rng)
        rows.append((w.snapshot(), float(lum.sum())))
    return rows

p1 = os.path.join(SCENES, "S2_obstacle_left.json")
a = rollout(p1, seed=11)
b = rollout(p1, seed=11)
c = rollout(p1, seed=12)
check("same scene+seed+version -> identical rollout", a == b)
check("different seed -> different rollout", a != c)

rngs_a = stream_rngs(load_scene(p1), 11)
rngs_b = stream_rngs(load_scene(p1), 11)
rngs_c = stream_rngs(load_scene(p1), 12)
check("streams reproducible per identity",
      all(np.array_equal(rngs_a[k].normal(size=8), rngs_b[k].normal(size=8))
          for k in rngs_a))
check("four streams mutually independent",
      len({tuple(rngs_a[k].integers(0, 1 << 30, size=4)) for k in rngs_a}) == 4)
check("streams reseed with seed", any(
    not np.array_equal(rngs_a[k].normal(size=8), rngs_c[k].normal(size=8))
    for k in rngs_a))

# ------------------------------------------- mirror changes real sensory data
def lateral_glare_centroid(w):
    """Lateral component (body frame, receptor +y axis) of glare centroid."""
    lum = w.render_luminance()
    wgt = np.clip(lum - 0.10, 0, 1) ** 2
    c = (wgt @ w.receptor_dirs) / max(float(wgt.sum()), 1e-9)
    return float(c[1])

wl = World.from_scene(os.path.join(SCENES, "S1_light_left.json"), seed=3)
wr = World.from_scene(os.path.join(SCENES, "S1_light_right.json"), seed=3)
wl.advance_clock(5.0)
wr.advance_clock(5.0)
ll = wl.render_luminance()
lr = wr.render_luminance()
check("mirror pair renders different retina vectors",
      float(np.abs(ll - lr).max()) > 0.05,
      f"max |dlum| = {float(np.abs(ll - lr).max()):.3f}")
cl = lateral_glare_centroid(wl)
cr = lateral_glare_centroid(wr)
check("body-frame lateral glare centroid flips sign under mirror",
      cl * cr < 0 and abs(abs(cl) - abs(cr)) < 0.3 * abs(cl),
      f"left={cl:+.3f} right={cr:+.3f}")
check("light is on the expected body side (left scene, +lateral)",
      cl > 0, f"centroid_lat={cl:+.3f} (receptor +y = CCW/left side)")

# ------------------------------------------------- observer/units contract
w4 = World.from_scene(os.path.join(SCENES, "S4_mixed_holdout.json"), seed=1)
disp = w4.scene()
check("scene() routes through display() with viewer contract",
      disp["scene_id"] == "S4_mixed_holdout" and
      set(disp["obstacles"][0]) >= {"x", "z", "r", "h"} and
      disp["sun"]["azimuth_deg"] == 200.0 and
      disp["obstacles"][0]["x"] == 42.0, json.dumps(disp["obstacles"][0]))
sun = w4.sun
az_back = math.degrees(math.atan2(sun[1], sun[0])) % 360
el_back = math.degrees(math.asin(sun[2]))
check("sun unit vector consistent with az/el display",
      abs(az_back - disp["sun"]["azimuth_deg"]) < 0.01 and
      abs(el_back - disp["sun"]["elevation_deg"]) < 0.01)
legacy = World(seed=5)
lscene = legacy.scene()
check("legacy world.scene() shape unchanged",
      isinstance(lscene["sun"], list) and len(lscene["obstacles"]) == 7 and
      set(lscene["obstacles"][0]) == {"x", "z", "r", "h"})
w0 = World.from_scene(os.path.join(SCENES, "S0_neutral.json"), seed=2)
check("uniform scene has no sun vector and flat-ish retina",
      w0.sun is None and float(w0.render_luminance().std()) < 0.06)

# scene reset stays deterministic
w2b = World.from_scene(os.path.join(SCENES, "S2_obstacle_left.json"), seed=9)
w2b.step_motor({"DNp20_R": 2.0, "DNp20_L": 1.0}, 0.1, yaw_noise=0.5, rng=w2b.rng)
w2b.reset()
check("scene reset restores exact start pose",
      np.allclose(w2b.pos, w2b.scene_obj.start_pos) and w2b.frames == 0)

# ---------------------------------------------------- scene v1.1 (0026)
s0v = load_scene(os.path.join(SCENES, "S0v_neutral.json"))
check("v1.1 scene loads with floor_texture and schema tag",
      s0v.schema == "flylaya.scene.v1.1" and
      s0v.light["floor_texture"]["contrast"] == 0.5)
v1_scene = load_scene(os.path.join(SCENES, "S1_light_left.json"))
check("v1 scenes keep the v1 schema on round-trip",
      v1_scene.to_dict()["schema_version"] == "flylaya.scene.v1")
wv = World.from_scene(os.path.join(SCENES, "S0v_neutral.json"), seed=1)
vent = wv.receptor_dirs[:, 2] < -0.3
lum_off = wv.render_luminance()
v_off = lum_off[vent]
wv.advance_clock(8.0)                      # texture on
lum_on = wv.render_luminance()
v_on = lum_on[vent]
wv.advance_clock(16.0)                     # texture off again
check("floor texture: ventral stats change, mean preserved, reversible",
      abs(v_off.mean() - v_on.mean()) < 0.01 and
      v_on.std() > 1.5 * v_off.std() and
      np.allclose(wv.render_luminance(), lum_off))
try:
    Scene({"schema_version": "flylaya.scene.v1.2", "scene_id": "x",
           "arena_m": [1, 1, 1], "duration_s": 30, "decision_dt_s": 0.3,
           "neural_dt_s": 0.1, "start": {"position_m": [.5, .5, .5],
                                         "yaw_deg": 0, "speed_m_s": 0.1},
           "light": {"mode": "uniform"}, "obstacles": [], "events": [],
           "mirror_axis": "x",
           "random_streams": ["scene", "controller", "neural", "motor"]})
    check("reject unknown schema version", False)
except SceneError:
    check("reject unknown schema version", True)
try:
    d = scene_dict("S0v_neutral")
    d["light"]["floor_texture"] = {"contrast": 1.5}
    Scene(d)
    check("reject floor_texture contrast > 1", False)
except SceneError:
    check("reject floor_texture contrast > 1", True)

print()
if FAIL:
    print(f"FAILED: {len(FAIL)} -> {FAIL}")
    sys.exit(1)
print("ALL PASS")
