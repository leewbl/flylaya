# TASK-0013 阶段 1 完成:接口诊断批

- 执行:tester(claim CLM-01M3CSXZ3WDX3ABTZVRBTPYCPQ)· 2026-09-25
- 28/28 零失败(7 场景×双脑×双耦合×30s×seed1,m5/runs_diag/,无 Laya 调用)。报告:m5/report/diag-phase1-report.md(传递函数表 diag-phase1.md/json)。

## 硬发现(按设计 §10 分支)

1. **skeleton 反号趋光**:光-DN 信号镜像对称(左光 −0.28/右光 +0.30)但两镜像航向都转离光源(mean_cos +0.5→−0.84)。M4 的 skeleton sun_R=0.527 是集中度幻觉(反号也高 R)——设计 §1 预警的陷阱被有符号指标证实。→ 修 skeleton 亮度→DN 符号映射,加镜像符号单元测试。
2. **connectome 无光方向响应**:ΔDN 两镜像同号(+0.57/+0.48),非方向编码;与 M4 sun_R≈0.04 一致,瓶颈在视网膜→连接组方位链路。
3. **S2 贴柱但 0 有效接近**:connectome 曾距柱 0.122m(79 帧<0.25m)但前方+闭合条件未满足;**H2 分母空是曝光/几何问题,不是接口断**——阶段 2 前须多种子+几何核验,检测器参数调整须版本化。
4. **motor_only 转向计数 2–3×**(yaw_noise 抖动跨阈):H 统计必须分层 coupling。
5. S3 墙通路 connectome 有信号(ΔDN +1.55,朝中心 +0.35),skeleton 无。

## 状态

阶段 2(语义确认:P_laya/P_yoked/P_rule×S1/S2 镜像,H1/H2 初判)**等 W2(TASK-0010)observable_state**——runner 适配器单点替换。给 backend 的两条可立即开工项:skeleton DN 符号修复、S2 场景多种子接近覆盖率核验。