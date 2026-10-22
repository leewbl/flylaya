# M5 接口诊断批 · 阶段 1 报告（TASK-0013，S0–S3 × P_fixed）

- 执行：tester（instance tester-01m3cd7byme0r7d00qsp50n1ns）· 2026-09-25
- 矩阵：7 场景 × {skeleton, connectome} × {sensory_only, motor_only} × 30s × seed1 = **28/28 零失败**
  （m5/runs_diag/，manifest 齐、流式日志、断点续跑语义、无 Laya 调用——本批**不作任何 Laya 优势统计**，设计 §5.2）
- 工具：m5/runner.py（W3）+ m5/metrics.py（W4）；表：m5/report/diag-phase1.md（本文件头部即传递函数表）

## 每场景传递函数结论（pre/post t_stim=5s）

### S1 双镜像（phototaxis 固定意图）——**主发现：skeleton 反号趋光**

| 脑 | 感官通路表现 | 判定 |
|---|---|---|
| skeleton | 光-DN 信号存在且**镜像对称**（左光 ΔDN(R−L)=−0.28、右光 +0.30），但两镜像航向都**转离光源**（mean_cos_to_light +0.50→−0.84/+0.50→−0.85，60° 误差漂到 ~147°）；转向幅度 ~5°/s（0.3Hz×YAW_GAIN 0.3），无 saccade 跨越 | **亮度不对称→DN 符号反了**：亮侧应指令转向亮侧，实际转离。M4 的 skeleton sun_R=0.527「显著趋光」是集中度幻觉——反号朝向同样产生高 R。设计 §1 预警的 sun_R 陷阱被有符号指标当场证实 |
| connectome | ΔDN 两镜像同号（+0.57/+0.48，非方向编码）；Δcos_target −0.20/−0.05，无镜像对称朝向漂移 | 无光方向响应（与 M4 connectome sun_R≈0.04 一致）；瓶颈在视网膜→连接组→DN 链路的方位信息，不在决策层 |

motor_only 参照：转向计数 2–3× 于 sensory_only（yaw_noise 抖动跨阈），速度 p50 受意图 thrust 调制（0.15 vs 0.16）——**运动通路工作正常，感官通路方向性缺失/反号**。

### S2 双镜像 + 后方负对照（avoid_obstacle 固定意图）——**[2026-09-25 修正]**

- 初版报告把「全格 0 有效接近」归因于曝光/几何——**错误**。TASK-0018 根因核验确认为
  runner 检测器输入 bug（场景静态 enabled 而非运行时使能状态）；修复并重生事件层后，
  7 种子 × 30s 每种子 3–5 个有效接近、109 个总计（见 s2-coverage-report.md）。
- 帧级事实（初版已测得但误读）：每格 84–161 个「≤0.25m ∧ 前方 ±45° ∧ 闭合≥0.02m/s」帧，
  connectome 曾距柱 0.015–0.145m。
- 前方 vs 后方负对照的 DN 差（connectome sensory：−1.08/−0.69 vs −0.62）幅度小于漂移，
  **looming 方位选择性未证明**（该结论不变）。

### S3 墙（center_in_arena 固定意图）

- connectome：ΔDN +1.55（全场最大），朝中心 cos −0.346→+0.006（+0.352）——**墙→DN→回中通路有信号**；
  motor_only 亦有 +0.201（thrust 调制贡献）。skeleton 无响应（Δcos≈0）。
- 判定：墙通路 connectome 侧可通，skeleton 侧不通。

### S0 基线（explore）

- connectome 自发转向 22（sensory）/69（motor）次/30s——motor_only 的高频主要来自 yaw_noise 抖动跨 150dps 阈，
  阶段 2 解读转向率时必须分层报告。skeleton/sensory_only 零转向（无噪声源、DN 平坦）。

## 设计 §10 解释分支落位

| 观察 | 分支 | 下一步 |
|---|---|---|
| skeleton 光-DN 镜像对称但航向转离 | 「感官编码→DN 符号断裂」 | 修 skeleton 亮度→DN 符号映射（W2/backend），加镜像单元测试：左光必须右转的符号断言 |
| connectome 无光方向 DN 响应 | 「视网膜→连接组方位信息丢失」 | 趋光读出修复（终报建议 4 方向：connectome 系 sun_R 保真） |
| 贴柱但 0 有效接近 | 「事件定义/曝光不足，非接口断」 | 阶段 2 前多种子+几何核验；检测器参数变更须版本化 |
| motor_only 全场转向 2–3× | 「后神经参数主导转向计数」 | H 统计必须分层 coupling，不得混桶 |

## 交付状态

- [x] 阶段 1 接口诊断批 28/28（manifest + 传递函数表 diag-phase1.md/json）
- [x] 负对照（S2 后方）与双镜像校验
- [ ] 阶段 2 语义确认批：**等 W2（TASK-0010）observable_state 落地**（runner 的 P_laya 适配器单点替换）；H1/H2 初判按设计 §2 阈值
- 复现：`python m5/report/diag_batch_phase1.py --reuse`（重算表）/ 去掉 --reuse 全重跑（~5min）
