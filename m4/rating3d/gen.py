"""FlyLaya 3D 盲评页: manifest 配对 + run 轨迹 -> 注入 template.html.

复用 2D 盲评的配对 manifest (rating/manifest_gen.py 产物), 但数据源是 run jsonl
本体, 由 Minecraft 风格双视窗 3D 世界同步回放。导出 schema 与 2D 页一致
(left/right 换成 run 名), 聚合脚本 rating/consistency.py 可混用两页结果。

新 A 重盲评管线 (TASK-0002, 等 TASK-0001 新批量数据落地后):
  # 1) 从新 runs 目录出 manifest (A_full vs 消融, 盲化左右)
  python3 rating/manifest_gen.py <new_runs_dir>/ rating/manifest_newA.json --n-trials 20
  # 2) 生成自包含 3D 盲评页
  python3 rating3d/gen.py --manifest rating/manifest_newA.json \
                          --runs-dir <new_runs_dir> --out rating3d/index_newA.html
  # 3) 评分回收后复算一致性
  python3 rating/consistency.py 'rating/flylaya_rating3d_*.json'
"""
import argparse
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
M4 = os.path.abspath(os.path.join(HERE, ".."))
STRIDE = 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=f"{M4}/rating/manifest.json")
    ap.add_argument("--runs-dir", default=f"{M4}/runs")
    ap.add_argument("--out", default=f"{HERE}/index.html")
    args = ap.parse_args()

    m = json.load(open(args.manifest))
    pairs = []
    runs_needed = set()
    for t in m["trials"]:
        l = re.sub(r"(_replay)?\.(mp4|webm|jsonl)$", "", os.path.basename(t["left"]))
        r = re.sub(r"(_replay)?\.(mp4|webm|jsonl)$", "", os.path.basename(t["right"]))
        pairs.append({"left": l, "right": r, "truth": t["truth"]})
        runs_needed.update([l, r])

    runs = {}
    for name in sorted(runs_needed):
        lines = [json.loads(x) for x in open(f"{args.runs_dir}/{name}.jsonl")]
        meta = next(d for d in lines if d.get("type") == "meta")
        frames = [d for d in lines if d.get("type") != "meta"]
        sun = meta.get("sun", {})
        az = math.radians(sun.get("azimuth_deg", 0.0))
        el = math.radians(sun.get("elevation_deg", 45.0))
        runs[name] = {
            "meta": {
                "obstacles": meta["obstacles"],
                "sun_unit": [round(math.cos(el) * math.cos(az), 4),
                             round(math.cos(el) * math.sin(az), 4),
                             round(math.sin(el), 4)],
            },
            "frames": [[f["t"], *(round(v, 1) for v in f["pos"]),
                        round(f["yaw"] % 360, 1), round(f.get("pitch", 0.0), 3),
                        round(f["speed"], 1)]
                       for f in frames[::STRIDE]],
        }
        assert runs[name]["frames"][-1][0] >= 299, name

    data = {"pairs": pairs, "runs": runs}
    tpl = open(f"{HERE}/template.html").read()
    html = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    open(args.out, "w").write(html)
    print(f"manifest={args.manifest} runs_dir={args.runs_dir}\n"
          f"pairs={len(pairs)} runs={len(runs)} "
          f"-> {args.out} {os.path.getsize(args.out) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
