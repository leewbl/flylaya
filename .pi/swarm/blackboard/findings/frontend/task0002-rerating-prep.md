# TASK-0002 准备就绪:新 A 重盲评管线 + 一致性复算 (2026-09-25)

状态:准备项全部完成并验证;**等待**(1) TASK-0001 新 A 批量数据 (tester in_progress) (2) 用户组织 ≥3 评分者。block 标记因 swarm_task_block 设备缺陷暂无法写入(已报 xd://report_issue),语义上 TASK-0002 = blocked-on-TASK-0001 + 人工评分。

## 交付物

### 1. `m4/rating/consistency.py` — 一致性/显著性复算
对旧 3 评分者 JSON(csx/lee/xixi)复算,**终报 §1/§1.2 全部数字逐项复现**:

| 指标 | 终报 | 复算 |
|---|---|---|
|A 被选|59/60=98.3%|✓|
|均分 A/B/C/D|4.22/1.55/1.00/1.33|✓|
|分评分者|csx 20/20 (4.20), lee 20/20 (4.55), xixi 19/20 (3.90)|✓|
|全一致 trials|19/20|✓|
|Gwet AC1|0.966|✓ (0.966)|
|Fleiss κ|−0.017|✓ (−0.017)|
|csx−lee Cohen κ|1.000|✓(完全一致+退化边际的约定 κ=1)|
|A−B 配对差|2.74, t(41)=18.4|✓|

勘误:终报写「双侧二项 p=5.3e-17」实为单侧;双侧=1.06e-16。脚本两者都输出。κ 悖论结论不变(主指标 AC1)。

用法:`python3 m4/rating/consistency.py 'm4/rating/flylaya_rating3d_*.json'`(glob 可混新旧)。

### 2. `m4/rating3d/gen.py` 参数化
`--manifest/--runs-dir/--out`,默认行为与旧版**逐字节一致**(已 cmp 验证)。新 A 管线 3 步已写入 gen.py docstring:manifest_gen.py 出 manifest → gen.py 生成自包含页 → consistency.py 复算。

### 3. 盲评页验证(headless Chromium, /rating3d/?rater=smoketest)
- 0 页面错误;双视窗回放正常(clock 推进,canvas 841×825)
- 完整一轮:评分 4/2 + 强制选左 + 下一对 → trial 2/20;localStorage 记录 schema 与 consistency.py 输入完全一致
- 盲化:可见 DOM/文案无配置名(仅 左/右);truth 只存在于导出 JSON/localStorage(设计如此,页面有勿看警告)

## 下一步(数据到位后)
1. TASK-0001 产出新 A runs → 按 gen.py docstring 三步生成 `rating3d/index_newA.html`
2. 用户组织 ≥3 评分者(建议复用 csx/lee/xixi;导出 JSON 存 `m4/rating/`)
3. `consistency.py` 合并复算 → 对比旧 98.3%/AC1 0.966,验证迭代①后 A−B 人类分离是否弱化