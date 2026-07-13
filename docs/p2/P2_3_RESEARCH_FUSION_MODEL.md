# P2.3 研究融合领域模型与流程

## 复用边界

P2.3 继续复用 `research_topics`、`research_topic_subjects`、`v05h_generated_reports`、`v05g_extraction_candidates`、`raw_intelligence` 和 `v04g_source_snapshots`。005 迁移只增量增加研究融合所需字段和关联表，不建立第二套企业、人物、项目或证据模型。

## 正式模型

- ResearchTopic：持续研究主题，增加研究范围、关键词、主体范围、负责人和试点批次。
- IndustryEvent：经人工审核的正式产业事件；一个事件可关联多个主体、候选和证据。
- FactAssertion：对主体、谓词、对象/数值、有效时间和证据的结构化陈述。
- FactConflict：并列保存冲突值、双方证据、采用值、理由、审核人和审核时间；不静默覆盖。
- ResearchFinding：严格区分 verified_fact、inference、analyst_opinion、hypothesis、conflict。
- ResearchReport：复用报告主表，增加专题、研究状态、报告类型、引用完整率和版本字段。

## 融合规则

确定性分类输出 `same_event`、`related_event`、`duplicate_report`、`update_event`、`conflict` 或 `unrelated`。特征包括主体、事件类型、产品、日期间隔、标题、正文和地区。涉及同事件、后续进展或冲突的候选必须进入人工确认；AI 不自动合并高风险事件。

## 审核门

- 无证据的事件不能提交审核。
- 有未解决冲突的事件不能通过。
- 只有 approved/published 事件能进入正式时间线和专题。
- verified_fact 只能引用已通过的 FactAssertion。
- 报告只读取已通过的研究发现；事实和推断章节必须有结构化引用。
- 报告状态为 draft → pending_review → needs_revision/approved → published。
- ResearchAgent 只读取已审核事实并生成 draft，记录 provider、model、prompt version、输入事实 ID 和输出哈希。

## 引用链

`ResearchReport → ResearchFinding → FactAssertion / IndustryEvent → FactCandidate → RawIntelligence → EvidenceSnapshot`。当前试点从既有 RawIntelligence/EvidenceSnapshot 起链；候选关联表保留用于后续人工把现有候选接入事件。
