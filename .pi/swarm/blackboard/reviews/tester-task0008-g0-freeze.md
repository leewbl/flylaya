# TASK-0008 完成:M5-G0 冻结旧资料

- 测试者:tester(instance tester-01m3cd7byme0r7d00qsp50n1ns)· 2026-09-25
- 归档提交:myylaya@471b431;canonical 报告:docs/reviews/flylaya-m5-g0-freeze.md

## 结果

1. **分目录+manifest**:四批(m4/runs 旧 40 段、runs_iter1params 新 40 段、iter1_confirm 3、iter1_smoke 1)各生成 manifest.json——逐文件 sha256/行数(内容级)/场景 meta 哈希/代码树 14 文件指纹/决策服务指纹(serve.py 哈希+2 确定性探针+HF 模型目录指纹)/批次窗口/env。生成器 m4/make_manifest.py。索引 m4/BATCHES.md。
2. **旧盲评历史标注**:m4/rating/PROVENANCE.md;3 份 rating3d JSON 与 myylaya@5a68024 逐字节一致(已校验);98.3%/AC1=0.966 标记「基于旧 A」;原始评分 JSON 未改动。
3. **重批完整性**:40/40 内容级校验通过(3001 行/段、seed 齐全、stats↔文件一一对应);批作业日志无一条 skip existing;批次窗口与日志时间线吻合。

## 追溯闭环

旧数字→flylaya-m4-v1params-40→stats sha256==myylaya@5a68024;新数字→flylaya-m4-iter1params-40→myylaya@471b431。旧批运行时代码无 VCS 快照(manifest notes 声明,行为锚=归档 stats 哈希);新批树哈希即运行树(TASK-0006 批中编辑零影响证据在 notes)。

**G0 验收通过,后续任务可进 G1。**