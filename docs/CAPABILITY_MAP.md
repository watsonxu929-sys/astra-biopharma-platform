# 能力地图

## P4 俱乐部运营能力

| 领域 | P4 能力 | 主要实现 | 边界 |
|---|---|---|---|
| membership | 申请审核、激活、变更、暂停、恢复、到期、退出 | `ClubMembershipService`、007 | 复用既有会员与主体 |
| club events | 生命周期、容量/候补、Token/手工签到、反馈 | `ClubEventService`、Web/API | 仅已批准报名可签到 |
| club resources | 统一供需审核、可解释匹配候选 | `ClubResourceMatchingService` | 旧供需只读，不自动联系 |
| deposition | 会后关系与 ClubLead 候选 | P4 候选表 | 不自动写 P3 正式关系或 Opportunity |
| operations | 16 个中文指标、工作队列、领域事件与审计 | `ClubOperationsDashboardService` | `manage_club` 后端权限 |


| 领域 | P3 正式能力 | 主要实现 | 边界 |
|---|---|---|---|
| entity governance | 别名、公开标识、强中弱候选、合并预览/审批/回滚 | `entity_governance_service.py`、006 | 不自动合并，不物理删除主档 |
| relationship network | 43 类关系、证据、有效期、审核、可见性 | `canonical_relationship_service.py`、P3 Web/API | 旧 relations 兼容读取 |
| relationship paths | 任意两点 1—3 跳、历史/类型过滤、置信度 | `RelationshipNetworkService` | SQLite 受限 BFS，不引入 Neo4j |
| connection candidates | 理由、路径、证据、置信度、风险提示 | `ConnectionRecommendationService` | 不联系、不发消息、不创建商机 |


| 领域 | P2.2能力 | 主要实现 | 边界 |
|---|---|---|---|
| real-source intelligence | HTTP/RSS条件请求、动态页、PDF/XLSX、质量门、评测 | `collection_service`、`collectors/`、`parsers/`、`evaluation_service`、004迁移 | 总量≤30、AI≤20、无自动审核/发布 |

| 领域 | 正式能力 | 主要实现 | 兼容来源 |
|---|---|---|---|
| identity | User、Person、Organization、Membership、身份链接 | `app/models.py`、身份/会员链接服务 | `v05a_users`、`v04f_club_memberships`、`v05d_member_accounts` |
| intelligence | 采集、加工、审核、发布、报告 | collection/processing/signal/report/unified intelligence 服务 | `raw_intelligence`、`v04g_*`、`v05f_*`、`v05g_*`、`v05h_*` |
| network | 关系、推荐、匹配、路径 | subject links、recommendation、relationship path | `relations`、`v04h_recommendations`、`v04f_club_matches` |
| community | 会员、活动、门户、通知 | `v04f_operations`、`v05c_club_events`、`v05d_member_portal` | v04/v05 页面与表 |
| marketplace | demand/supply 统一资源 | `UnifiedResourceService`、`v06_market_resources` | `resources`、club needs/offerings |
| opportunity | 机会、跟进、时间线、协同任务 | `UnifiedOpportunityService`、v06 机会表 | lead、action、recommendation、contact intent |
| operations | 权限、审计、任务、备份、健康 | security、tasks、operations | 历史 Windows 入口 |

网页和 `/api/v1` 应调用同一服务层；不得再新增第二套用户、人物、机构、会员、资源或机会模型。


| 领域 | P2.3 正式能力 | 主要实现 | 边界 |
|---|---|---|---|
| research fusion | 多来源事件、事实断言、冲突、正式时间线、专题工作区、企业/赛道对比、引用报告与版本 | fusion_service、research_engine_service、005 迁移、/api/v1/research-fusion | AI 只生成草稿；事件/事实/冲突/报告均保留人工审核门；无可靠数据不补造 |
