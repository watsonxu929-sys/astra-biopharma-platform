# P2.2 AI质量评测设计

金标位于 `evaluation/p2_2/gold_samples.jsonl`，共10条公开FDA监管样本。标注字段包含事件类型、机构、人物、产品、适应症、靶点、金额、日期、地区、阶段、重要性、证据片段和不确定项。

指标由 `app/services/evaluation_service.py` 计算：事件准确率、机构/人物P/R/F1、关键事实准确率、证据覆盖率与正确率、幻觉率、可审核率、采集/解析/AI延迟和单条成本；空样本不除零。

Rule、AI、Hybrid使用同一金标。无Key时AI与Hybrid标记 `not_run`，不以Mock或Rule冒充。真实AI最多20次、批次预算默认5美元、临时错误最多一次退避、schema最多一次修复。AI只生成候选，不发布或修改主档。
