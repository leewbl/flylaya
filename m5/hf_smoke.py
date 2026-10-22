"""High-frequency neural stepping smoke (TASK-0010 / design §3.3).

10 s of sim at 10 ms neural frames (1000 steps) through the connectome
kernel, plus the skeleton reference. Verdict per design: if the kernel
cannot sustain ~real-time at 10-20 ms, M5 downgrades fast-turn
experiments to 10 Hz coarse event counting and reports no
duration/peak-velocity claims.

Run: /Users/leewbl/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python m5/hf_smoke.py [dt_ms]
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flylaya.brains import make_brain

DT_MS = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
SIM_S = 10.0
dt = DT_MS / 1000.0
n = int(round(SIM_S / dt))

rng = np.random.default_rng(11)
lums = [rng.random(3335).astype(np.float32) * 0.6 for _ in range(n)]

for kind in ("skeleton", "connectome"):
    brain = make_brain(kind, seed=11)
    t0 = time.perf_counter()
    dn_sum = 0.0
    for lum in lums:
        out = brain.step(lum, dt)
        dn_sum += out["DNp20_R"] - out["DNp20_L"]
    wall = time.perf_counter() - t0
    mean_dn = dn_sum / n
    print(f"{kind:10s} dt={DT_MS:.0f}ms steps={n} wall={wall:6.2f}s "
          f"rt_factor={SIM_S / wall:5.2f}x mean_DNp20_diff={mean_dn:+.3f} Hz")

print()
print("VERDICT: kernel supports sub-frame neural stepping at "
      f"{DT_MS:.0f} ms" if wall < SIM_S * 3 else
      "VERDICT: kernel too slow — downgrade fast-turn experiments to "
      "10 Hz coarse event counting (no duration/peak claims)")
