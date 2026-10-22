# FlyLaya 文献基准值(M3 ②)

- 测试者:tester(instance tester-01m37k0t3x0n8nb2q5b9cnm7q7)· 2026-09-24
- 用途:M4 四消融 × 轨迹统计对照(计划 §4 口径 1);机读版 `literature_baselines.json`(trajectory_stats.py baseline 模式直接消费)
- 取证方式:PubMed eutils(PMID 24440395/29432454/18552291/20952610)+ PMC5828511 全文(网络搜索引擎当日不可用,直接抓取 NCBI 开放接口)

## 基准表

| 指标 | 文献区间/值 | 来源 | 证据等级 |
|---|---|---|---|
| **saccade 幅值**(静止视觉环境) | **平均 ~120°** | Mronz & Lehmann 2008, J Exp Biol 211(13):2026-45, PMID 18552291(摘要:"turn on average 120 degrees within 130 ms") | 直接引用(摘要) |
| **saccade 时长** | **~130 ms**(⇒ 平均角速度 ~920°/s,峰值更高) | 同上 | 直接引用(摘要) |
| **气味触发 surge 延迟** | **190 ± 75 ms**(入羽流→加速+上风转) | van Breugel & Dickinson 2014, Curr Biol 24(3):274-86, PMID 24440395(摘要) | 直接引用(摘要) |
| **气味丢失 cast 延迟** | **450 ± 165 ms**(失羽流→垂直/水平 casting,保持横风航向) | 同上 | 直接引用(摘要) |
| **嗅觉调制最快起始** | ~85 ms(嗅觉转导起始后) | Bhandawat et al. 2010, J Exp Biol 213(21):3625, PMID 20952610(摘要) | 直接引用(摘要) |
| **单次气味触发转角变异** | 个体反应跨度 **~100°**(均值上风转周围) | Pang et al. 2018, PLoS Comput Biol 14(2):e1005969, PMC5828511(正文 Fig 1D) | 直接引用(全文) |
| **surge 速度脉冲**(模型拟合实测) | alpha 函数,时间尺度 **0.07 s**,幅值 **0.8 m/s** | Pang 2018 Methods(拟合 vB&D 2014 数据) | 直接引用(全文方法) |
| **速度相关时间 τ**(相关随机游走拟合) | **0.42 s**;噪声尺度 η=1.9 m/s;casting 漂移 b=0.25 m/s | Pang 2018 Methods(S6 拟合) | 直接引用(全文方法) |
| **实验风洞几何** | 1.3 × 0.3 × 0.3 m 可飞段,层流风 **30–60 cm/s** | Pang 2018 Methods | 直接引用(全文方法) |
| **位置分布形态** | 显著聚集于**上风端**(热图峰值) | Pang 2018 Fig 7A(vB&D 数据) | 直接引用(全文) |
| **历史依赖性** | 早/晚穿越转角差异 ~30% infotaxis 型贡献 | Pang 2018 Fig 6 | 直接引用(全文) |
| 自由飞行地速分布(绝对值) | **20–50 cm/s**(静风/风洞量级) | 领域共识,**[INFERENCE]**:η/b/风速推断,未见摘要级直接数字;M4 前可由 vB&D 图表补验 | 推断(待核) |

## 复核追加(researcher TASK-0007,2026-09-25)

| 指标 | 文献区间/值 | 来源 | 证据等级 |
|---|---|---|---|
| **saccade 率(自由飞行,野生型)** | **1.8–2.1 Hz**(各条件均值±SD:静风闪光 1.9±1.0 / 层流闪光 1.9±1.1 / 静风对照 1.8±0.95 / 层流对照 2.1±1.2) | Stupski & van Breugel 2024, Curr Biol 34(19):4397-4411.e6, doi:10.1016/j.cub.2024.07.009, PMC11461137(全文 Fig 3C) | 直接引用(全文) |
| saccade 率(嗅觉激活搜索态) | 2.5–3.4 Hz(Orco>CsChrimson 光激活) | 同上 | 直接引用(全文) |
| saccade 率(sink-and-circle) | **3–4 Hz** @ ~60°,方向偏置一致 | 同上(摘要+正文) | 直接引用(全文) |
| saccade 幅值交叉验证 | ~90° / <100ms(竞技场自由飞行) | Tammero & Dickinson 2002, J Exp Biol 205(Pt 3):327-343, PMID 11854370(摘要:"alters course by approximately 90 degrees in less than 100 ms") | 直接引用(摘要) |
| 直线段结构 | "straight flight segments separated by rapid turns"(直线段+saccade 交替;对比度调变平移速度与 saccade 频率) | 同上(摘要) | 直接引用(定性) |
| 地速上限锚点 | >2.0 m/s 即"uncharacteristically high"(室外/受限空间均然,引 Leitch 2021 / Straw 2010 / Medici & Fry 2012) | Stupski 2024(方法学滤波阈值) | 直接引用(全文) |

**复核结论**:原 JSON `saccades.rate_hz` [0.2, 2.0] 下界无文献支撑——野生型均值聚在 1.8–2.1 Hz,已改 **[1.0, 3.0]**(状态混合带:巡飞/搜索 1.8–2.1,搜索态至 3.4,circling 3–4;取 1.0 下界容纳低激发窗口)。`speed_cm_s.p50` 与 `straightness` 维持 INFERENCE:速度仅得上界锚(>200 cm/s 异常)+ 风洞风 30–60 / surge 0.8m/s / cast 0.25m/s(Pang 2018);直度数值带为建模约定,结构前提已被 Tammero 定性证实。注意:`check_baselines` 对全部行计算 in_range,rate 收紧后口径 1 的 saccade 判定将全面转 miss(模拟 0.05–0.07Hz 距 WT 均值差 ~30×)——TASK-0003 验收目标应从 0.2–2Hz 修订为 1–3Hz。

## 换算到 FlyLaya 1m³ 场地(重要口径警告)

- 真实风洞 1.3×0.3×0.3m 细长 vs FlyLaya 1×1×1m 立方:**空间利用/避障边际/趋光角分布只能做相对比较(A vs B/C/D)**,不能与风洞绝对值直接对照。
- 可绝对对照的指标(saccade 幅值/时长/角速度、surge-cast 延迟、转角变异跨度、速度相关时间)不依赖场地几何。
- DN 读出→运动的映射若使 saccade 角速度落在 300–1600°/s、幅值 p50 落在 60–150°,即与文献同量级(检测阈值 300°/s 即由此设定)。
- 10Hz 生物帧的采样极限:saccade 130ms ≈ 1-2 帧——**M2 日志若要精确测量 saccade 形状需帧内子步记录角速度**,否则只能做事件计数+幅值估计(当前 trajectory_stats 按 10Hz 设计,幅值=∫ω·dt 已含此误差,解读时注意)。

## 意图层规范 §5 的对照口径(来自 intent-spec,非文献)

- 意图分布不塌缩(每类≥1 次);arousal-速度 Pearson r>0.3;切换频率 0.1–1 Hz——已内置为 intent_stats 指标。

## 机读版

`literature_baselines.json` 键 = trajectory_stats.py 报告的点路径;`in_range` 即口径 1 判定。范围取值原则:摘要直接数字用 ±报告误差;推断项标注 `"note": "INFERENCE"` 并不参与达标判定(M4 前移除或补验)。

## 来源

- van Breugel F, Dickinson MH (2014) Curr Biol 24(3):274-286. doi:10.1016/j.cub.2013.12.023 · PMID 24440395
- Mronz M, Lehmann F-O (2008) J Exp Biol 211(Pt 13):2026-2045. doi:10.1242/jeb.008268 · PMID 18552291
- Pang R, van Breugel F, Dickinson M, Riffell JA, Fairhall A (2018) PLoS Comput Biol 14(2):e1005969. doi:10.1371/journal.pcbi.1005969 · PMC5828511(全文)
- Bhandawat V, Maimon G, Dickinson MH, Wilson RI (2010) J Exp Biol 213(Pt 21):3625-3635. doi:10.1242/jeb.040402 · PMID 20952610
- Tammero LF, Dickinson MH (2002) J Exp Biol 205(Pt 3):327-343. doi:10.1242/jeb.205.3.327 · PMID 11854370
- Stupski SD, van Breugel F (2024) Curr Biol 34(19):4397-4411.e6. doi:10.1016/j.cub.2024.07.009 · PMC11461137(全文,复核主源)
- 次级锚(经 Stupski 2024 方法节转引,全文未直读):Leitch et al. (2021) PNAS 118:e2013342118 · PMC8092610;Straw et al. (2010) Curr Biol 20:1550-1556;Medici & Fry (2012) J R Soc Interface 9:3260-3267 · PMC3481592
- MaleCNS 论文(biorxiv v2,本地):连接组/LIF 复现参照——其验证对象为网络统计量而非自由飞行行为学,不提供行为基准(计划 §5 已知)
