# TASK-0021 战役执行准备就绪(tester,待 0019/0020 后认领)

- 认领被运行时依赖闸正确拦截(0019 in_progress)。执行资产已备齐并验证:

## 已备资产(m5/campaign/)

1. **gate_f_check.py**(Gate-F 复验台):20 段(4 场景×5 探索种子,~7min),F1 光读出(双镜 cos≥+0.3 且差≤0.2)/F2 looming(左>0.5 且差<0.2)/F3 护栏(ω p50<150,arou_r>0.3);出 gate-F-verdict.json,FAIL 即锁封存种子。
2. **run_campaign.py**(战役驱动):h1/h2/h3/s4 四阶段,种子域强制(h1h2=seeds[0:20]、s4=seeds[20:30]、探索=1–9999,越域拒跑)、yoked 失配重生成≤2 次后停批不放宽、每段 manifest 内容校验、gate-F 判定前置检查。

## 阴性对照(检测台有效性验证)

当前仪器(0019 部分落地+0020 未动)上 gate_f_check --reuse 判 **FAIL**:F1 左 0.225/右 0.354(注:此批在 0019 批中落地时跨代码态,数值仅供台验,正式 Gate-F 须在两修复 done 后整批重跑);F2 左 0.0/右 1.0(0020 未修,精确检出);F3 ω p50 133<150 过。封存种子锁定语义验证生效。

## 给 researcher 的两个对齐点

1. 封存文件实测 sha256 **c9e39da9…**(m5/research/confirmation_seeds.json,32 种子,首 10600/11103/…),与计划文中「5ad4a437…caa5」不符——冻结仪式前请对齐锚哈希(建议以实测文件哈希入 freeze-list)。
2. 复验批 S2 cos 为 None 是均匀光语义(检测台已修);F2 判据用 S2 转离率,与光无关。

Gate-F 正式复跑口径:0019+0020 皆 done 后 `gate_f_check.py`(不带 --reuse)整批重出数,单一代码态。