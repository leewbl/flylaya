# TASK-0009 · M5-W1 场景/世界合同交付(G1)

backend · 2026-09-25 · 设计规范: docs/findings/flylaya-next-experiment-system-design.md §4

## 交付物

- `flylaya/scene.py` — flylaya.scene.v1 合同: 严格解析(未知键=单位缺失提示/越界柱/重复 ID/矛盾采样周期/矛盾刺激序列)、`mirror_scene()`、`SceneClock`、`stream_rngs()` 四流、`Scene.display()` 单一 m→cm/az-el 换算
- `flylaya/world.py` — `World.from_scene()`; 障碍 enabled 遮罩(碰撞/遮挡/日挡); uniform/directional 光 + intensity + 事件开关; `advance_clock()/apply_event()`; 场景世界 `scene()` 走 display(); 旧构造器与数值行为不变
- `m5/scenes/*.json` ×8 — S0_neutral / S1_light_left|right / S2_obstacle_left|right / S2_obstacle_rear_negctrl / S3_wall / S4_mixed_holdout(300s)
- `m5/test_scene.py` — 41 项合同自测

## G1 验收(全部通过, `test_scene.py`)

1. **解析器拒绝**: 16 个 reject 用例——单位缺失(radius→后缀提示)、越界柱、重复 ID、decision_dt/duration 非 neural_dt 整数倍、错误 schema、未知键、off-when-off/双重 on、事件超期、未知 target、缺流、超速起点、方位角越界
2. **五场景族几何**: S2 前柱 32cm/25°(规范 20–40cm/20–35°); 后负对照等距 32cm、方位 180°; S1 光方位左 150°/右 210°(航向差 ±60°); S3 镜像轴 y
3. **镜像变换**: 几何+起始姿态+光方位+expect 动作符号同时变换; `mirror(S1_light_left) == S1_light_right` 磁盘文件严格相等(S2 同)
4. **真实感官翻转**: 左右镜像对视网膜向量 max|Δlum|=0.826; 机体坐标系眩光重心侧向分量变号(+0.585/−0.501); 列 stimulus_on 当帧 mean lum 0.366→0.330
5. **确定性**: 同 scene_id+version+seed → 120 帧驱动 rollout 位级相等; 异 seed 分岔; 四流互相独立且按身份复现(与 Laya 采样器零共享——LayaIntentSource 自持 RNG)
6. **观察器一致**: display() 输出与 m4 world_meta / mc_view build.py 消费合同一致(obstacles x/z/r/h cm + sun az/el deg); sun 单位向量↔az/el 互算一致

## 遗留路径零回归(三重证据)

- 旧 vs 新 world.py, 真实 connectome 环路(luminance→DN→state)3000 帧位级一致
- 今日两次独立进程重跑 B_no_laya(300s connectome)字节一致
- 注意: `m4/runs/B_no_laya_11.jsonl`(昨日批次)与今日重跑自 t=54.1s 分岔、前 542 行一致——昨日归档与今日环境之间的核级差异, 新旧代码今日均自洽, 与本改动无关。引用 m4/runs 旧批时留意

## 给 W2/W3 的集成注记

- `m5/metrics.py` 的 detect_events 读场景**静态** `enabled` 标志; S2 柱 t=5 才开。W3 runner 写 run 目录 `scene.json` 时需写事件解析后的最终态, 或依赖 frames 的 `stim` 标签(metrics 已支持)
- 场景随机流 scene/controller/neural 已建未消费(合同占位); motor 流接 step_motor 噪声
- 场景世界 `reset(seed=...)` 拒绝(re-derive 需重建 from_scene), 防止静默换种子

## 验证命令

```
PY=laya-mlx-deploy/.venv/bin/python
$PY m5/test_scene.py            # 41/41 PASS
$PY m3/test_trajectory_stats.py # SELF-TEST OK (在 m3/ 下运行)
```
