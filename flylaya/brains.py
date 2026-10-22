"""Brains: sensory->spikes->DN-rate providers behind one interface.

SkeletonBrain (M1 default): a lightweight deterministic rate-code stand-in.
It consumes the same luminance vector the real retina would and produces the
same readout-rate dict the MaleCNS decoder would, via leaky-integrator
"DN pools" driven by sensory asymmetries. No connectome, ~1ms/frame — enough
to validate the world loop, motor mapping, and viewer.

ConnectomeBrain (M2): wraps the vendored MaleCNS DOOMFLY kernel
(libneural.dylib, 166,700 neurons, 892MB). Lazily imported and off by
default; M2 wires it together with the Laya intent loop and gain
modulation. The interface below is frozen so M2 is an integration, not a
rewrite.
"""
import json
import math
import time

import numpy as np

from .world import _receptor_dirs


class SkeletonBrain:
    """Rate-code abstraction with the MaleCNS readout contract."""

    TAU = 0.15  # s, DN pool leak

    def __init__(self, seed=0, n_receptors=3335):
        self.rng = np.random.default_rng(seed + 1)
        self.dirs = _receptor_dirs(n_receptors)
        self.pools = {k: 0.0 for k in
                      ["DNp20_R", "DNp20_L", "MDN_R", "MDN_L",
                       "DNa02_R", "DNa02_L", "DNpe017_R", "DNpe017_L"]}
        self.last_spikes_hz = 0.0

    def step(self, luminance, dt):
        """One frame: luminance vector -> readout rates (Hz dict)."""
        # TASK-0017 sign fix: body frame is z-up, heading = +x, so the
        # receptor +y axis is the fly's LEFT and yaw+ (CCW) turns left.
        # The old masks had left/right swapped, making DNp20 drive the fly
        # AWAY from bright regions (diag batch: mean_cos_to_light +0.50 -> -0.84;
        # M4's skeleton sun_R=0.527 was the concentration artifact of a
        # consistently ANTI-sun heading). Phototaxis now: bright left ->
        # DNp20_R rises -> yaw+ -> turn toward the light, on both mirrors.
        frontal = self.dirs[:, 0] > 0.3
        left = self.dirs[:, 1] > 0.25      # geometric left (CCW side)
        right = self.dirs[:, 1] < -0.25    # geometric right (CW side)
        up = self.dirs[:, 2] > 0.3
        down = self.dirs[:, 2] < -0.3
        lum_l = float(luminance[left].mean())
        lum_r = float(luminance[right].mean())
        lum_f = float(luminance[frontal].mean())
        lum_u = float(luminance[up].mean())
        lum_d = float(luminance[down].mean())
        brightness = float(luminance.mean())

        # sensory-driven drives (Hz): contralateral turning structure
        beta = 1 - np.exp(-dt / self.TAU)
        targets = {
            # bright on the left -> turn left (DNp20_R rises): phototaxis
            "DNp20_R": 6.0 * lum_l + 1.2,
            "DNp20_L": 6.0 * lum_r + 1.2,
            # forward energy tracks frontal light and overall brightness
            "MDN_R": 8.0 * lum_f + 3.0 * brightness + 0.8,
            "MDN_L": 8.0 * lum_f + 3.0 * brightness + 0.8,
            # climb toward overhead light (TASK-0023: make it a real
            # differential — identical R/L targets left pitch dead and z
            # pinned at the start height; the R-L asymmetry now tracks the
            # dorsal/ventral luminance contrast, sign-matched to the
            # connectome sidecar: R-L > 0 climbs)
            "DNa02_R": 2.5 * lum_u + 0.6 + 2.0 * (lum_u - lum_d),
            "DNa02_L": 2.5 * lum_u + 0.6 - 2.0 * (lum_u - lum_d),
            "DNpe017_R": 1.5 * lum_f,
            "DNpe017_L": 1.5 * lum_f,
        }
        for k, tgt in targets.items():
            self.pools[k] += beta * (tgt - self.pools[k])
        self.last_spikes_hz = 1.6 + 4.0 * brightness  # stand-in mean rate
        return dict(self.pools)

    def dn_snapshot(self):
        """Motor-command view for HUD/serving (parity with ConnectomeBrain)."""
        return {k: round(v, 2) for k, v in self.pools.items()}

    def hud(self):
        return {"mean_spikes_hz": round(self.last_spikes_hz, 2)}

class ConnectomeBrain:
    """MaleCNS full-graph LIF (166,700 neurons) via the vendored kernel.

    Readout sidecar channels (TASK-0019/-0020): the kernel's brightness->DN
    mapping loses the azimuth of bright/dark regions (diag phase 1: light
    stimulus dDN same-sign on both mirrors; looming turn sign flips with
    mirror). The channels below reconstruct the luminance-weighted
    centroid of the retina in body frame and add a symmetric, bounded
    DNp20 differential — the R1-R6->DN structure the full graph fails to
    surface. Body frame convention matches SkeletonBrain (z-up, heading
    =+x, receptor +y is LEFT, yaw+ turns left).
    """

    PHOTO_K = 6.0   # Hz of DNp20 diff per unit sin(light bearing); tune on S1
    LOOM_K = 9.0    # TASK-0020: frontal looming-avoidance gain (Hz per sin)
    LOOM_ESC_HZ = 0.0   # latched escape turn (disabled: common-mode risk)
    VERT_K = 1.2        # Hz of DNa02 diff per unit dorsal-ventral contrast
    PHOTO_D = 1.2   # s, optomotor damping on the phototaxis bearing signal
    PHOTO_I = 4.0       # Hz/s, integral gain vs kernel glare yaw bias
    PHOTO_I_MAX = 4.0   # Hz, integrator clamp (anti-windup)
    TIE_HZ = 4.5        # dead-cone tie-break turn (Hz of DNp20 diff)
    TIE_S = 0.5         # s of tie-break turn (0.9 overrode real lateral corrections)

    def __init__(self, malecns_root="/Users/leewbl/aiworld/MaleCNS",
                 calibrate_frames=30, seed=0):
        import importlib.util
        import json
        import sys
        from pathlib import Path

        root = Path(malecns_root)
        spec = importlib.util.spec_from_file_location(
            "malecns_run_sim", root / "src/sim/run_sim.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["malecns_run_sim"] = mod
        spec.loader.exec_module(mod)
        mod.KERNEL, _build = mod.load_kernel()  # module global used by Sim.step
        self.sim = mod.Sim()
        self.readouts = json.loads(
            (root / "data/sim/graph_manifest.json").read_text())["readouts"]
        self.rates = np.zeros(len(self.readouts))
        self.index_of = {}
        for i, r in enumerate(self.readouts):
            key = f"{r['type']}_{r['side']}"
            if key not in self.index_of:  # MDN has duplicate L/R pairs; first wins
                self.index_of[key] = i
        self.last_total = 0
        # Tonic baseline calibration (tester root-cause: DNp20 readout carries
        # a constant L/R imbalance, ~11Hz at zero input -> 344 deg/s spin via
        # the yaw map). Measure per-readout tonic rate with zero luminance and
        # subtract it from the motor command channel (DC removal).
        self.receptor_dirs = _receptor_dirs(len(self.sim.retina))
        zeros = np.zeros(len(self.sim.retina), np.float32)
        acc = np.zeros(len(self.readouts))
        for _ in range(calibrate_frames):
            counts, _ = self.sim.step(zeros, duration_ms=100.0)
            acc += np.asarray([counts[r["index"]] / 0.1 for r in self.readouts])
        self.baseline = {k: float(acc[i] / calibrate_frames)
                         for k, i in self.index_of.items()}
        # TASK-0020 root cause: the tonic DNp20 R-L imbalance is ILLUMINATION
        # dependent — under a uniform 0.45 field it runs +6-8 Hz (a ~150 deg/s
        # left turn with no pattern cause). That mirror-symmetric drift turns
        # away from a right column and INTO a left one, which the sem batch
        # read as a looming sign flip. Calibrate the yaw-diff tonic at uniform
        # levels and subtract the level-interpolated bias per frame, so only
        # pattern-driven (mirror-antisymmetric) yaw commands survive.
        dR, dL = self.index_of["DNp20_R"], self.index_of["DNp20_L"]
        self._bias_levels = [0.0]
        self._bias_diff = [self.baseline["DNp20_R"] - self.baseline["DNp20_L"]]
        n_ret = len(self.sim.retina)
        for lvl in (0.2, 0.45, 0.7, 1.0):
            field = np.full(n_ret, lvl, np.float32)
            acc_d = 0.0
            for _ in range(12):
                counts, _ = self.sim.step(field, duration_ms=100.0)
                acc_d += counts[self.readouts[dR]["index"]] / 0.1 \
                       - counts[self.readouts[dL]["index"]] / 0.1
            self._bias_levels.append(lvl)
            self._bias_diff.append(acc_d / 12.0)
        # (A dark-patch common-mode calibration was tried here and removed:
        # synthetic-patch tables do not transfer to real silhouettes — the
        # kernel's response flips sign between uniform-dark and patterned-
        # dark fields at the same mean. Looming is handled by yaw-authority
        # suppression + the symmetric sidecar in step().)
        self._photo_lat = 0.0
        self._photo_init = False
        self._photo_i = 0.0
        self._up = self.receptor_dirs[:, 2] > 0.3
        self._down = self.receptor_dirs[:, 2] < -0.3
        self._frontal = self.receptor_dirs[:, 0] > 0.3
        self._loom_esc_sign = 0.0
        self._loom_esc_t = 0.0
        # TASK-0022: seeded entropy for the dead-ahead looming tie-break.
        # Deterministic per run seed (runner passes make_brain(kind, seed=...)).
        self._rng = np.random.default_rng((int(seed) + 0x217) & 0xFFFFFFFF)
        self._tie_sign = 0.0
        self._tie_t = 0.0

    def _centroid(self, luminance, weight):
        """Body-frame luminance-weighted centroid (unit vector or None)."""
        w = weight(np.asarray(luminance, np.float64))
        s = float(w.sum())
        if s < 1e-6:
            return None
        c = (w @ self.receptor_dirs) / s
        norm = float(np.linalg.norm(c))
        if norm < 1e-6:
            return None
        return c / norm

    def _centroid_drive(self, luminance, weight, gain):
        """Bounded DNp20-diff drive toward/away from a weighted centroid.

        weight maps luminance -> non-negative weights; the returned drive
        is gain * sin(bearing of the centroid). Zero input -> exactly 0
        (baseline-safe).
        """
        c = self._centroid(luminance, weight)
        return 0.0 if c is None else gain * float(c[1])

    def step(self, luminance, dt):
        counts, _wall = self.sim.step(luminance, duration_ms=dt * 1000.0)
        seconds = dt
        raw = np.asarray([counts[r["index"]] / seconds for r in self.readouts])
        b = 1 - np.exp(-seconds / 0.1)
        self.rates = self.rates * np.exp(-seconds / 0.1) + b * raw
        # motor commands are baseline-subtracted (tonic DC removed); rates
        # keep raw values for observability (dn_snapshot / HUD).
        out = {key: float(self.rates[i]) - self.baseline.get(key, 0.0)
               for key, i in self.index_of.items()}
        # illumination-level tonic yaw-bias removal (TASK-0020; see the
        # calibration block in __init__). ONLY valid on near-uniform
        # fields: the level table was measured under uniform illumination,
        # and under a patterned silhouette the kernel responds with the
        # OPPOSITE sign (probe: uniform level 0.25 -> +17 Hz tonic, dark
        # frontal patch at the same mean -> -17 Hz), so applying it there
        # doubles the error. Gate on field contrast; under looming the yaw
        # suppressor below takes over instead.
        lum64 = np.asarray(luminance, np.float64)
        contrast = float(lum64.max() - np.median(lum64))
        lf = lum64[self._frontal]
        ref = float(np.quantile(lf, 0.9)) if len(lf) else 1.0
        frac_dark = float((lf < 0.7 * ref).mean()) if len(lf) else 0.0
        frac_eff = frac_dark
        if contrast < 0.15:
            # uniform-field tonic removal (calibration tables are valid
            # only without spatial structure — see __init__ note)
            lvl = float(np.clip(lum64.mean(), 0.0, 1.0))
            bias = float(np.interp(lvl, self._bias_levels, self._bias_diff))
            out["DNp20_R"] -= 0.5 * bias
            out["DNp20_L"] += 0.5 * bias
        elif frac_eff > 0.15 or (len(lf) and float(lf.mean()) <
                                 0.6 * float(np.median(lum64[~self._frontal]))):
            # looming: the kernel's yaw channel is direction-blind for
            # silhouettes (same-sign turn for left- and right-frontal
            # columns, probe -14.6/-15.1 Hz), so fade its yaw authority
            # out as the silhouette grows — or whenever the frontal field
            # is broadly dimmed (near-field state where the relative dark
            # detector collapses) — and hand the command to the mirror-
            # linear fade toward 0.05 as the silhouette fills the field
            supp = max(0.05, 1.0 - frac_eff)
            out["DNp20_R"] *= supp
            out["DNp20_L"] *= supp
        # TASK-0019: azimuth-preserving phototaxis readout — steer toward
        # the luminance centroid (glare dominates the weighting; ambient
        # floor and ventral glow are cut by the 0.1 pedestal), with an
        # optomotor-style rate term (damps the pure-P orbit a laggy plant
        # otherwise locks into) and a bounded integrator (absorbs the
        # kernel's mirror-consistent slow glare yaw bias, diag ~4-5 Hz).
        # The contrast-salience gate keeps the channel dark on uniform or
        # fully occluded fields: without it the receptor field's own
        # asymmetry winds the integrator and drifts the heading before
        # any stimulus exists.
        gate = float(np.clip((contrast - 0.10) / 0.20, 0.0, 1.0))
        photo = 0.0
        if gate > 0.0:
            c = self._centroid(
                luminance, lambda lum: np.clip((lum - 0.10) / 0.90, 0, 1) ** 2)
            if c is not None:
                lat = float(c[1])
                dlat = (lat - self._photo_lat) / dt if self._photo_init else 0.0
                self._photo_lat, self._photo_init = lat, True
                self._photo_i = float(np.clip(
                    self._photo_i + self.PHOTO_I * lat * dt,
                    -self.PHOTO_I_MAX, self.PHOTO_I_MAX))
                photo = gate * (self.PHOTO_K * float(np.clip(
                    lat + self.PHOTO_D * dlat, -1.5, 1.5)) + self._photo_i)
        else:
            self._photo_lat, self._photo_init, self._photo_i = 0.0, False, 0.0
        # TASK-0020: symmetric frontal looming avoidance — steer away from
        # the silhouette (dark-centroid regime) or toward the open side
        # (bright-remnant regime at close range), with a proximity-scaled
        # gain and a timer-latched escape turn that breaks standoff
        # orbits. Mirror-symmetric by construction.
        loom = 0.0
        if frac_eff > 0.15:
            # dark-centroid steering. (A bright-remnant regime and a
            # latched escape turn were tried and removed: on a broadly
            # dimmed frontal field the "remnant" is the fixed receptor-
            # field geometry — same lateral bias on every mirror — and
            # the latch amplified it into a common-mode turn, probe
            # +30/+30 Hz on mirrored poses.)
            w = np.clip((ref - lf) / max(ref, 1e-6), 0, 1) ** 2
            s_d = float(w.sum())
            lat_c = 0.0
            if s_d > 1e-6:
                c = (w @ self.receptor_dirs[self._frontal]) / s_d
                norm = float(np.linalg.norm(c))
                if norm > 1e-6:
                    lat_c = float(c[1]) / norm
            # proximity-scaled gain, hard-capped: a sustained wall-
            # darkening looks like perpetual looming and would otherwise
            # hold ~200 dps turns (guardrail: omega p50 < 150 dps)
            loom = float(np.clip(-self.LOOM_K * lat_c * (0.4 + 1.2 * frac_eff),
                                 -8.0, 8.0))
            # TASK-0022: dead-ahead tie-break. Inside the +-12 deg cone the
            # dark-centroid lateral is noise and the kernel's 5% residual
            # handedness decides the window (P_rule left arm stuck at
            # 0.429). Latch a seeded-random turn for a fixed window —
            # deterministic per run seed, ~50/50 across mirrors.
            if abs(lat_c) < 0.20 and frac_eff > 0.15:
                if self._tie_t <= 0.0:
                    self._tie_sign = 1.0 if self._rng.random() < 0.5 else -1.0
                    self._tie_t = self.TIE_S
            elif abs(lat_c) >= 0.35:
                self._tie_t = 0.0   # clear lateral signal: no tie-break
        elif len(lf) and float(lf.mean()) < 0.6 * float(
                np.median(lum64[~self._frontal])):
            # near-field rescue: at close range the frontal field dims so
            # uniformly that the relative dark detector collapses. The
            # mean brightness contrast between the frontal halves is a
            # robust direction cue — steer toward the brighter half (the
            # open side). Mirror-antisymmetric by construction.
            fl = self._frontal & (self.receptor_dirs[:, 1] > 0)
            fr = self._frontal & (self.receptor_dirs[:, 1] < 0)
            if fl.any() and fr.any():
                dh = float(np.mean(lum64[fl]) - np.mean(lum64[fr]))
                if abs(dh) > 0.01:
                    loom = self.LOOM_K * 0.6 * math.copysign(1.0, dh)
        if self._tie_t > 0.0:
            self._tie_t -= dt
            loom += self._tie_sign * self.TIE_HZ
        if self._loom_esc_t > 0.0 and self.LOOM_ESC_HZ > 0.0:
            self._loom_esc_t -= dt
            loom += self._loom_esc_sign * self.LOOM_ESC_HZ
        s = photo + loom
        if s:
            out["DNp20_R"] += 0.5 * s
            out["DNp20_L"] -= 0.5 * s
        # TASK-0023: vertical light response. The DNa02 readout differential
        # is dead (probe: z constant to the 4th decimal over 300 s runs,
        # pitch std 0.0000), so nothing ever commands climb or descent.
        # Drive the DNa02 pair with the dorsal/ventral luminance contrast
        # under the same glare-salience gate as phototaxis: sun above ->
        # climb toward it, glare below the horizon -> descend. Sign:
        # pitch_cmd = DNa02_R - DNa02_L > 0 climbs.
        if gate > 0.0:
            up = lum64[self._up]
            dn_ = lum64[self._down]
            # structural light-source test: weight by the same glare
            # kernel as phototaxis and compare dorsal vs ventral BRIGHT
            # structure. An absolute dorsal-mean test (>=0.5) only opened
            # under fixed-phototaxis gain 2.0 and left S0v z pinned under
            # P_rule's intent mix (Gate-V0 precheck FAIL); a raw contrast
            # test opened under S2 obstacle shadows (dark asymmetry is not
            # a light). Bright-structure dominance is both cases-correct:
            # glare -> bu >> bd (climb); silhouette -> bu ~ bd (no climb);
            # uniform -> both ~0 (no climb).
            bu = float((np.clip((up - 0.10) / 0.90, 0, 1) ** 2).mean())
            bd = float((np.clip((dn_ - 0.10) / 0.90, 0, 1) ** 2).mean())
            if bu + bd > 1e-4 and bu > 4.0 * bd:
                dc = (bu - bd) / (bu + bd)
                vert = gate * self.VERT_K * float(np.clip(3.0 * dc, -1.0, 1.0))
                out["DNa02_R"] += 0.5 * vert
                out["DNa02_L"] -= 0.5 * vert
        self.last_total = int(counts.sum())
        return out

    def dn_snapshot(self):
        """Motor-command view (baseline-subtracted) for HUD/serving."""
        return {k: round(float(self.rates[i]) - self.baseline.get(k, 0.0), 2)
                for k, i in self.index_of.items()}

    def hud(self):
        return {"mean_spikes_hz": round(self.last_total / 166700 / 0.1, 4),
                "connectome": True,
                "dn_baseline": {k: round(v, 2) for k, v in self.baseline.items()}}

def make_brain(kind="skeleton", seed=0):
    if kind == "skeleton":
        return SkeletonBrain(seed=seed)
    if kind == "connectome":
        return ConnectomeBrain()
    raise ValueError(f"unknown brain kind {kind!r}")


class FixedIntentSource:
    """M1 intent stub: rotates through the intent set every N frames.

    M2 replaces this with the Laya /v1/systemone loop (choice over the
    intent set + arousal score -> gain modulation). Kept for
    FLYLAYA_INTENT=fixed and as an offline fallback. The vocab is
    single-sourced from intent.INTENTS so it cannot drift stale again
    (TASK-0006: it once carried the M1 4-class set).
    """

    def __init__(self, every_frames=30, log_path=None):
        from .intent import INTENTS
        self.intents = list(INTENTS)
        self.every = every_frames
        self.i = 0
        self._log = open(log_path, "a") if log_path else None

    def poll(self, frame, world, brain):
        if frame % self.every == 0:
            self.i = (self.i + 1) % len(self.intents)
            if self._log:
                self._log.write(json.dumps({
                    "t": time.time(), "source": "fixed", "frame": frame,
                    "intent": self.intents[self.i],
                    "applied": self.intents[self.i],
                }) + "\n")
                self._log.flush()
        return self.intents[self.i], 1.0
