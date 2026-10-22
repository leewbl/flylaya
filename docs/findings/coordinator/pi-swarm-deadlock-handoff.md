# pi-swarm 死锁修复交接(对外 handoff)

- 交接文档(自包含):/tmp/pi-swarm-deadlock-handoff.md
- 证据快照:/tmp/pi-swarm-deadlock-evidence-20260924.tar.gz(70 文件,含 agents/*.yaml 唤醒配置现场)
- 上游 issue:https://github.com/leewbl/pi-swarm/issues/1
- 机械根因:agents/coordinator.yaml `wakeup.events=[task.opened]` 且 `taskAvailable:false` —— 唯一能开任务解锁的角色只被「自己才会发的事件」唤醒;决策请求类自定义事件不在任何角色唤醒白名单。订阅≠唤醒。
- 修复工作项 W1 决策请求可达 / W2 定时检查点 / W3 复验回滚 / W4 闲置容量,验收标准与最小复现脚本见交接文档 §3–§4。
