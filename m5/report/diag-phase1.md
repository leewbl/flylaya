# M5 接口诊断批 阶段1 传递函数表

P_fixed × S0–S3 × 双脑 × 双耦合 × 30s × seed1（m5/runs_diag/，manifest 齐、无 Laya 调用、不作 Laya 优势统计）。
t_stim=5s（S1 光/S2 柱在 t=5 开启；S0/S3 无事件，pre/post 仅作漂移对照）。cos_target：S1 朝光源、S2 朝离开柱方向、S3/S0 朝场地中心。

| scene | brain | coupling | ΔDN(R−L) | Δcos_target | turns | appr | contact | turn_away | speed_p50 |
|---|---|---|---|---|---|---|---|---|---|
| S0_neutral | skeleton | sensory_only | +0.00 (-0.00→-0.00) | +0.004 (-1.000→-0.996) | 0 | 0 | 0 | - | 0.546 |
| S0_neutral | skeleton | motor_only | +0.23 (-0.23→+0.00) | +0.105 (-0.915→-0.810) | 18 | 0 | 0 | - | 0.422 |
| S0_neutral | connectome | sensory_only | +0.27 (+6.31→+6.57) | +0.200 (-0.209→-0.008) | 22 | 0 | 0 | - | 0.160 |
| S0_neutral | connectome | motor_only | +0.28 (+6.31→+6.59) | +0.196 (-0.235→-0.039) | 69 | 0 | 0 | - | 0.136 |
| S1_light_left | skeleton | sensory_only | -0.28 (+0.00→-0.28) | -1.340 (+0.502→-0.839) | 0 | 0 | 0 | - | 0.320 |
| S1_light_left | skeleton | motor_only | -0.14 (+0.02→-0.12) | -1.068 (+0.418→-0.651) | 1 | 0 | 0 | - | 0.276 |
| S1_light_left | connectome | sensory_only | +0.57 (+5.50→+6.07) | -0.198 (+0.169→-0.028) | 23 | 0 | 0 | - | 0.160 |
| S1_light_left | connectome | motor_only | +0.42 (+5.73→+6.14) | -0.276 (+0.271→-0.005) | 51 | 0 | 0 | - | 0.150 |
| S1_light_right | skeleton | sensory_only | +0.30 (+0.00→+0.30) | -1.343 (+0.498→-0.845) | 0 | 0 | 0 | - | 0.320 |
| S1_light_right | skeleton | motor_only | +0.43 (-0.05→+0.37) | -0.304 (+0.186→-0.118) | 0 | 0 | 0 | - | 0.289 |
| S1_light_right | connectome | sensory_only | +0.48 (+5.50→+5.98) | -0.047 (-0.032→-0.078) | 16 | 0 | 0 | - | 0.160 |
| S1_light_right | connectome | motor_only | +0.10 (+5.93→+6.02) | +0.223 (-0.262→-0.039) | 46 | 0 | 0 | - | 0.150 |
| S2_obstacle_left | skeleton | sensory_only | -0.00 (-0.00→-0.00) | +0.160 (+0.786→+0.946) | 0 | 0 | 0 | - | 0.554 |
| S2_obstacle_left | skeleton | motor_only | +0.34 (-0.20→+0.14) | -0.031 (+0.731→+0.700) | 6 | 0 | 0 | - | 0.363 |
| S2_obstacle_left | connectome | sensory_only | -1.08 (+6.30→+5.23) | +0.075 (-0.030→+0.045) | 19 | 0 | 0 | - | 0.160 |
| S2_obstacle_left | connectome | motor_only | -0.35 (+6.71→+6.36) | -0.117 (+0.094→-0.022) | 67 | 0 | 0 | - | 0.122 |
| S2_obstacle_right | skeleton | sensory_only | -0.00 (-0.00→-0.00) | +0.171 (+0.785→+0.956) | 0 | 0 | 0 | - | 0.553 |
| S2_obstacle_right | skeleton | motor_only | +0.23 (-0.40→-0.17) | +0.056 (+0.705→+0.762) | 8 | 0 | 0 | - | 0.373 |
| S2_obstacle_right | connectome | sensory_only | -0.69 (+6.30→+5.61) | -0.096 (+0.089→-0.007) | 21 | 0 | 0 | - | 0.160 |
| S2_obstacle_right | connectome | motor_only | -0.01 (+6.31→+6.30) | -0.156 (+0.116→-0.040) | 65 | 0 | 0 | - | 0.122 |
| S2_obstacle_rear_negctrl | skeleton | sensory_only | +0.00 (-0.00→-0.00) | -0.004 (+1.000→+0.996) | 0 | 0 | 0 | - | 0.561 |
| S2_obstacle_rear_negctrl | skeleton | motor_only | -0.22 (+0.19→-0.03) | -0.236 (+0.991→+0.755) | 9 | 0 | 0 | - | 0.368 |
| S2_obstacle_rear_negctrl | connectome | sensory_only | -0.62 (+6.31→+5.69) | -0.040 (+0.073→+0.032) | 20 | 0 | 0 | - | 0.160 |
| S2_obstacle_rear_negctrl | connectome | motor_only | +0.35 (+6.31→+6.65) | -0.180 (+0.158→-0.021) | 72 | 0 | 0 | - | 0.122 |
| S3_wall | skeleton | sensory_only | -0.02 (+0.02→+0.00) | +0.038 (-1.000→-0.962) | 0 | 0 | 0 | - | 0.294 |
| S3_wall | skeleton | motor_only | +0.13 (-0.10→+0.03) | +0.146 (-0.990→-0.844) | 0 | 0 | 0 | - | 0.414 |
| S3_wall | connectome | sensory_only | +1.55 (+5.31→+6.87) | +0.352 (-0.346→+0.006) | 23 | 0 | 0 | - | 0.160 |
| S3_wall | connectome | motor_only | +0.72 (+5.73→+6.45) | +0.201 (-0.193→+0.007) | 50 | 0 | 0 | - | 0.136 |
