# 盲评启动记录 v2（2026-09-25 07:00 PDT, coordinator-01m3ccf…sryh）

## 双入口（均已 selftest 干跑 20 对 + 导出验证通过）
- **3D 盲评（推荐, 用户指定）**: `http://127.0.0.1:8960/rating3d/?rater=<名字>`
  - Minecraft 方块世界双视窗并排, 每对左右各一个 run 的完整 300s 轨迹同步回放
  - 可各自拖拽旋转/缩放; 共享 播放/暂停/0.5–8× 速度
  - 盲化: 不显示配置名/意图/速度/种子——只有两个世界 + 计时 + 进度
  - 代码: m4/rating3d/{template.html, gen.py, index.html}（0.97MB, 17 run 内嵌）
- **2D 视频盲评（备用）**: `http://127.0.0.1:8960/rating/?manifest=manifest.json&rater=<名字>`
- 两页导出 schema 一致（trial/rater/ts/left/right/rating_left/rating_right/forced_choice/truth）,
  3D 页 left/right 为 run 名; TASK-0018 聚合可混用, 但建议同一批评者只用一种入口

## 评分者须知
1. 一次坐完（两页均不支持下断点续评）
2. 3D 页建议 2× 速度看全程 (~2.5min/对), 20 对约 50–70 分钟
3. 导出 JSON 含真值, 勿打开, 直接放 `~/aiworld/flylaya/m4/rating/`
4. 收口门不变: ≥3 份 → TASK-0018

## 已修的坑（3D 页开发中）
- template 尾部被编辑事故截断（__rating3d/show()/闭合标签丢失）→ 模块静默半执行, 时钟走但流程死; 已补全并重验
- 诊断陷阱: 模块内 const 不上 window, 需走 __rating3d 钩子

## 后续候选（frontend, 本批收完前不动评分页）
- localStorage 断点续评（两页同改）
- 3D 页多相机预设（跟随蝇视角/俯视一键切换）
