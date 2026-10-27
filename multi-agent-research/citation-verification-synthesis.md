# 多智能体并行研究 · 核验记分卡与组织落地合成

- 核验人：Chief of Staff（OpenClaw/javis）｜2026-10-21
- 对象：Grok 交接 HANDOFF（27 格矩阵衍生，多智能体并行主题）
- 方法：逐条 web_fetch 原文，关键词+原句匹配；三轮共 10 项

## 一、核验记分卡

| # | 主张 | 来源 | 结果 |
|---|---|---|---|
| 1 | +90.2%；token 解释 80% 方差；约 15× token | anthropic.com/engineering/multi-agent-research-system | ✅ 三项全中（15× 为乘号写法） |
| 2 | Agent 时长:员工 = 6:1 | anthropic.com/research/employment-at-anthropic | ✅ "six to one" 原句在 |
| 3 | 实质评审 PR 16%→54% | claude.com/blog/code-review | ✅ 两个数字均在 |
| 4 | MAST 14 种失败模式、3 类 | arxiv.org/abs/2503.13657 | ✅ "14 unique modes, clustered into 3 categories" 原句在 |
| 5 | 单一写入者（multi-agent works best when writes stay single-threaded） | cognition.com/blog/multi-agents-working | ✅ "single-threaded" 在 |
| 6 | 等预算下单 Agent ≥ 多 Agent | arxiv.org/abs/2604.02460 | ✅ "match or outperform" + "held constant" 均在 |
| 7 | METR 翻倍期 131 天 | metr.org/blog/2026-1-29-time-horizon-1-1/ | ✅ |
| 8 | Cursor kernel 几何平均 1.38×、63% 优于基线 | cursor.com/blog/multi-agent-kernels | ✅ 两数字均在 |
| 9 | OpenAI Codex P99 约 71 小时/天 | arxiv 2606.26959 | ⚠️ 论文存在且含并发内容，但两次抓取（abs+html）均未见 "71 hours/99th percentile" 原句——疑在 PDF 正文深处。**降级：待 PDF 级核对** |
| 10 | 美团 9 万员工/3 万 Agent/AgentOS/Multica | tech.meituan.com CatPaw 文 | ⚠️ 文章真实（CatPaw/LongCat 均在），但 AgentOS/Multica/员工数字**不在该文中**——应归 QCon 演讲来源，需单独核验 QCon 链接 |

**总评**：10/10 来源真实、无死链、无编造；8/10 完全核实；2 项数字级待核（#9 #10）。交接质量高。

## 二、口径警示（承接交接 §5，补充一条）

- #9 的 71h 与 #2 的 6:1 分属不同口径（个人 P99 叠加时长 vs 全公司总量比），不可同表比较——交接已指出，维持。
- 补充：6:1 的分母是"人数 × 假定 40h/周"的推算值，不是实测工时；引用时建议注明。

## 三、组织落地判据（从证据直接推出）

### 3.1 并发价值分层（按证据强度排）

| 场景 | 结论 | 证据强度 |
|---|---|---|
| 审查/查漏 | 多 Agent 并行找问题+验证排序，被大规模证实（16%→54%） | 强 |
| 广度研究 | 多 Agent 有效（+90.2%、AAR PGR 0.97），但成本约 15× | 强（成本已知） |
| 长程工程 | 可拆+任务文件锁+强测试/oracle 时成立（C 编译器案例） | 中 |
| 有界任务 | 并发持平或更差（59% vs 83%；等预算研究一致） | 强（反方向） |

### 3.2 增益机制

多 Agent 的增益主要是**token/算力换的**（80% 方差），不是"协作智能涌现"。决策视角：多 Agent 是"买更多推理"，不是"买更好推理"——预算表上应与算力开销同栏。

### 3.3 架构铁律

单一写入者：一个 Agent 写，其余审查/建议/管理。写并发是 MAST 三类失败中两类的直接来源。

### 3.4 组织启示

- OpenAI 内部 28.6% 员工峰值 ≥5 并发 vs 外部用户 67.4% 零并发 → **"用起来"本身是组织能力**：Skill 沉淀（内部 96.2% 使用率）+ 委托验收流程。
- 汇报口径：Agent 工时类数据（6:1、71h）只证明**采用深度**，不证明**质量/ROI**，分开呈报。

### 3.5 给蜂群 A/B 模板的补充建议

交接 §7 模板已符合证据口径（等 token 预算、分层任务、≥20 任务×3 次）。加一条：**返工率按"写入者数量"分组统计**，直接检验单一写入者假设在自己任务上的成立边界。

## 四、空白区与可接续工作

1. OpenAI 官方单 vs 多 Agent 质量对照（可跟踪 codex 讨论 #9724）
2. Cursor best-of-n 效果数据
3. Replit、Amp/Sourcegraph、Google Jules/Antigravity、GitHub Copilot 具名数据
4. X 具名实践者数据（改为按具名账号检索：Cognition/Cursor/Anthropic 工程师）
5. Factory 官方文档原文核实；arXiv 2610.10263 同行评审状态

以上 5 条可由本方 researcher 并发补齐（英文定点+具名账号通道是强项）。

## 五、文件关系

- 本文件：核验+合成层
- 上游：Grok 交接 HANDOFF 及其文件索引（../REPORT.md 等，在本机不存在，存于 Grok 侧）
