# MVP-R3 Legacy Inventory

| Legacy Table | Records | Current Reader（R3前） | Current Writer | Canonical Target | Product Value | Migration Decision |
|---|---:|---|---|---|---|---|
| relations | 26 | Relationship API、Subject API、Q-BAY path、Legacy/Frozen research | 0 | p3_canonical_relationships / p3_relationship_evidence | 25条主体可解析；1条主体已不存在 | MIGRATE（25）/ MANUAL_REVIEW（1） |
| resources | 8 | Legacy/Frozen主体与采集页面；Q-BAY评分 | 0 | v06_market_resources | 真实空间、技术、政策、网络等供给 | MIGRATE |
| v04f_club_needs | 0 | Q-BAY会员详情/活动/会员门户（R3前） | 0 | v06_market_resources | 无数据 | EMPTY_IGNORE |
| v04f_club_offerings | 1 | Q-BAY会员详情/活动/会员门户（R3前） | 0 | v06_market_resources | 真实会员工艺评估供给 | MIGRATE |
| v04f_club_matches | 0 | Q-BAY会员门户（R3前） | 0 | p4_resource_match_candidates | 无数据 | EMPTY_IGNORE |
| v04f_lead_records | 0 | Legacy线索/候选服务 | 0 | v06_opportunities | 无数据 | EMPTY_IGNORE |
| v04f_lead_stage_history | 0 | Legacy线索页面 | 0 | 无 | 无数据 | EMPTY_IGNORE |
| v04f_lead_suggestions | 0 | Legacy线索页面 | 0 | 无 | 无数据 | EMPTY_IGNORE |
| p4_club_lead_candidates | 0 | Q-BAY候选流程 | Canonical转化前候选 | v06_opportunities（仅人工转化后） | 无数据 | EMPTY_IGNORE |
| actions | 7 | Legacy/Frozen Action页面 | 0 | v06_collab_tasks | 资料核验、名单整理、数据导入和试跑任务；无Opportunity关联，不是正式商务协作Task | ARCHIVE_ONLY |
| task_queue | 0 | 基础设施 | scheduler | 不适用 | 系统任务，不是商务任务 | EMPTY_IGNORE |
| task_runs | 0 | 基础设施 | scheduler | 不适用 | 系统运行记录，不是商务任务 | EMPTY_IGNORE |

## 明确不迁移

AI、Recommendation、Research、P2、Favorites、Follows、Subscription、实验/空壳、测试、migration历史表均不进入 Canonical。本轮不创建任何空壳记录。
