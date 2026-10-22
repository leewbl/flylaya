"""M5 W5 viewer/盲评 builder — spec: flylaya-next-experiment-system-design.md §8.

从冻结的 run 轨迹(不重新仿真)生成两模式页面 + 离线真值钥匙:
  index.html   诊断模式: 配置/意图/DN 图层/事件层全开, 含文件名
  blind.html   科研盲评模式: 匿名 clip id, 无真值/文件名/参数, 双问题协议,
               训练题, 按评分者随机顺序+左右
  blind_key.json  真值钥匙(离线保管, 任何页面不得引用/加载)

用法:
  python3 build.py --runs-dir ../m4/runs --n-trials 20 --seed 7 \
                   [--out-dir .] [--has-real-reference]

数据源兼容: m4 run jsonl(type=meta/frames) 与 m5 trajectory.jsonl(逐帧 dict,
同键名 + 可选 dn/events)。DN/事件缺省时诊断模式图层置灰标注。

安全边界: blind.html 内嵌数据仅含 clip 几何/运动学帧 + 匿名 id;
真值(config/seed/run 名/参数)只进 blind_key.json。
"""
import argparse
import hashlib
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
STRIDE = 2
INTENTS = ["phototaxis", "avoid_obstacle", "explore", "center_in_arena", "rest_hover"]
TRAINING_TRIALS = 2
SALT = "flylaya-m5-blind-v1"


def clip_id(run_name):
    return "c" + hashlib.sha256((SALT + ":" + run_name).encode()).hexdigest()[:10]


def load_run(path):
    lines = [json.loads(x) for x in open(path)]
    meta = next(d for d in lines if d.get("type") == "meta")
    frames = [d for d in lines if d.get("type") != "meta"]
    sun = meta.get("sun", {})
    az = math.radians(sun.get("azimuth_deg", 0.0))
    el = math.radians(sun.get("elevation_deg", 45.0))
    m = {
        "obstacles": meta["obstacles"],
        "sun_unit": [round(math.cos(el) * math.cos(az), 4),
                     round(math.cos(el) * math.sin(az), 4),
                     round(math.sin(el), 4)],
    }
    out, dn_seen = [], False
    for f in frames[::STRIDE]:
        it = INTENTS.index(f["intent"]) if f.get("intent") in INTENTS else 2
        row = [round(f["t"], 1), *(round(v, 1) for v in f["pos"]),
               round(f["yaw"] % 360, 1), round(f.get("pitch", 0.0), 3),
               round(f["speed"], 1), it,
               round(f.get("intent_conf", 0.0), 3),
               round(f.get("arousal", 0.0), 1)]
        if "dn" in f:
            dn_seen = True
            row.append({k: round(v, 2) for k, v in f["dn"].items()})
        out.append(row)
    if frames:
        assert out[-1][0] >= frames[-1]["t"] - 1.0, path
    # 刺激事件层: 可选同级 {name}.events.jsonl (m5 合同 §6; m4 无 -> 空)
    events = []
    ev_path = path[:-6] + ".events.jsonl"
    if os.path.exists(ev_path):
        for l in open(ev_path):
            e = json.loads(l)
            events.append([round(e.get("t", 0), 1), str(e.get("kind", "ev"))[:12]])
    return {"meta": m, "frames": out, "has_dn": dn_seen, "events": events,
            "brain": meta.get("brain"), "config": meta.get("config"),
            "seed": meta.get("seed"), "intent_source": meta.get("intent_source")}
def build_plan(pool, rng, n_trials):
    """A_full vs 消融随机配对 (与 m4 manifest_gen 同规则)。"""
    a_runs = pool.get("A_full", [])
    flats = [f for k, v in pool.items() if k != "A_full" for f in v]
    if not a_runs or not flats:
        raise SystemExit(f"need A_full + ablations; got {sorted(pool)}")
    trials = []
    for _ in range(n_trials):
        a, x = rng.choice(a_runs), rng.choice(flats)
        trials.append(sorted([a, x]))  # 排序去侧别; 页面按评分者再随机左右
    # 训练题: 与正式题不同的两对
    seen = {tuple(t) for t in trials}
    train = []
    while len(train) < min(TRAINING_TRIALS, len(seen) + 8):
        pair = tuple(sorted([rng.choice(a_runs), rng.choice(flats)]))
        if pair not in seen and pair not in [tuple(t) for t in train]:
            train.append(list(pair))
    return train, trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--n-trials", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out-dir", default=HERE)
    ap.add_argument("--has-real-reference", action="store_true",
                    help="有真实果蝇同场景参照时,Q2 才称『拟真』; 缺省报『方案间偏好』")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    pool, loaded = {}, {}
    for fn in sorted(os.listdir(args.runs_dir)):
        if (fn.endswith(".jsonl") and not fn.endswith(".events.jsonl")
                and "_" in fn and fn[0].isupper()):
            name = fn[:-6]
            run = load_run(f"{args.runs_dir}/{fn}")
            pool.setdefault(run["config"] or name.rsplit("_", 1)[0], []).append(name)
            loaded[name] = run

    train, trials = build_plan(pool, rng, args.n_trials)

    plan_train = [{"pair": [clip_id(a) for a in p], "training": True} for p in train]
    plan_main = [{"pair": [clip_id(a) for a in p], "training": False} for p in trials]
    all_cids = {c for t in plan_train + plan_main for c in t["pair"]}

    # --- 匿名 clip 数据 (盲评页唯一输入): 仅几何+运动学前 6 列 ---
    blind_runs = {}
    for name, run in loaded.items():
        c = clip_id(name)
        if c not in all_cids:
            continue
        blind_runs[c] = {"meta": run["meta"], "frames": [[*f[:6]] for f in run["frames"]]}

    # --- 诊断页: 全量 (同样按 cid 索引, run 内带 name 供显示) ---
    diag_runs = {}
    for name, run in loaded.items():
        c = clip_id(name)
        if c not in all_cids:
            continue
        r = dict(run)
        r["name"] = name
        diag_runs[c] = r

    blind_data = {
        "plan": plan_train + plan_main,
        "runs": blind_runs,
        "hasRealRef": bool(args.has_real_reference),
        "salt": SALT,  # 供复算顺序(不含真值)
    }
    diag_data = {
        "plan": plan_train + plan_main,
        "runs": diag_runs,
        "hasRealRef": bool(args.has_real_reference),
    }

    tpl = open(f"{HERE}/template.html").read()
    for mode, data, fname in (("blind", blind_data, "blind.html"),
                              ("diag", diag_data, "index.html")):
        html = (tpl.replace("__MODE__", mode)
                   .replace("__DATA__", json.dumps(data, separators=(",", ":"))))
        open(f"{args.out_dir}/{fname}", "w").write(html)
        print(f"{mode}: {fname} {os.path.getsize(args.out_dir + '/' + fname) / 1e6:.2f} MB")

    key = {
        "_warning": "真值钥匙: 离线保管, 严禁发给评分者/嵌入页面; aggregate.py 专用",
        "salt": SALT,
        "clips": {clip_id(n): {"run": n, "config": loaded[n]["config"],
                               "seed": loaded[n]["seed"],
                               "brain": loaded[n]["brain"],
                               "intent_source": loaded[n]["intent_source"]}
                  for n in loaded if clip_id(n) in all_cids},
    }
    open(f"{args.out_dir}/blind_key.json", "w").write(json.dumps(key, indent=1))
    print(f"key: blind_key.json ({len(key['clips'])} clips) "
          f"trials={len(plan_main)} training={len(plan_train)}")


if __name__ == "__main__":
    main()
