# PROVENANCE — 历史盲评批（勿混入新战役）

- 标注时间：2026-09-25 · TASK-0008（M5-G0 冻结旧资料）

## 本目录内容 = 历史批

- `flylaya_rating3d_{csx,lee,xixi}_*.json`：3 份评分（3 评分者 × 20 对），**基于旧参数 A 轨迹**
  （回放源 `m4/replays/` ← 旧批 `m4/runs/`，experiment_id `flylaya-m4-v1params-40`，见
  `m4/runs/manifest.json`）。
- 结论「A_full 被选 59/60=98.3%，Gwet AC1=0.966」**基于旧 A（tau=1.0/eps=0.0，avoid 塌缩版）**。
  新参数 A（`flylaya-m4-iter1params-40`，tau=1.6/eps=0.06）**未经重新盲评**——引用 98.3% 时必须注明。
- 依据：HANDOFF.md §2、终报 §7、docs/reviews/flylaya-m4-rerun-iter1params.md（口径 2 注记）。

## 追溯锚（内容寻址）

| 文件 | sha256 | 归档锚 |
|---|---|---|
| flylaya_rating3d_csx_1790348146368.json | 3dff2d5f586959733a8f8834ad09fbe4add298535a60320b0e87ad1427aa22f4 | myylaya@5a68024 |
| flylaya_rating3d_lee_1790348540093.json | a840d3a71dc49ec19bd0721cae9c3be997342b11cbd953be21107672c36e1b9f | myylaya@5a68024 |
| flylaya_rating3d_xixi_1790347587738.json | e33b0f8a6d644ef918c0716ecf290b092130417abeb470afbdf943acbb5f972c | myylaya@5a68024 |

三份文件与 `git -C myylaya show 5a68024:reports/findings/flylaya-rating/<name>` 逐字节一致（2026-09-25 校验）。

## 注意

- 本目录 JSON **含真值标签**（manifest.json 的 truth 字段），不得在评分者可见处展示（HANDOFF §8.2）。
- 新版盲评（新 A + matched yoked 对照）见设计文档 §8：观察器从冻结轨迹生成，两问题分离，勿复用本 manifest。
- `consistency.py`、`manifest_gen.py` 为分析工具，不属于评分数据。
