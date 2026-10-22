# FlyLaya 实验：果蝇连接组 × Laya 意图决策拟真实验计划

- researcher 制定 · 2026-09-24 · 工作目录 /tmp/flylaya（数据引用 ~/aiworld/MaleCNS，Laya 服务 localhost:8000）
- 假设：最大似然校准决策模型（Laya）作意图层 + 生物连接组作传感运动层，组合可逼近真实果蝇行为；实验测定其拟真度上限

## 1. 系统架构

```
3D 世界（1m³ 场地：障碍柱、阳光方向、可选气味源）
   │ 感观：复眼抽象 → R1-R6 亮度向量（MaleCNS Sim 驱动接口）
   ▼
果蝇连接组全图 LIF（166,700 神经元，DOOMFLY Metal 内核，0.93×实时，100ms/帧）
   │ 读出：DN 下行神经元频率（DNp20_L/R 等 manifest readouts）
   ▼
运动映射：DN 差分 → 偏航/推力/俯仰 → 位姿积分（帧内子步插值）
   ▲                                    │
   │ 意图调制（增益/偏置按 Laya choice 切换）  │ 每 2-5 帧一次
   └── Laya（mlx-serve /v1/systemone）◄── 状态编码为文本 state
       choice: {趋光, 避障优先, 探索巡航, 边界规避, 悬停休息}
       score: 唤醒度（调制整体运动增益）
```

关键约束（已实测）：16GB RAM → 全图 892MB/实例 → 批量仿真串行或最多双并发；10×5min@0.93× ≈ 54min。浏览器只做渲染（three.js + websocket），仿真在服务端。

## 2. 里程碑

- **M1 世界与回路骨架**（backend）：3D 场地+障碍+光照；复眼→R1-R6 编码；DN→运动映射；FastAPI+websocket 服务；three.js 交互查看器（轨迹带、HUD：意图/置信度/尖峰频率/DN率、暂停/变速/相机/种子）
- **M2 全连接组 × Laya 闭环**（backend）：接入 libneural 全图；Laya 每 200-500ms 意图决策（调 laya-serve）；意图→通路增益调制矩阵；确定性种子
- **M3 评估三件套**（tester）：①轨迹统计模块（飞行段长度/转角分布 saccade、速度谱、趋光角分布、避障边际、空间利用热图）②文献基准值收集（van Breugel & Dickinson 2014、Mronz & Lehmann 2008 等 + MaleCNS 论文 LIF 实验参照）③消融配置：A=完整系统 B=无Laya(固定意图轮换) C=无连接组(Laya直控运动) D=随机意图
- **M4 批量与交付**（tester+researcher）：10 种子×5min×4 消融=40 段仿真（串行，~3.6h）；交互页+回放（浏览器 MediaRecorder 导出 mp4，10 段 5min 完整系统回放）；人类评分表（A/B/C/D 盲评随机回放）；researcher 终报（拟真度三口径结论）

## 3. Laya 意图层规范（researcher 维护）

state 文本模板（每例）：位置分区、最近障碍方位距离、阳光方位与视线夹角、当前速度、上次意图、唤醒度。意图集 ≤6 类、互斥明显（R3/R5 教训）；已知风险：Laya 零样本模糊类高置信错误——意图描述词要行为化、避免抽象近义词。

## 4. 拟真度判定（三口径合一）
1. **轨迹统计对照**：每指标给文献区间 vs 四消融实测，卡方/KS 检验
2. **人类盲评**：随机成对回放（A vs B/C/D），五点量表（像真果蝇吗）
3. **消融增益**：完整系统相对 B/C/D 在口径 1/2 的提升量 = Laya×连接组各自贡献

## 5. 诚实预期（researcher 判断）
MaleCNS 复现验证的是网络统计量，非「驱动即得真实行为」；R1-R6 抽象视觉 + DN 线性读出是强简化。实验的真实产出是**量化这条路径的天花板与失败模式**，而非证明拟真必然成功。

## 6. 任务映射
TASK-M1→backend（p60）TASK-M2→backend（p55，依赖M1）TASK-M3→tester（p50）TASK-M4→tester（p45，依赖M2+M3）；researcher 全程：意图集/编码规范先行（M1 内交付）、逐里程碑验收、终报。