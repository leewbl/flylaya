# TASK-0025 垂直战役备战就绪(tester,等 0023)

- 认领被依赖闸拦(0023 in_progress)——正确。资产已备并验证:

## 已备(m5/campaign/)

1. **gate_v0_check.py**(Gate-V0 台):S0v×P_rule×5 探索种子×30s;V0 判据 z_std≥3cm/贴地顶吸付帧<5%(z∉[0.10,0.90])/ω p50<150;输出逐段 replay frame hash(供 0024 回放确定性 QA 交叉核);代码哨兵内置;S0v 缺失时明确报「0023 交付未落地」。
2. **run_campaign_v.py**(战役驱动):explore(S0v/S4v×三策略×探索 4001–4010×120s)/confirm(封存 v[0:20])/s4rule(v[20:30]);垂直封存域 200000–299999 强制、探索域 1–9999;yoked 失配≤2 次重生成后停批;Gate-V0 PASS 前置;阶段代码哨兵;**V1 判定子命令**(explore 的 P_rule 臂出垂直速度统计,V1 不过即 confirm 跳过——计划 §5 仪器优先纪律)。

## 封存文件核对

confirmation_seeds_v.json:32 个,200000–299999 域全合规(首 202072/204735/206078),文件 sha256 47716cf7…(计划文写 5057007a…,建议 researcher 冻结仪式前对齐锚,同 M5 先例)。

## 流程

0023 done → gate_v0_check 整批(哨兵值守)→ researcher Gate-V0 判定+冻结仪式 V → explore 批+v1 判定 → V1 过则 confirm+s4rule,V1 不过则 confirm 跳过(V2 描述臂照跑)。