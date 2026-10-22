"""FlyLaya world: 1m^3 arena, abstract compound eye, motor integration.

The fly lives in a box [0,1]^3. Obstacles are vertical cylinders from a
deterministic seed; the sun is a directional light. The compound eye is an
abstract R1-R6 field with exactly `n_receptors` directions (default 3335 to
match MaleCNS retina_mapped, so the same luminance vector feeds either brain
implementation unchanged). Sensory render is pure numpy: sun glare by
receptor/sun angle, obstacle silhouettes by ray-cylinder occlusion, ambient
floor glow ventrally.

Motor: DN rate dict -> yaw (DNp20 R-L), thrust (mean MDN + base), pitch
(DNa02 R-L + DNpe017 mean). Substep integration with wall clamp and
obstacle pushout. Deterministic under a seed.

Scene mode (TASK-0009, flylaya.scene.v1): World.from_scene() builds a
world whose geometry, light and start pose come from a validated scene
file instead of the seeded random layout. Obstacles can be toggled by
stimulus events, the light can be uniform or directional with an event
clock, and the motor RNG is the scene's "motor" stream (independent of
the Laya sampler). The legacy constructor and its behavior are unchanged
for the default 1 m arena.
"""
import math

import numpy as np

from .scene import SceneClock, load_scene, stream_rngs

ARENA_MIN = np.zeros(3)
ARENA_MAX = np.ones(3)
N_RECEPTORS = 3335


def _receptor_dirs(n):
    """Front-biased, dorsally-tilted deterministic unit directions.

    Fixed rng (part of the "eye" anatomy): every World and SkeletonBrain
    sees the identical receptor set for a given n.
    """
    rng = np.random.default_rng(12345)  # fixed: geometry is part of the "eye"
    n_front = int(n * 0.55)
    # frontal cone
    yaw = np.deg2rad(rng.uniform(-60, 60, n_front))
    pitch = np.deg2rad(rng.uniform(-45, 45, n_front))
    d = np.stack([np.cos(pitch) * np.cos(yaw),
                  np.cos(pitch) * np.sin(yaw),
                  np.sin(pitch)], axis=1)
    # remainder: uniform sphere, minus a rear bias duplicate filter
    n_rest = n - n_front
    v = rng.normal(size=(n_rest * 2, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    keep = v[:, 0] < 0.95  # avoid duplicating the forward pole
    d = np.vstack([d, v[keep][:n_rest]])
    while len(d) < n:
        extra = rng.normal(size=(8, 3))
        extra /= np.linalg.norm(extra, axis=1, keepdims=True)
        d = np.vstack([d, extra[extra[:, 0] < 0.95]][: n - len(d)])
    # dorsal tilt of the whole field by 10 degrees
    th, dor = np.deg2rad(10.0), np.array([0.0, 0.0, 1.0])
    return d * np.cos(th) + np.cross(dor, d) * np.sin(th) + (d @ dor)[:, None] * dor * (1 - np.cos(th))


def _floor_texture_pattern(dirs):
    """Fixed mean-preserving +/-1 checker over coarse angular cells
    (scene v1.1 floor texture): spatially coherent patches in the ventral
    field, deterministic across runs, zero vertical-position information."""
    az = (np.degrees(np.arctan2(dirs[:, 1], dirs[:, 0])) + 360.0) % 360.0
    el = np.degrees(np.arcsin(np.clip(dirs[:, 2], -1.0, 1.0)))
    cells = (az // 15.0).astype(int) * 13 + (el // 7.5).astype(int)
    table = np.random.default_rng(0xF100).choice([-1.0, 1.0], size=4096)
    return table[cells % 4096].astype(np.float32)


class World:
    def __init__(self, seed=0, n_obstacles=7, n_receptors=N_RECEPTORS):
        self.scene_obj = None
        self.terrain = None       # M6 terrain mode gate (TASK-0027)
        self.arena_min = ARENA_MIN.copy()
        self.arena_max = ARENA_MAX.copy()
        self.light = None          # None -> legacy directional sun
        self.light_on = True
        self.floor_texture_on = False   # scene v1.1 floor texture toggle
        self.floor_texture_c = 0.0
        self.clock = None
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.n_receptors = n_receptors
        self.receptor_dirs = _receptor_dirs(n_receptors)
        # obstacles: vertical cylinders (x, z, radius, height)
        self.obstacles = np.column_stack([
            self.rng.uniform(0.2, 0.8, n_obstacles),
            self.rng.uniform(0.2, 0.8, n_obstacles),
            self.rng.uniform(0.03, 0.06, n_obstacles),
            self.rng.uniform(0.25, 0.7, n_obstacles),
        ])
        az = self.rng.uniform(0, 2 * np.pi)
        el = np.deg2rad(self.rng.uniform(35, 65))  # elevation
        self.sun = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
        self.ambient = 0.08
        self.obstacle_enabled = np.ones(len(self.obstacles), bool)
        self.reset()
        self._floor_pattern = _floor_texture_pattern(self.receptor_dirs)

    # ------------------------------------------------------------ terrain mode
    @classmethod
    def from_terrain(cls, terrain_seed=20260926, seed=0, start=None,
                     n_receptors=N_RECEPTORS):
        """M6-W1 natural world (TASK-0027): fixed terrain, open bounds.

        Ground is the Terrain heightfield (no box floor), trees are the
        terrain's obstacle list, the sky has no ceiling, and walls do not
        exist — outside the map the terrain falls back to a plain. The
        fly spawns over dry land at a safe altitude. Legacy/scene modes
        are untouched (terrain branches are gated on self.terrain)."""
        from .terrain import Terrain
        w = cls.__new__(cls)
        w.scene_obj = None
        w.terrain = Terrain(terrain_seed)
        w.seed = int(seed)
        w.n_receptors = n_receptors
        w.receptor_dirs = _receptor_dirs(n_receptors)
        w.arena_min = None                 # open world: no box
        w.arena_max = None
        w.obstacles = np.array(w.terrain.trees, dtype=float).reshape(-1, 4) \
            if w.terrain.trees else np.zeros((0, 4))
        w.obstacle_enabled = np.ones(len(w.obstacles), bool)
        w._ob_index = {}
        w.light = {"mode": "directional", "azimuth_deg": 205.0,
                   "elevation_deg": 50.0, "intensity": 0.9,
                   "initially_on": True}
        w.light_on = True
        w.sun = np.array([math.cos(math.radians(50)) * math.cos(math.radians(205)),
                          math.cos(math.radians(50)) * math.sin(math.radians(205)),
                          math.sin(math.radians(50))])
        w.clock = None
        w.streams = None
        w.rng = np.random.default_rng(seed)
        w.ambient = 0.08
        w.last_luminance = None
        w.floor_texture_on = True          # ground texture always on outside
        w.floor_texture_c = 0.6
        w._floor_pattern = _floor_texture_pattern(w.receptor_dirs)
        w._photo_i = 0.0
        w._frontal = w.receptor_dirs[:, 0] > 0.3
        w._up = w.receptor_dirs[:, 2] > 0.3
        w._down = w.receptor_dirs[:, 2] < -0.3
        w._loom_esc_sign = 0.0
        w._loom_esc_t = 0.0
        w._tie_sign = 0.0
        w._tie_t = 0.0
        if start is None:
            rng = np.random.default_rng(seed ^ 0x51A7)
            for _ in range(200):
                x = float(rng.uniform(-24, 24))
                y = float(rng.uniform(-24, 24))
                h = w.terrain.height_at(x, y)
                if h > w.terrain.water_level + 0.5:
                    start = (x, y, h + 1.2)
                    break
            else:
                start = (0.0, 0.0, w.terrain.height_at(0, 0) + 1.5)
        w.pos = np.array(start, dtype=float)
        w.yaw = float(np.random.default_rng(seed).uniform(0, 2 * np.pi))
        w.pitch = 0.0
        w.vel = 0.12 * w._heading()
        w.trail = [w.pos.copy()]
        w.frames = 0
        return w

    @classmethod
    def from_scene(cls, scene, seed=0, n_receptors=N_RECEPTORS):
        """Deterministic world from a flylaya.scene.v1 scene (design §4).

        Same scene_id + version + seed -> identical world: geometry comes
        from the file, the four RNG streams are derived from the scene
        identity, and the motor stream feeds step_motor noise. Nothing
        here consumes the legacy layout RNG.
        """
        scene = load_scene(scene)
        w.scene_obj = scene
        w.terrain = None
        w.seed = int(seed)
        w.n_receptors = n_receptors
        w.receptor_dirs = _receptor_dirs(n_receptors)
        w.arena_min = np.zeros(3)
        w.arena_max = np.array(scene.arena, dtype=float)
        w.obstacles = scene.obstacle_array()
        w.obstacle_enabled = np.array([ob["enabled"] for ob in scene.obstacles],
                                      bool)
        w._ob_index = {ob["id"]: i for i, ob in enumerate(scene.obstacles)}
        w.light = dict(scene.light)
        w.light_on = scene.light.get("initially_on", True)
        w.sun = scene.sun_vector()
        w.clock = SceneClock(scene)
        w.streams = stream_rngs(scene, seed)
        w.rng = w.streams["motor"]
        w.ambient = 0.08
        w.last_luminance = None
        ft = scene.light.get("floor_texture")
        w.floor_texture_on = False       # starts off; events toggle (v1.1)
        w.floor_texture_c = float(ft["contrast"]) if ft else 0.0
        w._floor_pattern = _floor_texture_pattern(w.receptor_dirs)
        w._reset_pose()
        return w

    def _reset_pose(self):
        """Start pose from the scene (scene mode only)."""
        sc = self.scene_obj
        self.pos = np.array(sc.start_pos, dtype=float)
        self.yaw = math.radians(sc.start_yaw_deg)
        self.pitch = 0.0
        self.vel = sc.start_speed * self._heading()
        self.trail = [self.pos.copy()]
        self.frames = 0

    def reset(self, seed=None):
        if self.scene_obj is not None:
            if seed is not None:
                raise ValueError("scene worlds re-derive from the scene file; "
                                 "construct World.from_scene(scene, seed) instead")
            self._reset_pose()
            return
        if seed is not None:
            self.seed = int(seed)
            self.rng = np.random.default_rng(self.seed)
        # fly starts center-ish, random heading
        self.pos = np.array([0.5, 0.5, self.rng.uniform(0.4, 0.6)])
        self.yaw = self.rng.uniform(0, 2 * np.pi)
        self.pitch = 0.0
        self.vel = np.zeros(3)
        self.trail = [self.pos.copy()]
        self.frames = 0

    # ---------------------------------------------------------------- sensory
    def _heading(self):
        cp, sp, cy, sy = np.cos(self.pitch), np.sin(self.pitch), np.cos(self.yaw), np.sin(self.yaw)
        return np.array([cp * cy, cp * sy, sp])

    def render_luminance(self, mod=None):
        """Per-receptor brightness in [0,1]: sun glare * visibility + occlusion.

        `mod` applies intent modulation (spec §3): light gain scales the sun
        channel, looming scales obstacle silhouettes, wall scales near-wall
        darkening. Brains stay luminance-only consumers.

        Scene mode: a uniform light renders flat ambient everywhere; a
        directional light renders glare scaled by its intensity and is
        skipped entirely while switched off (event clock). Wall darkening
        and the vertical reflex are arena-extent relative, identical to
        legacy numerics on the default 1 m cube.
        """
        m = mod or {}
        light = float(m.get("light", 1.0))
        looming = float(m.get("looming", 1.0))
        wall_gain = float(m.get("wall", 1.0))
        # receptor directions in world frame (rotate by yaw around z, pitch around y')
        cy, sy = np.cos(self.yaw), np.sin(self.yaw)
        d = self.receptor_dirs
        w = np.stack([d[:, 0] * cy - d[:, 1] * sy, d[:, 0] * sy + d[:, 1] * cy, d[:, 2]], axis=1)
        uniform = self.light is not None and self.light["mode"] == "uniform"
        lum = np.full(len(d), self.light["level"] if uniform else self.ambient,
                      np.float32)
        if self.sun is not None and self.light_on:
            # sun glare: cos similarity, sharpened; receptors pointing sunward light up
            cosun = w @ self.sun
            glare = np.clip((cosun - 0.2) / 0.8, 0, 1) ** 3
            # sun occlusion: does the ray pos -> pos + sun_dir*t hit any cylinder first?
            sun_vis = self._sun_visibility()
            intensity = self.light.get("intensity", 1.0) if self.light else 1.0
            lum += 0.92 * intensity * light * glare * sun_vis
        # ventral floor glow; with floor_texture ON (scene v1.1) a fixed,
        # mean-preserving receptor-space pattern scales the glow by
        # (1 + contrast * pattern): ventral brightness STATISTICS change
        # (optic-flow texture). TERRAIN mode (M6): glow scales with ground
        # proximity (altitude signal via optic flow) and dims over water.
        if self.terrain is not None:
            gh = self.terrain.height_at(self.pos[0], self.pos[1])
            clear = max(self.pos[2] - gh, 0.0)
            prox = float(np.exp(-clear / 1.2))          # 1 at ground -> 0 high
            water = 0.35 if gh < self.terrain.water_level else 1.0
            glow = 0.10 * prox * water * np.clip(-w[:, 2], 0, 1)
            glow = glow * (1.0 + self.floor_texture_c * self._floor_pattern)
        else:
            glow = 0.05 * np.clip(-w[:, 2], 0, 1)
            if self.floor_texture_on and self.floor_texture_c > 0:
                glow = glow * (1.0 + self.floor_texture_c * self._floor_pattern)
        lum += glow
        # obstacle silhouettes: receptors whose rays graze a nearby cylinder darken
        occ = self._obstacle_occlusion(w)
        lum *= (1.0 - 0.85 * looming * occ)
        # near-wall darkening: receptors pointing toward the closest wall dim
        # with proximity — gives wall-avoidance structure to any phototactic
        # brain (fixes the skeleton corner-freeze; M4 review item 2)
        if wall_gain > 0 and self.terrain is None:
            ax, ay = self.arena_max[0], self.arena_max[1]
            dmin = min(pos_c for pos_c in (self.pos[0], ax - self.pos[0],
                                           self.pos[1], ay - self.pos[1]))
            if dmin < 0.25:
                strength = (1 - dmin / 0.25) * 0.7 * wall_gain
                toward = np.zeros(len(d), np.float32)
                if dmin == self.pos[0]:
                    toward = np.maximum(toward, -w[:, 0].astype(np.float32))
                if dmin == ax - self.pos[0]:
                    toward = np.maximum(toward, w[:, 0].astype(np.float32))
                if dmin == self.pos[1]:
                    toward = np.maximum(toward, -w[:, 1].astype(np.float32))
                if dmin == ay - self.pos[1]:
                    toward = np.maximum(toward, w[:, 1].astype(np.float32))
                lum *= (1.0 - strength * toward)
        # (A floor/ceiling proximity-darkening cue was added here for
        # TASK-0023 and reverted: dimming receptors by upward direction
        # also dimmed the sun-glare region near the ceiling, degrading the
        # phototaxis channel (S1 mean_cos 0.546/0.628 -> 0.299/0.144).
        # Altitude limiting comes from the vertical reflex vs the VERT_K=2
        # climb drive balance instead.)
        out = np.clip(lum, 0, 1).astype(np.float32)
        self.last_luminance = out  # 1-frame-stale retina view for observable_state
        return out

    def _sun_visibility(self):
        """Fraction-free single visibility: any cylinder between fly and sun."""
        for k, (x, z, r, h) in enumerate(self.obstacles):
            if not self.obstacle_enabled[k]:
                continue
            # ray from p toward sun: p + t*sun, t in (0, 0.5]
            ox, oz = self.pos[0] - x, self.pos[1] - z
            dx, dz = self.sun[0], self.sun[1]
            a = dx * dx + dz * dz
            if a < 1e-9:
                continue
            b = 2 * (ox * dx + oz * dz)
            c = ox * ox + oz * oz - r * r
            disc = b * b - 4 * a * c
            if disc <= 0:
                continue
            sq = np.sqrt(disc)
            for t in ((-b - sq) / (2 * a), (-b + sq) / (2 * a)):
                if 0.05 < t < 0.5:
                    y = self.pos[2] + t * self.sun[2]
                    if y < h:  # cylinder shorter than sun elevation path
                        return 0.0
        return 1.0

    def _obstacle_occlusion(self, w, max_obstacles=3):
        """Vectorized ray-cylinder graze test against the nearest obstacles."""
        pxz = self.pos[:2]
        dist2 = ((self.obstacles[:, :2] - pxz) ** 2).sum(axis=1)
        near = np.argsort(dist2)[:max_obstacles]
        occ = np.zeros(len(w), np.float32)
        for i in near:
            if not self.obstacle_enabled[i]:
                continue
            x, z, r, h = self.obstacles[i]
            if h < self.pos[2] - 0.02 and self.pos[2] > h:
                continue  # flying above it
            ox, oz = pxz[0] - x, pxz[1] - z
            dx, dz = w[:, 0], w[:, 1]
            a = dx * dx + dz * dz
            a[a < 1e-9] = 1e-9
            b = 2 * (ox * dx + oz * dz)
            c = ox * ox + oz * oz - (r * 1.35) ** 2  # graze margin
            disc = np.clip(b * b - 4 * a * c, 0, None)
            sq = np.sqrt(disc)
            t1 = (-b - sq) / (2 * a)
            hit = (t1 > 0.02) & (t1 < 0.45)
            # ray must also point downward enough to actually hit the column
            t_hit_y = self.pos[2] + t1 * w[:, 2]
            hit &= (t_hit_y < h + 0.05)
            occ = np.maximum(occ, hit.astype(np.float32) * np.clip(1 - t1 / 0.45, 0.2, 1.0))
        return occ

    # ---------------------------------------------------------------- motor
    YAW_GAIN = 0.3          # rad/s per Hz of DNp20 diff (TASK-0017: 1.6 saturated
                            # the channel -- visual asymmetry ~6Hz post-DC gave
                            # 344-550dps spin attractors; 0.3 lands omega p50 ~100dps)
    PITCH_GAIN = 0.10       # rad/s per Hz of DNa02 diff (differential only)
    THRUST_GAIN = 0.09      # m/s per Hz of mean MDN
    BASE_THRUST = 0.16      # m/s hovering forward bias
    MAX_SPEED = 0.5
    N_SUBSTEPS = 10

    def step_motor(self, dn_rates, dt, gains=None, yaw_noise=0.0, rng=None, yaw_bias=0.0):
        """Integrate one bio frame (dt seconds) from DN rates (Hz, dict).

        M4 review fixes: pitch is differential-only (DNpe017's tonic mean was
        a constant climb command -> ceiling pinning); a geometric vertical
        reflex biases pitch away from ceiling/floor (brain-independent);
        yaw_noise injects per-intent wander (spec modulation table).
        """
        g = gains or {}
        thrust_mult = float(g.get("thrust", 1.0))
        yaw_diff = dn_rates.get("DNp20_R", 0.0) - dn_rates.get("DNp20_L", 0.0)
        pitch_cmd = (dn_rates.get("DNa02_R", 0.0) - dn_rates.get("DNa02_L", 0.0))
        thrust = self.BASE_THRUST * thrust_mult + self.THRUST_GAIN * thrust_mult * (
            dn_rates.get("MDN_R", 0.0) + dn_rates.get("MDN_L", 0.0)) * 0.5
        yaw_rate = self.YAW_GAIN * yaw_diff + yaw_bias
        if yaw_noise and rng is not None:
            yaw_rate += float(rng.normal(0.0, 0.9 * yaw_noise))
        pitch_rate = self.PITCH_GAIN * pitch_cmd
        # vertical reflex: box modes use soft ceiling/floor bands; terrain
        # mode uses ground clearance (below).
        if self.terrain is not None:
            # terrain mode: ground-proximity reflex (no ceiling — open sky;
            # the ground clearance replaces the box floor band)
            h = self.terrain.height_at(self.pos[0], self.pos[1])
            clear = self.pos[2] - h
            if clear < 0.35:
                pitch_rate += 0.6 * (0.35 - clear) / 0.35
        else:
            az = self.arena_max[2]
            # wide soft bands (TASK-0025 Gate-V0: with a live vertical drive a
            # 70-deg sun pinned the fly to the ceiling 23% of frames under the
            # old 0.85/0.15 bands; 0.70/0.30 ramps the descent pressure in
            # earlier so the climb equilibrates mid-high instead of riding the
            # clamp)
            top, bot, span = az * 0.60, az * 0.40, az * 0.40
            if self.pos[2] > top:
                pitch_rate -= 0.5 * (self.pos[2] - top) / span
            elif self.pos[2] < bot:
                pitch_rate += 0.5 * (bot - self.pos[2]) / span
        yaw_rate = float(np.clip(yaw_rate, -6.0, 6.0))
        pitch_rate = float(np.clip(pitch_rate, -1.2, 1.2))
        sub = dt / self.N_SUBSTEPS
        for _ in range(self.N_SUBSTEPS):
            self.yaw += yaw_rate * sub
            self.pitch = float(np.clip(self.pitch + pitch_rate * sub, -0.6, 0.6))
            h = self._heading()
            self.vel = thrust * h
            self.pos = self.pos + self.vel * sub
            self._collide()
        self.trail.append(self.pos.copy())
        if len(self.trail) > 4000:
            del self.trail[: len(self.trail) - 4000]
        self.frames += 1

    def _collide(self):
        if self.terrain is not None:
            # terrain mode: clamp above the heightfield, push out of trees;
            # no walls (open world)
            h = self.terrain.height_at(self.pos[0], self.pos[1])
            if self.pos[2] < h + 0.02:
                self.pos[2] = h + 0.02
            for k, (x, z, r, ht) in enumerate(self.obstacles):
                if not self.obstacle_enabled[k] or self.pos[2] >= ht:
                    continue
                dx, dz = self.pos[0] - x, self.pos[1] - z
                d2 = dx * dx + dz * dz
                rmin = r + 0.015
                if d2 < rmin * rmin:
                    d = max(math.sqrt(d2), 1e-6)
                    self.pos[0] = x + dx / d * rmin
                    self.pos[1] = z + dz / d * rmin
            return
        # walls: clamp + slight inward nudge
        self.pos = np.clip(self.pos, self.arena_min + 0.01, self.arena_max - 0.01)
        for k, (x, z, r, h) in enumerate(self.obstacles):
            if not self.obstacle_enabled[k] or self.pos[2] >= h:
                continue
            dx, dz = self.pos[0] - x, self.pos[1] - z
            d2 = dx * dx + dz * dz
            rmin = r + 0.015
            if d2 < rmin * rmin:
                d = max(np.sqrt(d2), 1e-6)
                self.pos[0] = x + dx / d * rmin
                self.pos[1] = z + dz / d * rmin

    # ---------------------------------------------------------------- snapshot
    def snapshot(self):
        h = self._heading()
        return {
            "pos": [round(float(v), 4) for v in self.pos],
            "heading": [round(float(v), 4) for v in h],
            "yaw": round(float(self.yaw), 4),
            "pitch": round(float(self.pitch), 4),
            "speed": round(float(np.linalg.norm(self.vel)), 4),
            "frames": self.frames,
        }

    def scene(self):
        if self.scene_obj is not None:
            # single unit conversion for scene worlds (design §4)
            out = self.scene_obj.display()
            out["seed"] = self.seed
            return out
        return {
            "seed": self.seed,
            "obstacles": [
                {"x": round(float(x), 4), "z": round(float(z), 4),
                 "r": round(float(r), 4), "h": round(float(h), 4)}
                for x, z, r, h in self.obstacles
            ],
            "sun": [round(float(v), 4) for v in self.sun],
        }

    # ------------------------------------------------------------ stimulus
    def advance_clock(self, t_s):
        """Deliver due scene events at sim time t_s; returns the events."""
        if self.clock is None:
            return []
        return [self.apply_event(e) for e in self.clock.due(t_s)]

    def apply_event(self, ev):
        kind, tgt = ev["kind"], ev["target"]
        if tgt == "light":
            if self.light is None or self.light["mode"] != "directional":
                raise ValueError("stimulus events on 'light' need a directional light")
            self.light_on = kind == "stimulus_on"
        elif tgt == "floor_texture":
            if not self.floor_texture_c:
                raise ValueError("floor_texture events need light.floor_texture")
            self.floor_texture_on = kind == "stimulus_on"
        else:
            self.obstacle_enabled[self._ob_index[tgt]] = kind == "stimulus_on"
        return ev
