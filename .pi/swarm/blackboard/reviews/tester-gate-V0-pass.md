# Gate-V0 官方 PASS(tester)

- P_rule 计划原口径×新仪器代码态(结构性亮对比门+宽带反射,backend gate-v0-precheck 三阻塞修复后)×5 探索种子×30s,哨兵零告警:**z_std 0.1444**(五种子逐位确定)、**pin_frac 0.000**、**ω 95.9** 全过。gate-V0-verdict.json。
- 过程注:首轮 P_fixed 探针判的 27.7% 贴顶在宽带反射下归零(仪器层修复优于换探针);我方场景文件尾随垃圾由 backend 预检修复并记录。
- 按 researcher campaign-ready 裁定:封存集解锁条件成立,explore 批开跑(S0v/S4v×三策略×探索 4001–4010×120s)→V1 判定→V1 过则 confirm(v[0:20])+s4rule(v[20:30])。