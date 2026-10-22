# FlyLaya M4 终报：批量/回放/盲评就绪（TASK-0016 完成）

- 测试者：tester（instance tester-01m37k0t3x0n8nb2q5b9cnm7q7）· 2026-09-24
- 批量结果：reviews/flylaya-m4-batch-results.md（口径 1+3）；冒烟/根因链：reviews/flylaya-m4-smoke-and-m2-blockers.md、flylaya-m2-refix-verification-spin-rootcause.md

## 交付清单（对照计划 §1 M4）

| 项 | 状态 | 位置/验证 |
|---|---|---|
| 10 种子×5min×4 消融 = 40 段 | ✅ | /tmp/flylaya/m4/runs/（40 jsonl；1h51m；0 失败）|
| 全指标统计表 + 池化 KS + 基线判定 | ✅ | runs/stats_{metrics.json,tables.md}（口径 1/3 详见批量结果报告）|
| 10 段 5min 完整系统回放 | ✅ | replays/A_full_{11..111}_replay.mp4（h264 1100×620，时长恰 300.0s）|
| 消融回放（评分配对用） | ✅ | 另 10 段：B×6 + C×2 + D×2（共 20 段 43MB）|
| 盲评页 + 配对 manifest | ✅ | rating/{index.html,manifest.json}：20 对（A vs B/C/D，盲侧随机，truth 不外显）；浏览器实测双视频 readyState 4 / 300.0s / 门控-推进-持久化 / 0 控制台错误 |
| 人类盲评执行 | ⬜ researcher 组织 | 评分入口：http://127.0.0.1:8940/rating/?manifest=manifest.json&rater=<姓名>（hub 进程 flylaya-m4-static 托管）；结果 localStorage + 导出 JSON（含 truth 供分析） |

## 工程备注

- 回放走离线 matplotlib→ffmpeg 渲染（render_replays.py，5fps 实时速、双面板俯/侧视、意图着色蝇点+轨迹带、HUD）：浏览器 MediaRecorder 路径在无头环境状态保持不稳定（tab 复位无错误日志），离线路径确定性可复跑（~40s/段）。
- manifest_gen.py 只配对已渲染回放（防 404），A 源 10 个、B/C/D 各 2-6 个；研究侧如需更多 C/D 配对可 `render_replays.py runs/C_no_connectome_44.jsonl ...` 增量渲染后重生成 manifest。
- laya-serve :8000 与静态页 :8940 仍在运行（hub 托管：无命名进程，供评分/复查）。

## 给 researcher 终报（三口径）的数据接口

1. 轨迹统计对照：runs/stats_tables.md + literature_baselines.json（判定器 `trajectory_stats.py baseline`）
2. 人类盲评：评分导出 JSON（forced_choice + 双 5 点量表 + truth）
3. 消融增益：stats_tables.md 池化 KS 段（A−B/A−C/A−D/B−D）

## 复现

```bash
cd /tmp/flylaya/m4
V=/tmp/laya-mlx-deploy/.venv/bin/python
$V run_batch.py --seconds 300 --out runs                       # 40 段 ~1h51m
$V render_replays.py runs/A_full_11.jsonl ... --out replays    # ~40s/段
python3 rating/manifest_gen.py runs rating/manifest.json --n-trials 20 --seed 7 --replay-ext .mp4
# 评分页: http://127.0.0.1:8940/rating/?manifest=manifest.json&rater=<name>
```
