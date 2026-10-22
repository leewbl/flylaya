# M5 8 小时数据战役 · 执行总结（TASK-0021，tester）

- 执行：tester（claim CLM-01M3DZMF2ASCP35VRDYEDXQA5D）· T0=2026-09-25 23:49（Gate-F PASS 判定后）
- 前置链：Gate-F 判据 v2（预注册读法 A/B）正式 PASS → researcher 解除封存禁令 → 冻结代码态（六源哨兵快照，含 arousal 浮点修复与 RNG 审计注记）

## 批次与判定（200/200 段零失败，manifest 全 verify，哨兵全程零告警）

| 阶段 | 构成 | 墙钟 | 判定 |
|---|---|---|---|
| H1 确认 | S1 双镜像×{P_laya,P_yoked}×封存[0:20]×30s | 33min | **不成立**：diff 左 −0.0044/右 −0.0155，CI 跨零，远低 +0.15 |
| H2 确认 | S2 双镜像×同种子 + 后方负对照(探索 2001–2010) | 36min | **接触口径不可判**（38/40 配对双臂 0 接触，185/177 接近）；fallback 无 Laya 优势（左镜 yoked 反优 0.410 vs 0.299）；负对照弱通过 |
| H3 中介 | 计划条件条款（有效应场景）| — | **条件跳过**：双主终点均负，无可中介效应（记录性跳过，非缺省） |
| S4 开放 | ×{P_laya,P_yoked,P_rule}×封存[20:30]×300s | 102min | P_laya≈P_yoked 全指标（speed 0.160/switch 0.51/5 类/cos +0.395 vs +0.402/away 0.258 vs 0.237）；P_rule 混合冲突形态（cos 塌至 +0.039、away 最高 0.667、结构性高频切换 6.7Hz） |
| H4 高频 | hf_smoke 10/20ms 双档 | 22s | **内核支持**（connectome rt×1.52/1.58）——快转向可报时长/峰值，无需 §3.3 降级 |
| 盲评包 | S4 30 段→21 匿名 clips→20 试验+2 训练 | 1min | blind.html 0.49MB + 离线 blind_key.json；**渗透检查 PASS**；真值映射(A_full=P_laya,X_abd1/2=P_yoked/P_rule)只在本报告与 key |

## 核心结论（供 W6 终报）

1. **L1 确认性证伪（当前 observable 状态编码）**：仪器可表达性已由 P_rule 证明（S1 cos 0.55–0.63、S2 away 0.67–1.0），而 Laya≈yoked 于 H1（配对差≈0）与 H2（fallback 无优势）——失败定位在决策层的状态语义，非接口。迭代方向按设计 §10：状态可观测性/意图定义/模型专门化。
2. **S4 holdout 形态**：P_rule 在多线索冲突下趋光崩溃（+0.039 vs 单线索 0.55+）而避障最强——简单/混合场景能力分离的实证素材。
3. **H2 左镜像天花板**（预注册声明 ≈0.8–0.85）与死轴锥随机破缺在确认批数据中可复核。
4. 封存种子消耗：[0:20] H1/H2、[20:30] S4、[30:32] 机动未动。预算：有效计算 ~2.9h（8h 窗内）；首跑 H1 因我方 docstring 编辑触发哨兵作废重跑（+33min 走缓冲，判据记录在案）。

## 复现

```bash
python m5/campaign/run_campaign.py stage h1   # 依次 h1/h2/s4（h3 条件跳过已记录）
python m5/metrics.py pair-batch m5/runs_confirm
python m5/campaign/blind_leak_check.py m5/viewer
```

数据：m5/runs_confirm/（200 段+manifests+analysis.json）；盲评真值映射 /tmp/blind_src_name_map.json 已随本报告归档说明；评分入口 m5/viewer/blind.html（人类评分≥3 人双问题协议，不计 8h 窗）。
