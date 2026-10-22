# FlyLaya M5-G0：旧资料冻结验收（TASK-0008）

- 测试者：tester（instance tester-01m3cd7byme0r7d00qsp50n1ns）· 2026-09-25
- 依据：docs/findings/flylaya-next-experiment-system-design.md §9 G0；归档提交 myylaya@471b431

## 交付 1：分目录 + manifest

四批各生成 `manifest.json`（schema `flylaya-m4-batch-manifest/1`，生成器 `m4/make_manifest.py`）：

| experiment_id | 目录 | 参数 | 完整性 |
|---|---|---|---|
| flylaya-m4-v1params-40 | m4/runs/ | tau=1.0/eps=0.0 | 40/40 ok，stats 40 条与文件一致 |
| flylaya-m4-iter1params-40 | m4/runs_iter1params/ | A: 1.6/0.06 | 40/40 ok，stats 40 条与文件一致 |
| flylaya-iter1-confirm-3 | m4/iter1_confirm/ | 1.6/0.06 | 3/3 ok |
| flylaya-iter1-smoke-1 | m4/iter1_smoke/ | 1.6/0.06 | 1/1 ok（120s 段按实际时长校验） |

manifest 内容：逐文件 sha256、行数（内容级完整性，非文件名级）、逐种子场景 meta 哈希（首行，含障碍布局）、
mtime；代码树指纹（14 个 shaping 文件：flylaya/*.py、m3/trajectory_stats.py、m3/literature_baselines.json、
m3/ablation/*.json、m4/run_batch.py）；决策服务指纹（serve.py sha256 844cd6b3…，三副本一致；2 个确定性
探针的 state/response 哈希——服务推理已验证 deterministic；HF 缓存模型目录指纹）；批次窗口/env 参数/notes。

## 交付 2：旧盲评历史标注

- `m4/rating/PROVENANCE.md`：3 份 rating3d JSON 标为历史批，**98.3%/AC1=0.966 标记「基于旧 A」**
  （tau=1.0/eps=0.0，avoid 塌缩版）；新 A 未重盲评，引用必须注明。
- 内容寻址锚验证通过：3 份 JSON 与 `git -C myylaya show 5a68024:reports/findings/flylaya-rating/<name>`
  **逐字节一致**（sha256 见 PROVENANCE.md 表）。
- 原始评分 JSON 未改动（评分数据不可变；真值标签风险已重申）。

## 交付 3：重批完整性核查（内容级，非文件名级）

- 40/40 段：每段 sha256 + 精确行数 3001（3000 帧 + 1 meta）+ seed 解析齐全；
- stats_metrics.json 40 条 ↔ 40 文件一一对应；
- 无静默跳过：批作业日志逐种子打印 frames/wall（A 10 条、B/D 20 条、C 10 条），无一条 `skip existing`；
  manifest 批次窗口与日志时间线吻合（旧批 09-24 18:33–20:15，新批 09-25 08:49–09:53）。

## 追溯闭环（验收口径）

任意旧数字 → experiment_id → manifest 哈希链：

- 旧批数字（12.2cm/s、switch 0.0033、A−B D=0.394、98.3%…）→ `flylaya-m4-v1params-40`；
  其 stats_tables.md（adc8480e…）/stats_metrics.json（793a40df…）与 myylaya@5a68024 归档**逐字节一致**（已校验）。
- 新批数字（switch 0.545、A−B D=0.187、2/7…）→ `flylaya-m4-iter1params-40`；
  stats 归档于 myylaya@471b431 `reports/findings/flylaya-m4-iter1params-stats/`。
- 旧批运行时代码无 VCS 快照（事后树含迭代①+TASK-0006 编辑，manifest notes 已声明）；行为锚 = 归档 stats 哈希。
- 新批 TASK-0006 批中编辑的零影响证据（B/D 冒烟逐字节一致）记于 manifest notes。

索引：`m4/BATCHES.md`（批次表 + 追溯规则）。归档镜像：myylaya@471b431（10 文件：4 manifest + 索引 +
PROVENANCE + 新批 stats ×2 + tester 报告 ×2）。

## 结论

G0 验收通过：批次清单可追溯，旧/新分目录且内容寻址，旧盲评明确标为历史批，重批 40 段内容级完整性无静默跳过。
新战役后续任务（场景合同 G1 起）可以此为门进入。
