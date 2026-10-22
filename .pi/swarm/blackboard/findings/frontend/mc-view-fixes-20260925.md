# mc_view 修复记录 — 2026-09-25

目标:`m4/mc_view/`(Minecraft 风格 3D 回放观察器)修复与验证。修改 `template.html` + `gen.py`,重新生成 `index.html`。

## 修复

1. **播放速率 4× 过快**(行为 bug):帧距 0.2s(10Hz 源 × stride 2),原代码 `fi += dt*10*speed*2` = 20 帧/s → 1× 档实为 4× 实时。改为 `dt*5*speed`。gen.py docstring 同步更正(原文“20fps 采样”是错误来源)。
2. **speckle() 纹理全黑点**:`rnd(-vary, vary)` 传数组 → NaN → 所有随机像素 rgb(0,0,0)。改为按通道 `base + v*vary[j]`。验证:8×8 采样 53 色、0 黑像素。
3. **平行光方向与太阳方块不一致**:`sunLight.position.copy(太阳位置)` 但 target 默认原点 → 光照方向偏移。改为 position=场地中心+sun_unit×300、target=场地中心,与 buildSun 方块一致(趋光行为目视判断需要)。
4. **loadRun 不刷新 HUD**:暂停态切换 run 后 t/cfg 显示旧值。loadRun 尾部加 `updateHUD(true)`。
5. **死代码**:`$('follow').onchange` 空操作、`tlg.drawImage` noop 播放头块,删除;follow 的 target lerp 移出 `if(playing)`(暂停+seek 时也跟随)。
6. **尾迹按意图着色**:trail instanceColor = 当时意图色(与时间轴/名牌配色一致),3D 内直接可见意图分段。材质基色改白以免叠色。

注:地板 `k++` 未定义 fatal bug 由并行编辑者先修(`let k=0`),本次与其无冲突收尾。

## 验证(Chromium headless, http://127.0.0.1:8960/mc_view/)

- 页面 0 error、0 console 报错;module 完整执行
- 1× 速率:5s 墙钟 = 5.0s 仿真;4× 档:4s 墙钟 = 16.0s 仿真 ✓
- 暂停 → 切 D_random_intent_11:meta2=`intent_source=random` ✓;切 C:HUD 立即刷 `0s/300s` ✓
- 时间轴 seek 95% → 285s/300s ✓;4 配置 select 齐全 ✓

## 已知小事
- 本会话发现 template.html 有并行编辑(地板修复同期)。后续编辑前先 read 刷新快照。
- evaluate 在隔离世界取不到 `window.__fly`(debug 句柄),DOM/行为验证不受影响。
- 静态服务:hub daemon `mcview` 端口 **8960**(根=m4/),非 HANDOFF §5 的 8940。