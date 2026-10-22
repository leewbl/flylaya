# 池状态 2 + 完成验收（2026-09-25 09:30 PDT, coordinator）

## 完成验收（产物核实过）
- **0001 重批** ✓ `m4/runs_iter1params/`（40 jsonl + stats，40/40 零失败，2 路并发 1h8m）
  - 新 A 六护栏全过：ω 99dps / switch 0.545 / 5/5 类 / 最大类 33.3% / arou_r 0.468 / rest 0.15
  - 口径 3 如实：A−B 分离塌缩（speed D 0.394→0.187、ω 0.036、sacc_amp p=0.46 失效）；B−D 仍不可分；C 主导不变
  - 报告：docs/reviews/flylaya-m4-rerun-iter1params.md
- **0007 文献复核** ✓ 关键修订：**saccade 率基线下界 0.2Hz 无文献支撑**，WT 均值 1.8–2.1Hz，
  区间改 [1.0, 3.0]。speed/直度维持 INFERENCE 属有据决定（仅上界锚）。注意 saccade 判定将全面转 miss（模拟 0.057Hz 距 WT ~30×）
- **0006 词表小修** ✓ brains.py FixedIntentSource 改为 single-source intent.INTENTS（防再漂移）

## 需要 researcher 动作
- **TASK-0003 验收标准过期**：正文写"率进 0.2–2Hz"，0007 修订后应为 **1–3Hz**（且模拟现状 0.057Hz，差距 ~30×，
  瞬态通道改造量级比原任务假设的大）。建议修订任务正文或建修订 note。
- 流程记录：0006 由 tester 认领（eligibleRoles 仅 backend/frontend）——Boundary Gate 放行了，产物合格，
  后续建任务时 eligibleRoles 与实际执行面建议对齐。

## 池现状
| 任务 | 状态 | 备注 |
|---|---|---|
| 0002 新 A 重盲评 | in_progress (frontend) | 数据已就绪（runs_iter1params），可推进 |
| 0003 saccade 瞬态 | open | **等 backend + 验收标准待修订** |
| 0004 趋光读出 | open | 等 backend |
| 0005 B−D 可分性 | open | 等 architect+backend |
