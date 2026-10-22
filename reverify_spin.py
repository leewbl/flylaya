"""TASK-0017 re-verification: spin gone after tonic baseline subtraction?

Replicates the tester's headless metric on the M2 loop with the fixed
ConnectomeBrain: omega p50 / >300dps frame fraction / xy-span / z range.

Usage: HF_HUB_OFFLINE=1 python reverify_spin.py [frames]
"""
import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")

from flylaya.brains import make_brain
from flylaya.intent import modulation_for
from flylaya.world import World


def main(frames=150):
    import time

    t0 = time.perf_counter()
    w = World(seed=11)
    b = make_brain("connectome")
    print(f"connectome loaded+calibrated in {time.perf_counter() - t0:.1f}s")
    print("DN baseline (Hz):", {k: round(v, 2) for k, v in b.baseline.items()
                                if k.startswith(("DNp20", "DNa02", "MDN"))})

    for yaw_gain, label in [(1.6, "control g=1.6"), (0.3, "g=0.3"), (-0.3, "sign-flip g=-0.3")]:
        w = World(seed=11)
        yaw_rates, xs, zs = [], [], []
        for i in range(frames):
            mod = modulation_for("explore", 1)
            lum = w.render_luminance(mod)
            rates = b.step(lum, 0.1)
            yaw_diff = rates.get("DNp20_R", 0.0) - rates.get("DNp20_L", 0.0)
            yaw_rates.append(yaw_gain * yaw_diff)
            w.YAW_GAIN = yaw_gain
            w.step_motor(rates, 0.1, gains={"thrust": mod["thrust"]},
                         yaw_noise=0.0, rng=w.rng)
            xs.append((float(w.pos[0]), float(w.pos[1])))
            zs.append(float(w.pos[2]))
        yaw_deg = np.abs(np.degrees(np.asarray(yaw_rates)))
        xs = np.asarray(xs)
        print(f"[{label}] omega p50 {np.percentile(yaw_deg, 50):.0f}dps | "
              f">300dps {(yaw_deg > 300).mean() * 100:.0f}% | "
              f"xy-span {np.ptp(xs[:, 0]) * 100:.0f}x{np.ptp(xs[:, 1]) * 100:.0f}cm | "
              f"z {min(zs):.2f}-{max(zs):.2f}", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 150)
