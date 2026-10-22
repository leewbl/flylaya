# FlyLaya 项目状态（coordinator 维护）

> 会话交接快照 2026-09-26：HANDOFF.md 已重写（M5 收口+M6 进行中）；myylaya 归档推至 d96ef47。新 coordinator 从本文件 + HANDOFF.md 接手。
## 方向决议（2026-09-25，用户敲定）
**实验方向 = `docs/findings/flylaya-next-experiment-system-design.md` v1.0（M5 战役）**。
研究问题三件套：语义有效性（L1）/ 神经通路有效性（L2）/ 行为拟真度（L3）；预注册判据 H1–H4；
W1–W6 分包 + G0–G5 门槛；主张分级不可用弱证据替代强主张，负结果也是完整交付。


## 战役状态（2026-09-26 · 0021 八小时战役 done）
| 阶段 | 状态 | 判定 |
|---|---|---|
| 全部开发+修复+诊断 | done ✓ | G0–G4、Gate-F、0017/0019/0020/0022 |
| **0021 确认战役** | **done** ✓ | 200/200 零失败；**H1 证伪**（Laya≈yoked，仪器可表达性由 P_rule 证明）→ 断点=决策层状态语义；H2 接触口径不可判；H3 条件跳过；S4 P_laya≈P_yoked、P_rule 冲突崩溃；H4 内核支持 10/20ms |
| **盲评包** | 就绪 | `m5/viewer/blind.html`（20+2 训练，双问题，渗透 PASS）——**待 ≥3 评分者，优先于 m4 旧入口** |
| 0015 W6 终报 | in_progress（数据齐）| L1 判定材料完备；等盲评包 |
| **0023 z 轴解钉**（新立项）| open | pitch 恒 0 / z 钉 50cm 的运动学修复；验收 S0 z_std≥3cm+水平护栏；backend |
| **0024 Minecraft 3D 测试台**（新立项）| open | M5 场景方块渲染 + live/replay 双模式 + 垂直可视化 + 诊断图层；frontend(+backend live 桥)；诊断工具，与盲评管线分流 |

## M6 开放世界探索线（用户指令 2026-09-26：「像在我的世界中探索…有山有树有水有阳光，果蝇随意探索」）
与 M5 受控假设线并行、互不替代（M5 冻结物不动）。M5 垂直战役 0025+0026 已 done。
- **0027 W1 自然世界引擎**（backend，open）：flylaya.scene.v2 固定地形 5m×5m（山/树/水/阳光）+ 地形碰撞 + 体素感官渲染 + 自由探索跑批
- **0028 W2 地形观察器**（frontend，open）：Minecraft 风格地形渲染 + 地面影子/高度尾迹 + 覆盖率仪表 + 蝇视角第一人称 + replay/live 双模式
- 后续（两者落地后立项）：探索批数据战役 + 与 M5 结论的对照分析

## 四角色协调结构（用户指令 2026-09-25）
- **researcher**（设计权威）：0015 终报 + 阈值/场景冻结决策；对池任务有 supersede 权（0003-0005 先例）
- **frontend**（W5+盲评线）：0014 观察器 v2 → 0002 新 A 重盲评执行段（**阻塞在用户组织 ≥3 评分者**）
- **backend**（W1/W2 关键路径）：0009 场景世界 → 0010 感官/神经接口 → 0011 批量日志
- **tester**（W4+执行线）：0012 指标统计 → 与 backend 在 0011 会合 → 0013 RUN 诊断批 → 0016 8h 战役
- coordinator：验收每个 done（产物落地核查）、维护 project.md/DAG、吞吐偏差预警、不执行

## 协调要点
1. 全部任务 frontmatter dependsOn 空——信任正文，真实 DAG 见 findings/coordinator/m5-dispatch-plan.md
2. 旧战役 0003/0004/0005 已被 campaign.superseded 作废，勿认领
3. 旧盲评 98.3% = 历史批结论（PROVENANCE.md 已锚定），新 A 重盲评未做前不得引用为新参数结论
4. 确认批种子用 0015 封存清单；saccade 率文献区间已修订 [1.0, 3.0]（0007）
