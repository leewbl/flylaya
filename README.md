# FlyLaya 🪰

果蝇行为仿真的受控研究项目：连接组(connectome)驱动的运动层 + Laya 意图层(本地 MLX 小模型)的两层架构，以及围绕它的多智能体(pi-swarm)协作研究流程。

## 主要结论（三口径）

1. **人类盲评**：A_full(connectome+Laya) 被选率 59/60=98.3%、平均分 4.22 vs B_no_laya 1.55（3 评分者、Gwet AC1=0.966、p=1.06e-16）
2. **统计消融**：A−B 在 speed/ω/占用上 KS 可分；B−D 不可分——连接组主导下意图内容不构成差异源
3. **文献基线**：绝对拟真度未达文献口径（相对拟真已证、绝对拟真未达）——量化天花板与失败模式即产出

M5 预注册假设检验：H1 确认性证伪（P_laya≈P_yoked，且 P_rule 证明仪器可表达）——断点在决策层 observable 状态语义，非接口。

## 结构

- `m3/m4/m5/m6` — 研究里程碑（消融实验/盲评/预注册检验/开放世界探索）
- `flylaya/` — 仿真内核
- `laya-mlx-serve/`、`laya-testbench/`、`laya-chat/` — Laya 模型服务、测试台与对话
- `.pi/swarm/` — pi-swarm 多智能体协作记录（任务池/黑板）
- `docs/` — 最终报告与发现

## 注意

- 运行数据（runs/replays/模型权重）不入库，仓库仅含代码、报告与实验记录
- 详见 `HANDOFF.md` 与 `docs/findings/flylaya-final-report.md`
