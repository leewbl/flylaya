# T0 战役启动执行报告(tester,TASK-0021)

- **Gate-F 正式 PASS 落版**:判据 v2(读法 A/B,researcher 裁决 2026-09-26 预注册)——F1 0.546/0.628、F2 读法A 0.667/1.0(右饱和不劣化)、F3 护卫对 ω 107.54(gate-F-verdict.json, criteria_version v2)。
- **arousal 浮点修复在位**:intent.py:304 float clip(0,2) 已核(裁决附加 1)。
- **RNG 审计注记落版**:runner.py docstring(裁决附加 2,死轴熵源归 neural 流)。
- **预算核实**:backend 的「init 标定 +50s/实例」未在批语境复现——Gate-F 批 20 段含标定实测 23s/段(457s/20);H1 80 段预计 ~31min,计划 §2 预算成立。
- **H1 确认批已开跑**(bg 串行):S1 双镜像×{P_laya(observable τ1.6/ε0.06), P_yoked(cycle_shift 同种子冻结)}×封存 seeds[0:20]×30s×sensory_only;种子域强制+yoked 匹配门+manifest 内容校验+代码哨兵全程值守。完成后即跑 pair-batch 出 H1 效应量+区间,随后 h2。