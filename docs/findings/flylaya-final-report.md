# FlyLaya 三口径终报（TASK-0018 收口）

- 撰写：coordinator（instance coordinator-01m3ccf…sryh）· 2026-09-25 · 数据全部来自已归档交付
- 结论一句话：**三口径一致指向——连接组决定运动学形态，Laya 意图层是行为拟真度的关键增量；但绝对拟真度（文献口径）仍低，系统处于「相对拟真已证、绝对拟真未达」阶段。**

## 0. 系统与数据

四配置消融（各 10 种子 × 300s × 10Hz，共 40 段 0 失败）：A_full（connectome+Laya）/ B（connectome+固定意图）/ C（skeleton+Laya）/ D（connectome+随机意图）。
批量与统计：`reviews/flylaya-m4-batch-results.md`；自旋修复复验：`reviews/flylaya-m2-refix-verification-spin-rootcause.md`（ω p50 344→77dps，>300dps 0%）。

## 1. 口径 2：人类盲评（本次新增，3 评分者）

**方法**：3D 盲评页（`m4/rating3d/`，Minecraft 风格方块世界双视窗）：每对左右两个 run 的完整 300s 轨迹同步回放，评分者可自由旋转/缩放视角；界面不含配置名/意图/速度数值（盲化）。每对双 5 点量表（各自拟真度）+ 强制二选一。20 对（A_full 20 出现、B 14、C 3、D 3），配对与 2D 页 manifest 同源。
**评分者**：csx / lee / xixi，全 20 对完成，导出 JSON 存 `m4/rating/`。

### 1.1 结果

| 配置 | 被选率(合并) | 平均分(n) |
|---|---|---|
| **A_full** | **59/60 = 98.3%** | **4.22** (60) |
| B_no_laya | 1/42 = 2.4% | 1.55 (42) |
| C_no_connectome | 0/9 | 1.00 (9) |
| D_random | 0/9 | 1.33 (9) |

分评分者：csx 20/20 选 A（4.20）；lee 20/20（4.55）；xixi 19/20（3.90）——**三位独立评分者中两位零失误识别 A**。

### 1.2 一致性与显著性

- 全一致 trials：19/20；两两选择一致率 95–100%
- **Gwet AC1 = 0.966**（prevalence 稳健）；两两 Cohen κ：csx−lee = 1.000
- **Fleiss κ = −0.017（κ 悖论，如实报告）**：边际分布极端偏斜（98% 选 A）使 chance 一致率 P̄e≈P̄o≈0.967，κ 被压到 0 附近——κ 在高偏斜/高一致并存时失效，AC1 与原始一致率才是有效读数
- A 被选 59/60：双侧二项检验 **p = 1.06e-16**（勘误 2026-09-25：原写 5.3e-17 为单侧值，frontend consistency.py 复算发现；结论不变）
- A−B 评分配对差：**2.74 分**，t(41) = 18.4

### 1.3 结论

**A−B 人类分离是极端的**（98% vs 2%，评分差 2.7 分）：Laya 意图层带来的行为差异（活动量、空间利用、rest 压缩）不仅统计可分（口径 3），而且**肉眼一票可辨**。B/C/D 全部落在"完全不像"档（1.0–1.6）。

## 2. 口径 3：消融增益（统计口径，引自批量报告）

- **A−B（Laya 在连接组上）**：可分离（speed KS D=0.394、ω D=0.192、sacc_amp D=0.206，p<1e-3）；rest 21%→1.4%、占用 32%→37%
- **A−D（意图序列信息量）**：幅度与 A−B 相近（speed D=0.394；occ 0.37 vs 0.225）
- **B−D（内容 vs 节奏）**：全分布不可分（ω p=0.24、heading p=1.0）——连接组主导下意图内容与节奏均不构成差异源
- **C−其余（连接组贡献）**：最强分离（speed/ω D 0.5–0.71）
- A 内部：arousal-speed r=0.671（规范 >0.3 达标）

口径 2 与口径 3 互相印证：B≈D（统计不可分 + 人类同判"不像"），A 独立可辨。**人类分离(98%)比统计分离(D=0.39)更极端**——活动量/rest 这类积分量对人类观察者比逐帧分布更显著。

## 3. 口径 1：轨迹统计 vs 文献基线

全配置 1–2/7 指标落入文献区间（首种子判定，逐段在 stats json）：
- **未达**：saccade 率 0.05–0.07Hz vs 0.2–2Hz（INFERENCE 标注区间）；saccade 幅值 32–34° vs ~120°；speed 12–14cm/s vs 20–60；直度超区间
- **达标项**：rest 占比、空间占用类（A 配置）
- connectome 系无趋光（sun_R≈0.03–0.04）而 skeleton 有（0.527）——R1-R6→DN 通路丢太阳方位信息
- z 全配置恒 49cm（垂直反射钉中线），无垂直探索

**判定：绝对拟真度低——「轨迹统计意义上的果蝇相似度」未达文献口径**，与实验计划 §5 的诚实预期一致（量化天花板与失败模式即产出）。

## 4. 失败模式章节（根因链）

1. **自旋吸引子（已修复）**：DNp20 读出偏置 × 旧 YAW_GAIN=1.6 饱和 → ω 344–550dps 旋转吸引子；修复=增益 0.3 + 视觉不对称 DC 去除 → ω p50 77dps（`reviews/flylaya-m2-refix-verification-spin-rootcause.md`）
2. **B−D 不可分离**：意图作用于主导通路（连接组）时内容无效——Laya 价值只在增益调制改变积分行为处显现（活动量/占用），需让意图作用到非主导通路（调制深度）才能产生内容敏感性
3. **意图切换率 0.0033Hz**（spec 0.1–1Hz，差两个数量级）：1s 滞留护栏 + Laya 选择保守 + state 变化慢三因素叠加（researcher 迭代方向：`findings/flylaya-intent-spec.md`）
4. **saccade 节律缺失**：yaw 映射无快速瞬态或 DN 读出时间常数过长
5. **connectome 趋光性≈0**：亮度→DN 映射丢太阳方位；skeleton 脑保留（sun_R 0.527）证明感官侧信息存在、读出侧丢失
6. **盲评 κ 悖论（方法论）**：非系统 bug；后续盲评若任务再如此极端偏斜，主指标应预设为 AC1/原始一致率

## 5. 下轮迭代建议（优先级序）

1. **意图切换率**（第一优先）：温度采样/滞留护栏调参/state 编码增扰动，目标 0.1–1Hz——直接决定 Laya 决策动态是否可见
2. **意图→非主导通路**：增益调制深度作用于 thrust/yaw 噪声结构而非仅光/障碍增益，制造 B−D 可分性
3. **saccade 瞬态**：DN 读出加高通/短时程通道，目标率 0.2–2Hz、幅值向 120° 靠拢
4. **趋光读出**：修复亮度→DN 方位保持，让 connectome 系 sun_R 从 0.04 → ≥0.3
5. **z 探索**：垂直反射改软偏置，放开 49cm 钉死
6. 小修：FixedIntentSource 词表过期（M1 旧 4 类，FLYLAYA_INTENT=fixed 静默回退 explore）

## 6. 交付物索引
| 项 | 位置 |
|---|---|
| 40 段批量 + 全指标 | `m4/runs/`（stats_metrics.json / stats_tables.md） |
| 回放视频 20 段 | `m4/replays/` |
| 2D 盲评页 / manifest | `m4/rating/` |
| **3D 盲评页**（本次实际使用） | `m4/rating3d/`（template.html / gen.py / index.html） |
| 3 份评分 JSON | `m4/rating/flylaya_rating3d_{csx,lee,xixi}_*.json` |
| 口径 1/3 明细 | `docs/reviews/flylaya-m4-batch-results.md` |
| 文献基线 | `m3/literature_baselines.{md,json}` |
| 本报告 | `docs/findings/flylaya-final-report.md` |

## 7. 迭代①追加（2026-09-25，终报后执行）

意图切换率修复（spec v1.1 state 前置性短语 + ε 探索非 rest + τ=1.6 + avoid 逃离偏置，env 旋钮默认关）：
- switch_hz 0.0033 → **0.50–0.56**（3 种子 × 300s 稳定，进 0.1–1 spec 区间）
- 意图分布 2/5（avoid 98.9%）→ **5/5**（avoid 27–33%，无类 >80%）
- 护栏：ω p50 97–108dps、arou_r 0.43–0.52、speed_p50 12.2 均保持
- **代价**：A−B 运动学分离弱化——speed KS D 0.394→0.178，ω/rest 分离消失（新 A 的 rest 0.19–0.24 ≈ B 0.207）；旧 A 的"超活跃"签名本是 avoid 塌缩产物。§2 的 98% 人类偏好结论基于旧 A，新 A 需重盲评复验
- 待决：全量 40 段重批 + 新 A 重盲评（researcher 决策）
- 证据链与逐档冒烟记录：黑板 `findings/coordinator/iter1-intent-switch.md`；数据 `m4/iter1_{smoke*,confirm}/`

## 8. 勘误 2（2026-09-25，M5 诊断批发现）

§3 与 §4-5 中「C（skeleton+Laya）趋光显著（sun_R 0.527）」的解读**不成立**：
M5 接口诊断批（`m5/report/diag-phase1-report.md`）以有符号指标复核——skeleton 脑光→DN 存在
镜像对称信号（左光 ΔDN(R−L)=−0.28、右光 +0.30），但两镜像航向均**转离**光源
（mean_cos_to_light +0.50→−0.84）。sun_R 是集中度度量，反号定向同样产生高 R；
0.527 实为「稳定背光」的伪影。根因是亮度不对称→DN 映射符号反转（修复任务 TASK-0017）。
受影响结论：口径 1 的"skeleton 保留趋光"条目、§6 失败模式 5 的对比表述。
