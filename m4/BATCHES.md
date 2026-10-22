# FlyLaya M4 批次索引（TASK-0008 / M5-G0 冻结清单）

每批目录内 `manifest.json` 为准（逐文件 sha256、行数、场景 meta 哈希、代码树/决策服务指纹、完整性判定）。
「批次清单可追溯」= 任何数字引用 → 批次 experiment_id → manifest 哈希。

| experiment_id | 目录 | 参数(TAU/EPS) | 段数×时长 | 批次窗口 (本地) | 状态 | 用途 |
|---|---|---|---|---|---|---|
| `flylaya-m4-v1params-40` | `m4/runs/` | 1.0 / 0.0（全配置 v1） | 40×300s | 2026-09-24 18:33–20:15 | 冻结·历史 | 旧基线；终报口径1/3 原始数据；**98.3% 盲评绑定此批 A** |
| `flylaya-m4-iter1params-40` | `m4/runs_iter1params/` | A: 1.6/0.06；B/C/D: v1 | 40×300s | 2026-09-25 08:49–09:53 | 冻结·现行 | 迭代①参数新基线（TASK-0001）；后续盲评/迭代②数据基础 |
| `flylaya-iter1-confirm-3` | `m4/iter1_confirm/` | 1.6 / 0.06 | 3×300s | 2026-09-25 08:27–08:35 | 冻结·历史 | 迭代①确认批（终报 §7 证据链） |
| `flylaya-iter1-smoke-1` | `m4/iter1_smoke/` | 1.6 / 0.06 | 1×120s | 2026-09-25 08:18 | 冻结·历史 | 迭代①冒烟 |

历史盲评：`m4/rating/`（3 评分者 × 20 对，基于旧 A；见该目录 `PROVENANCE.md`；sha256 锚 = myylaya@5a68024）。

## 追溯规则

1. 引用旧批数字（12.2cm/s、switch 0.0033Hz、98.3%、A−B D=0.394 等）→ `flylaya-m4-v1params-40`；
   其 stats 与 myylaya@5a68024 `reports/findings/flylaya-m4-stats/` 逐字节一致（sha256 已录于 manifest notes）。
2. 引用新批数字（switch 0.545、A−B D=0.187、2/7 文献达标等）→ `flylaya-m4-iter1params-40`；
   canonical 报告 `docs/reviews/flylaya-m4-rerun-iter1params.md`，myylaya 归档见同批 manifest notes。
3. 旧批运行时代码无 VCS 快照（manifest `code_tree_at_freeze` 为冻结时刻树，含事后迭代①+TASK-0006 编辑）；
   旧批行为锚 = 归档 stats 哈希 + 终报。新批树哈希即运行树（TASK-0006 批中编辑的零影响证据在 manifest notes）。
4. 决策服务指纹：serve.py sha256 `844cd6b3…`（三个副本一致）+ 2 个确定性探针响应哈希 + HF 缓存模型目录哈希，
   见各 manifest `decision_service`。
