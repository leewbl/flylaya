# M5-W6 研究验收准备件(researcher,TASK-0015)

- 撰写:researcher-01m3cbvc…qfq · 2026-09-25 · 上游(W4/RUN/W5)未完成前只做零悔准备
- 规范:`docs/findings/flylaya-next-experiment-system-design.md` v1.0(冲突以其为准)

## 1. 确认种子封存(已执行,不可撤销)

- 文件:`m5/research/confirmation_seeds.json` — 32 个种子,确定性抽取(`random.Random(20260925).sample(range(10000,100000),32)`),payload SHA-256 `5ad4a4371f4abbd75e9c595abb28d82706c9eb28fb42225fe77ed0c11e54caa5`
- **规则**:探索期(冒烟/试跑/RUN 语义确认批)只能用 1–9999 区间种子;确认批(≥20 个,设计 §7.1)从封存集抽取,抽取规则在冻结清单里写死。任何探索代码/脚本出现 ≥10000 的种子即为污染,该批不得进确认汇总。
- W3(runner)实现者注意:种子域校验应作为 manifest 完整性检查的一项。

## 2. 冻结清单模板(探索期结束时填值锁版)

`m5/research/freeze-list.template.md` 已建。字段:场景 schema 版本与场景清单、state 提示模板版本、Laya 权重哈希、温度/探索旋钮值、接口版本(sensory/motor/direct 关断状态)、指标实现版本、排除规则、确认种子抽取规则、探索批数据哈希。锁定后任何改动=新版本+整批重跑。

## 3. G5 终报骨架

`m5/research/g5-report-skeleton.md` 已建:H1–H4 逐项(证据/效应量/区间/判定/未通过原因)+ L0–L3 分级判定表 + 解释分支对照(设计 §10)+ 批次哈希索引 + 局限章节。负结果栏预置,防事后只写好消息。

## 4. 待上游(手动跟踪,block 工具缺角色绑定)

- TASK-0012(W4 指标合同)→ 终报的指标口径来源
- TASK-0013(RUN 诊断+语义确认)→ 探索期数据 + 冻结清单填值输入
- TASK-0014(W5 盲评 v2)→ S4 开放场景盲评执行
