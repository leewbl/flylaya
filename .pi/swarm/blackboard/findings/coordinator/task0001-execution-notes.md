# TASK-0001 执行提示：B/C/D 无需重跑（2026-09-25 08:45 PDT, coordinator）

## 结论
迭代① 代码改动全部在 LayaIntentSource 路径 + env 旋钮（FLYLAYA_INTENT_TAU/EPS 默认关）。
B_no_laya（FixedRotationSource）/ C（skeleton 脑）/ D（RandomIntentSource）行为与旧批
逐位一致——**重跑它们只烧串行预算 ~2.7h，不产生新信息**。

## 建议命令（认领者直接用）
```bash
cd ~/aiworld/flylaya/m4
FLYLAYA_INTENT_TAU=1.6 FLYLAYA_INTENT_EPS=0.06 \
  ~/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python run_batch.py \
  --configs A_full --seeds 11 22 33 44 55 66 77 88 99 111 --seconds 300 --out runs_v2
cp runs/B_no_laya_*.jsonl runs/C_no_*.jsonl runs/D_random_*.jsonl runs_v2/   # 复用旧批
cp runs/B_no_laya_11.jsonl runs_v2/ 2>/dev/null  # (glob 已覆盖)
~/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python run_batch.py --aggregate-only --out runs_v2
```
预算：A 10 段 ≈ 70–85min（rt×1.4–1.66），而非任务原文的 3.6h 全量。

## 验收补充（护栏判定脚本现成）
- `iter1_check.py <jsonl>` 单段四指标 + 意图分布
- 全批护栏：ω p50<150dps、arousal r>0.3、switch 0.1–1、意图 ≥4/5、无类 >80%
- 对比表：runs_v2 的 A vs runs/ 的 A（参数化前后）+ A_v2−B/C/D 池化 KS（B/C/D 同数据）

## 依任务原文验收不变的部分
40/40 零失败、三口径重算、docs/reviews/ 对比表落档。
