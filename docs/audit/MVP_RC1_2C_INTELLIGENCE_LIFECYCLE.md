# MVP-RC1.2C 情报生命周期代码事实审计

## 结论

情报采集是 `CORE_INTELLIGENCE_CAPABILITY`，不是 Legacy 或 Debug Tool。正式产品继续保留采集概览、Source、Source Discovery、批量导入、采集任务、原始采集与历史快照；RC1.2C只补生命周期与安全删除，不改变RC1.2B信息架构。

## 实际对象与表

| 阶段 | 正式对象 | 真实表 | 已有状态/生命周期 |
|---|---|---|---|
| 1 | Source | `v04g_monitoring_sources` | `is_enabled`、`health_status`、`deactivated_at`；有历史时退役而非级联删除 |
| 2 | Collection Run | `v04g_monitoring_runs` | pending/running/success/partial/failed/cancelled 等 |
| 3 | Snapshot / Raw Content | `v04g_source_snapshots` | immutable evidence；保存正文、HTML、hash、时间与来源 |
| 4 | Raw Collection | `v05f_collection_items` | dedup/change/processing status，可重新排队加工 |
| 5 | Processing Job / Block | `v05g_processing_jobs`、`v05g_processing_blocks` | pending/running/success/failed；任务可重跑，原始记录可reprocess |
| 6 | Candidate | `v05g_extraction_candidates` | pending/needs_review/approved/rejected/applied 等；未确认且无正式引用才可删 |
| 7 | Candidate Evidence / Match | `p2_fact_candidate_evidence`、`v05g_subject_match_candidates` | 证据与候选绑定；确认前可随安全候选清理 |
| 8 | Formal Intelligence | `v06_intelligence_items` | `published` / `withdrawn` / `archived`，另有草稿/待审状态 |
| 9 | Subject Link | `core_intelligence_subject_links` | 正式主体上下文；存在即阻止情报硬删除 |
| 10 | Business Downstream | Relationship / Evidence / Resource / Match / Opportunity / FollowUp / Report | 正式业务历史；任何引用均阻止硬删除 |

## Collection → Intelligence真实链路

1. `collection_service.create_job` 或 Scheduler 创建 `v04g_monitoring_runs`。
2. Collection Worker抓取Source，写入不可变 `v04g_source_snapshots` 和去重后的 `v05f_collection_items`。
3. `intelligence_flow_service.run_collection_worker_with_cascade` 对新Raw Collection自动创建 `v05g_processing_jobs`，`trigger_type=collection_worker`。
4. 独立 Processing Worker调用 `processing.processing_job_service.process_job`，按现有确定性规则拆分Block并产生 `v05g_extraction_candidates`，同时生成主体匹配与证据。
5. Candidate经 `IntelligenceReviewService` / `FactCandidateService` 人工审核。正式写入前必须为approved并有 `p2_fact_candidate_evidence`。
6. `IntelligenceProductService.publish_candidate` 创建 `v06_intelligence_items`，并写入 `p2_intelligence_product_candidates` 与 `p2_intelligence_product_evidence` 形成可追溯链。
7. 用户在正式UI人工确认Subject Link；之后才允许沿Golden Loop形成Resource、Match、Opportunity、FollowUp、Outcome、Relationship/Evidence。

## 自动与人工边界

- 自动：Source调度、采集、Snapshot/Raw入库、去重、新Raw对应Processing Job入队。
- 不是自动：Processing Job的实际执行仍依赖独立Processing Worker或管理员“立即执行一次”。
- 人工：Candidate审核、正式Intelligence发布、Subject确认、Resource/Opportunity/Relationship等正式业务写入。
- 可重新加工：Raw Collection可通过现有Processing入口reprocess；失败/待处理Processing Job可重跑。

`PROCESSING_AUTOMATION_GAP=true`：采集成功会自动进入Processing队列，但如果独立Processing Worker未运行，管理员仍需人工执行加工。RC1.2C只登记，不重构Worker或Processing Engine。

## 生命周期动作

- DELETE：仅当Subject Link、Relationship/Evidence、Resource/Match、Opportunity/FollowUp、Report引用均为0时允许。删除前展示Impact Preview；删除时仅清理收藏等辅助幽灵链接和产品自身的技术性lineage，Source、Snapshot、Candidate以及所有核心业务对象不被删除。
- WITHDRAW：写 `status=withdrawn`。退出情报首页、今天值得处理、新匹配/新报告入口与Organization正常动态；历史引用、机会、跟进、关系证据、已生成报告均保留。Admin/Operator可恢复。
- ARCHIVE：写 `status=archived`。退出最新流与今天值得处理，但历史详情和Organization历史动态可访问。Admin/Operator可恢复。
- RESTORE：仅允许 `withdrawn` / `archived` 恢复为 `published`，并写现有 `p2_intelligence_audit_log`。

## Raw / Processing / Candidate删除

- Raw Collection：只有Processing、Candidate、Formal Intelligence、Resource、Workflow、重复子记录均为0时可单独删；Source和Snapshot保留。
- 错误采集链：管理员明确确认错误/测试/垃圾后，只有全部Candidate未确认且Product、Relationship Evidence、Signal、Application Log等正式引用为0时，才可删除本Raw、Processing Job/Block及未确认Candidate；Source和Snapshot继续保留。
- Processing Job：普通历史默认保留；只在上述安全错误链中清理。
- Candidate：仅 pending/needs_review/rejected 且没有Product、Relationship Evidence、Signal或Application Log时可删；approved/applied/published/merged一律保护。

## 正式下游引用

真实引用和推荐行为见 `MVP_RC1_2C_INTELLIGENCE_DELETE_MATRIX.csv`。特别注意：多个核心表的 `source_intelligence_id` 没有FK，不能依赖SQLite级联或页面表象判断，必须由Service显式预检；`core_intelligence_subject_links` 虽为CASCADE，产品规则仍把它视为正式引用并阻止硬删除。

## 权限与审计

- Formal Intelligence生命周期：Admin / Operator；Viewer后端POST为403。
- Raw Collection删除：Admin / 具备 `manage_monitoring` 的采集运营；其他角色403。
- Candidate删除：Admin / 具备 `review_data` 的审核人员；其他角色403。
- DELETE / WITHDRAW / ARCHIVE / RESTORE复用 `p2_intelligence_audit_log`，不新增第二套审计系统。

## Source与Intelligence独立性

Source是未来采集配置，Intelligence是审核后的业务成果。删除或下架Intelligence不会影响Source；Source退役也不会删除历史Intelligence、Snapshot或业务历史。两者必须独立管理，避免一次内容纠错破坏持续监测能力。
