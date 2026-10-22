# M5-V 垂直维度战役 · 执行总结（TASK-0025，tester）

- 执行：tester（claim CLM-01M3FB4H5TEN548NVGWFSRE4B4）· 2026-09-26
- 前置链：0023 解钉（+backend gate-v0-precheck 三阻塞修复：场景文件尾随垃圾、绝对门→结构性亮对比判据、反射带加宽消贴顶）→ **Gate-V0 官方 PASS**（z_std 0.144/pin 0.000/ω 95.9，P_rule 计划原口径，哨兵净）→ 封存集解锁

## 批次与判定（150/150 零失败，manifest 全 verify，哨兵全程零告警）

| 阶段 | 构成 | 墙钟 | 判定 |
|---|---|---|---|
| explore | S0v/S4v×{laya,yoked,rule}×探索 4001–4010×120s | 1h22m | **V1 可表达性 PASS**：全策略 z_std 0.11–0.17、z_mean 0.54–0.62 中带、平衡非漂移 |
| V3 confirm | S0v/S4v×{laya,yoked}×封存 v[0:20]×120s | 1h54m | **无垂直语义增益**（区间报告，预注册无硬门）：z_mean −0.001[−0.009,+0.008]、z_std +0.003[−0.012,+0.015]、v_act +0.001[−0.004,+0.004]——三指标 CI 全跨零 |
| s4rule | S4v×P_rule×封存 v[20:30]×120s | 12m | P_rule 垂直参照臂（数据入 W6 素材） |

## 结论（供 W6）

1. **V0 通道修复实证**：z 从恒 0.500 钉死 → std 0.14+、中带平衡、零贴附——垂直自由度可用（0023+预检联合交付）。
2. **V1 过、V3 负**：仪器可表达而 Laya≈yoked——**L1 证伪从水平（H1/H2）推广到垂直维度**，当前 observable 状态编码下无空间语义增益的结论在两个维度独立成立。
3. V2-①（z_cv>10× 解钉前）达成（0.14/0.0000 → ∞）；V2-③ 边缘追踪与 V2-④ 瞬态形状留 W6 描述分析（S4v 高低柱数据在库）；**V2-②（Straw 光流设定点）deferred**——地板纹理 schema（TASK-0026 已 done，本次战役窗口未及纳入 V3 后补测）。
4. 探针方法论沉淀：垂直探针与意图光增益的耦合（P_rule z_std=0.0 假象）已由结构性判据根除并记入检测台。

## 消耗与复现

- 封存 v[0:20]（V3）、v[20:30]（s4rule）、[30:32] 机动未动；有效计算 ~3.9h（8h 窗内）。
- 数据：m5/runs_confirm_v/（150 段+manifests+v3-analysis.json）。
- 复现：`python m5/campaign/run_campaign_v.py stage explore|confirm|s4rule`；聚合 `python m5/campaign/v3_aggregate.py`。
