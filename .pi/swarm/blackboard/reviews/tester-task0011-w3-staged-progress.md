# TASK-0011 W3 runner 分段进度(tester 认领,in_progress)

- 认领:tester(claim CLM-01M3CS7DR0VTXTJHNF6X037CJW)· 2026-09-25
- 状态:合同无关部分已交付并验证;仿真环适配器等 W1(TASK-0009,in_progress)/W2(TASK-0010,open) 合同落地后补齐。
- 注:swarm_task_block/swarm_request_create 报 'No swarm role bound'(已报 issue),改依 task.completed 事件驱动续作。

## 已交付(m5/runner.py)

1. **YokedGenerator**(设计 §5.1 交付 4):游程级受限置换+循环位移;冻结 P_laya 的(intent,arousal)流→打乱与状态对应。实测教训两则已修:块置换会合并同邻块致驻留膨胀 67%→改游程级;贪心修复在尾部失效致 12.5% 漂移→改拒绝采样式受限洗牌。验证:3 意图×10 种子分布与驻留时长多重集精确不变、match verdict 全 PASS、序真被打乱 10/10;两意图等长退化夹具(序列级打乱数学不可能)与单意图边界不炸。判定不过→整批重跑语义由 verdict 文件承载。
2. **write_manifest/verify_run**(§6):全字段(experiment_id/四 RNG 流/设备/起止/状态/场景哈希/代码哈希/检测器版本/来源批次);断点续跑按内容(sha256+行数+状态+缺字段清单),非文件名存在;篡改检测实测通过。
3. **plan_matrix + CLI**(yoked/verify/plan)。

## 待 W1/W2 后补

Runner.run_one 仿真环:场景→World(W1)、耦合可关断意图源(W2)、流式写 trajectory/decisions/events(字段=合同 v1,检测器复用 m5/metrics.py flylaya.m5.events.v1 单一实现)。回归基线:m5/test_metrics.py 19/19 + pair-batch 端到端 H1 判定演示(修复过 _prep 对空 frames 桩的误判)。