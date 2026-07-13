# 当前领域模型地图

## P3 增量模型

| 表/模型 | 含义 | 状态与边界 |
|---|---|---|
| `p3_product_assets` | ProductAsset 正式兼容主档 | 与 Project 分离；没有复用 P2 情报产品或媒体资产 |
| `p3_entity_aliases` / `p3_entity_external_identifiers` | 四类主体的别名与公开权威标识 | 审核后使用；禁止敏感标识 |
| `p3_entity_resolution_candidates` | 主体解析候选 | 不自动覆盖正式主档 |
| `p3_entity_merge_records` / `p3_entity_redirects` | 合并审计、旧 ID 跳转和回滚 | 来源主体软停用，不物理删除 |
| `p3_relationship_type_registry` | 43 个受控关系类型 | 保存正反向名、端点类型、风险级别 |
| `p3_canonical_relationships` / `p3_relationship_evidence` | 已审核时态关系及结构化证据 | 新关系正式层；旧 `relations` 兼容保留 |
| `p3_relationship_candidates` | 情报、研究和手工关系候选 | 审核前不进入网络 |
| `p3_connection_candidates` | “我应该认识谁”候选接口 | 只供研判，不自动执行动作 |


| 表/模型 | 业务含义 | 创建位置 | 主要写入 | 主要读取 | 使用状态 | 重复/映射与建议 |
|---|---|---|---|---|---|---|
| `v05a_users` | User 登录与安全身份 | `scripts/migrate_v05a.py` | security/身份服务 | 中间件、API | 正式 | 不并入 Person |
| `people` | Person 现实人物主档 | `app/models.py` | 主体服务、人工接入 | 主体页/API | 正式 | Membership 只保存 `person_id` |
| `organizations` | Organization 机构主档 | `app/models.py` | 主体服务 | 主体页/API | 正式 | 所有板块复用 |
| `relations` | PersonOrganizationRelation 等主体关系 | `app/models.py` | `subject_links.py` | 关系页/路径服务 | 正式 | 关系类型和时间范围待逐步补齐 |
| `v04f_club_memberships` | Membership 俱乐部资格 | `scripts/migrate_v04f.py` | 会员链接/门户服务 | 会员页/API | 正式兼容 | 通过 user/person/org 外键映射，不复制人物主档 |
| `v05d_member_accounts` | 旧会员门户账号 | `scripts/migrate_v05d.py` | 旧门户 | 旧门户 | 兼容 | 禁止扩展为第二套 User |
| `v04g_monitoring_snapshots`、`v05f_collection_items` | CollectionSnapshot 来源证据 | v04g/v05f 迁移 | 采集服务 | 采集页/加工服务 | 正式阶段映射 | 保留 URL、抓取时间、正文/哈希 |
| `raw_intelligence` | RawIntelligence 清洗正文 | `app/models.py` | 接入/同步 | 情报页/统一情报服务 | 正式阶段映射 | 不删除 |
| `v05g_extraction_candidates`、`v04c_review_items` | FactCandidate 待审核事实 | v05g/v04c 迁移 | 加工/审核服务 | 审核页 | 正式阶段映射 | 证据和审核状态必填 |
| `v06_intelligence_items`、`v05e_industry_signals`、`v05h_generated_reports` | IntelligenceProduct | 平台/v05 迁移 | 统一情报、信号、报告服务 | 平台/API | `v06_intelligence_items` 正式，其余兼容产品 | 新增证据类型、旧 ID 和哈希字段 |
| `v06_market_resources` | MarketResource demand/supply | 平台迁移 + `001` | `UnifiedResourceService` | 平台资源页/API | 正式 | 映射 resources/needs/offerings |
| `resources` | 历史通用资源 | `app/models.py` | 旧页面 | 旧页面/兼容服务 | 兼容 | 禁止新功能直接写入 |
| `v04f_club_needs`、`v04f_club_offerings` | 会员需求/供给 | v04f 迁移 | 旧俱乐部页面 | 兼容服务 | 兼容 | 逐条映射到 MarketResource，不自动覆盖 |
| `v04h_recommendations` | Recommendation | v04h 迁移 | 推荐服务 | 推荐页 | 兼容候选 | 不自动转 Opportunity |
| `v04f_club_matches` | MatchCandidate | v04f 迁移 | 匹配服务 | 俱乐部页 | 兼容候选 | 运营确认前不是商机 |
| `v04f_lead_records`、`v06_contact_intents` | Lead | v04f/平台迁移 | 线索/联系服务 | 运营页 | 兼容来源 | 人工确认后才转正式机会 |
| `v06_opportunities` | Opportunity | 平台迁移 + `001` | `UnifiedOpportunityService` | 机会页/API | 正式 | 强制 `human_confirmed`，保留确认人/时间 |
| `v06_follow_ups` | FollowUp 时间线沟通 | 平台迁移 | 统一机会服务 | 机会详情 | 正式 | 必须关联机会 |
| `v06_collab_tasks` | CollaborationTask | 平台迁移 | 统一机会服务 | 工作台/机会详情 | 正式 | 可分配参与者并关联机会 |
| `actions` | 历史行动任务 | `app/models.py` | 旧页面 | 旧页面 | 兼容 | 不直接视为 CollaborationTask |
| `platform_entity_mappings` | 旧 ID—正式 ID 映射 | `001` | 显式迁移 | 兼容层/审计 | 正式基础 | 唯一约束保证幂等 |
| `platform_migration_conflicts` | 人工冲突清单 | `001` | 显式迁移 | 人工审核 | 正式基础 | 禁止静默覆盖 |
