# HANDOFF — FlyLaya @ ~/aiworld/flylaya（M5 收口 + M6 进行中）

> 交接时间：2026-09-26 · 交接人：coordinator（instance coordinator-01m3ccf…sryh）
> 给新会话：读完即可接手。状态唯一入口 = `.pi/swarm/blackboard/project.md`（coordinator 维护）；本文件是快照。
> 上一版 HANDOFF（M4 战役期）已被本版取代；历史在 docs/。

## 0. 快速自检

```bash
cd ~/aiworld/flylaya
cat .pi/swarm/blackboard/project.md                    # 战役状态表
ls .pi/swarm/tasks/                                    # 池任务状态
curl -s localhost:8964/ -o /dev/null -w "%{http_code}\n"   # 地形观察器
curl -s localhost:8962/m5/viewer/blind.html -o /dev/null -w "%{http_code}\n"  # 盲评包
```

## 1. 项目两线

**M5 受控假设检验线（已完成判定，收尾中）**
- 问题：Laya 意图能否经连接组产生目标行为（L0–L3 主张阶梯，H1–H4 预注册）
- 里程碑：G0–G4 全过；诊断/语义/确认三批（28+60+200 段零失败）
- **主结论**：H1 确认性证伪（P_laya≈P_yoked 配对差≈0，而 P_rule 证明仪器可表达 cos 0.55–0.63）→ 断点=决策层 observable 状态语义，非接口；H2 接触口径不可判；H3 条件跳过；S4 holdout P_laya≈P_yoked；H4 内核支持 10/20ms 高频
- 过程硬发现（均已修复）：skeleton 光→DN 符号反转、连接组光方位读出丢失、左前 looming 符号反转、z 轴钉死（DNa02 差分结构性死亡）——全部带 probe 级根因存档于黑板 findings/backend/
- 报告：`m5/report/campaign-summary.md`、diag/sem 两报告、`docs/findings/flylaya-final-report.md`（含两份勘误）

**M6 开放世界探索线（进行中，用户 2026-09-26 指令）**
- 需求原话：像在我的世界中探索一样，固定 3D 地图（山/树/水/阳光），果蝇随意探索
- **0028 地形观察器（frontend）done**：`http://127.0.0.1:8964/`（terrain.v1 合同 + 山/树/水/日渲染 + 小地图 + 回放 + LIVE 501 降级待 W1）
- **0027 自然世界引擎（backend）in_progress**：flylaya.scene.v2 固定地形 + 地形碰撞 + 体素感官渲染 + 探索跑批——**当前唯一关键路径**
- 落地后待立项：探索批数据战役 + M5/M6 对照分析

## 2. 池状态（保存时）

| 任务 | 状态 | 说明 |
|---|---|---|
| 0027 自然世界引擎 | in_progress (backend) | M6 关键路径 |
| 0015 M5-W6 终报 | in_progress (researcher) | **等盲评包 ≥3 人** |
| 0002 m4 新 A 重盲评 | in_progress (frontend) | 等评分者，次要 |
| 0028 地形观察器 | done | 见上 |
| 0004/0005 | open（死条目）| 已被 campaign.superseded，勿领 |
| 其余 22 项 | done | 全链交付记录在任务文件 Completion 段 |

## 3. 人工项（阻塞在用户，不在 agent）

1. **M5 盲评（优先）**：`http://127.0.0.1:8962/m5/viewer/blind.html?rater=<名字>`——≥3 人，双问题协议，导出 JSON 勿看直接交；收齐后 0015 出 L0–L3 终报
2. m4 重盲评（可选）：`http://127.0.0.1:8962/m4/rating3d/index_newA.html?rater=<名字>`

## 4. 服务

| 端口 | 服务 | 管理 |
|---|---|---|
| :8000 | laya-serve（MLX 决策） | OS 进程（旧会话起，/health 验活） |
| :8962 | m5view（仓库根静态） | OS daemon |
| :8964 | m5bench（观察器 bench_serve） | OS daemon，`m5/viewer/bench_serve.py --port 8964` |
| :8960 | m4 静态 | **本会话 hub 进程 mcview，会话结束可能死**；死了重跑：`python3 -m http.server 8960 --directory ~/aiworld/flylaya/m4` |

## 5. 协调机制（新会话 coordinator 接手须知）

- swarm：`.pi/swarm/`；角色实例 coordinator/frontend/backend/researcher/tester；任务池 `tasks/`、黑板 `blackboard/`（project.md = 状态唯一入口；findings/<role>/ 是各角色工作笔记）
- **frontmatter dependsOn 大多为空——真实 DAG 看 project.md / m5-dispatch-plan.md**（正文信任惯例）
- 已验证的流程纪律：done 必验产物（Completion 段+文件落地）、supersede 用事件不用口头、封存种子域隔离（水平 [0:32]、垂直 v 域 200000–299999）、负结果完整交付
- 关键合同：`flylaya.scene.v1/v1.1/v2(进行中)`、`m5/research/m5-{8h-campaign,vertical-8h}-plan.md`
- git 归档仓：`myylaya/`（github.com/leewbl/myylaya）——终报+报告+盲评数据已推至 9b51d79；**M5 战役报告与 m5 树尚未归档**（新会话收口 0015 后一并提交）

## 6. 新会话建议动作序

1. 读 project.md + 本文件
2. 若 backend 的 0027 完成 → 验收（体素感官合理性/不穿地/护栏）→ 立项探索批战役
3. 若盲评 JSON 到齐 → consistency.py 复算 → 推 0015 收口
4. M5 全收口后：归档 m5 树 + 报告进 myylaya，写 M5 终版 handoff
