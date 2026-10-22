# [阻断级] brains.py PHOTO_I 未定义崩溃(tester 复验发现)

- 现场:正式 Gate-F 整批复跑(gate_f_check.py),S1_light_left/P_rule/sensory_only/connectome **种子 1、2 OK,种子 3 崩**:
  `AttributeError: 'ConnectomeBrain' object has no attribute 'PHOTO_I'. Did you mean: 'PHOTO_D'?`(flylaya/brains.py:263,`self._photo_i + self.PHOTO_I * lat * dt`)。
- 类常量只有 `PHOTO_D = 1.2`(100 行)与 `PHOTO_I_MAX = 4.0`(101 行)——**积分增益 PHOTO_I 本体未定义**;触发条件性(同场景种子 1/2 不触发),与 0022 报告的「光通道积分器」路径一致。
- 影响:阻断 Gate-F 与一切含该路径的战役批次;brains.py 文件时间 21:27 与 TASK-0022 认领时间相邻,可能是 0022 在途编辑的半落状态,也可能是 0019/0020 落地即有的潜伏崩溃。
- 请 backend(TASK-0022 owner)优先补 `PHOTO_I` 定义或修引用;修后我立即整批重跑 Gate-F。此前封存种子保持锁定(gate-F-verdict.json 缺失,战役驱动拒绝开跑,语义正确)。