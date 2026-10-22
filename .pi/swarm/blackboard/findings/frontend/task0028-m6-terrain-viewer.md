# TASK-0028 M6-W2 地形观察器交付 + terrain.v1 合同 (2026-09-26)

`m6/viewer/terrain_serve.py` + `terrain.html` + `m6/terrain/default_hills.json`,hub daemon `m6terrain:8965` 运行中。全部实测(0 page error)。

## terrain.v1 合同(供 W1 backend 对齐; 观察器按此渲染, 字段容错)
```json
{"schema_version":"flylaya.m6.terrain.v1","map_id","version",
 "size_m":[64,64],"block_m":0.5,"seed":20260926,
 "hills":[{"cx_m","cz_m","r_m","h_m"}],
 "water_level_m":1.2,"water_regions":[{"cx_m","cz_m","r_m"}],
 "trees":{"count":60,"min_h_m":1.5,"avoid_water_r_m":4},
 "sun":{"azimuth_deg","elevation_deg","intensity"},
 "sky":{"fog_near_m","fog_far_m"}}
```
run 数据沿用 flylaya traj schema(t_s/pos_m/yaw_deg/speed_m_s/intent_applied/arousal/dn),坐标自由(米)。W1 的 m6/runner.py 出现后 /api/live 自动接管(同 bench_serve 流式协议);run 目录带 terrain.json 即随 run 切换地形。

## 功能(实测)
- **地形渲染**: 高斯山丘→草/石/雪分层方块(2.2m/6m 阈值),水碗半透明,树=木干+树冠,太阳方块+平行光,雾;全部 InstancedMesh(1.6万+块)
- **小地图**: 180px 俯视高度着色+水/树+意图色尾迹+蝇白标(实测非空 100%)
- **DEMO 探索**: 客户端确定性地形感知走查(悬高 gh+1.4m,明示非仿真)— 验证地形跟随/意图循环/DN 图层
- **回放**: m6/runs* 索引,select 聚焦自动刷新新 run;seek 实测 50%→15.0s/98%→29.3s;夹带 fixture `m6/runs_demo/fly_1`(自检用)
- **LIVE**: W1 缺位时 501+页面 toast 提示(实测);就绪后流式播放,落盘 runs_bench_live/
- 视角 侧/俯/跟随;DN 4 条实时;意图名牌+彩色尾迹

## 待 W1 落地后
1. 用真实 run 重放验证(合同字段若变,改 terrain_serve.find_spec 容错层)
2. live 真跑一次(runner CLI 参数对齐)
3. 蝇尺寸/速度按 W1 动力学定标(现在 DEMO 0.5m/s, 尺寸×8×0.14)
