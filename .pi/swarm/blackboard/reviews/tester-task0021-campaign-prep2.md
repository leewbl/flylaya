# TASK-0021 备战资产补齐:盲评渗透检查器(tester)

- m5/campaign/blind_leak_check.py:扫描评分者面(blind* 文件;构建器/诊断模式按设计合法含真值,默认排除,--all 全扫)。四规则:禁引 *key*.json、禁策略/配置/场景/实验 token、嵌入行字段白名单(仅运动学/几何)、真值钥匙离线在位。**正反验证通过**:现行 m5/viewer/blind.html 判 PASS;注入 P_laya 负对照精确检出。战役 T4:45 窗口「盲评包渗透检查」工具就绪。
- 至此 0021 三件执行资产齐:gate_f_check(等 PHOTO_I 修复后正式复跑)/run_campaign(种子域+yoked 纪律)/blind_leak_check。封存种子仍锁定。