# TASK-0002 进展:新 A 盲评入口就绪 (2026-09-26)

TASK-0001 完成后(m4/runs_iter1params/, 40 段),已生成并验证:

- `m4/rating/manifest_newA.json` — 20 对 A_full vs 消融,盲化左右(--replay-ext .webm 避免 manifest 与旧 mp4 回放耦合/旧基础路径)
- `m4/rating3d/index_newA.html` — 20 对/25 runs/1.41MB,gen.py 修复 run 名 stem 提取(兼容 .jsonl 名)
- 冒烟:0 error、回放推进、完整一轮记录 schema 与 consistency.py 兼容、DOM 无配置名
- 一致性脚本 `m4/rating/consistency.py` 已验证可逐项复算旧批终报 §1 数字(见 task0002-rerating-prep.md)

## 剩余(人工门槛)
≥3 评分者完成 20 对 → 导出 JSON 存 `m4/rating/` → `consistency.py` 新旧对比:
- 入口: `http://127.0.0.1:8962/m4/rating3d/index_newA.html?rater=<名字>` (m5view daemon, 仓库根)
- 对比基线: 旧 98.3%/AC1 0.966;迭代①后 A−B speed D 0.394→0.187,预期人类分离度同步弱化
- 注: 此页为 m4 协议(导出含 truth,页面有勿看警告);若要零泄漏协议可用 m5/viewer v2 管线(--runs-dir m4/runs_iter1params)
