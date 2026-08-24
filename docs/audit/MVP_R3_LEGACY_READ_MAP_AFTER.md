# MVP-R3 Legacy Read Map After

扫描日期：2026-08-24（Asia/Shanghai）

## 结论

正式产品对本轮目标 Legacy 业务表的 `PRODUCT_READ` 为 **0**。源码中仍保留的表名引用均已归入一次性迁移、结构审计、历史测试或已冻结代码；它们不再是正式产品事实来源。

## 正式产品 Canonical Read

| Domain | Canonical source | 正式读取位置 |
|---|---|---|
| Relationship / Evidence | `p3_canonical_relationships` / `p3_relationship_evidence` | Relationship API、Subject API、关系路径、人物/机构详情、Q-BAY关系统计 |
| Resource | `v06_market_resources` | `/resources`、Resource API、全局搜索、Q-BAY会员/活动/会员门户 |
| Match | `p4_resource_match_candidates` | Q-BAY匹配页、会员门户、Resource候选 |
| Opportunity | `v06_opportunities` | `/opportunities`、`/collaboration`、Opportunity API、协作统计 |
| FollowUp | `v06_follow_ups` | Opportunity详情、协作队列、Golden Loop |
| Task | `v06_collab_tasks` | 协作首页、Subject汇总、Q-BAY统计、Dashboard、Opportunity详情 |

`/collaboration/leads` 及其三个旧 POST 入口仅保留无数据读取/写入的 303 兼容重定向，统一指向 `/opportunities`。Capability `collaboration.leads` 已标记 `disabled`，正式协作首页不再展示“线索审核”。

## Legacy 引用分类

| 分类 | 位置/类型 | R3后处理 |
|---|---|---|
| PRODUCT_READ | 正式 Relationship、Resource、Match、Opportunity、FollowUp、Task 页面/API/Q-BAY | **0；已全部切换 Canonical** |
| MIGRATION_ONLY | `scripts/migrations/mvp_r3_legacy_to_canonical.py` | 保留；仅显式命令执行，不在启动/import/页面访问时运行 |
| AUDIT_ONLY | `app/services/schema_preflight.py`、本目录审计文档和 evidence CSV | 保留；只检查结构/证据，不作为业务事实读取 |
| HISTORICAL_TEST | 旧 migration、v06i/v06j/v06k、Legacy行为测试 | 保留；已知历史债务，不恢复为正式产品行为 |
| DEAD_CODE / FROZEN | `app/main.py` 的旧 ORM Dashboard/`/resources/legacy`/`/relations`/`/actions`；`app/v04f_operations.py` 旧 Lead；`subject_profile_service.py` 旧 `/subjects` 聚合；旧 Recommendation/Research/Monitoring；对应旧模板 | 冻结，不在五个一级导航、正式 Q-BAY 场景和 Canonical API中使用；后续 Housekeeping 才允许物理清理 |

`app/services/business_collaboration_service.py` 中无人调用的 Legacy Lead create/list/detail/review/convert 方法已删除；正式服务保留的 Opportunity、FollowUp、Task、Meeting 等逻辑均读写 Canonical。

## Q-BAY边界

Q-BAY继续保留 Membership、Member Account、Event、Registration、Check-in 场景表。Q-BAY涉及 Resource、Match、Opportunity、FollowUp、Relationship、Task 的正式页面和统计已读取平台 Canonical 表，不再读取 `v04f_club_needs`、`v04f_club_offerings`、`v04f_club_matches` 或 `v04f_lead_records` 作为事实来源。

## Legacy退役标记

下列表本轮均未 DROP，原记录未改：

| Legacy table | 状态 |
|---|---|
| `relations` | LEGACY / READ ONLY / HISTORICAL / NO PRODUCT WRITE / NO FORMAL PRODUCT READ |
| `resources` | LEGACY / READ ONLY / HISTORICAL / NO PRODUCT WRITE / NO FORMAL PRODUCT READ |
| `v04f_club_needs` | LEGACY / READ ONLY / HISTORICAL / NO PRODUCT WRITE / NO FORMAL PRODUCT READ |
| `v04f_club_offerings` | LEGACY / READ ONLY / HISTORICAL / NO PRODUCT WRITE / NO FORMAL PRODUCT READ |
| `v04f_club_matches` | LEGACY / READ ONLY / HISTORICAL / NO PRODUCT WRITE / NO FORMAL PRODUCT READ |
| `v04f_lead_records` | LEGACY / READ ONLY / HISTORICAL / NO PRODUCT WRITE / NO FORMAL PRODUCT READ |
| `actions` | LEGACY / READ ONLY / HISTORICAL / NO PRODUCT WRITE / NO FORMAL PRODUCT READ |

物理删除必须至少等待一个真实运营周期，并作为后续独立 Housekeeping 任务处理。
