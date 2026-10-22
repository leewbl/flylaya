# FlyLaya 意图层规范 v1.1（researcher 修订：修意图塌缩）

变更仅 §1 state 编码；问题集/调制表/调用纪律 v1 不变。依据：M2 实测（intent_log.jsonl 313 调用，avoid_obstacle 311/313）+ backend 请求（findings/backend/flylaya-m2-connectome-laya.md §残留3）。

## 根因判断（researcher）

state 恒报 near 障碍（含身后者）→ Laya 零样本不辨 aheadness → avoid 恒赢。修法：方位信息升维为**前置性短语**，而非裸度数。

## §1 state 编码 v1.1 变更

`nearest_obstacle` 字段改为：
```json
"nearest_obstacle": {
  "where": "behind, not in the flight path"  |  "ahead 30 deg left, in the flight path"  |  "abeam right, off the flight path",
  "distance_cm": 12, "band": "near", "closing": true
}
```
规则：
- `where` 必须含三选一前置判定：`in the flight path`（|bearing|<45° 且在前方）/ `off the flight path`（|bearing|≥45° 且在前方）/ `not in the flight path`（后方，bearing 相对航向 |·|>90°）
- 距离档附原文；`closing` 仅在 in-flight-path 时为有效语义（后方障碍 closing 省略）
- `wall` 同样格式化：`wall: "behind, not in the flight path, 8 cm"`
- 障碍 >40cm（far）时 nearest_obstacle 直接写 `"none within 40 cm ahead"`

## 调制表补充（配套，防 avoid 逃离性不足）
- avoid_obstacle 增加瞬时逃离偏置：yaw 命令 += 120°/s × sign(−bearing)，持续 ≤0.5s（仅切换瞬间）——防止 Laya 选了 avoid 但映射层无动作
- rest_hover 时 wall 增益降为 0.5（静止贴墙不应触发回中抖动）

## 验收补充（M4 口径）
- 意图分布：5 类中 ≥4 类出现，且无单类 >80%（原「每类至少出现」放宽——30s 段太短，300s 段仍按原口径）

注：DNp20 基线扣除修复（TASK-0017，backend）与本规范独立并行，互不阻塞。