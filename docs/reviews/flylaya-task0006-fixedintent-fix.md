# FlyLaya TASK-0006：FixedIntentSource 词表/日志/回退修复复审

- 测试者：tester（instance tester-01m3cd7byme0r7d00qsp50n1ns）· 2026-09-25
- 变更：`flylaya/brains.py`（FixedIntentSource）、`flylaya/server.py`、`flylaya/intent.py`

## 事实核对（与任务描述的出入）

- 任务前提「仍是 M1 旧 4 类词表」在当前工作树**已过时**：修复前实测 `FLYAYA_INTENT=fixed` 起
  服务，HUD 35s 内五类意图（phototaxis/avoid_obstacle/explore/center_in_arena/rest_hover）正常轮转。
  真正的问题是该词表是独立字面量、与 `intent.INTENTS` 双源——历史上已漂移过一次。
- 修复前实际存在的缺陷：
  1. `FLYAYA_INTENT_LOG` 在 fixed 模式被完全忽略——intent_log 文件不创建（验收口径直接失败）；
  2. `FLYAYA_INTENT` 为未知值时静默回退 fixed 轮转；
  3. `modulation_for` 对未知意图静默回退 explore 增益。

## 修复内容

1. `brains.py` `FixedIntentSource`：词表单一源自 `intent.INTENTS`（不可再漂移）；新增
   `log_path`，轮转帧写 jsonl `{t, source:"fixed", frame, intent, applied}`（10Hz×30 帧一转 ≈ 1 行/3s）。
2. `server.py`：`FLYAYA_INTENT` 非 `laya`/`fixed` 时 `logging.warning` 后回退 fixed；
   `FixedIntentSource` 接入 `FLYAYA_INTENT_LOG`。
3. `intent.py` `modulation_for`：未知意图回退 explore 增益前打 warning（每个未知值仅一次）；
   增益数值与回退行为不变。

## 验收证据

| 验收点 | 结果 |
|---|---|
| fixed 服务 intent_log 出现显式词表意图 | 35s 12 行、5 类齐全、`source:"fixed"`（修复前 0 行/文件不存在） |
| 回退打 warning | `bogus_mode` → `WARNING ... falling back to fixed rotation`；未知意图 → `WARNING ... -> explore gains`（各一次） |
| 无其他行为变化 | HUD 轮转直方图修复前后逐项一致（79/90/60/60/60）；`modulation_for` 已知意图数值不变；30s 冒烟（种子 11）**B/D 两配置 jsonl 与修复前逐字节一致**（cmp IDENTICAL），表行全同 |

A/C 冒烟行有差异：依赖 laya-serve 实时采样与墙钟 state_text，本就非确定，非回归信号；B/D 的
逐字节一致覆盖了共享导入路径（`flylaya.intent`/`flylaya.brains`）零行为变化的严格判定。

## 复现

```bash
PY=~/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python; cd ~/aiworld/flylaya
FLYLAYA_PORT=8100 FLYLAYA_INTENT=fixed FLYLAYA_INTENT_LOG=/tmp/i.jsonl $PY run.py &
# ws 客户端连 ws://127.0.0.1:8100/ws 驱动 35s → 检查 /tmp/i.jsonl
FLYAYA_PORT=8101 FLYLAYA_INTENT=bogus_mode $PY run.py &   # 看 stderr WARNING
```

## 结论

验收通过。与 TASK-0001 重批并发进行；FixedIntentSource 不在任何批量配置路径（A=laya、
B=fixed_rotation[run_batch 自有类]、C=laya、D=random[run_batch 自有类]），重批轨迹不受影响。
