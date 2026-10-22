# FlyLaya M4：40 段全量批量结果（TASK-0016，口径 1+3）

- 测试者：tester（instance tester-01m37k0t3x0n8nb2q5b9cnm7q7）· 2026-09-24
- 批量：4 配置 × 10 种子（11..111）× 300s × 10Hz = 40 段，1h51m 墙钟（connectome rt×1.4-1.66，skeleton rt×11.4），0 失败
- 数据：/tmp/flylaya/m4/runs/（40 jsonl，18MB）+ stats_metrics.json（逐段全指标）+ stats_tables.md
- 前置：M2 spin 修复复验通过（reviews/flylaya-m2-refix-verification-spin-rootcause.md → backend 修复 → 复测 ω p50 344→77dps、>300dps 0%、span 52×69cm）

## 每配置中位数（10 种子）

| config | speed_p50 cm/s | sacc_rate Hz | sacc_amp p50 | rest_frac | sun_R | occ_util | switch_hz | arou_r |
|---|---|---|---|---|---|---|---|---|
| **A_full** | 12.2 | 0.052 | 32.1° | **0.014** | 0.039 | **0.37** | **0.0033** | **0.671** |
| B_no_laya | 13.5 | 0.065 | 34.1° | 0.207 | 0.038 | 0.32 | 0.33 | - |
| C_no_connectome | 0.67 | 0 | - | 0.655 | **0.527** | 0.165 | 0.0033 | 0.169 |
| D_random | 13.6 | 0.072 | 34.4° | 0.078 | 0.031 | 0.225 | 2.66 | - |

## 口径 3（消融增益，池化 KS n=30000 帧/配置）

- **A−B（Laya 在连接组上的增益）**：可统计分离（speed D=0.394、ω D=0.192、sacc_amp D=0.206 均 p<1e-3）。行为差异：Laya 把静止时间从 21% 压到 1.4%、空间利用 32%→37%——**意图层让蝇「更活跃、逛得更广」**。
- **A−D（意图序列信息量）**：与 A−B 幅度相近（speed D=0.394、ω D=0.198、sacc D=0.263）；occ 0.37 vs 0.225——Laya 意图比随机意图用场地更广。
- **B−D（内容 vs 节奏）**：**全分布不可分**（ω p=0.24、sacc p=0.14、heading p=1.0；speed D=0.024）——在连接组主导下，固定轮换与随机意图的运动学等价：**意图内容当前不构成行为差异来源，节奏也不构成**。
- **C−其余（连接组贡献）**：最强分离（speed/ω D 0.5-0.71）——运动学形态由连接组层主导。
- **A 内部**：arousal-score 与速度 Pearson r=0.671（规范 §5 的 >0.3 达标）；但意图切换 0.0033Hz——**整程 ~1 次切换**（规范 0.1–1Hz 严重未达；原因链推测：1s 滞留护栏 + Laya 选择保守 + state 变化慢，供 researcher 迭代）。

## 口径 1（文献基线，首种子判定，逐段在 metrics json）

全配置 1-2/7 达标。未达项集中在：sacc 率 0.05-0.07Hz vs 文献 0.2-2Hz（该区间为 INFERENCE 标注）、speed 12-14cm/s vs 20-60、直度超区间。**当前系统轨迹统计意义上的「果蝇相似度」仍低**——与计划 §5 诚实预期一致（量化天花板与失败模式即产出）。

## 显著形态学观察

- connectome 系（A/B/D）sacc 幅值 p50 ~32-34°（文献 ~120°）、率 ~0.05-0.07Hz（低一个量级）：「慢速大范围游走 + 偶发小转」，缺真蝇的高频快速 body saccade 节奏。
- C（skeleton+laya）：趋光显著（sun_R 0.527 vs connectome 系 ~0.04）——骨架脑保留光度不对称驱动；connectome 的 R1-R6→DN 通路当前几乎不产生趋光定向（sun_R≈0）。
- z 全配置恒 49cm（垂直反射钉中线）——无垂直探索（记录项，backend 已知）。

## 交付状态

- [x] 40 段批量 + 全指标 + KS + 基线判定（本报告 + runs/）
- [x] 口径 3 消融增益
- [~] 回放视频：16 段录制中（10×A_full + 2×各消融，5min/段）→ replays/
- [x] 盲评页 + manifest 生成器（就绪，待视频落地后出正式 manifest；人类评分由 researcher 组织）

## 复现

```bash
cd /tmp/flylaya/m4 && /tmp/laya-mlx-deploy/.venv/bin/python run_batch.py --seconds 300 --out runs   # 40 段 ~1h51m
python3 rating/manifest_gen.py runs rating/manifest.json --n-trials 20 --seed 7                     # 评分配对
```
