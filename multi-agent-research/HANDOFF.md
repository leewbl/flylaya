# HANDOFF：多智能体研究报告材料包

- 给：报告撰写人 · 整理：Chief of Staff（OpenClaw）· 2026-10-27
- 目的：一份多智能体研究报告的全部证据材料、核验状态与建议结构

## 材料清单（本仓）

| 文件 | 内容 | 状态 |
|---|---|---|
| `multi-agent-research/architecture-1946-agents-gpt-rosalind.md` | 1,946 Agent 全脑图谱事件核验与架构分析 | ✅ 三路信源核验 |
| `multi-agent-research/flylaya-swarm-experiment-analysis.md` | flylaya 果蝇实验对 swarm 的证明/不证明 | ✅ 本地一手档案 |
| `multi-agent-research/citation-verification-synthesis.md` | 多智能体研究 10 条承重引文核验记分卡+落地判据 | ✅ 逐条 fetch 核验 |
| `multi-agent-research/pi-swarm-report.html` | pi-swarm 协调运行时工程报告（264 用例、架构、对抗测试） | ✅ 浏览器可开 |
| `m4/solo_ab_analysis.md` + `.py` | 单 Agent 独立复现分析（精确置换检验，321s） | ✅ 已提交 |
| `m4/solo-vs-swarm-comparison.md` | 单 vs 多对照实验记录（墙钟/质量/口径教训） | ✅ 已提交 |
| `.pi/swarm/tasks/` + `blackboard/` | 28 张任务卡全生命周期时间戳、五角色协作记录 | ✅ 已提交 |
| `docs/findings/flylaya-final-report.md` | 三口径终报（盲评98.3%/统计消融/文献基线） | ✅ 已提交 |

## 核验过的关键数字（可直接引用）

| 数字 | 来源 | 置信度 |
|---|---|---|
| 1,946 agents / 32 min / 770万细胞 | OpenAI 官宣+TechRounder | 高 |
| Anthropic: +90.2%、token 解释 80% 方差、~15× token | multi-agent-research-system | 高（原文核验） |
| 评审覆盖 16%→54% | Anthropic Code Review | 高 |
| 等预算下单Agent≥多Agent（SAS consistently match or outperform MAS） | arXiv 2604.02460 | 高 |
| SWE-Verified 并发 59% vs 顺序 83% | Claude Code 团队 | 高 |
| MAST 14 种失败模式 3 类 | arXiv 2503.13657 | 高 |
| 单一写入者（writes stay single-threaded） | Cognition | 高 |
| flylaya: 288段零失败、盲评 AC1=0.966、H1 确认性证伪 | 本仓档案 | 高 |
| 单Agent 321s vs 多Agent任务卡28-42min | 本仓对照实验 | 中（n=1、范围不对等） |
| flylaya 全程 ~7,100万 token（input 70.7M/output 0.72M，100:1） | 转录重建估算 | 中（上界偏向） |
| Codex P99 71h/天、美团9万员工3万Agent | 见核验记分卡 | 待核（数字级） |

## 建议报告结构（六段）

1. 执行摘要：多Agent赢广度吞吐、单Agent赢深度与 bounded 任务；增益本质是算力（80%方差）
2. 证据地图：三条证据链——厂商案例(1946 agents/Anthropic)、学术对照(等预算研究/MAST)、自有实验(flylaya/单Agent对照)
3. 架构判据：map-reduce+单一写入者+任务包标准化+验收闸门（1946案例=超大规模实证）
4. 口径警示：厂商vs学术口径不可混用；偏好≠正确；解释吞吐≠新证据
5. 组织启示：编制的前提是流程重设计（OpenAI内部28.6%≥5并发 vs 外部67.4%零并发；flylaya协调债）
6. 开放问题：等预算对照缺失、token成本核算、验证缺口（lead未经实验验证）

## 已知缺口（报告里应声明）

- 1946 事件的"文献引用几十倍"倍数未核到原文
- Codex P99 71h、美团 AgentOS 数字待 PDF 级核对
- 自有对照实验 n=1、范围不对等、token 未实时记账
- 1946 事件无等预算单Agent臂（OpenAI 未做，结论只能落在"解释吞吐"）

## 相关仓库

- 本仓：github.com/leewbl/flylaya
- 归档仓：github.com/leewbl/myylaya（终报+盲评数据）
