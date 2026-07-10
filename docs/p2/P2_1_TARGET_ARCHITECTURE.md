# P2.1 目标架构

正式主链固定为：

`IntelligenceSource(v04g_monitoring_sources)` → `CollectionJob(v04g_monitoring_runs)` → `EvidenceSnapshot(v04g_source_snapshots)` → `RawIntelligence(raw_intelligence)` → `FactCandidate(v05g_extraction_candidates)` → 人工审核 → `IntelligenceProduct(v06_intelligence_items)` → 信号/专题/报告。

网页路由和 `/api/v1` 只调用服务层。采集层只能写任务、快照、采集条目和标准化正文；规则或 AI 只能写候选；发布服务只接受已审核候选且必须建立产品—候选—快照关系。旧 URL 和表继续兼容读取。

P2.1 新增的表都是关联、运行审计或试点治理表，不是新的来源、任务、快照、候选或产品主表。

- `p2_fact_candidate_evidence`：候选与快照多对多证据定位。
- `p2_intelligence_product_candidates`：产品与获批候选多对多关系。
- `p2_intelligence_product_evidence`：产品与快照多对多引用。
- `p2_ai_analysis_runs`：AI/规则调用、结构校验和结果哈希审计。
- `p2_pilot_batches`：试点数据可识别、可清理的批次边界。
- `p2_intelligence_audit_log`：审核、合并、发布和证据关联状态变化。

本阶段不引入微服务、Scrapy、Crawlee、OpenSearch 或 PostgreSQL，不重跑历史数据，不自动批准候选。
