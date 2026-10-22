# 8 小时实验时间记录

| 项目 | 值 |
|---|---|
| 实验名称 | 8-hour experiment (FlyLaya 迭代战役) |
| 记录人 | coordinator-01m3a4r6rv6h1a6vpd7pndf332 |
| 开始时间 | 2026-09-24 09:43:21 PDT (Thursday) |
| 计划时长 | 8 小时 |
| 预计结束时间 | 2026-09-24 17:43:21 PDT |
| 迭代计划 | findings/coordinator/experiment-plan.md(8 轮 × 60min,55min 工作 + 5min 检查点) |
| **实际结束(swarm 自动部分)** | **2026-09-24 20:40:42 PDT**(TASK-0016 m4.completed,超窗 +2h57m) |
| 事故 | 10:16–18:22 决策死锁 8h06m(根因/修复交接见 findings/coordinator/pi-swarm-deadlock-handoff.md 与 leewbl/pi-swarm#1) |
| 遗留(人类环节) | 盲评(入口 http://127.0.0.1:8940/rating/,≥3 评分者)+ researcher 三口径终报(依赖盲评 JSON) |

## 说明
- 开始时间以用户宣布启动实验、coordinator 执行 `date` 记录的系统时间为准。
- 实际结束时间取最后一个 swarm 任务(TASK-0016)的 `m4.completed` 事件时刻(03:40:42Z)。

## 日志
- 2026-09-24 09:43:21 PDT — 实验启动,计时开始。
- 2026-09-24 09:47 PDT — 用户授权协调者自定轮次;8 轮迭代计划已发布,节奏已广播(event 01M3A51S…)。
- 2026-09-24 10:16–18:22 PDT — 决策死锁,全员 idle(详见 swarm-run-log-2026-09-24.md)。
- 2026-09-24 18:22 PDT — 用户介入解锁;TASK-0017(M2 自旋基线扣除修复)开出并被认领。
- 2026-09-24 20:16 PDT — 40/40 批量完成(1h51m,0 失败;修复验证 ω p50 344→77dps)。
- 2026-09-24 20:40:42 PDT — TASK-0016 done:统计表 + 20 段回放视频 + 盲评页(20 对 manifest)全部交付;**swarm 自动执行部分至此全部完成,17/17 任务 done**。
