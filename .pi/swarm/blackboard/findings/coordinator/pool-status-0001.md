# 池状态与依赖缺陷（2026-09-25 09:05 PDT, coordinator）

## 当前
| 任务 | 状态 | 认领者 | 依赖 |
|---|---|---|---|
| 0001 重批(迭代①参数) | in_progress | tester | — |
| 0002 新 A 重盲评准备 | in_progress | frontend | **缺 dependsOn: [0001]** |
| 0003 saccade 瞬态 | open | —（需 backend） | — |
| 0004 趋光读出 | open | —（需 backend） | — |
| 0005 B−D 可分性 | open | —（需 architect+backend） | — |
| 0006 FixedIntentSource 词表 | open | —（backend/frontend 均可） | — |

## 缺陷 1：TASK-0002 的数据依赖未建模
任务正文首行即"依赖 TASK-0001 完成后的新 A 回放数据"，但 frontmatter `dependsOn: []`。
frontend 已 claim+start，而 0001（A 10 段 ≈ 70–85min）刚起步。
建议（认领者自查）：用 swarm_task_block 把 0002 阻塞在 0001 上，或先做无数据依赖的
准备件（评分者须知更新、AC1/κ 计算脚本），把回放/manifest 生成留到 runs_v2 落地后。
researcher 后续建任务请把数据依赖写进 dependsOn，避免抢跑。

## 缺陷 2：0003/0004/0005 无可认领实例
live 实例只有 coordinator/frontend/researcher/tester；backend 与 architect 角色未上线。
0006 是 frontend 可做的热身小修（当前 frontend 忙）。
→ 需要人工拉起 backend（0003/0004/0006）与 architect（0005 设计页）实例。

## 执行提示（已有）
- 0001：`task0001-execution-notes.md`（B/C/D 复用旧批，省 ~2.7h）
