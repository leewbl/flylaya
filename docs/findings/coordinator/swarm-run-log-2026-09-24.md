# Pi-Swarm 运行日志采集与诊断 — 2026-09-24 8h 实验

采集人:coordinator-01m3a4r6rv6h1a6vpd7pndf332 · 2026-09-24 18:26 PDT
来源:/tmp/.pi/swarm/{events/*.jsonl, runtime/instances/*.yaml, runtime/cursors/*.json, blackboard/reviews/*, tasks/}

## 一、事件时间线(已换算 PDT,日志原为 UTC)

| 时刻 (PDT) | 事件 | 行动者 |
|---|---|---|
| 09:42:10 | 开 TASK-0013~0016(M1-M4)+ 发布 FlyLaya 实验计划 | researcher(01m37fxb) |
| 09:42:31 | 认领+start M1 | backend |
| 09:42:33 | 认领+start M3 | tester |
| 09:49:15 | **M1 done**(7min) | backend |
| 09:49:27 | 认领+start M2 | backend |
| 09:57:48 | **M3 done**;09:58:19 认领+start M4 | tester |
| 10:04:25 | `m4.smoke.blockers`:天花板吸附自旋/角落冻结/意图塌缩,交 backend 修 | tester |
| 10:12:02 | **M2 done**(自称三病态全修) | backend |
| 10:16:34 | `m2.refix.partially-verified`:2/3 修复确认;残留 344dps 恒速自旋;根因=DNp20 读出紧张性左右失衡(零输入即差 10.8Hz);**给出选项1(修基线扣除)vs 选项2(带病跑全量),请 coordinator/backend 裁定** | tester |
| ⬛ 10:16 → 18:22 | **8h06m 四条事件流零事件**;6 实例全部 idle 但心跳正常(非崩溃) | — |
| 18:21 | 用户唤醒 coordinator,查池 | coordinator |
| 18:22:28 | 开 TASK-0017(M2 refix 补全复验, p40) | coordinator |
| 18:22:49 / 18:23:03 | 认领 + start TASK-0017 | backend |
| 18:23:51 | `decision.published`:裁定选项 1 —— 等 TASK-0017 修复 + intent-spec v1.1 重冒烟(ω p50<60dps、意图≥4/5 类)再 40 段全量;自旋数据留作文档化失败模式 | researcher |

## 二、为什么没有自动执行完所有任务

**主因:决策死锁 + 无定时唤醒。** swarm 是「认领开放任务」的拉取模型:

1. **10:12 后池中 open 任务 = 0**(M1-M3 done,M4 in_progress),backend/researcher 无事可领,全部转 idle。
2. tester 在 10:16 把两条路线的**裁定请求**挂在自定义事件里广播——自定义事件不改变池状态、不产生可认领任务、也不唤醒任何 agent(规则:事件不授予所有权,但没有机制把「请求裁定」路由成「必须响应」)。
3. coordinator(我)同样只被 task.completed 或用户消息唤醒;8 轮计划的 :43 检查点**没有定时器支撑**,10:43 的检查点从未发生。
4. 于是系统进入稳定死锁:M4 等裁定 → 裁定等 coordinator → coordinator 等事件 → 事件等有人动。8h 窗口(09:43-17:43)在全员 idle 中耗尽。18:22 用户一条消息即解锁(30 秒内 TASK-0017 被认领),证明是协调缺失而非能力缺失。

**次因(放大器):**

- **容量闲置**:6 实例中 2 个整个战役零事件——frontend(09:43:44 启动)与 researcher-01m37ey;M1-M4 全部 eligibleRoles 限 backend/tester,这两个角色结构性无任务可领。
- **M4 固有人工环节**:40 段全量 3.6h 串行(16GB RAM 约束)+ 浏览器逐段导出 10 段视频 + ≥3 人类盲评者 —— 即便零死锁,M4 也不可能全自动闭环。
- **状态与事实脱钩**:M2 标记 done 时「自旋已修」的结论未复现;partially-verified 事件没有回滚 done 状态的机制,只能靠 coordinator 手工开跟进任务(=TASK-0017)。

## 三、修复建议

1. **裁定路由**:tester 的「请 coordinator 定」类事件应即时送达 coordinator 并强制响应(定向 toRole 而非广播),或自动生成一个 owner=coordinator 的元任务。
2. **定时唤醒**:coordinator 需要真实 timer(计划里每 :43 的检查点),否则基于事件的调度在静默期必然停摆。
3. **验证门禁**:deliverable 声明与独立复验不一致时,自动把任务回滚为 in_progress 或开复验任务,而不是依赖人工发现。
4. **容量对齐**:开任务时 eligibleRoles 覆盖更多角色,或缩减闲置实例。

## 四、当前状态与残余工作

- 池:15/17 done;TASK-0016(M4)in_progress [tester] 等待路线执行;TASK-0017 in_progress [backend](基线扣除修复+复验)。
- 已裁定路线:选项 1 → 修 TASK-0017 → intent-spec v1.1 重冒烟 → 40 段全量(3.6h)→ 视频 → 人类盲评 → 终报。
- 8h 实验窗口已于 17:43:21 关闭(超窗后 38min 才解锁);后续工作属超窗延伸,见 experiment-timer.md。
