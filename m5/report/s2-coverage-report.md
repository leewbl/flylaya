# TASK-0018：S2 有效接近覆盖率核验报告

- 执行：tester（claim CLM-01M3CTBJ5RG9GWPZDTMQVP87TF）· 2026-09-25
- 批：S2 双镜像 × {sensory_only, motor_only} × connectome × P_fixed(avoid_obstacle) × 30s × 种子 1–7 = 28/28
  （m5/runs_s2cov/，manifest 齐；初跑 3 段因 runner 重写碰撞失败已重跑）

## 根因修正（推翻阶段 1 的「曝光不足」归因）

阶段 1 报告把 S2 零接近归因于曝光/几何——**错误**。帧级事实：每格有 84–161 个
「≤0.25m ∧ 前方±45° ∧ 闭合≥0.02m/s」帧。真因是 runner 给检测器喂了场景**静态**
`enabled`（S2 柱初始 false），运行时 t=5 的 stimulus_on 使能状态（world.obstacle_enabled）
没有传入。已修复（runner 按运行时使能状态构造检测器输入），两批 56 段的 events.jsonl
已按轨迹重生、manifest 哈希更新并注记 `events_regenerated`。轨迹数据未动。

## 覆盖率结果（修复后）

| cell | 总接近 | 每种子 | 有事件种子 | contacts | 正确转离 | 反应延迟 p50 |
|---|---|---|---|---|---|---|
| S2_left/sensory_only | 35 | 5,5,5,5,5,5,5 | 7/7 | 0 | **0.000** | 0.5s |
| S2_left/motor_only | 26 | 1,1,8,1,7,1,7 | 7/7 | 0 | 0.038 | 0.1s |
| S2_right/sensory_only | 21 | 3,3,3,3,3,3,3 | 7/7 | 0 | **1.000** | 0.2s |
| S2_right/motor_only | 27 | 4,3,7,8,1,3,1 | 7/7 | 0 | 1.000 | 0.1s |

- 合计 109 个有效接近；sensory_only 每种子确定性 3–5 个（同种子同场景同策略复现一致），
  motor_only 因 yaw_noise 1–8 个。
- contacts=0（30s 内无碰撞——起点距柱 20–40cm 与速度 0.12m/s 下的通过几何）。

## 阶段 2 最低曝露方案

- **探索批（现行配置即可）**：30s × 5 种子 × 双镜像 ≈ 每臂每镜像 15–25 个接近事件，
  足够 H2 的效应量初判（风险比区间会宽，如实报告）。
- **确认批**：30s × ≥20 封存种子（W4 seal-seeds 机制）× 双镜像 ≈ 60–100 事件/臂/镜像。
- 无需改场景几何或检测器阈值（v1 保持）；若后续要提事件密度，改起点-柱距离属场景版本变更。

## 新发现（转 backend）

- **P_fixed(avoid) 下正确转离率镜像不对称**：左柱 0.000 vs 右柱 1.000（sensory_only，
  7 种子一致）。左前方 looming 时连接组转向柱侧而非离柱侧——与 TASK-0017（skeleton
  光符号反转）同类但发生在连接组 looming→yaw 映射上。这会直接压 H2（避障风险降低
  依赖正确转离），建议并入符号映射审计。
