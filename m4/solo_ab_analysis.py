#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立分析：A_full vs B_no_laya 轨迹行为指标对比。

只用 m4/runs_iter1params/ 下的 A_full_*.jsonl 与 B_no_laya_*.jsonl 原始数据，
不读仓库里任何现成报告。无 scipy/numpy，KS 全手算。

指标（每段轨迹一个值）：
  mean_speed   全部帧速度均值（cm/s）
  mean_abs_w   相邻帧 yaw 差折算角速度的绝对值均值（deg/s），差值折到 [-180,180]
  still_ratio  speed < 2 cm/s 的帧占比
  coverage     5cm 网格去重格数 / 400（100cm 场地 20x20 格）

每算完一个指标就追加写 m4/solo_ab_analysis.md。
KS：两样本 D 统计量（经验分布函数差的最大值，只在并列值组末尾取值）；
p 值两个口径——p_exact 精确置换（C(20,10)=184756 种分组），p_asym Kolmogorov 渐近级数。
"""
import glob
import itertools
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "runs_iter1params")
MD = os.path.join(HERE, "solo_ab_analysis.md")
A_FILES = sorted(glob.glob(os.path.join(DATA, "A_full_*.jsonl")))
B_FILES = sorted(glob.glob(os.path.join(DATA, "B_no_laya_*.jsonl")))
SPEED_STILL = 2.0   # cm/s，静止判定阈值
GRID = 5.0          # cm，占用网格边长
CELLS = 20 * 20     # 100cm 场地 5cm 网格共 400 格


def load(path):
    meta, frames = None, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("type") == "meta":
                meta = rec
            else:
                frames.append(rec)
    return meta, frames


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def mean(xs):
    return sum(xs) / len(xs)


def std(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def ks_d(xs, ys):
    """两样本 KS 的 D：合并全部取值，只在每个并列值组的末尾比较经验分布函数差。"""
    n1, n2 = len(xs), len(ys)
    sx, sy = sorted(xs), sorted(ys)
    i = j = 0
    c1 = c2 = 0
    d = 0.0
    while i < n1 or j < n2:
        v1 = sx[i] if i < n1 else math.inf
        v2 = sy[j] if j < n2 else math.inf
        v = min(v1, v2)
        while i < n1 and sx[i] == v:
            i += 1
            c1 += 1
        while j < n2 and sy[j] == v:
            j += 1
            c2 += 1
        diff = abs(c1 / n1 - c2 / n2)
        if diff > d:
            d = diff
    return d


def ks_p_exact(d, n1, n2, pooled_sorted):
    """精确置换 p：枚举 C(n1+n2,n1) 种标签划分重算 D，数 D_perm >= D_obs 的比例。
    D_perm 与 ks_d 同口径，只在并列值组末尾取值。"""
    m = n1 + n2
    eval_here = [pooled_sorted[i] != pooled_sorted[i + 1] for i in range(m - 1)] + [True]
    total = ge = 0
    for combo in itertools.combinations(range(m), n1):
        s = set(combo)
        c1 = c2 = 0
        dp = 0.0
        for i in range(m):
            if i in s:
                c1 += 1
            else:
                c2 += 1
            if eval_here[i]:
                diff = abs(c1 / n1 - c2 / n2)
                if diff > dp:
                    dp = diff
        total += 1
        if dp >= d - 1e-12:
            ge += 1
    return ge / total  # 观测分组本身在枚举内，ge>=1，p 不会为 0


def ks_p_asym(d, n1, n2):
    """Kolmogorov 渐近级数。"""
    ne = n1 * n2 / (n1 + n2)
    x = ne * d * d
    if x <= 0:
        return 1.0
    s, k = 0.0, 1
    while True:
        term = (-1) ** (k - 1) * math.exp(-2.0 * k * k * x)
        s += term
        if abs(term) < 1e-12:
            break
        k += 1
    return max(0.0, min(1.0, 2.0 * s))


def fmt(v, nd=3):
    return f"{v:.{nd}f}"


def per_traj(frames):
    speeds = [f["speed"] for f in frames]
    ws = [
        abs(wrap180(frames[i + 1]["yaw"] - frames[i]["yaw"]))
        / (frames[i + 1]["t"] - frames[i]["t"])
        for i in range(len(frames) - 1)
    ]
    cells = {
        (min(int(f["pos"][0] // GRID), 19), min(int(f["pos"][1] // GRID), 19))
        for f in frames
    }
    return {
        "mean_speed": mean(speeds),
        "mean_abs_w": mean(ws),
        "still_ratio": sum(1 for s in speeds if s < SPEED_STILL) / len(speeds),
        "coverage": len(cells) / CELLS,
    }


def main():
    assert len(A_FILES) == len(B_FILES) == 10, (len(A_FILES), len(B_FILES))
    A = {os.path.basename(p): load(p) for p in A_FILES}
    B = {os.path.basename(p): load(p) for p in B_FILES}

    arena_cm = list(A.values())[0][0]["arena"]["size_cm"]
    nframes = {len(v[1]) for v in list(A.values()) + list(B.values())}
    dts = set()
    for _, frames in list(A.values()) + list(B.values()):
        dts.update(round(frames[i + 1]["t"] - frames[i]["t"], 6) for i in range(20))
    assert nframes == {3000}, nframes

    md = open(MD, "w", encoding="utf-8")
    md.write(
        "# A_full vs B_no_laya 轨迹指标独立分析\n\n"
        "## 方法\n\n"
        f"- 数据：`runs_iter1params/` 下 A_full 与 B_no_laya 各 10 段，每段 {sorted(nframes)[0]} 帧"
        f"（{sorted(nframes)[0]/10:.0f}s @10Hz），场地 {arena_cm:.0f}x{arena_cm:.0f}cm，"
        f"采样间隔 {sorted(dts)[0]:.1f}s。分析只读这两组 jsonl 原始帧数据。\n"
        "- 指标定义（每段轨迹汇总成一个数）：\n"
        "  - 平均速度：全部帧 `speed` 字段均值（cm/s）。\n"
        "  - 平均角速度绝对值：相邻帧 `yaw`（度）之差折到 [-180,180] 后除以采样间隔，"
        "取绝对值后求均值（deg/s），每段 2999 个差分。\n"
        f"  - 静止占比：`speed` < {SPEED_STILL:.0f} cm/s 的帧数 / 总帧数。\n"
        f"  - 空间占用：位置 (x,y) 落入 {GRID:.0f}cm 网格，去重格数 / {CELLS}（格占比）。\n"
        "- 显著性：两样本 KS 检验，D 手算（经验分布函数差的最大值）。p 值两个口径：\n"
        "  精确置换（枚举全部 C(20,10)=184756 种分组，n=10 vs 10 的严谨口径，主用）；\n"
        "  Kolmogorov 渐近级数（仅参考，小样本下有偏差）。\n"
        "- 环境：纯 python3，无 scipy/numpy。\n\n"
        "## 中间结果（逐指标）\n"
    )
    md.flush()

    seeds = [os.path.basename(p).rsplit("_", 1)[1].split(".")[0] for p in A_FILES]
    mA = {k: per_traj(fr) for k, (m, fr) in A.items()}
    mB = {k: per_traj(fr) for k, (m, fr) in B.items()}

    metric_labels = [
        ("mean_speed", "平均速度 (cm/s)"),
        ("mean_abs_w", "平均角速度绝对值 (deg/s)"),
        ("still_ratio", "静止占比"),
        ("coverage", "空间占用 (格占比)"),
    ]

    # 逐指标：算完立刻落盘
    for key, label in metric_labels:
        va = [mA[k][key] for k in A]
        vb = [mB[k][key] for k in B]
        md.write(f"\n### {label}\n\n| seed | A_full | B_no_laya |\n|---|---|---|\n")
        for s, a, b in zip(seeds, va, vb):
            md.write(f"| {s} | {fmt(a)} | {fmt(b)} |\n")
        md.write(
            f"\nA 均值±std = {fmt(mean(va))} ± {fmt(std(va))}；"
            f"B 均值±std = {fmt(mean(vb))} ± {fmt(std(vb))}\n"
        )
        md.flush()
        print(f"[metric done] {key}")

    # 汇总 + KS
    md.write(
        "\n## 两组均值±std 与 KS 检验\n\n"
        "| 指标 | A_full (n=10) | B_no_laya (n=10) | KS D | p(精确置换) | p(渐近) |\n"
        "|---|---|---|---|---|---|\n"
    )
    ks_out = {}
    for key, label in metric_labels:
        va = [mA[k][key] for k in A]
        vb = [mB[k][key] for k in B]
        d = ks_d(va, vb)
        pe = ks_p_exact(d, 10, 10, sorted(va + vb))
        pa = ks_p_asym(d, 10, 10)
        ks_out[key] = (d, pe, pa)
        md.write(
            f"| {label} | {fmt(mean(va))} ± {fmt(std(va))} | {fmt(mean(vb))} ± {fmt(std(vb))} "
            f"| {fmt(d)} | {fmt(pe)} | {fmt(pa)} |\n"
        )
        md.flush()
        print(f"[ks done] {key}: D={d:.4f} p_exact={pe:.4f} p_asym={pa:.4f}")

    # 结论：按数值方向 + 显著性生成
    lines = ["\n## 结论\n"]
    n_sig = sum(1 for k in ks_out if ks_out[k][1] < 0.05)
    for key, label in metric_labels:
        va = [mA[k][key] for k in A]
        vb = [mB[k][key] for k in B]
        d, pe, _ = ks_out[key]
        cmp_word = "高于" if mean(va) > mean(vb) else "低于"
        sig_word = "差异显著（精确置换 p<0.05）" if pe < 0.05 else "未达显著（精确置换 p≥0.05）"
        lines.append(
            f"- {label}：A 组 {mean(va):.3f}，B 组 {mean(vb):.3f}，"
            f"A 组均值{cmp_word} B 组（差 {abs(mean(va)-mean(vb)):.3f}），KS D={d:.2f}，{sig_word}。"
        )
    lines.append(
        f"- 4 个指标中精确置换 p<0.05 的有 {n_sig} 个；"
        "n=10 vs 10 时精确置换的最小可达 p 约为 5e-6，D 小于 0.5 的分布差异在此样本量下很难显著。\n"
    )
    md.write("\n".join(lines))
    md.close()

    print(f"md written: {MD}")
    print(
        "SUMMARY: "
        + " | ".join(
            f"{key} D={ks_out[key][0]:.3f} (p_exact={ks_out[key][1]:.4f})"
            for key, _ in metric_labels
        )
    )


if __name__ == "__main__":
    main()
