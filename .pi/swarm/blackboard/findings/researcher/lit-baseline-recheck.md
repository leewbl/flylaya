# 文献基线复核差异说明(TASK-0007, 2026-09-25, researcher)

**给 TASK-0003(saccade 通道)认领人与后续口径 1 判定的所有消费方**:

1. `m3/literature_baselines.json` 的 `saccades.rate_hz` 从 [0.2, 2.0](INFERENCE)改为 **[1.0, 3.0](VERIFIED)**。主源:Stupski & van Breugel 2024, Curr Biol 34(19):4397-4411.e6, PMC11461137 全文——野生型自由飞行四条件均值 1.8–2.1 Hz;嗅觉激活搜索态 2.5–3.4;sink-and-circle 3–4 Hz @~60°。旧下界 0.2 无任何文献支撑。
2. **TASK-0003 验收目标随之修订:率 0.2–2Hz → 1–3Hz**(幅值 ≥90° 维持,已有三源支持:Mronz ~120°/Tammero ~90°/Stupski circling ~60°)。
3. `check_baselines` 对全行算 in_range,收紧后旧 A 的 rate 0.06Hz 判 miss 且差距放大到 ~30×(旧基线下差 4×)。已实测:A_full seed11 用新基线 7 项中 6 项 miss(仅 duration 过)——后续 stats 报告引用口径 1 数字时必须注明基线版本。
4. 仍为 INFERENCE(诚实保留):`kinematics.speed_cm_s.p50`(仅有锚点:风 30–60cm/s、surge 0.8m/s、cast 0.25m/s、>200cm/s 异常滤值;实测分布未取得——JEB/PNAS 全文被出版商与反爬墙挡,Leitch 2021 PMC8092610 为下一步取数目标);`segments.mean_straightness`(结构前提已由 Tammero 2002 定性证实,数值带仍为建模约定)。
5. 检索路径备忘:web 搜索引擎当日全部超时/反爬;可用通道 = NCBI eutils(esearch/efetch/摘要)+ EPMC REST(搜索可用,fullTextXML 对非 OA 500)+ 浏览器直读(被 PMC 墙)。Stupski/Currier 全文 XML 可经 efetch db=pmc 正常取得。