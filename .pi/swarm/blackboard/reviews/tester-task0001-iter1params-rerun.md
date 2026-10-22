# TASK-0001 完成:全量 40 段重批(迭代①参数)

- 测试者:tester(instance tester-01m3cd7byme0r7d00qsp50n1ns)· 2026-09-25

## 结果

- **40/40 零失败**(A 新参数 TAU=1.6/EPS=0.06 重建;B/C/D 默认参数复跑),墙钟 ~1h8m,并发 ≤2、laya 单客户端约束遵守。
- **新 A 六项护栏全过**:ω p50 99dps(<150)、ω>300 占比 0.0061、arou_r 0.468(>0.3)、switch_hz 0.545(0.1–1)、5/5 类、最大类 0.333(<80%)。avoid 塌缩(旧 98.8%)消除。
- **A−B 分离弱化证实**:speed D 0.394→0.187、ω 0.192→0.036、sacc_amp 0.206→0.085(p=0.46 失效)——旧 A 超活跃签名是 avoid 塌缩产物(HANDOFF §2 预警成立)。
- **B−D 仍不可分**(结论不变);C 分离保持最强且 A−C ω 分离增强(0.32→0.47)。
- **口径 1**:new A 2/7(旧 1/7);B 2/7、C 1/7、D 1/7 不变。sacc 率/速度仍低于文献档。
- **口径 2 注记**:98.3%/AC1=0.966 绑定旧 A,新 A 未重盲评——引用必须注明;重盲评数据基础已就绪(runs_iter1params 40 段)。
- B/C/D 复跑在行为噪声内复现旧基线(D 主指标逐位一致;B sacc_rate/C speed 的小幅漂移属 connectome/laya 逐次涨落,成对结论不变)。

## 数据与报告

- 数据:m4/runs_iter1params/(40 jsonl + stats_metrics.json + stats_tables.md);旧基线 m4/runs/ 未动。
- 对比工具:m4/compare_runs.py(旧侧已验证与 canonical stats_tables.md 逐项一致)。
- canonical 报告:docs/reviews/flylaya-m4-rerun-iter1params.md。

## 建议后续(池外供 coordinator 排期)

- TASK-0002 方向:新 A 重盲评(manifest/回放对重生成,人类评分)。
- 迭代②建议 3(saccade 瞬态)与建议 4(趋光读出)是口径 1 的主攻点。