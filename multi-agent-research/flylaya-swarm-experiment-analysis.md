# FlyLaya 果蝇多智能体实验：能证明 swarm 的什么

- 分析：Chief of Staff（OpenClaw）· 2026-10-21 · 基于本地一手工程档案

## 实验是什么

果蝇行为仿真（连接组运动层 + Laya 意图层），用 pi-swarm 五角色（coordinator/frontend/backend/researcher/tester）+ 任务池 + 黑板协作完成：
- M4：四配置消融（A_full/B_no_laya/C/D，10 种子×300s×10Hz，40 段零失败）+ 3 人盲评
- M5：预注册假设检验（H1–H4、yoked 锁控、holdout、G0–G4 门禁，28+60+200 段零失败）
- 工程：pi-swarm 264 测试用例验收、真实 4 子进程并发认领竞争验证

## 关键：它没有"swarm vs 单Agent"对照臂

A/B/C/D 是模型配置消融，不是智能体数量消融。时间缩短无数据、深度提升无对照、token 成本未记账（事后重建估算约 7,100 万 token，input:output≈100:1，85% 集中在 5 个角色长会话）。

## 证明了的四件事

1. **执行底座可靠性**：288 段批量零失败；原子认领恰一胜者；2000 任务创建 13.5s
2. **流程深度**：预注册+yoked+holdout+盲评 3 人 Gwet AC1=0.966+p=1.06e-16，带勘误记录；4 个 P0 级 bug 全部 probe 级根因存档——审查/查漏是强证据场景
3. **诚实负结果交付**：H1 确认性证伪（P_laya≈P_yoked 且 P_rule 证明仪器可表达 cos 0.55–0.63）——区分"组件无效"与"测不到"
4. **swarm 自身成本**：D-5 P0 宿主契约缺陷致 7 个命令 TUI 全不可用；任务卡 dependsOn 空置、真实 DAG 靠人肉维护——协调债真实存在

## 与同仓对照实验的关系

单 Agent（omp 无头）完成同数据窄口径分析 321s、质量达研究级（精确置换检验）；多 Agent 同类任务卡 28–42 分钟但范围更宽。详见 ../m4/solo-vs-swarm-comparison.md。

## 要拿到硬结论的路径

蜂群 A/B 模板：同模型等 token 预算，A=单Agent B=pi-swarm 五角色，三层任务（有界bug/长程模块/审查查漏），指标=通过率/返工/评审时长/token/墙钟，每格≥20任务×3次，返工率按写入者数量分组。
