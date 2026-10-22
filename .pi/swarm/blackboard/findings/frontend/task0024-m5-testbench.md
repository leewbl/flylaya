# TASK-0024 M5 Minecraft 风格 3D 测试台交付 (2026-09-26)

`m5/viewer/bench_serve.py` + `bench.html`,复用 mc_view 方块美学,验收全过:

## 功能(全部实测)
- **场景渲染**(scene.v1): m→cm×100 方块场地;directional 光源=太阳方块(azimuth/elevation/intensity),uniform=环境光;障碍=方块柱,`enabled:false` → 半透明 ghost;windows 呈时间轴背景带
- **回放模式**: /api/runs 索引 439 个 run(runs_confirm 优先),select 切换,seek/暂停/变速,10Hz 真实速率
- **live 仿真**: /api/live 起 m5/runner.py run,trajectory.jsonl 增量流式回传,页面实时动画;完成后自动转回放。实测 P_fixed/skeleton 10s 与 P_laya/connectome 6s 均完成,run 落盘 `m5/runs_bench_live/`,runner verify ok:true
- **垂直运动可视化**: 右侧高度仪表(z 轨迹+当前标记)、地面影子随 z 缩放/变淡、z 读数;m5 z 真实变化(实测 0.45–0.80)
- **事件层**: stimulus_on 精确实时生效 — S1 光源 t<5s 隐藏/t≥5s 点亮,S2 障碍 ghost→黑曜石,DOM data-stim 可审计;事件列表+时间轴色标
- **DN/意图图层**: 8 条 DN 读出条 + gains_post 5 条 + 意图名牌/尾迹/事件列表
- 视角: 侧视/俯视/跟随三档;拖拽轨道+滚轮缩放

## 使用
```
python3 m5/viewer/bench_serve.py --port 8964   # hub daemon `m5bench` 已在跑
open http://127.0.0.1:8964/
```
live P_laya 需 laya-serve(8000)在跑;P_fixed/P_rule 无依赖。live 产物目录 m5/runs_bench_live/ 可用 runner verify 复核。

## 安全边界
本地开发工具:run 目录限定 m5/runs_*;scene id 白名单字符校验;非盲评页(诊断用途,显示真值)。
