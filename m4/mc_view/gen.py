"""FlyLaya Minecraft-style viewer: inject run data into template.html.

Frames -> compact arrays [t, x, y, z, yaw_deg, pitch, speed, intent_idx, conf, arousal]
at stride 2: source runs are 10 Hz, so sampled frames are 0.2 s apart (5 fps).
The viewer advances 5 frames/s at speed 1x to play back in real time.
"""
import json
import math
import os

WANT = ["A_full_11", "B_no_laya_11", "C_no_connectome_11", "D_random_intent_11"]
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RUNS = ROOT + "/m4/runs"
INTENTS = ["phototaxis", "avoid_obstacle", "explore", "center_in_arena", "rest_hover"]
STRIDE = 2

data = {}
for name in WANT:
    path = f"{RUNS}/{name}.jsonl"
    if not os.path.exists(path):
        print("skip missing", name)
        continue
    lines = [json.loads(l) for l in open(path)]
    meta = next(d for d in lines if d.get("type") == "meta")
    frames = [d for d in lines if d.get("type") != "meta"]
    sun = meta.get("sun", {})
    az = math.radians(sun.get("azimuth_deg", 0.0))
    el = math.radians(sun.get("elevation_deg", 45.0))
    unit = [math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)]
    m = {
        "obstacles": meta["obstacles"],
        "sun_unit": [round(v, 4) for v in unit],
        "seed": meta.get("seed"),
        "brain": meta.get("brain"),
        "intent_source": meta.get("intent_source"),
    }
    out = []
    for f in frames[::STRIDE]:
        it = INTENTS.index(f["intent"]) if f.get("intent") in INTENTS else 2
        out.append([round(f["t"], 1), *(round(v, 1) for v in f["pos"]),
                    round(f["yaw"] % 360, 1), round(f.get("pitch", 0.0), 3),
                    round(f["speed"], 1), it, round(f.get("intent_conf", 0.0), 3),
                    round(f.get("arousal", 0.0), 1)])
    data[name] = {"meta": m, "frames": out}
    pitches = [abs(f.get("pitch", 0)) for f in frames]
    print(f"{name}: {len(out)} frames (stride {STRIDE}), "
          f"pitch max {max(pitches):.3f} rad, "
          f"intents used {sorted(set(f['intent'] for f in frames))}")

tpl = open(f"{HERE}/template.html").read()
html = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")))
open(f"{HERE}/index.html", "w").write(html)
print("wrote", f"{HERE}/index.html", f"{os.path.getsize(HERE + '/index.html') / 1e6:.2f} MB")
