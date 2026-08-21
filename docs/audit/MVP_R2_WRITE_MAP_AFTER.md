# MVP-R2 Write Map After

核验日期：2026-08-21。范围仅为8个Canonical领域及其平台等价Legacy写入；Read Model、查询Service、历史迁移和基础设施Scheduler任务不计入业务Writer。

| Domain | Canonical Table | Canonical Owner | Delegate | Legacy Read Only | Deleted Writer |
|---|---|---|---|---|---|
| Intelligence | `v06_intelligence_items` | `IntelligenceProductService`：审核Candidate发布、人工草稿、受控更新、删除 | Admin Route、`product_recovery_service.publish_collection_item` | `raw_intelligence`只作为历史/采集Read Model | Route ORM创建/更新/发布；Collection ORM直写 |
| Resource | `v06_market_resources` | `UnifiedResourceService` | Platform、Golden Loop、Q-BAY会员内容审核、Q-BAY Resource提交/审核 | `resources`、`v04f_club_needs`、`v04f_club_offerings` | Golden Loop SQL；Q-BAY补列/审核SQL；会员导入和审核Legacy写入 |
| Match | `p4_resource_match_candidates` | `GoldenLoopService`的Match持久化/审核/机会关联方法 | Golden Loop人工匹配、Q-BAY规则算法、Q-BAY审核/转线索 | `v04f_club_matches` | Q-BAY算法自行INSERT、审核/转线索UPDATE、会员反馈Legacy UPDATE |
| Opportunity | `v06_opportunities` | `UnifiedOpportunityService` | Platform、Golden Loop、Business Collaboration、Q-BAY Lead转化 | `v04f_lead_records`保留为候选/历史读取 | Golden Loop INSERT/结果UPDATE；Business补列/阶段UPDATE；platform_service shadowed ORM writer |
| FollowUp | `v06_follow_ups` | `UnifiedOpportunityService` | Platform、Golden Loop、Business Collaboration | `v06_follows` | Golden Loop和Business SQL INSERT；platform_service shadowed ORM writer |
| Task | `v06_collab_tasks` | `UnifiedOpportunityService` | Platform、Golden Loop、Business Collaboration、Q-BAY活动会后独立任务 | `actions`只读；`task_queue/task_runs`是基础设施任务，不是业务Task | Golden/Business SQL；platform shadowed ORM；旧线索/信号/推荐Action冻结；活动Action改委托 |
| Relationship | `p3_canonical_relationships` | `CanonicalRelationshipService` | Candidate审核、Golden Loop won结果、Entity Governance实体合并/回滚 | `relations`、`v04c1_canonical_relations` | Golden Loop关系复制SQL；Entity Governance直接UPDATE；会员导入Legacy relation |
| Relationship Evidence | `p3_relationship_evidence` | `CanonicalRelationshipService` | Candidate审核、Golden Loop won证据 | `v04c1_fact_evidence` | Golden Loop证据复制SQL |

## 最终Owner清单

```text
Intelligence：1 Writer
Resource：1 Writer
Match：1 Writer
Opportunity：1 Writer
FollowUp：1 Writer
Task：1 Writer
Relationship：1 Writer
Evidence：1 Writer
```

对应文件固定为：

- `app/services/intelligence_product_service.py`
- `app/services/unified_resource_service.py`
- `app/services/golden_loop_service.py`
- `app/services/unified_opportunity_service.py`
- `app/services/canonical_relationship_service.py`

## 硬规则核验

- 正式Route直接写8张Canonical表：`0`。
- 非Owner Service直接写对应Canonical表：`0`。
- 正式源码对平台等价Legacy表 `resources / v04f_club_needs / v04f_club_offerings / v04f_club_matches / relations / actions` 的写入：`0`。
- 新增业务Service：`0`；新增Model：`0`；新增表：`0`；新增版本目录：`0`。
- Q-BAY的Membership、Event、Registration等场景数据保留；Need/Offering/Match/Task等平台对象改为委托Canonical Owner。
- `tests/test_mvp_r2_single_write_contract.py`固定Owner名单，并扫描Canonical SQL、ORM构造和Legacy等价写入；Owner变化或新增旁路时测试失败。
