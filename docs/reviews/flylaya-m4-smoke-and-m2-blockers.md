# FlyLaya M4 冒烟报告:管线打通 + M2 待调项（TASK-0016 进行中）

- 测试者：tester（instance tester-01m37k0t3x0n8nb2q5b9cnm7q7）· 2026-09-24
- 交付物（已完成部分）：`/tmp/flylaya/m4/`（run_batch.py + replay/index.html + rating/{index.html,manifest_gen.py}）；静态服务 hub 进程 `flylaya-m4-static` :8940
- 阻塞项：全量 40-run 批量等 M2（TASK-0014，backend 在途）——见「M2 待调项」

## 管线验证（4 配置 × 1 种子 × 30s，含 connectome+laya 真闭环）

- 四配置全部跑通：A_full（connectome+laya，rt×1.35）、B（connectome+fixed，rt×1.65）、C（skeleton+laya，rt×8.8）、D（connectome+random，rt×1.63）
- run→metrics→汇总表（每配置中位数）→池化 KS→文献判定 全链路产出；laya-serve :8000 服务化决策正常
- 日志契约核验：yaw 连续无跳变、单位换算（m→cm）正确、障碍/太阳元数据与 World 一致

## M2 待调项（阻塞全量批量，请 backend 在 M2 内处理）

冒烟暴露两个病态吸引子 + 一个规范违背，**均为仿真行为而非日志/统计缺陷**（驱动日志已逐项核验）：

1. **A_full/D（connectome 系）天花板吸附自旋**：z 钉在 99cm（天花板 1cm 内）、以 ~344°/s 恒定角速度在小半径（~4cm）圆上持续旋转 30s；空间占用 2%；「saccade 幅值 p50 10⁴°」实为整段连续旋转被检测为单一事件（真实测量，正确标记非 saccade 行为）。俯仰通道把蝇推到天花板后无法脱离。
2. **C（skeleton+laya）角落吸附冻结**：贴边近静止（speed p50 2.4cm/s、87% 时间 rest、yaw 冻结），Laya 持续输出 turn_away_from_the_wall 但 skeleton 执行不了。
3. **意图塌缩（规范 §5 违背）**：A/C 两种 laya 配置 30s 内只出现 2/5 类（slow_down_and_turn_away_from_obstacle / turn_away_from_the_wall）——按 researcher 验收口径「每类至少出现」将不达标。可能需要 state_text 里把天花板/地面与四壁区分、以及调制表给墙排斥设上限或死区。

文献基线侧证：四配置 0-2/7 达标——当前任何配置都还「不像果蝇」，主因即上述吸引子。

## 已就绪组件（M2 落地后即可全量）

| 组件 | 状态 | 验证 |
|---|---|---|
| run_batch.py（4 配置×10 种子×300s 驱动 + 聚合表） | ✅ | 30s×4 冒烟通过；connectome 懒加载 0.2s；断点续跑（skip existing） |
| replay/index.html（轨迹→3D 回放→MediaRecorder 导出 webm/mp4） | ✅ | 浏览器实测：HUD/播放推进（26/300 帧）/意图着色轨迹/跟随相机/零控制台错误 |
| rating/index.html（A vs B/C/D 盲评：双单独 5 点评分 + 强制二选一） | ✅ | 浏览器实测：门控（三项齐全才可下一步）/推进 2/8/localStorage 持久化/真值不外显/零错误 |
| rating/manifest_gen.py（随机配对 + 盲侧随机化） | ✅ | 冒烟 manifest 8 对生成 |

## 全量执行清单（M2 修复后）

1. `run_batch.py --seconds 300`（40 段，串行 ~3.6h，rt×1.3-1.7 折算）
2. 浏览器逐段导出 10 段 A_full 回放（replay 页 MediaRecorder）
3. `manifest_gen.py --n-trials 20` + 人类盲评（≥3 评分者）
4. 聚合表 + 盲评 JSON 交 researcher 终报（三口径）

## 复现（冒烟）

```bash
cd /tmp/flylaya/m4
# 起 laya-serve :8000 后
/tmp/laya-mlx-deploy/.venv/bin/python run_batch.py --seeds 11 --seconds 30 --out smoke_runs
python3 rating/manifest_gen.py smoke_runs rating/manifest.json --n-trials 8
# 浏览器: http://127.0.0.1:8940/replay/ 与 /rating/?manifest=manifest.json&rater=<name>
```
