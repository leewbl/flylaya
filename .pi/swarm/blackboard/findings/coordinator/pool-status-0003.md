# 池状态 3：M5 开发波次验收 + 战役修正（2026-09-25 11:10 PDT, coordinator）

## 本波完成（产物已核：m5/{scenes,runner.py,metrics.py,viewer,report,runs_diag} 在位）
- **0009 W1 场景世界**（backend）done → **G1 过门**
- **0011 W3 批量日志**（tester）done——按设计 §6 合同先行实现（清单驱动/流式/断点续跑），已实际驱动诊断批 28/28
- **0012 W4 指标统计**（tester）done——有符号 mean_cos_to_light 当场抓到 M4 幻觉（见下）
- **0014 W5 观察器 v2**（frontend）done

## 阶段 1 诊断批（0013 tester，28/28 零失败）两大发现
1. **skeleton 光→DN 符号反转**（→TASK-0017，open，backend-only）：
   信号存在且镜像对称（ΔDN −0.28/+0.30）但航向转离光源（Δcos +0.5→−0.84）。
   **M4 终报"skeleton 趋光 sun_R=0.527"是集中度幻觉**——终报已加勘误（见 docs/findings §7-bis）
2. **H2 分母红灯**（→TASK-0018，tester 自建自领 in_progress）：
   S2 全 14 格有效接近=0（贴柱 0.122m 存在但前方+闭合不满足）；阶段 2 前必须解决曝光/几何

## TASK-0016（8h 战役）修正
- H2 段新增前置：**0018 的最低曝露方案落地后才可编排 H2 确认批**
- H1 段不受影响（S1 传递函数已判定）
- 0017 修复完成前，skeleton 只用于 C 系对照展示，不进 H1/H2 主判

## 0017 排期
backend 在 0010（W2 接口，关键路径）上；0017 排 0010 之后接续。无人空闲，无需催。

## 角色负荷
backend 0010｜tester 0013+0018｜frontend 0002（等评分者）+空闲｜researcher 0015
