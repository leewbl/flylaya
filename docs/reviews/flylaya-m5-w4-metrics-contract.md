# FlyLaya M5-W4：评估/统计合同交付（TASK-0012，G3 验收）

- 测试者：tester（instance tester-01m3cd7byme0r7d00qsp50n1ns）· 2026-09-25
- 依据：docs/findings/flylaya-next-experiment-system-design.md §2/§5.1/§7（唯一规范）
- 交付：`m5/metrics.py`（库+CLI）· `m5/test_metrics.py`（19 项手算用例单测）

## 指标实现（§7 五类）

| 类别 | 实现 | 陷阱处理 |
|---|---|---|
| 决策 | switch_rate/class_shares/mean_dwell/timeout·fallback 率；条件命中率（avoid\|前障碍）、前/后障碍误报、photo\|光侧 | 空分母 → {n:0, rate:None}，绝不解释为成功 |
| 光方向 | **mean_cos_to_light**（有符号主指标）、朝目标位移、首次正确转向延迟（基线−15° 判据）；sun_R **必须联报平均方向** | sun_R 字段名 sun_R_with_mean_dir，注释明确「仅集中度」；非方向光场景 → None+reason |
| 避障 | 有效接近（距离≤0.25m ∧ 前方±45° ∧ 闭合≥0.02m/s 三条件）/接触率/最小间隙/正确转离率（转离=与障碍方位反号）/反应延迟 | 分母=n_valid_approaches 固定先行；空分母 → 显式失败与 fallback 报告路径 |
| 神经中介 | 预指定 DN 对（DNp20/MDN/DNa02/DNpe017 左右）、turn 窗 ±0.3s 差值符号一致率、DN 先于转向比例（10% 阈值跨越时序）、**直接通路偏航份额** | 事件窗口不足 → 跳过计数；direct 份额单列，不得计入神经通路成功 |
| 飞行 | 转向率/幅值/速度/z/休息/贴墙 | **时长/峰值仅在 median dt≤20ms 组报告**（10Hz 数据被门禁抑制并给 gate_note） |

## 统计单位与区间

- 独立单位 = **场景内种子**；配对差按 (scene,seed) 对齐（P_laya − P_yoked 同种子同场景）。
- 分层 bootstrap：先抽场景（放回）→ 场景内抽种子（放回），10000 次，固定 RNG seed 可复现。
- 池化帧 KS 仅描述（复用 m3/trajectory_stats.ks2samp），输出带 "frames are not the independent unit" 注记。

## H1/H2 判定（§2 预注册判据）

- **H1**：每镜像 mean_cos_to_light 配对差 ≥ +0.15 ∧ Bonferroni 单侧 2.5% 下界 > 0，**双侧镜像均须成立**。
- **H2**：接触风险比 RR=laya/yoked 的降低 ≥ 25% ∧ Bonferroni 单侧 2.5% 上界 < 1；零有效接近种子被剔除并计数，报告转离率/最小间隙/事件数 fallback，**不解释为成功**。
- 多重比较：H1/H2 为两个共同主终点，Bonferroni α=0.05/2；同时报告普通双侧 95% CI。

## yoked 匹配检查（§5.1/§7，可执行）

`metrics.py yoked-check LAYA_DIR YOKED_DIR`：类占比绝对差 ≤0.02、平均停留相对差 ≤10% 判定配对可否进主分析；唤醒度差默认 report-only（设计未给数，容差参数化，未擅自定死）。不过 → 整批重跑（设计语义）。

## 20 确认种子封存机制（§7.1）

`metrics.py seal-seeds --n 20 --out m5/confirm_seeds.json`：一次性写只读文件（chmod 444）+ 内容 sha256；
`verify-seals` 校验完整性 + 与探索批 run 目录的种子重叠（重叠即不可用于确认批）。
**机制就位即 G3 验收；实际封存动作在探索期结束、确认批执行前由 W6 编排触发。**
已修复初版 `rng.choice(range(1,1<<30))` 物化 10 亿元素的内存炸弹（改为 integers 去重循环）。

## 数据合同 v1（供 W1–W3 对齐）

trajectory/decisions/events 的字段名在 `m5/metrics.py` 模块 docstring 固化（SI 单位；yaw_deg 为 h_xy 数学航向；pos_m=[x,y,z] 水平 x/y）。事件检测器 `flylaya.m5.events.v1` 在 metrics.py 单一实现（闭合速度门槛含慢速负例测试），W3 runner 可直接导入——避免双实现漂移。无 events.jsonl 时按同一检测器从轨迹重建并记录版本。

## 验证证据

- `python m5/test_metrics.py` → **19/19 通过**，每项带手算期望值（mean_cos 手算 0 与 1/3；位移投影 0.5m；R=1/3；contact 0.5；转离反号判真；RR 0.2/降低 0.8；退化 bootstrap 收缩到点估计；封存篡改检测等）。
- CLI 端到端：合成 contract 批（S1 双镜像 × P_laya/P_yoked × 2 种子）→ `pair-batch` 给出 H1_pass=True、diff=1.0、CI>0、双镜像成立；`yoked-check`/`seal-seeds`/`verify-seals`/`run`（→metrics.json）均演示通过。
- 发现并修复：判定函数入口接受原始 run 或 metrics dict（`_prep` 归一）；空场景 bootstrap 返回类型不一致。

## 边界与未做

- 旧 M3 口径未触碰（m3/trajectory_stats.py 原样，仅按 §6「兼容不覆盖」复用 ks2samp）。
- blind-eval 层的「再抽评分者」分层：设计属 W5/W6 编排；当前 bootstrap 已留 raters 层扩展点（diffs_by_scene 同构可加层），未擅自实现数据不存在的部分。
- H3/H4 为解释性与独立评价，不设确认性阈值判定函数（设计 §2：H3 是 L2 门槛证据、H4 负结果也交付）；metrics 已提供其原料（DN 一致率/先于比例/直接份额；飞行类全指标+HF 门禁）。
