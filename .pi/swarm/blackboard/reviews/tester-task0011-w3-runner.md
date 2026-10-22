# TASK-0011 完成:M5-W3 批量/日志 runner

- 测试者:tester(claim CLM-01M3CS7DR0VTXTJHNF6X037CJW)· 2026-09-25
- 交付:m5/runner.py(run/yoked/verify/plan CLI+库)。报告:docs/reviews/flylaya-m5-w3-runner.md。

## 验收全过

- 同配置同种子复现:两独立进程 trajectory sha256 逐字节一致。
- 16GB 串行安全:connectome 10s 段 8.5s(rt×1.2),单实例串行。
- 5 场景×1 种子×10s 冒烟 10/10(S0/S1L/S1R/S2L/S2R × sensory_only/motor_only)。

## 要点

- 流式写(修复 M4 rows 驻留);四件套+scene.json;§6 manifest 全字段+显式 status;断点续跑按内容(sha256+行数+字段)非文件名。
- 三通路耦合在增益施加点过滤,gains_pre/post 分列;direct 默认关。
- 四策略:P_fixed/P_yoked(游程级受限置换,分布+驻留多重集精确不变)/P_rule(truth_assisted 标注)/P_laya(**oracle 适配器**,meta.state_source=oracle)。
- P_yoked 生成器实测修两缺陷(块合并驻留膨胀 67%、贪心尾部 12.5%);真实 laya 段 verdict PASS。
- W3→W4 集成:metrics.py 直接消费 runner 产物出六族指标。

## 给 TASK-0013 的门

语义确认批必须等 W2(TASK-0010)的 observable_state;runner 的 P_laya 适配器在 W2 落地后原地替换(单点 seam)。接口诊断批(P_fixed×S0–S3×sensory/motor_only)现在即可跑。