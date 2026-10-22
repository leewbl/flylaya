# TASK-0021 备战补遗:代码哈希哨兵(tester)

- 动机:正式 Gate-F 批坐实批中编辑污染(brains.py mtime 21:37:15 落于批窗口 21:30–38,S2 左右臂跨代码态;已记 reviews/tester-gate-F-official-verdict.md 的 F2 污染注)。
- 措施:gate_f_check.py 与 run_campaign.py 均加代码哨兵——六个仿真源(brains/intent/world/scene/runner/metrics)批前快照 sha256、批后校验,变更即 `CODE CHANGED MID-BATCH — verdict invalid` 中止;战役驱动每阶段进出各校验(阶段间编辑=新版本,整阶段重跑,符合设计 §6)。
- 现状:0021 已认领 in_progress;守卫实测报「gate-F FAIL — sealed seeds off-limits」语义正确。等 TASK-0022(死轴锥+ω 护栏)done → 哨兵保护下重跑正式 Gate-F → PASS 后按计划 T0 开跑。