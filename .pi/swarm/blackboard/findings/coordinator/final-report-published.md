# TASK-0018 收口：三口径终报已发布（2026-09-25 07:15 PDT, coordinator-01m3ccf…sryh）

- 终报全文: `docs/findings/flylaya-final-report.md`（agent:// 不可用, 项目 docs 树为 canonical）
- 盲评数据: `m4/rating/flylaya_rating3d_{csx,lee,xixi}_*.json`（3D 入口, 3/3 完成）

## 核心数字
- 口径 2: A_full 被选 59/60 = 98.3%, 均分 4.22 vs B 1.55 / C 1.00 / D 1.33
- 一致性: Gwet AC1 = 0.966, 全一致 19/20; Fleiss κ = -0.017（κ 悖论, 边际偏斜 98%→chance 一致≈实际一致, 已在报告 §1.2 如实说明并给出稳健指标）
- 显著性: A 被选二项 p = 5.3e-17; A−B 配对评分差 2.74 分 t(41)=18.4
- 三口径合流: Laya 意图层 = 拟真度关键增量（人类 + 统计双证）; 绝对拟真度（文献口径）1–2/7 未达

## 状态
- TASK-0018 验收点逐项对照: 三口径定量结论 ✅ / 数字与 reviews 一致 ✅ / 盲评一致性已算（含 κ 悖论处理）✅ / 已达未达区分 ✅ / 迭代建议 §5 ✅
- 收口后待办: 归档 myylaya git 仓; §6/报告 §5 迭代项待排期
