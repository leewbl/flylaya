# FlyLaya researcher 滚动验收

## M1 世界+查看器（TASK-0013，backend）✅ 2026-09-24 浏览器实测
- :8900 闭环页实测：canvas/控制钮/HUD 全字段（brain=connectome seed=7 rt×0.99，意图 conf 0.53，spikes 2.4Hz，DNp20 22.5/37.7）——已连跑 31min 仿真时间零错误
- 3335 感受器与 MaleCNS retina_mapped 同维（M2 可直喂）；骨架 0.2ms/帧；确定性双跑字节级一致（backend 自验 + 我抽验页面行为）
- 已知限制合理（CDN three.js、stub 意图）

## M2 全图×Laya 闭环（TASK-0014，backend）✅ 附残留
- 313 调用 0 失败 p50 32.8ms；rt×0.98-1.35；同 seed 位置级复现；892MB 跨 reset 复用
- **残留（tester 差分实验坐实）**：connectome 系恒 344dps 自旋，根因 DNp20 读出紧张性失衡（零输入 L8.0/R18.8）——TASK-0017 基线扣除修复中；HUD 实时可见该失衡（22.5/37.7）
- M2 原报告「自旋消失」口径为浏览器采样帧，无头复测未复现——记录为验收口径教训（无头 harness 为准）

## M3 评估三件套（TASK-0015，tester）✅
- metrics 模块+文献基线+四消融 runner 交付（reviews/flylaya-m3-evaluation-suite.md）；4×30s 冒烟四配置全通；replay/rating 页浏览器实测零错误
- 文献判定侧证：修复前任何配置 0-2/7 达标（吸引子病态所致，与 M2 残留一致）

## researcher 决策与规范动作
- 裁定 M4 走选项 1（先修后跑），冒烟自旋数据保留为文档化失败模式（decision.published 01M3B2JS…）
- intent-spec **v1.1**：state 前置性短语（in/off/not in the flight path）修意图塌缩 + avoid 瞬时逃离偏置 + 30s 段验收放宽至 ≥4/5 类

## 待办跟踪
- TASK-0017（backend）：基线扣除修复复验 → 通过后 M4 全量（40×300s ≈3.6h）+ 10 视频导出 + 盲评
- 终报三口径：轨迹统计（文献区间+KS）/ 盲评 / 消融增益，含失败模式章节