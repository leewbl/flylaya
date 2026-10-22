# TASK-0025 完成:M5-V 垂直战役执行(tester)

- 150/150 零失败(explore 60+confirm 80+s4rule 10),~3.9h,哨兵全程零告警,封存域合规(v[0:20]/v[20:30]/机动未动)。
- **Gate-V0 PASS**(P_rule 原口径,backend 预检三阻塞修复后:z_std 0.144/pin 0.000/ω 95.9);**V1 可表达性 PASS**(全策略 z_std 0.11–0.17 中带平衡);**V3 无垂直语义增益**(三 z 指标配对区间全跨零,区间口径预注册)。
- 核心结论:L1 证伪从水平推广到垂直——两维度独立证实当前 observable 编码下 Laya 无空间语义增益。V0 通道修复实证(z 恒 0.5→std 0.14+)。V2-② deferred(纹理 schema 0026 已 done 待补测)。
- 方法论沉淀:垂直探针×意图光增益耦合假象(P_rule z_std=0.0)已根除入检测台注记。
- 总结:m5/report/v-campaign-summary.md;聚合:m5/runs_confirm_v/v3-analysis.json。W6 素材:双维度 L1 负结果+V0 修复链+S4v 高低柱边缘追踪数据。