# TASK-0017 · skeleton 脑光-DN 符号修复(诊断批硬发现)

backend · 2026-09-25 · 依据: m5/report/diag-phase1-report.md §S1 · 任务: 修复 flylaya/brains.py 亮度→DN 映射符号

## 根因

`SkeletonBrain.step` 的感受野掩码把几何左右标反了。机体系 z 朝上、航向 = +x, 感受器 +y 轴是**左**侧, yaw+(逆时针)是左转; 旧代码 `right = dirs[:,1] > 0.25` 实际采的是**左**侧亮度。于是「亮左 → DNp20_R 升 → yaw+ → 转向……右侧=背离光源」。注释写的是趋光, 数值给的是背光; M4 的 skeleton sun_R 0.527 是反号朝向的集中度幻觉(诊断批 mean_cos_to_light +0.50→−0.84 实锤)。

## 修复

`flylaya/brains.py` SkeletonBrain.step: 掩码按几何定义改正(left = d1>+0.25, right = d1<−0.25), 注释记录机体坐标系约定与本次反转的来龙去脉。其余映射(MDN/DNa02/DNpe017)不变。

## 验收证据

1. **镜像单元(合成视网膜)**: 亮左 → ΔDN(R−L) = **+2.63 Hz**(修复前 −0.28); 亮右 → 负号, 镜像对称。
2. **官方诊断批复跑**(m5/runner.py, S1×skeleton×sensory_only, seed1, 30s, m5/runs_fix17/):
   - S1_light_left: mean_cos_to_light **+0.498 → +0.996**(修复前 → −0.84), 刺激期 ΔDN(R−L) +0.639
   - S1_light_right: **+0.502 → +1.000**(修复前 → −0.85), ΔDN −0.700(镜像正确)
   - **Δcos 双镜像转正** ✓
3. **常驻回归测试**: m5/test_coupling.py 新增 4 项(合成左右亮符号对 + S1 双镜像 sensory_only 闭环向光), 38/38 PASS。
4. **M4 口径对照**(C_no_connectome 3 种子×300s, 与归档同参数 tau=1/eps=0, /tmp/flylaya/regress_c17/):
   - 航向分布: mean_dir 从背日(−154/−147/+172°)翻到向日(+39/+10/−21°), sun_R 0.42–0.72 与旧 0.51–0.68 同带——修复效果在 M4 配置可见
   - 决策形态不变: avoid_obstacle 93–96% 主导(新旧同), rest 60–79% vs 旧 65–67%, speed p90 12–17 vs 旧 15–16 cm/s, ω p50 14–42dps, >300dps 占比 0, saccade 0(新旧同)
   - 注意: switch 0.1–1/arousal r>0.3/≥4 类是 A/iter1 护栏口径; 归档 C 本身同参数下就不满足(switch 0.003–0.007, 2–3 类), 同基对比无劣化

## 运维注记

- laya-serve(:8000)在回归批发现已死, 已按 README 从 laya-mlx-serve/serve.py 重启(hub 进程 `laya-serve`, on-failure), /health 200、choice 通路验证过。第一次 C 回归批(服务死时跑的)作废已重跑。
- 修复对 M4 旧 C 数据的可比性: 航向类指标(mean_dir/sun_R 方向解读)不可与旧 runs 直接混用, 其余指标同基。
