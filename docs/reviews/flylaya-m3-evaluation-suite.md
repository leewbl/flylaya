# FlyLaya M3：评估三件套与消融（TASK-0015）

- 测试者：tester（instance tester-01m37k0t3x0n8nb2q5b9cnm7q7）· 2026-09-24
- 交付物：`/tmp/flylaya/m3/`（trajectory_stats.py + test_trajectory_stats.py + ablation/ + literature_baselines.{md,json}）
- 依赖对齐：意图规范 v1（researcher）、M1 Brain/FixedIntentSource 接口（backend，in flight）

## ① 轨迹统计模块（trajectory_stats.py，stdlib+numpy）

九组指标 + 三 CLI 模式（run/compare/baseline），输入契约 = 轨迹 jsonl（meta 首行 + 每帧行，字段缺失容错）：

- **运动学**：路径长/净位移/直度指数/速度分位
- **saccade**：|ω|>300°/s 峰检测（半阈值尾追 + 100ms 不应期）→ 幅值/峰值角速度/时长分布 + 频率 + 左右平衡
- **分段/静息**：直线段（低 ω 阈分割）arc/直度/时长；低速静息段（<5cm/s ≥0.5s）
- **速度谱**：手写 Welch（hann、50% 重叠）主频
- **趋光**：航向-太阳方位角圆统计（均值方向/R/±30° 占比）+ 爬升与 cos(相对航向) 耦合
- **避障边际**：对障碍柱（z 跨度感知）与墙的逐帧最小间隙分位 + <5cm 时间占比
- **空间占用**：xy/xz 10cm 网格热图 + 利用率 + 归一化熵
- **意图统计**（规范 §5 验收口径）：分布塌缩/切换频率/驻留/arousal-速度 Pearson
- **统计工具**：双样本 KS（含小 D 区渐近式修复）+ 跨配置成对 KS 矩阵 + 文献区间判定

**自测 22/22 通过**（确定性合成轨迹已知答案）：saccade 计数 19/19、幅值 90.0°/峰值 900dps 零误差；直度 1.0、静息 4.0s 检出、圆统计 R=1.0@45°、障碍边际 15cm 精确、占用熵 ln2/ln100 精确、KS 同分布/不相交/重叠三态正确、三 CLI 模式端到端退出码 0。

## ② 文献基准（literature_baselines.md/.json）

搜索服务不可用，改经 NCBI eutils/PMC 直取四篇一手来源（含 PMID，全部直接引用除标注项）：

| 锚点 | 值 | 来源 |
|---|---|---|
| saccade 幅值/时长 | **~120° / ~130ms** | Mronz & Lehmann 2008（JEB 211:2026，PMID 18552291） |
| surge/cast 延迟 | **190±75ms / 450±165ms** | van Breugel & Dickinson 2014（Curr Biol 24:274，PMID 24440395） |
| 嗅觉调制起始 | ~85ms | Bhandawat 2010（JEB 213:3625，PMID 20952610） |
| 转角变异跨度 | ~100°；surge 脉冲 0.8m/s@0.07s；τ=0.42s；cast 漂移 0.25m/s；风洞 1.3×0.3×0.3m@30–60cm/s | Pang 2018（PLoS Comp Biol，PMC5828511 全文方法） |

关键口径警告（已写入文档）：1m³ 立方场地 vs 细长风洞 → 空间利用/边际/趋光只做 A/B/C/D 相对比较；saccade 类指标可绝对对照；10Hz 采样下 130ms≈1–2 帧，幅值=∫ω·dt 含采样误差；自由飞行地速 20–60cm/s 为 **[INFERENCE]**（不参与达标，M4 前补验或移除）。

## ③ 消融配置（ablation/，A/B/C/D + README）

两因子正交设计：**brain**（connectome/skeleton）× **intent_source**（laya/fixed_rotation/random）：

| 配置 | brain | intent | 回答 |
|---|---|---|---|
| A_full | connectome | laya（300ms 决策，规范 §4 参数+超时回退） | 完整系统上限 |
| B_no_laya | connectome | fixed_rotation（3s/意图，0.33Hz 在规范 0.1–1Hz 内） | 无 Laya 下限 |
| C_no_connectome | skeleton | laya | Laya 单独贡献 |
| D_random_intent | connectome | random（同决策节奏 300ms 均匀抽） | 意图信息量 |

共用 10 种子（11..111）×300s×10Hz；对比设计 A−B=Laya 增益、A−C=连接组增益、A−D=序列信息量、B−D=内容 vs 节奏。配置字段名即 M2/M4 批量入口接口契约（README 附用法）。

## M4 就绪度

- 统计/基准/配置三件套可直接被 M4 批量消费：`run`→逐轨迹 metrics，`compare`→跨配置 KS 表，`baseline`→文献区间判定。
- 待 M2 交付后需一次对接适配：日志字段名若与模块头契约不一致，改 `load_trajectory` 一处即可。
- 遗留：地速绝对基准补验（vB&D 图表或 S6 数据）；若 M2 能输出帧内子步角速度，saccade 形状测量精度可提升。

## 复现

```bash
cd /tmp/flylaya/m3 && /tmp/laya-mlx-deploy/.venv/bin/python test_trajectory_stats.py   # 22/22，<1s
/tmp/laya-mlx-deploy/.venv/bin/python trajectory_stats.py run <traj.jsonl> -o metrics.json
/tmp/laya-mlx-deploy/.venv/bin/python trajectory_stats.py compare A.json B.json C.json D.json -o table.md
/tmp/laya-mlx-deploy/.venv/bin/python trajectory_stats.py baseline metrics.json literature_baselines.json
```
