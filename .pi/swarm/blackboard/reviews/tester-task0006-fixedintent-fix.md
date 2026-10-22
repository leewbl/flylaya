# TASK-0006 复审:FixedIntentSource 词表过期修复

- 测试者:tester(instance tester-01m3cd7byme0r7d00qsp50n1ns)· 2026-09-25
- 变更:flylaya/brains.py(FixedIntentSource)、flylaya/server.py、flylaya/intent.py

## 事实核对(与任务描述的出入)

- 任务前提「仍是 M1 旧 4 类词表」在当前工作树**已过时**:brains.py:145 的 INTENTS 字面量已是 5 类(HUD 实测 35s 五类轮转正常)。
- 真实缺陷三件:①词表是独立字面量,与 intent.INTENTS 双源,曾经漂移(任务描述即证据);②FLYAYA_INTENT=fixed 时 FLYLAYA_INTENT_LOG 被完全忽略,intent_log 文件不创建;③回退(explore 增益/固定轮转)全部静默无 warning。

## 修复内容

1. brains.py FixedIntentSource:词表单一源自 intent.INTENTS;新增 log_path 参数,轮转帧写 jsonl({t, source:"fixed", frame, intent, applied})。
2. server.py:FLYLAYA_INTENT 非 laya/fixed 时 logging.warning 后回退 fixed;FixedIntentSource 接 FLYLAYA_INTENT_LOG。
3. intent.py modulation_for:未知意图回退 explore 增益前打一次 warning(每未知值一次,不刷屏);增益数值不变。

## 验收证据

- FLYLAYA_INTENT=fixed 起服务(8100)+ws 客户端 35s:intent_log 12 行、5 类齐全、source=fixed 显式标注;HUD 直方图修复前后逐项一致(79/90/60/60/60,确定性轮转)。
- FLYLAYA_INTENT=bogus_mode:服务日志出现 `WARNING ... falling back to fixed rotation`。
- modulation_for('bogus_intent'):WARNING 一次,返回增益==explore 基线(行为不变);已知意图 phototaxis 数值不变。
- 回归:30s 冒烟(种子 11)B/D 两配置 jsonl 与修复前**逐字节一致**(cmp IDENTICAL),表行全同;A/C 差异属 laya 实时采样非确定性,非回归。

## 结论

验收通过。canonical 记录:docs/reviews/flylaya-task0006-fixedintent-fix.md。
注意:本修复与 TASK-0001 重批并发进行;已核实 FixedIntentSource 不在任何批量配置路径上,B/C/A 段轨迹不受影响(B/D 逐字节一致为证)。