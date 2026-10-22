# FlyLaya M2 修复复测 + 自旋根因定位（tester 差分实验,TASK-0016 内）

- 测试者：tester（instance tester-01m37k0t3x0n8nb2q5b9cnm7q7）· 2026-09-24
- 对象：backend M2 交付（findings/backend/flylaya-m2-connectome-laya.md）后重跑 4×30s 冒烟
- 结论：**两个阻塞项已修，一个残留 + 根因已定位**;全量批量仍建议等下述修复（或带着「自旋顶」结果跑,见文末选项）

## 修复确认 ✅

| M4 冒烟病态 | M2 修复 | 复测 |
|---|---|---|
| 天花板吸附（z→99） | DNa02 差分独占 + 垂直反射 | ✅ z 全程 49（但见观察 3） |
| 角落冻结（skeleton+laya） | 近墙暗化 | ✅ C 配置 xy-span 49×98cm 全场穿越,ω p50 43dps 无 >300dps 帧 |
| 边际 | — | ✅ margin_p05 1→44cm |

## 残留阻塞：connectome 系恒速自旋（「自旋消失」结论未复现）

无头 4 配置冒烟（新 M2 环路逐字复刻,含 modulation_for/render_luminance(mod)/yaw_noise）：

| 配置 | ω p50 | >300dps 帧占比 | z | xy-span |
|---|---|---|---|---|
| A_full(laya) | **344dps** | 99% | 49 恒定 | 7×6cm |
| B(fixed) | **344dps** | 100% | 49 恒定 | 6×6cm |
| D(random) | 同上 | — | — | — |
| C(skeleton+laya) | 43dps | 0% | 49 | 49×98cm |

三意图源下自旋完全相同 → **意图层无关**;M2 报告的「344°/s 自旋消失」与无头实测不符（或其验证口径不同）。

## 根因（三步差分实验，21.8s）

| 实验 | DNp20 L/R | 结论 |
|---|---|---|
| 闭环 200 帧 | 30.4/47.0 Hz（diff 16.6） | 恒定失衡驱动自旋 |
| **开环**（冻结 200 帧亮度,只跑脑） | 29.8/47.0 Hz（**diff 17.2 仍在**） | **非视动正反馈**——视觉冻结不消除 |
| **零输入**（新鲜脑,全黑亮度 50 帧） | **8.0/18.8 Hz（diff 10.8）** | **连接组读出本身带紧张性左右失衡** |

⇒ 根因 = **DNp20 读出偏置**：左右基线放电率不等（零输入已差 ~11Hz）,光照再拉大到 ~17Hz;经 yaw 映射成为恒定 ~344°/s。**建议修复：per-side 基线扣除**——启动时以零/均匀亮度测每侧紧张率 L₀/R₀,偏航命令改用 (R−R₀)−(L−L₀)（DC 去除）;或对 yaw 命令高通。预期修复后 connectome 系才具备「直线飞行 + saccade」的形态学前提。

## 附带发现

1. **库内 FixedIntentSource 词表过期**（M1 旧 4 类）,在 server 里用 FLYLAYA_INTENT=fixed 时四个旧标签全部 miss MODULATION → 静默回退 explore 调制。我的批量驱动已自带 5 类 FixedRotationSource 规避；server 侧建议同步（或删 stub 防误用）。
2. z 恒 49：垂直反射现在是「钉中線」而非「离地/天花板才介入」——高度无变化,与真蝇高度分布不符（记录为 M4 观察口径,非阻塞）。
3. C(skeleton+laya) 是当前最「像蝇」的配置:全场穿越 + 正常 ω + 61% rest（偏多）;speed p50 1.3cm/s 偏慢。

## 对全量批量的两个选项（请 coordinator/backend 定）

- **选项 1（推荐）**:backend 做基线扣除修复（预计小改）→ 我重冒烟确认无自旋 → 40 段全量。总延迟 ~1h 修复 + 3.6h 批量。
- **选项 2**:接受现状跑全量,A/B/D 的自旋顶行为本身成为消融结论（「连接组读出偏置导致运动崩塌,Laya 无法救」也是科学结果——计划 §5 本就允许失败模式量化）;盲评预期 A 不优于 B/D。

## 复现

```bash
# 冒烟(4 配置×30s)
cd /tmp/flylaya/m4 && /tmp/laya-mlx-deploy/.venv/bin/python run_batch.py --seeds 11 --seconds 30 --out smoke_runs
# 根因三步(见 reviews 本文档实验段,可直接内联复跑)
```
