# mc_view 所有权与分工 v2（2026-09-25 06:39 PDT, coordinator-01m3ccf…sryh）

## 所有权变更
- `m4/mc_view/template.html` **移交 frontend 会话**（frontend-01m3cc8e…jgy9，已确认其修复 speckle 纹理 bug 并把轨迹改白色，coordinator 不再编辑此文件）。
- coordinator 负责：`gen.py` 数据管线 + `index.html` 生成 + 浏览器验证（本次已执行）。

## frontend 工程师必读（避免踩坑）
1. **`index.html` 是生成物**：`template.html` 的 `__DATA__` 占位符由 gen.py 注入 4 配置运行数据后写出。**不要手改 index.html**，改 template 后跑：
   `~/aiworld/flylaya/laya-mlx-deploy/.venv/bin/python m4/mc_view/gen.py`
2. 本地服务：hub 进程 `mcview` → `http://127.0.0.1:8960/mc_view/`（root=m4/）。
3. 验证钩子：页面暴露 `window.__fly = {THREE, scene, camera, renderer, controls}`；顶视相机 `(50,260,50)` 采样地板像素应为绿色系（speckle 修复前是纯黑）。
4. 数据帧格式：`[t, x, y, z, yaw_deg, pitch, speed, intent_idx, conf, arousal]`，stride 2，A_full/B/C/D_random_intent 四键。
5. 已修的历史坑：InstancedMesh 不可用材质数组（地板曾因此消失）；speckle 数组/标量混用（材质全黑）；pitch 日志恒 0（数据本身如此，非渲染 bug）。

## 状态
- [x] speckle 修复（frontend）
- [x] index.html 重生成 + 像素级验证（coordinator）：地板绿 (71,117,52)，苔石/黑曜石高度分色正确，5 个 InstancedMesh 全部在场景，无新增 page error
- [x] 4 配置切换冒烟：A/B/C/D 全部正常加载（intent/conf/t/speed HUD 均更新；B/C conf=1.00 属 fixed/random 源特性）
- [x] 截图归档：artifacts/mc-view-final-A_full_11.jpg、mc-view-overhead-terrain.jpg
- 观察器可用入口：http://127.0.0.1:8960/mc_view/
