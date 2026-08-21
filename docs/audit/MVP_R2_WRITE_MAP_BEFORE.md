# MVP-R2 Write Map Before

审计时间：2026-08-21。范围是八张Canonical表及会产生平台等价对象的Legacy表。结论来自逐表搜索、函数体阅读和Route/API/脚本调用链追踪，不以grep命中数代替runtime判断。

分类：A=`CANONICAL_OWNER`，B=`DELEGATE`，C=`LEGACY_READ_ONLY`，D=`DELETE_WRITER`。

| Domain | Canonical Table | Writer File | Function | Caller | Active Runtime | Route/User Entry | Decision |
|---|---|---|---|---|---|---|---|
| Intelligence | `v06_intelligence_items` | `app/services/intelligence_product_service.py` | `publish_candidate` / `delete` | Processing Web/API、P2 pilot | Yes | `/processing/candidates/{id}/publish`、`/api/v1/processing/...` | A；保留唯一审核+证据发布Owner |
| Intelligence | `v06_intelligence_items` | `app/services/product_recovery_service.py` | `publish_collection_item` | `routes_platform.admin_publish_collection_item`、旧验证脚本 | Yes | `/admin/intelligence/collection/{id}/publish` | B；必须委托已审核Candidate发布，删除ORM直写 |
| Intelligence | `v06_intelligence_items` | `app/routes_platform.py` | `admin_create_intelligence` / `admin_update_intelligence` / `admin_publish_intelligence` | Admin Web Route自身 | Yes | `/admin/intelligence*` | B；Route ORM直写必须归零；草稿创建/更新委托Owner，发布必须经过审核Candidate门禁 |
| Resource | `v06_market_resources` | `app/services/unified_resource_service.py` | `create` / `update_status` | Platform Web/API、platform adapter | Yes | `/resources/new`、资源API | A；保留唯一Resource Owner |
| Resource | `v06_market_resources` | `app/services/golden_loop_service.py` | `create_resource_from_intelligence` | Golden Loop Web/API | Yes | 情报转需求/供给 | B；保留校验，持久化委托UnifiedResourceService |
| Resource | `v06_market_resources` | `app/services/club_operations_service.py` | `create_member_resource` | Q-BAY运营Web/API、pilot | Yes | `/club/resources/...` | B；当前部分委托但仍直接补写Canonical列，需归零 |
| Resource | `v06_market_resources` | `app/services/club_operations_service.py` | `review_resource` | Q-BAY运营Web/API | Yes | Q-BAY资源审核 | B；状态写入委托UnifiedResourceService |
| Resource | `v04f_club_needs` / `v04f_club_offerings` | `app/v05d_member_portal.py` | `review_content` | Q-BAY会员内容审核 | Yes | `/club/member-content/{id}/review` | B；审核通过改为创建Canonical Resource，不再写Legacy |
| Resource | `v04f_club_needs` / `v04f_club_offerings` | `app/v05b_member_import.py` | `_confirm_draft`内自动建供需 | 会员批量导入确认 | Yes | Q-BAY会员导入 | D；自动导入不得生成正式供需对象，删除Legacy写块 |
| Match | `p4_resource_match_candidates` | `app/services/golden_loop_service.py` | `confirm_match` / `set_match_intention` / match link update | Golden Loop Web/API | Yes | 人工确认匹配、意向、转机会 | A；作为平台Match持久化Owner |
| Match | `p4_resource_match_candidates` | `app/services/club_operations_service.py` | `generate_matches` | Q-BAY Web/API、pilot | Yes | Q-BAY生成匹配 | B；算法保留，持久化委托Match Owner |
| Match | `p4_resource_match_candidates` | `app/services/club_operations_service.py` | `review_match` / `create_lead_from_match` | Q-BAY Web/API | Yes | Q-BAY审核/转线索 | B；状态写入委托Match Owner |
| Match | `v04f_club_matches` | `app/v05d_member_portal.py` | `match_feedback` | Legacy会员门户 | Yes但R1已从正式入口重定向 | `/member/matches/{id}/feedback` | C；允许反馈记录，删除对Legacy Match状态更新 |
| Opportunity | `v06_opportunities` | `app/services/unified_opportunity_service.py` | `create` / `update_stage` | Platform Web/API、platform adapter、BusinessCollaboration部分调用 | Yes | 手工机会、Contact Intent转化 | A；保留唯一Opportunity Owner |
| Opportunity | `v06_opportunities` | `app/services/golden_loop_service.py` | `convert_match_to_opportunity` / `close_outcome` | Golden Loop Web/API | Yes | Match转机会、登记结果 | B；业务流程保留，创建/结果更新委托Owner |
| Opportunity | `v06_opportunities` | `app/services/business_collaboration_service.py` | `convert_lead`内补写 / `update_stage` / 跟进时补写 | P5 Collaboration Web/API | Yes | 线索转机会、阶段、跟进 | B；校验和P5审计保留，Canonical字段委托Owner |
| FollowUp | `v06_follow_ups` | `app/services/unified_opportunity_service.py` | `create_follow_up` | Opportunity API、platform adapter | Yes | 机会详情跟进 | A；保留唯一FollowUp Owner |
| FollowUp | `v06_follow_ups` | `app/services/golden_loop_service.py` | `add_follow_up` | Golden Loop Web/API | Yes | Golden Loop登记跟进 | B；委托Owner |
| FollowUp | `v06_follow_ups` | `app/services/business_collaboration_service.py` | `add_follow_up` | P5 Web/API | Yes | 协作详情登记跟进 | B；P5审计保留，持久化委托Owner |
| Task | `v06_collab_tasks` | `app/services/unified_opportunity_service.py` | `create_task` / task update extension | Opportunity API、platform adapter | Yes | 机会详情任务 | A；保留唯一业务Task Owner |
| Task | `v06_collab_tasks` | `app/services/golden_loop_service.py` | `create_task` | Golden Loop Web/API | Yes | Golden Loop创建任务 | B；委托Owner |
| Task | `v06_collab_tasks` | `app/services/business_collaboration_service.py` | `create_task` / `update_task` | P5 Web/API | Yes | 协作任务创建/更新 | B；P5审计保留，持久化委托Owner |
| Opportunity / FollowUp / Task | 对应Canonical三表 | `app/services/platform_service.py` | 文件前部重复`create_*`函数 | 被同文件后置同名delegate覆盖 | No（shadowed dead writer） | 无独立入口 | D；删除重复ORM writer，仅保留后置delegate |
| Task | `actions` | `app/v05c_club_events.py` | `create_followup_action` | Q-BAY活动Web | Yes | 活动会后跟进 | B；委托Canonical Task Owner创建独立业务任务 |
| Task | `actions` | `app/v04f_operations.py` / `signal_service.py` / `recommendation_service.py` | 三个旧Action转换函数 | Legacy/实验入口 | Legacy或R1已冻结 | 旧线索、信号、推荐转任务 | D/C；停止新增`actions`，返回冻结说明或410，不恢复实验能力 |
| Relationship | `p3_canonical_relationships` | `app/services/canonical_relationship_service.py` | `review_candidate`→`_insert_relationship` / `archive` | Network Web/API、P3 pilot | Yes | 关系候选审核、归档 | A；保留唯一Relationship Owner |
| Evidence | `p3_relationship_evidence` | `app/services/canonical_relationship_service.py` | `_insert_relationship` | 同上 | Yes | 关系候选审核 | A；与Relationship同一事务Owner |
| Relationship | `p3_canonical_relationships` | `app/services/golden_loop_service.py` | `_cooperation_relationship` | `close_outcome(won)` | Yes | 合作达成 | B；委托CanonicalRelationshipService |
| Evidence | `p3_relationship_evidence` | `app/services/golden_loop_service.py` | `_cooperation_relationship` | `close_outcome(won)` | Yes | 合作达成证据 | B；委托CanonicalRelationshipService |
| Relationship | `p3_canonical_relationships` | `app/services/entity_governance_service.py` | `execute` / `rollback`实体合并重指向 | 管理员实体治理 | Yes（Admin） | 实体合并/回滚 | B；事务内调用CanonicalRelationshipService的重指向方法 |
| Relationship | `relations` | `app/v05b_member_import.py` | `_confirm_draft`自动建任职关系 | 会员批量导入确认 | Yes | Q-BAY会员导入 | D；未审核导入不得产生正式关系，删除Legacy写块 |

## 修改前正式runtime Writer数量

| Domain | Writer文件数 | 说明 |
|---|---:|---|
| Intelligence | 3 | 一个证据审核Owner、一个可绕过审核的Collection直写、一个Admin Route ORM直写组 |
| Resource | 4个Canonical写函数组 + 2个Legacy写入口 | Unified、Golden Loop、Q-BAY补写/审核、会员内容/导入Legacy |
| Match | 2个Canonical Writer文件 + 1个Legacy状态Writer | Golden Loop、Q-BAY、Legacy会员门户 |
| Opportunity | 3个Active + 1个shadowed死Writer | Unified、Golden Loop、Business Collaboration；platform_service前部重复实现被后置函数覆盖 |
| FollowUp | 3个Active + 1个shadowed死Writer | Unified、Golden Loop、Business Collaboration；platform_service前部重复实现被后置函数覆盖 |
| Task | 3个Canonical Active + 1个shadowed死Writer + 4个Legacy Action入口 | Unified、Golden Loop、Business Collaboration；基础设施`task_queue/task_runs`不属于业务Task |
| Relationship | 3个Canonical Writer文件 + 1个Legacy Writer | Canonical、Golden Loop、Entity Governance、会员导入Legacy |
| Evidence | 2 | Canonical、Golden Loop |

## 非正式runtime写入

`scripts/migrations/*`、demo seed、pilot/verify脚本和测试中存在建表、迁移、测试数据写入或清理SQL。它们不由正式Web/API runtime调用，R2不删除历史迁移；Single Write Contract将它们排除在正式runtime Owner计数之外，但所有执行仍必须指向临时测试库。`scripts/restore_test_opp.py`属于历史修复脚本，不作为正式入口。
