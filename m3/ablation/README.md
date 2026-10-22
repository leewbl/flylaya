# FlyLaya 消融配置（M3 ③）

四配置共用同一 arena/种子/时长（10 种子 × 5min × 10Hz），只切换两个正交因子：
**brain**（connectome 全图 LIF vs skeleton 速率编码 stub）× **intent_source**（Laya vs 非智能基线）。

| 配置 | brain | intent_source | 回答的问题 |
|---|---|---|---|
| **A_full** | connectome | laya | 完整系统拟真度上限 |
| **B_no_laya** | connectome | fixed_rotation（每 3s 轮换 5 意图，M1 FixedIntentSource 语义） | 去掉 Laya：连接组+固定调制的下限 |
| **C_no_connectome** | skeleton | laya | 去掉连接组：Laya 意图单独贡献 |
| **D_random_intent** | connectome | random（每 300ms 均匀抽意图，同决策节奏） | 意图层是否有信息量（vs 随机） |

对比设计：A−B = Laya 在连接组上的增益；A−C = 连接组的增益；A−D = 意图序列信息量；
B−D = 固定轮换 vs 随机（节奏相同、内容不同）。

## 约定

- `decision_every_n_frames=3`（300ms @10Hz）与意图规范 v1 §4 一致；B 的 `hold_n_frames=30`（3s）
  是刻意的低频对照（切换频率 0.33Hz，落在规范验收区间 0.1–1Hz 内）。
- 随机源（D）与场景同种子流：`seed` 派生 `rng = numpy.random.default_rng(seed ^ 0xD)`，保证可复现且与障碍布局解耦。
- 每配置一份 trajectory jsonl（格式见 trajectory_stats.py 模块头）+ A/C 额外 laya 调用日志（规范 §4）。
- Laya endpoint 指向 laya-mlx-serve（R1 交付）；A/C 需先起服务。

## 使用（M4 批量）

```bash
for cfg in A_full B_no_laya C_no_connectome D_random_intent; do
  for seed in 11 22 33 44 55 66 77 88 99 111; do
    flylaya-run --config m3/ablation/$cfg.json --seed $seed --out m4/runs/${cfg}_$seed.jsonl
  done
done
```
（`flylaya-run` 为 M2/M4 批量入口；配置字段名即其接口契约。）
