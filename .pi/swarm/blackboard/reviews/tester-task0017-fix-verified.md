# TASK-0017 修复独立复核(tester)

- 复核口径(建任务时定义):S1 双镜像 skeleton/sensory_only 下 mean_cos_to_light 相对基线改善且镜像对称。数据:m5/runs_fix17(backend 自测产物)。
- 结果:**通过**。S1L −0.84→**+0.90**、S1R −0.85→**+0.90**(镜像对称);pre/post 复核 +0.50→+0.98 / +0.50→+0.99(刺激后向光转);首次正确转向延迟 0.5–0.6s 两镜像一致。skeleton 光-DN 符号反转已消除。