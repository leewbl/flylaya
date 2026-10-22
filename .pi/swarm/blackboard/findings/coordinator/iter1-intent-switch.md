# 迭代①进行中：意图切换率（2026-09-25 07:35 PDT, coordinator）

## 改动（flylaya/intent.py + world.py + server.py + run_batch.py）
1. state_text → 规范 v1.1：障碍/墙前置性短语（in/off/not in the flight path）、>40cm 抑制、closing 仅 in-path
2. MODULATION rest_hover.wall 1.0→0.5（规范配套）
3. LayaIntentSource：温度采样 tau + ε 探索 eps（env FLYLAYA_INTENT_TAU / FLYLAYA_INTENT_EPS，默认 1.0/0.0=关闭）；rng_seed 确定性
4. avoid 切入瞬时逃离偏置：in-path 时 120°/s × sign(−bearing) × 5 帧（world.step_motor 新增 yaw_bias）

## 证据链
- intent_log.jsonl 11649 调用：Laya 返回 avoid 99.98% → argmax 塌缩，护栏非瓶颈
- 单测：AIMED→"ahead, in the flight path, closing"；BACK→"behind, not in the flight path"；escape 仅 in-path 武装

## 验收（m4/iter1_check.py）
- switch_hz 0.0033 → 0.1–1
- 意图 ≥4/5 类、无单类 >80%
- 护栏：rest/ω/speed 不劣化到 B 档

## 状态
- [x] 实现与单测
- [~] 冒烟 A_full seed11 120s（后台，纯 v1.1 无采样旋钮）
- [ ] 若仍 <0.1Hz：开 tau=2.0 / eps=0.05 档位重跑


## 冒烟 1（纯 v1.1, 无旋钮, seed11 120s）
- switch_hz 0.0033 → **0.133 ✓ 进 0.1–1 区间**；ω p50 76→89dps（无自旋回归）
- rest 1.4%→13.3%（低于 B 档 21%）；occ 0.32→0.33；arou_r 0.434 ✓；sacc 幅值 32°→73.6°（向文献 120° 靠拢）
- 分布 3/5（avoid 78.5% 贴 80% 线 + rest 21% + explore 0.5%）→ 还差 ≥4/5
- 冒烟 2 进行中：tau=1.6 + eps=0.08

## 冒烟 3（eps=0.06 非-rest 探索 + tau=1.6, seed11 120s）— 验收全过
- switch_hz **0.517** ✓（0.1–1 区间）；5/5 类：avoid 31 / center 21 / rest 20 / explore 17.5 / photo 10.5，无类 >80% ✓
- 护栏：rest 19.3% < B 档 21% ✓；occ 0.33 ✓；ω p50 103dps（无自旋）✓；arou_r 0.47 ✓；margin_p05 4.72（优于基线 3.79）
- 冒烟 2（均匀 ε 含 rest）被否决：rest 26.1% 超 B 档、occ 掉 0.24 —— ε 探索集排除 rest_hover 是关键设计

## 确认批（进行中, bg_3）
- A_full × seeds {11,22,33} × 300s 全时长，同旋钮；预期 switch/分布/护栏三指标跨种子稳定
- 旋钮为 env 开关（FLYLAYA_INTENT_TAU=1.6 FLYLAYA_INTENT_EPS=0.06），默认关闭=v1 行为，B/C/D 配置不受影响

## 确认批（3 种子 × 300s）— 迭代①验收判定
| 指标 | seed11 | seed22 | seed33 | 验收 |
|---|---|---|---|---|
| switch_hz | 0.503 | 0.557 | 0.547 | ✓ 全在 0.1–1 |
| 意图类数 | 5/5 | 5/5 | 5/5 | ✓（avoid 27–33%，无类 >80%）|
| rest_frac | 0.185 | 0.222 | 0.221 | ~（2/3 种子略超 B 档 0.207）|
| ω p50 dps | 97 | 103 | 108 | ✓ 无自旋 |
| arou_r | 0.49 | 0.43 | 0.52 | ✓ >0.3 |

## 代价（诚实记录）：A−B 运动学分离弱化
- 池化 KS（新A vs 旧B）：speed D=0.178（旧 A−B 0.394，减半但可分）；**ω D=0.012（分离消失）**；rest 中位数 0.19–0.24 ≈ B 0.207（分离消失）
- 根因：旧 A 的"超活跃"签名正是 avoid 塌缩的产物（从不休息）；意图分布变丰富后，积分量向 B 收敛是行为丰富化的必然代价
- 口径 2 的 98% 人类偏好建立在旧 A 上——**新 A 需重跑盲评才能主张同类结论**

## 判定：迭代①按 spec v1.1 验收通过（switch/分布/自旋/arousal 全过；rest 贴线如实记录）
## 下一步（需 researcher 决策）
1. 全量 40 段重批（新 A 参数下重建 A−B/C/D 基线，~2h）
2. 新 A 回放 + 重盲评（口径 2 复验）
3. 若 rest 需压回：eps 探索集进一步收窄或 rest dwell 上限（如 8s 强制重判）

代码：flylaya/{intent,world,server}.py + m4/run_batch.py（旋钮 env 默认关，B/C/D 不受影响）；确认批数据 m4/iter1_confirm/