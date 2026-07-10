# 能力地图

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
