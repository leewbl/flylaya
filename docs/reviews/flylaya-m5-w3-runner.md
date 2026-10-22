# FlyLaya M5-W3：批量/日志 runner 交付（TASK-0011）

- 测试者：tester（instance tester-01m3cd7byme0r7d00qsp50n1ns）· 2026-09-25
- 依据：设计文档 §3.2/§5.1/§6（唯一规范）；W1 合同 = flylaya/scene.py + World.from_scene（TASK-0009 实际产出）
- 交付：`m5/runner.py`（run/yoked/verify/plan CLI + 库）

## 验收对照（TASK-0011 验收行）

| 验收项 | 证据 |
|---|---|
| 同配置同种子复现 | S1L/seed5/P_fixed/sensory_only 两次独立进程 → trajectory sha256 **逐字节一致**（1baabb6d…） |
| 16GB 串行安全 | 单 run 单连接组实例；connectome 10s 段 8.5s 墙钟（rt×1.2）；全程串行驱动 |
| 5 场景×1 种子×10s 冒烟 | S0/S1L/S1R/S2L/S2R × {sensory_only, motor_only} × P_fixed/skeleton = **10/10 通过**（verify ok） |

## 交付物明细

1. **清单驱动**：plan_matrix(scene×policy×seed) + `run` CLI（--scene/--seed/--policy/--coupling/--brain/--seconds）。
2. **流式写**：逐帧写 trajectory.jsonl（全量 rows 不驻留内存——修复 M4 run_batch 的内存驻留问题）；events 由场景时钟事件（stimulus_on/off）+ 检测器 v1（m5/metrics.py 单一实现）追加。
3. **合同文件四件套 + scene.json**：trajectory（合同 v1 字段：碰撞前 min_gap、三通路 gains_pre/post、直接偏航量、DN 左右、stim 标签、arousal）/decisions（仅 P_laya；原始概率与 applied 分列、state_text sha256、延迟）/events/manifest（§6 全字段：experiment_id、四 RNG 流名、scene sha256、代码哈希、检测器版本、起止、**显式 status**）。
4. **断点续跑按内容**：verify = sha256+行数（meta 行计入）+status+必填字段清单，非文件名存在；篡改（追加一行）实测检出。
5. **三通路耦合（§3.2）**：sensory_only/motor_only/full/direct_off 在增益施加点过滤——sensory 关时 light/looming/wall=1.0（基线亮度），motor 关时 thrust=1.0/yaw_noise=0；direct 仅 full 模式消费 yaw_bias（默认关，机制实验口径）。gains_pre（调制全量）与 gains_post（实际施加+耦合名）分列可审计。
6. **四策略**：P_fixed（常量目标）；P_yoked（重放冻结序列，容差门）；P_rule（几何规则，meta 标注 truth_assisted=true）；P_laya（oracle 适配器，**meta.state_source="oracle"**，W2 落地后换 observable——设计 §5.2 语义确认批以此为准）。
7. **P_yoked 生成器**：游程级受限置换（分布与驻留时长**多重集**精确不变）+循环位移；实测修复两缺陷（块合并致驻留膨胀 67%、贪心尾部失效致 12.5%）；真实 P_laya 10s 段 yoked 化 verdict PASS（dwell_rel=0.0）。

## 集成验证

- W3 输出 → W4 消费：`metrics.py run` 对 runner 产物出全六族指标（mean_cos_to_light 0.4373、switch_hz 0.101、hit|light 窗口 n=50、HF 门禁在 10Hz 正确抑制时长/峰值）。
- runner 拷贝 scene.json 入 run 目录（可独立复算指标）；metrics 单测 19/19 保持绿。

## 过程修复（记录）

Scene.random_streams 属性名（streams）、verify 行数含 meta 行的语义、局部导入丢失、Laya 适配器 log_path（decisions 曾空）、stim 标签 light_on 语义（条件命中率的光窗此前恒空）。

## 边界

- P_laya 为 oracle 状态源适配（模块 docstring 与 meta 双处标注）；observable 源是 W2（TASK-0010）交付，落地后在此适配器内替换——TASK-0013 语义确认批在此之前不得启动（设计 §5.2）。
- 高频（10–20ms）神经推进是短程实验专用（设计 §3.3），runner 的 dt 取 scene.neural_dt_s，高频场景文件落地即可跑。
