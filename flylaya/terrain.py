"""flylaya.terrain — M6-W1 natural world: fixed deterministic terrain.

One fixed map (TASK-0027): fBm value-noise heightfield with mountains,
valleys and water, trees scattered on dry land, one sun. Everything is a
pure function of the map seed — the same seed reproduces the same world
bit-for-bit, matching the M5 determinism discipline.

Coordinate frame: x/y in meters, z up. The map is defined on
[-HALF, HALF]^2; outside it the height falls back to a flat plain so the
fly can wander without hitting an artificial wall. Heights are in
[0, MAX_H] meters; water fills everything below WATER_LEVEL.
"""
import math

import numpy as np

HALF = 64.0          # map half-extent (m); 128 x 128 m world
MAX_H = 14.0         # peak height (m)
WATER_LEVEL = 4.2    # everything below is water (~8% of the map: lakes)
TREE_MIN_GAP = 2.5   # min spacing between trees (m)
TREE_R = (0.25, 0.45)
TREE_H = (4.0, 9.0)


def _hash01(ix, iy, seed):
    """Deterministic [0,1) per integer lattice cell (uint64 mixing)."""
    ix = np.asarray(ix, np.uint64)
    iy = np.asarray(iy, np.uint64)
    s = np.uint64(seed & 0xFFFFFFFF)
    h = ix * np.uint64(374761393) + iy * np.uint64(668265263) + s * np.uint64(0x9E3779B1)
    h = (h ^ (h >> np.uint64(29))) * np.uint64(0xBF58476D1CE4E5B9)
    h = h ^ (h >> np.uint64(32))
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / 0x1000000

def _value_noise(x, y, seed):
    """Smooth bilinear value noise on the integer lattice."""
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = x - x0, y - y0
    u = fx * fx * (3 - 2 * fx)
    v = fy * fy * (3 - 2 * fy)
    x0 = x0.astype(np.int64)
    y0 = y0.astype(np.int64)
    a = _hash01(x0, y0, seed)
    b = _hash01(x0 + 1, y0, seed)
    c = _hash01(x0, y0 + 1, seed)
    d = _hash01(x0 + 1, y0 + 1, seed)
    return a * (1 - u) * (1 - v) + b * u * (1 - v) + c * (1 - u) * v + d * u * v


class Terrain:
    """The fixed natural map. height(x,y), water mask, tree list."""

    def __init__(self, seed=20260926):
        self.seed = int(seed)
        self.half = HALF
        self.water_level = WATER_LEVEL
        self.trees = self._place_trees()

    # ------------------------------------------------------------ height
    def height(self, x, y):
        """Terrain height (m) at world x/y. Vectorized; flat plain outside
        the map extent so exploration never hits an artificial wall."""
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        inside = (np.abs(x) <= HALF) & (np.abs(y) <= HALF)
        xi = np.where(inside, x, np.clip(x, -HALF, HALF))
        yi = np.where(inside, y, np.clip(y, -HALF, HALF))
        # fBm over 4 octaves; frequency in map units so features span
        # tens of meters (mountain ridges) down to a few meters (boulders)
        n = 0.0
        amp = 1.0
        freq = 1.0 / 22.0
        for o in range(4):
            n += amp * _value_noise(xi * freq + 31.7 * o, yi * freq - 17.3 * o,
                                    self.seed + o)
            amp *= 0.5
            freq *= 2.1
        n /= 1.875  # normalize by the amplitude sum
        h = 1.0 + np.power(np.clip(n, 0, 1), 1.4) * MAX_H
        # outside the map extent the world falls back to a flat plain at
        # 1 m so exploration never hits an artificial wall
        return np.where(inside, h, 1.0)

    def height_at(self, x, y):
        """Scalar convenience wrapper."""
        return float(self.height(np.array([x]), np.array([y]))[0])

    def is_water(self, x, y):
        return self.height_at(x, y) < self.water_level

    # ------------------------------------------------------------ trees
    def _place_trees(self):
        """Deterministic tree scatter on dry land with a minimum gap:
        jittered-grid candidate sampling, accepted if land + not too steep.
        Trees are cylinders (x, y, radius, height) like scene obstacles."""
        rng = np.random.default_rng(self.seed ^ 0x7EE)
        trees = []
        step = TREE_MIN_GAP
        for gx in np.arange(-HALF + 2, HALF, step):
            for gy in np.arange(-HALF + 2, HALF, step):
                jx = gx + rng.uniform(-0.8, 0.8)
                jy = gy + rng.uniform(-0.8, 0.8)
                h0 = self.height_at(jx, jy)
                if h0 < self.water_level + 0.5 or h0 > MAX_H * 0.62:
                    continue  # in/near water or above the tree line
                # local slope check (trees avoid cliffs)
                d = 1.0
                slope = max(abs(self.height_at(jx + d, jy) - h0),
                            abs(self.height_at(jx, jy + d) - h0))
                if slope > 1.2:
                    continue
                if rng.random() < 0.18:
                    trees.append((jx, jy,
                                  float(rng.uniform(*TREE_R)),
                                  float(rng.uniform(*TREE_H))))
        return trees

    # ------------------------------------------------------------ views
    def summary(self):
        """Compact map description for manifests / viewers."""
        xs = np.linspace(-HALF, HALF, 128)
        grid = self.height(*np.meshgrid(xs, xs))
        water_frac = float((grid < self.water_level).mean())
        return {"seed": self.seed, "half_m": HALF, "max_h_m": MAX_H,
                "water_level_m": self.water_level, "n_trees": len(self.trees),
                "water_frac": water_frac,
                "height_grid": np.round(grid, 2).tolist()}
