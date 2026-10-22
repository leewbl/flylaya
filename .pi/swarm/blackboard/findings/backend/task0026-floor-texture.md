# TASK-0026 · 场景 schema v1.1:地板纹理开关(V2-② 前置)

backend · 2026-09-26 · 改 flylaya/scene.py + flylaya/world.py + m5/scenes/S0v_neutral.json + m5/test_scene.py

## 交付

1. **schema v1.1**(向后兼容): `flylaya.scene.v1.1` 与 v1 并存;light 新增可选 `floor_texture: {"contrast": 0-1}`;事件目标新增 `floor_texture`(stimulus_on/off, 起始恒关);顺带放行 `expect.note` 注记键(研究员的 S0v 原稿就带 note, 但该文件此前 JSON 损坏从未真正解析过)
2. **纹理渲染**(world.py): 固定均值保持 ±1 棋盘(15° 角单元格, 确定性表驱动)调制腹侧地板辉光: `glow *= (1 + contrast·pattern)`。模式定义在感受器空间(随蝇旋转扫过 = 正确光流语义), 构造上**零垂直位置信息**(均值不变);legacy 世界默认关
3. **S0v_neutral.json 升 v1.1**: 纹理 contrast 0.5, 事件窗 t=8 开 / t=16 关, 三诊断窗(baseline_notex / texture_on / texture_off)
4. **测试**: test_scene 新增 5 项(v1.1 加载 / v1 round-trip 保持 v1 / 纹理统计可逆 / 未知 schema 拒绝 / contrast 越界拒绝), 全套 **47/47 PASS**;coupling/metrics 套件同绿

## 验收证据

- **腹侧亮度统计显著差异而均值保持**: off/on 腹侧均值 0.1092/0.1102(|Δ|<0.01), std ×1.96, 关窗后亮度逐位还原(allclose)
- **z 无系统性迁移的机制可测**(skeleton × S0v × 30s, 固定趋光): z 均值 pre 0.721 / 纹理窗 0.668 / 关窗后 0.647——漂移单调延续过开关边界, 无纹理态锁定反转(若有光流设定点, 关窗应反向回迁);V2-② Straw 反证测试现在可跑
- **v1 全向后兼容**: 现存 8 个 v1 场景全加载, round-trip schema 不变

## 给 vertical 战役

- S0v 现为 v1.1(带纹理事件)——战役若复用旧 manifest 哈希需重算场景原文哈希;V2-② 从 deferred 转可执行
- 纹理起始恒关, 不影响 V0/V3 口径(其窗口在 t<8s 判据不受纹理窗污染, 但 V3 若用 S0v 全 120s 段请注意 t=8/16 事件存在)
