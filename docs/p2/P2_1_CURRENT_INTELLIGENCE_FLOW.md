# P2.1 当前情报主链审计

审计日期：2026-07-10。审计方式：代码、路由、导航注册表与正式数据库只读统计；测试使用数据库副本。

## 当前主链

| 阶段 | 当前正式存储/服务 | 结论 |
|---|---|---|
| 来源 | `v04g_monitoring_sources` | 复用为 IntelligenceSource；已覆盖 RSS/API/网页/列表/动态页/手工 URL、频率、启停和健康信息。 |
| 采集任务 | `v04g_monitoring_runs` | 复用为 CollectionJob；已有调度、运行状态、计数、错误和重试次数。 |
| 原始证据 | `v04g_source_snapshots` | 复用为 EvidenceSnapshot；保存 URL、抓取时间、HTTP 状态、原始 HTML、清洗文本、哈希和前一版本。 |
| 采集条目 | `v05f_collection_items` | 作为去重、变化检测和处理排队视图，不再承担正式证据语义。 |
| 标准化正文 | `raw_intelligence` | 复用为 RawIntelligence；现有字段不足，需增量增加 snapshot、哈希、语言、内容类型和处理状态。 |
| 解析任务 | `v05g_processing_jobs`、`v05g_processing_blocks` | 已按快照拆块，并保存正文字符起止位置。 |
| 事实候选 | `v05g_extraction_candidates` | 复用为 FactCandidate；规则候选已进入审核队列，需补生成者、模型/规则版本与证据关联。 |
| 审核 | `v05g_candidate_review_history`，兼容 `v04c_review_items` | 已保存审核人和时间；旧候选通过后还会转入旧审核项，形成二次队列。P2.1 以候选审核历史为主审计链。 |
| 正式产品 | `v06_intelligence_items` | 复用为 IntelligenceProduct；已有 raw 来源标识，但发布入口没有强制候选审批和结构化证据关系。 |
| 信号 | `v05e_industry_signals`、`v05h_signal_evidence` | 由已确认事件和规则生成，证据表已存在但当前数据关联稀少。 |
| 专题与报告 | `v05j` 研究主题、`v05h_generated_reports` | 报告保存 `citations_json`，可追溯性依赖松散 JSON，尚未统一到产品证据链。 |

## 保存、去重与解析

- 原始 HTML 和清洗 HTML 均保存在 `v04g_source_snapshots`；附件尚无正式路径字段。
- 同一来源 URL 的相同 `content_hash` 复用旧快照；URL 内容变化时通过 `previous_snapshot_id` 新建快照。
- `v05f_collection_items` 通过规范化 URL、内容哈希和 `duplicate_of_item_id` 标记 unchanged/duplicate/changed。
- HTML 正文使用 BeautifulSoup；处理层按页面结构拆块，规则提取机构、人物、项目、事件、关系、字段等候选。

## 断链与重复

1. 快照原始字段没有数据库级不可变约束，未来代码可能误覆盖。
2. `raw_intelligence` 未关联快照，清洗正文不能可靠回溯原始证据。
3. 候选虽有 `snapshot_id` 和摘要，但没有多证据、页码/表格/定位器关系。
4. `publish_from_raw` 可绕过候选审核直接发布，正式产品没有候选及快照多对多关系。
5. AI/规则输出缺少统一 provider、model、prompt/rule version 和结果哈希审计。
6. 旧 `v04c` 审核与 `v05g` 候选审核并存；P2.1 保留兼容入口但不再新增第三套队列。
7. 情报二级菜单已集中注册，但“企业动态/产业信号”、情报运营/管理入口存在同路由或高重叠入口。

## 正式数据库只读基线

审计时主要记录数：来源 3、采集任务 6、快照 2、采集条目 1、处理任务/块/候选均 0、旧审核项 8、RawIntelligence 1、正式情报产品 20、产业信号 1、报告 1。P2.1 不批量迁移这些历史记录。
