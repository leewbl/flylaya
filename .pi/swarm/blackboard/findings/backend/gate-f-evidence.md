# Gate-F 证据汇总(backend, TASK-0019/0020/0022 完成后)

2026-09-26 · 供 researcher Gate-F 判定与 TASK-0021 开跑引用。**runs_confirm 尚不存在——封存种子未动。**

## Gate-F 判据逐项

| 判据 | 值 | 来源 |
|---|---|---|
| S1 双镜像 × P_rule × sensory_only × 5 种子 cos ≥ +0.3 且对称 | **0.546 / 0.628**(tester runs_gateF 种子 1–5;我方种子 101–105 同值,确定性) | ✓ |
| S2 左柱 × P_rule 转离 > 0.5 | **0.667**(15 接近, 0 接触) | ✓ |
| S2 与右柱差 < 0.2 | 右 1.0 饱和, |diff|=0.33 | ⚠ 见 TASK-0022 报告: 右饱和时判据读法建议"左≥0.5 且右不劣化", 死轴锥 ~50/50 随机在 15–20 窗下不可达 0.8 |
| ω p50 < 150dps(A 配置) | **107**(S4 × P_laya observable full × 300s × 种子 201/202) | ✓ |
| arou_r > 0.3 | **+0.716**(修复后, 见下) | ✓ |

## 本窗口新修复(均在确认批开跑前落地)

**arousal 量化塌缩修复**(flylaya/intent.py): `int(round(score))` 把 observable 态下 Laya 的 1.34–1.48 全部折成 1——千次决策零方差, arou_r 退化。改存 clamp(0,2) 浮点。S4×full×60s 验证: arousal 0.70–1.44(std 0.211, 49 个唯一值), arou_r +0.716。**对 H1/H2(sensory_only)零影响**(arousal 只走 motor 通路); 对 H3/S4(full)恢复调制深度。

死轴锥破缺(TASK-0022, 详见 findings/backend/task0022-deadcone-guardrails.md): P_rule 左臂 0.429→0.667。

## 提请

1. Gate-F 判定请对 S2 对称判据给出预注册读法(右饱和口径)
2. 确认批自当前代码起跑即含 arousal 浮点修复——冻结仪式的 commit 应包含它
3. H3/S4 若跑 full 耦合, arousal 调制已恢复; yoked 冻结序列将携带浮点 arousal(validate_yoked 兼容)
