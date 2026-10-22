"""Self-test for the M6-W1 natural terrain world (TASK-0027).

Deterministic. Validates: map reproducibility, water/trees presence and
placement rules, the above-terrain invariant over a driven rollout,
altitude/water luminance responses, legacy-mode numerical isolation, and
exploration sanity (travel, no spin).
import math
import os
lum_high_g = lum_high - 0.08
lum_low_g = lum_low - 0.08
check("ventral glow grows near the ground (altitude signal)",
      lum_low_g > 1.5 * lum_high_g, f"low={lum_low_g:.4f} high={lum_high_g:.4f}")
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from flylaya.brains import make_brain
from flylaya.intent import modulation_for
from flylaya.terrain import Terrain
from flylaya.world import World

FAIL = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAIL.append(name)


# ------------------------------------------------------------------ map
t1 = Terrain(20260926)
t2 = Terrain(20260926)
xs = np.linspace(-64, 64, 128)
g1 = t1.height(*np.meshgrid(xs, xs))
g2 = t2.height(*np.meshgrid(xs, xs))
check("terrain map is a pure function of the seed (bit-identical)",
      np.array_equal(g1, g2) and t1.trees == t2.trees)
g3 = Terrain(20260927).height(*np.meshgrid(xs, xs))
check("different seed -> different map", not np.array_equal(g1, g3))
check("map has mountains (max > 8m) and valleys (min < 4m)",
      float(g1.max()) > 8.0 and float(g1.min()) < 4.0,
      f"h {float(g1.min()):.2f}-{float(g1.max()):.2f}")
water_frac = float((g1 < t1.water_level).mean())
check("water present as lakes (1-20% of map)", 0.01 < water_frac < 0.20,
      f"frac={water_frac:.3f}")
check("trees exist and all stand on dry, low-slope land",
      len(t1.trees) > 50 and all(
          t1.height_at(x, y) > t1.water_level + 0.4 for x, y, r, h in t1.trees))
check("outside the map the terrain falls back to a plain (no wall)",
      abs(t1.height_at(200.0, 0.0) - 1.0) < 1e-9)

# ------------------------------------------------------------- world mode
w = World.from_terrain(terrain_seed=20260926, seed=11)
check("terrain world spawns above dry ground",
      w.pos[2] > t1.height_at(w.pos[0], w.pos[1]) + 0.5)
check("terrain world has trees as obstacles and no arena box",
      len(w.obstacles) == len(t1.trees) and w.arena_min is None)

# ------------------------------------------------------------- luminance
h0 = t1.height_at(w.pos[0], w.pos[1])
vent = w.receptor_dirs[:, 2] < -0.3
lum_high = w.render_luminance()[vent].mean()
w.pos[2] = h0 + 0.5
lum_low = w.render_luminance()[vent].mean()
check("ventral glow grows near the ground (altitude signal)",
      lum_low > 1.5 * lum_high, f"low={lum_low:.4f} high={lum_high:.4f}")
# over water the ventral field dims
wx, wy = next((x, y) for x in np.arange(-60, 60, 4.0) for y in np.arange(-60, 60, 4.0)
              if t1.height_at(x, y) < t1.water_level)
w2 = World.from_terrain(terrain_seed=20260926, seed=11)
w2.pos = np.array([wx, wy, t1.height_at(wx, wy) + 1.0])
lum_water = w2.render_luminance()[vent].mean()
lx, ly = next((x, y) for x in np.arange(-60, 60, 4.0) for y in np.arange(-60, 60, 4.0)
              if t1.height_at(x, y) > t1.water_level + 2.0)
w2.pos = np.array([lx, ly, t1.height_at(lx, ly) + 1.0])
lum_land = w2.render_luminance()[vent].mean()
check("ventral glow dims over water", lum_water < 0.7 * lum_land,
      f"water={lum_water:.4f} land={lum_land:.4f}")

# ------------------------------------------------------------- rollout
brain = make_brain("skeleton", seed=11)
w = World.from_terrain(terrain_seed=20260926, seed=11)
clears, yaws, xy = [], [w.yaw], []
for f in range(600):
    mod = modulation_for("explore", 1, "sensory_only")
    rates = brain.step(w.render_luminance(mod), 0.1)
    w.step_motor(rates, 0.1, gains={"thrust": mod["thrust"]}, rng=w.rng)
    clears.append(w.pos[2] - t1.height_at(w.pos[0], w.pos[1]))
    yaws.append(w.yaw)
    xy.append((w.pos[0], w.pos[1]))
clears = np.array(clears)
xy = np.array(xy)
check("above-terrain invariant holds over a 60 s rollout",
      clears.min() > 0.015, f"min clearance {clears.min():.3f} m")
travel = float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1)))
check("free exploration covers real ground (>10 m in 60 s)", travel > 10.0,
      f"{travel:.1f} m")
om = np.rad2deg(np.abs(np.diff(yaws))) / 0.1
net = math_deg = (yaws[-1] - yaws[0])
check("no spin attractor (omega p50 < 150 dps, net turn < 8 rotations)",
      float(np.percentile(om, 50)) < 150 and abs(math.degrees(net)) < 8 * 360,
      f"p50={float(np.percentile(om, 50)):.0f}dps net={math.degrees(net):+.0f}deg")

# ------------------------------------------------------------- determinism
def rollout_states(seed):
    w = World.from_terrain(terrain_seed=20260926, seed=seed)
    b = make_brain("skeleton", seed=seed)
    states = []
    for f in range(150):
        mod = modulation_for("explore", 1, "sensory_only")
        rates = b.step(w.render_luminance(mod), 0.1)
        w.step_motor(rates, 0.1, gains={"thrust": mod["thrust"]}, rng=w.rng)
        states.append((tuple(np.round(w.pos, 6)), round(w.yaw, 6)))
    return states

check("same terrain+run seed -> identical rollout",
      rollout_states(7) == rollout_states(7))

# ------------------------------------------------- legacy isolation
legacy = World(seed=11)
lum_l = legacy.render_luminance()
legacy.step_motor({"DNp20_R": 2.0, "DNp20_L": 1.0, "MDN_R": 3.0, "MDN_L": 3.0},
                  0.1, yaw_noise=0.5, rng=legacy.rng)
snap = legacy.snapshot()
check("legacy box world numerically unchanged by terrain mode",
      abs(snap["speed"] - 0.43) < 0.02 and len(legacy.obstacles) == 7,
      f"speed={snap['speed']}")

print()
if FAIL:
    print(f"FAILED: {len(FAIL)} -> {FAIL}")
    sys.exit(1)
print("ALL PASS")
