# Gate-F 正式判定(tester 整批复跑,单时代码 21:28 版)

- 批:m5/runs_gateF,4 场景×5 探索种子×P_rule×sensory_only×connectome×30s,PHOTO_I 崩溃修复后。
- **F1 光读出 PASS**:左 0.546/右 0.378(双镜≥0.3,差 0.168≤0.2)——0019 修复稳定。
- **F2 looming FAIL**:左转离 0.0 vs 右 0.8。注:backend 0022 报告称左臂 0.429,本批 0.0——差异可能来自(a)0022 在途编辑于本批窗口内再动 brains.py,(b)我的口径计入死轴锥进入段(0022 残余 A 所述)。无论何因,左臂远未达 >0.5 门。
- **F3 护栏 FAIL**:ω p50 151.78>150(0022 残余 B,边缘超标)。
- **总裁定 FAIL:封存种子保持锁定,确认批不得开跑**——与 TASK-0022 开放范围精确重合(死轴锥+ω 护栏)。0022 done 后我立即重跑本台;若 backend 认为中途编辑干扰,建议其 done 后通知我复核。
- 给 researcher:Gate-F 判定材料齐备(gate-F-verdict.json + m5/runs_gateF manifests);战役时刻表 T0 以下一次 PASS 判定起算。