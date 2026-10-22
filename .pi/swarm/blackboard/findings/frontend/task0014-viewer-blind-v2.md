# TASK-0014 M5-W5 观察器/盲评 v2 交付 (2026-09-25)

`m5/viewer/` 新建三件套,全部验证通过,spec §8 逐条落地:

## 文件
- `build.py` — 离线构建器:`--runs-dir m4/runs --n-trials 20 --seed 7` → `index.html`(诊断)+ `blind.html`(盲评)+ `blind_key.json`(真值钥匙,页面零引用)。兼容 m4 jsonl 与 m5 trajectory 合同(可选 `dn` 帧 dict + `{name}.events.jsonl` 刺激事件 sidecar,m5 W3 落地后即插即用)。
- `template.html` — 单引擎双模式(`__MODE__`):俯视/侧视预设、统一比例尺、同步时间轴、刺激事件红标(诊断)、DN/意图图层(诊断)、镜像切换(两模式)、FREEZE 冻结块(FOV/相机/光照/尾迹/帧率=真实速率 5 帧/s/像素比)。
- `aggregate.py` — 导出复算:training 丢弃、Q1(任务判断)/Q2(方案间偏好,无真实参照不称拟真)分列、一致率+Gwet AC1 主指标+Fleiss κ 附报、pairwise、二项检验、按唯一 clip 对+评分者聚类披露、导出文件真值泄漏审计。

## 反泄漏设计(全部实测)
- 匿名 clip id = sha256(salt:run)[:10];blind 帧仅前 6 列几何/运动学
- 文件级审计:blind.html 无 config/seed/brain/intent_source/run 名/.jsonl/blind_key 引用(仅静态 INTENTS 词表常量,不绑定数据)
- 运行时:`window.DATA` 不可达(module 作用域);可见 DOM 无配置名
- 导出审计:aggregate.py 对导出 JSON 做字段泄漏检查 → NONE
- 按评分者随机:顺序(训练题固定在前,正式题内乱序)+ 左右,seed=salt+rater;实测两评分者首题 tid 不同
- 训练题 2 道(紫标「训练题」),导出带 training 标记

## E2E 验证(headless Chromium)
- 双 raters 完整 22 对评分 → 导出 → aggregate.py 复算出 AC1/κ/聚类(合成点击,验证机制非结论)
- 诊断模式 0 error:名称/意图 HUD/事件/DN 正常
- 合成 m5 数据(带 dn+events)验证:DN 值逐帧显示、事件红标位置=t/时长 精确(16.8/41.3/67.4% = 5/12.3/20.1s of 30s)
- 俯视↔侧视、镜像开关正常;盲评 gating(四项输入齐才可下一对)

## 使用
```
python3 m5/viewer/build.py --runs-dir <runs> --n-trials 20 --seed 7
# 盲评: http://127.0.0.1:8962/m5/viewer/blind.html?rater=<名字>  (m5view daemon, 根=仓库根)
# 诊断: .../index.html?rater=<名字>
# 回收后: python3 m5/viewer/aggregate.py --key m5/viewer/blind_key.json <导出json...>
```
注意:blind_key.json 严禁发给评分者;诊断页导出含文件名,不得混入盲评数据。

已知边界:Q2 判断页依赖 build 时 `--has-real-reference` 开关切换拟真/偏好文案;真实果蝇参照未取得(本批无)。
