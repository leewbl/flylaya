# TASK-0012 完成:M5-W4 评估/统计合同

- 测试者:tester(instance tester-01m3cd7byme0r7d00qsp50n1ns)· 2026-09-25
- 交付:m5/metrics.py(库+CLI:run/pair-batch/yoked-check/seal-seeds/verify-seals)、m5/test_metrics.py(19 项手算用例,19/19 绿)。报告:docs/reviews/flylaya-m5-w4-metrics-contract.md。

## G3 验收对照

- **H1/H2 指标与独立单位固定**:mean_cos_to_light 配对差(≥+0.15 且 Bonferroni 单侧 2.5% 下界>0,双侧镜像)与接触风险比(降低≥25% 且上界<1);独立单位=场景内种子,分层 bootstrap 先场景后种子;池化帧 KS 仅描述。空分母显式失败+fallback 报告,不解释为成功。
- **yoked 匹配检查可执行**:类占比差≤0.02、停留相对差≤10%,唤醒差 report-only(容差参数化);不过→整批重跑语义写入。
- **20 确认种子封存机制就位**:seal-seeds 只读+sha256,verify-seals 完整性+探索重叠检查;实际封存由 W6 在确认批前触发。

## 关键陷阱落实

sun_R 仅集中度且强制联报平均方向;转向时长/峰值仅 dt≤20ms 组报告;直接偏航份额单列不计神经成功;事件检测器 v1 单一实现(W3 可导入)修复了 rng.choice 内存炸弹。

## 给并行 W1-W3 的合同对接点

m5/metrics.py 模块 docstring 固化了 trajectory/decisions/events 字段契约(SI 单位,首行 meta);runner 缺 events.jsonl 时按同版本检测器重建。判定函数接受 run 目录产物或 metrics dict(_prep)。

**G3 统计合同门通过。**