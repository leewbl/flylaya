# TASK-0010 · M5-W2 感官/神经接口交付(G2)

backend · 2026-09-25 · 设计规范: docs/findings/flylaya-next-experiment-system-design.md §3

## 交付物(改 flylaya/intent.py + brains.py + world.py 一行缓存)

1. **双状态源可切换**(`FLYLAYA_STATE_SOURCE=oracle|observable` 或构造参数)
   - `oracle_state` = 原 `state_text`(真值: 障碍/太阳/位置)
   - `observable_state` **感官可观测版 v1**(非纯神经版): 只读 render 后视网膜向量(world.last_luminance 缓存, 1 帧延迟)、标注的机体自感(速度/爬升)、DN 读出(DNp20 左右差)、意图历史。字段登记 `OBS_FIELDS`(source+latency_s 逐字段)
   - 防泄漏为结构性: 测试中把障碍/太阳/位置真值全部污染, observable 文本逐字节不变, oracle 文本改变
2. **三通路独立关断**(`FLYLAYA_COUPLING=full|sensory_only|motor_only`)
   - sensory_only: thrust 钉 1.0、yaw_noise 0、 arousal 不再缩放 thrust —— 无运动捷径
   - motor_only: light/looming/wall 钉 1.0, motor 通路照常
   - full = M2 旧数值逐项不变(单测断言)
   - direct(逃离偏置): **默认关**且 `_arm_escape` 内部硬 no-op(不存在绕过 poll 的武装路径); `FLYLAYA_DIRECT=on` 恢复 iter1 行为
3. **审计与无静默回退**
   - `audit_row(mod, t0, t1)`: source_paths(sensory/motor 布尔)+数值+起止
   - `LayaIntentSource.last_decision`: m5 decisions.jsonl 合同字段(t_s/state_source/state_text_sha256/raw_choice/raw_probabilities/sampled/applied/dwell_guard/arousal_score/latency_ms/timeout/fallback_reason), raw argmax 与采样分列
   - 连续 3 错 failover 必打 WARNING 并记录 fallback_reason
4. **决策组**: P_laya(原类, 增强 raw/sampled 分列)、P_yoked(`load_sequence`/`permute_sequence`(cycle_shift|block_perm, t 网格不动)/`validate_yoked`(占比差 ≤0.02、平均停留相对差 ≤10%, 超差拒绝)/`YokedIntentSource`)、P_rule(`RuleIntentSource(use_truth=)`, 真值版标注)、P_fixed(`FixedGoalSource`)
5. `SkeletonBrain.dn_snapshot()` 与 connectome 合同对齐

## 验收(G2, `m5/test_coupling.py` 34/34 PASS)

- sensory_only 无运动捷径 / motor_only 不改感官 / direct 默认关: 均有单测
- 高频冒烟 `m5/hf_smoke.py 10`: 连接组 10ms 步进 1000 步 wall 6.87s, **rt 1.45x —— 支持 10–20ms 神经推进, 无需降级**(骨架 361x)
- 回归: m5/test_scene.py ALL PASS、m3 自测 OK、server 导入链 OK; 默认 coupling=full 下 modulation 数值与 M2 逐项相等

## 给 W3 (TASK-0011) 的接口

- 每决策帧读 `src.last_decision` 直接落 decisions.jsonl; 调制段用 `intent.audit_row(mod, t_start, t_end)`
- P_yoked 流程: 先跑 P_laya 冻结序列 → `permute_sequence` 生成 yoke → `validate_yoked` 通过才入批
- A 配置复现 iter1 行为需 `FLYLAYA_DIRECT=on`(direct 默认关是 M5 设计决定, 会改变旧 A 的 avoid 逃离)
- 观察: direct 关闭后 S2 类场景的避障完全依赖 sensory/motor 通路 —— 正是 H2/H3 要测的
