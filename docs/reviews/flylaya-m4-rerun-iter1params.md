# FlyLaya M4：全量 40 段重批（迭代①参数，TASK-0001）

- 测试者：tester（instance tester-01m3cd7byme0r7d00qsp50n1ns）· 2026-09-25
- 批量：4 配置 × 10 种子（11..111）× 300s × 10Hz = 40 段，**40/40 零失败**；2 路并发（A∥B/D，C 串行接力保持 laya-serve 单客户端），墙钟 ~1h8m（A 41min rt×1.2、B/D 67min rt×1.5、C 5min rt×10.5）
- 参数：A_full 于 `FLYLAYA_INTENT_TAU=1.6 FLYLAYA_INTENT_EPS=0.06` 下重建；B/C/D 默认参数（tau=1/eps=0，v1 行为）
- 数据：`m4/runs_iter1params/`（40 jsonl + stats_metrics.json + stats_tables.md，聚合由 run_batch 对全 40 段生成）；旧基线 `m4/runs/` 未动
- 工具：`m4/compare_runs.py`（新旧对比；旧侧 KS/中位数已验证与 canonical stats_tables.md 逐项一致）

## 新 A 护栏（HANDOFF §3，全部 PASS）

| 护栏 | 旧 A | 新 A | 门限 |
|---|---|---|---|
| ω p50 dps | 74.7 | **99** | <150 ✓ |
| ω>300dps 占比 | 0.0051 | **0.0061** | ≈0 ✓（与 B/D 0.007 同档） |
| arousal-speed r | 0.671 | **0.468**（逐种子 0.351–0.53） | >0.3 ✓ |
| switch_hz | 0.0033 | **0.545**（逐种子 0.52–0.58） | 0.1–1 ✓ |
| 意图类数 | 2 | **5/5** | ≥4 ✓ |
| 最大类占比 | 0.988（avoid 塌缩） | **0.333** | <80% ✓ |

新 A 意图分布（10 种子中位数）：avoid_obstacle 0.333 · center_in_arena 0.239 · rest_hover 0.153 · explore 0.142 · phototaxis 0.122；平均驻留 1.82s。avoid 塌缩消除，五类全活。

## 每配置中位数（旧 → 新；B/C/D 为复跑对照）

| config | speed_p50 cm/s | sacc_rate Hz | sacc_amp p50 | rest_frac | sun_R | occ_util | switch_hz | arou_r |
|---|---|---|---|---|---|---|---|---|
| **A_full** | 12.2→**13.5** | 0.052→**0.057** | 32.1°→**34.4°** | 0.014→**0.15** | 0.039→**0.026** | 0.37→**0.395** | 0.0033→**0.545** | 0.671→**0.468** |
| B_no_laya | 13.5→13.5 | 0.065→0.073 | 34.1°→34.4° | 0.207→0.202 | 0.038→0.033 | 0.32→0.31 | 0.33→0.33 | - |
| C_no_conn | 0.67→0.375 | 0→0 | - | 0.655→0.653 | 0.527→0.523 | 0.165→0.145 | 0.0033→0.0033 | 0.169→0.153 |
| D_random | 13.6→13.6 | 0.072→0.072 | 34.4°→34.4° | 0.078→0.079 | 0.031→0.034 | 0.225→0.23 | 2.66→2.66 | - |

B/C/D 复跑在行为噪声内复现旧基线（D 主指标逐位一致；B sacc_rate 中位数 0.065→0.073 与 C speed 0.67→0.375 属 connectome/laya 采样的逐次涨落，成对结论不变）。

## 口径 3（消融增益，池化 KS n=30000 帧/配置，旧→新）

- **A−B**：speed D 0.394→**0.187**；ω D 0.192→**0.036**（p=1.4e-17 仅因池化 n 大，效应量近零）；sacc_amp D 0.206→**0.085（p=0.46 失效）**；heading 两代均 ~0.01。**A−B 统计分离显著弱化——证实旧 A 的「超活跃签名」（rest 1.4%、occ 0.37）本是 avoid 塌缩产物**（HANDOFF §2 预警成立；与 iter1_confirm 3 种子的 speed D=0.178 一致）。
- **A−D**：同模式（speed 0.394→0.187，ω 0.198→0.040，sacc_amp 0.263→0.128 p=0.082 失效）。
- **B−D**：两代均不可分（speed p 0.24→0.31、ω p 0.36、sacc p 0.14-0.15）——**「意图内容/节奏不构成行为差异来源」结论不变**。
- **C−其余**：分离保持最强且 ω 分离增强（A−C speed D 0.71→0.63、ω 0.32→**0.469**）——运动学形态由连接组层主导的结论不变。

## 口径 1（文献基线，逐种子计数中位数）

- A_full：1/7（旧）→ **2/7（新，逐种子稳定 2-2）**；B 2/7、C 1/7、D 1/7 与旧一致。
- 未达项不变：sacc 率 ~0.06Hz vs 文献 0.2–2Hz、speed 13.5 vs 20–60cm/s、直度超区间。绝对拟真度仍低，迭代②方向（saccade 瞬态、趋光读出）见终报 §5。

## 口径 2（人类盲评）——必须注记

**本次重批不产生口径 2 数据。终报 98.3%/AC1=0.966 结论绑定旧 A 轨迹，对新 A 无效**；引用时按 HANDOFF §2 规则注明。重盲评入口（rating3d 重生成 manifest/回放对）为后续任务（池内 TASK-0002 方向），本批 40 段即其数据基础。

## 复现

```bash
PY=~/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python; cd ~/aiworld/flylaya/m4
FLYLAYA_INTENT_TAU=1.6 FLYLAYA_INTENT_EPS=0.06 $PY run_batch.py --configs A_full --out runs_iter1params   # ~41min
$PY run_batch.py --configs B_no_laya D_random_intent C_no_connectome --out runs_iter1params                 # ~1h8m
$PY compare_runs.py runs runs_iter1params   # 新旧对比全表（本报告数据源）
```

并发约束遵守：任意时刻 ≤2 批进程、laya-serve 单客户端（A 与 C 不重叠）。断点续跑语义已验证（skip existing）。
