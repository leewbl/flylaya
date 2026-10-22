# FlyLaya 迁移记录

- 迁移时间:2026-09-25 02:30–02:50 PDT
- 目标:本目录 `~/aiworld/flylaya`(总 ~1.4GB)
- 方式:rsync 全量镜像;代码/配置内项目路径已统一改写(`/tmp/<proj>` → `/Users/leewbl/aiworld/flylaya/<proj>`);docs/ 为事发历史记录,保留原 /tmp 表述

## 迁移清单

| 目录 | 内容 | 大小 |
|---|---|---|
| (根) | flylaya 本体:world/brains/server/intent.py、m3 评估套件、m4 批量/视频/盲评、40-run 数据、intent_log 等 | 65M |
| `myylaya/` | 上游 git 仓(github.com/leewbl/myylaya,含 .git;含 calib/、mlx-serve/ 副本) | 1.0M |
| `laya-mlx-deploy/` | MLX 部署 + **.venv**(批量/统计的解释器,3.12.13 + numpy 2.5.3,迁移后实测可用) | 419M |
| `laya-deploy/` | Laya 模型权重等部署资产 | 914M |
| `laya-calib/` `laya-testbench/` `laya-mlx-serve/` `laya-chat/` | 校准 harness / 测试战役数据与脚本 / serve 工程 / chat | ~8M |

docs/:黑板 flylaya findings/reviews + coordinator 实验记录 + TASK-0013~0018 任务/认领记录。

## 自包含性验证

- `m3/trajectory_stats.py run m4/runs/A_full_11.jsonl` 在新家 exit 0,指标 JSON 正常产出(kinematics/margins/intent/…)。
- venv 从新位置直接可用(非 symlink 到 /tmp)。
- 代码 `HERE` 相对寻址;50 个文件内的 /tmp 项目引用已全部改写(剩余 0;docs/ 除外)。

## 仍在 /tmp 的活体(未切断,盲评期间以 /tmp 为准)

| 项 | 说明 |
|---|---|
| hub 静态服务 `:8940` | 服务 /tmp/flylaya/m4(盲评/回放入口) |
| `laya-serve :8000` | Laya 决策服务(进程的 cwd/权重在 /tmp) |
| 全部 /tmp 原件 | 保留;终报(TASK-0018)收口后可删 |

## 盲评 JSON 收件处

主收件:`~/aiworld/flylaya/m4/rating/`(/tmp 旧路径仍接受;TASK-0018 已注明)。

## 服务重启到新家(收口后建议)

- laya-serve:在 `~/aiworld/flylaya/laya-mlx-deploy` 重启(权重在 laya-deploy)
- 静态页:hub 服务根指向 `~/aiworld/flylaya/m4`
