# P2.3 当前研究能力审计

审计日期：2026-07-13。依据实际路由、服务、模板和正式库只读查询，不按文档推测。

| 能力 | 实际入口/结构 | 当前结论 |
|---|---|---|
| 专题列表与详情 | `/research`、`/research/topics`、`/research/topics/{id}`；`research_topics` | 页面和CRUD入口真实存在，但正式库专题为0，详情目前是统计面板而非完整工作区。 |
| 专题主体 | `research_topic_subjects` | 可加入/移除企业、人物、项目；缺产品类型、研究问题和事件关联。 |
| 专题快照 | `research_snapshots` | 只保存计数与松散JSON，不保存事实、发现或引用版本。 |
| 企业比较 | `/research/companies/compare`、`compare_companies` | 可运行，但维度偏基础；产品管线、临床阶段、证据数与可靠缺失提示不足。 |
| 赛道分析 | `/research/tracks` | 基于企业标签、旧事件和信号做轻量统计；不是多来源事实融合。 |
| 专题时间线 | `/research/topics/{id}/timeline` | 直接聚合旧 `events` 和 `signals`；未限定为审核后的正式产业事件。 |
| 报告中心 | `/reports`、`v05h_generated_reports` | 草稿、审核和发布入口真实存在；正式库报告1条。 |
| 报告引用 | `citations_json` | 主要是松散JSON与末尾引用，不能保证每个结论逐层追溯到Snapshot。 |
| 产业信号 | `/signals`、`v05e_industry_signals` | 真实可用，正式库1条；可关联快照/事件，但不等同正式研究事实。 |
| 旧事件 | `events` | 正式库6条，5条“已确认”；内容以俱乐部活动为主，不应用于P2.3生物医药试点。 |
| P2证据链 | Candidate → RawIntelligence → EvidenceSnapshot | 真实存在；正式库候选0、Raw 1、Snapshot 2，样本不足但链路可复用。 |
| 正式情报产品 | `v06_intelligence_items` | 正式库20条，可作线索入口；没有统一FactAssertion或多来源事件层。 |
| 主体主档 | organizations/people/projects | 分别24/44/5条；产品仍分散在项目、事件、情报字段中。 |

当前断裂点：候选审核后缺少多来源 IndustryEvent 与 FactAssertion；冲突无法在研究页并列裁决；ResearchFinding 未区分事实、推断、观点和假设；报告段落与证据不是规范化多对多关系；删除或改版报告时缺少独立版本链。

P2.3采用增量兼容层：保留v05J专题和v05H报告作为现有入口，新增研究融合表与服务，不重建主体、证据或报告系统。
