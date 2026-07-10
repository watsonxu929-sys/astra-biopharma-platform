# Route Compatibility v1

| 原路径 | 新路径 | 保留方式 | 是否重定向 | 统一服务 |
|---|---|---|---|---|
| `/intelligence` | `/intelligence` | 保留 v0.6 前台情报流，读取发布层 | 否 | `UnifiedIntelligenceService` |
| `/intelligence/{item_id}` | `/intelligence/{item_id:int}` | 保留 v0.6 详情，限制为整数动态段，避免抢占静态路径 | 否 | `UnifiedIntelligenceService` |
| `/intelligence/subscriptions` | `/intelligence/subscriptions` | 保留订阅页，静态路径不再被动态详情抢占 | 否 | `UnifiedIntelligenceService` |
| 旧情报列表 `/intelligence` | `/intelligence/legacy` | 迁至 legacy 后台兼容入口 | 否 | 旧情报治理服务 |
| 旧情报详情 `/intelligence/{item_id}` | `/intelligence/legacy/{item_id:int}` | 迁至 legacy 后台兼容入口 | 否 | 旧情报治理服务 |
| `/api/v1/intelligence` | `/api/v1/intelligence` | API 列表和详情改读发布层 | 否 | `UnifiedIntelligenceService` |
| `/resources` | `/resources` | 保留 v0.6 资源市场，主读 `v06_market_resources` 并投影旧俱乐部供需 | 否 | `UnifiedResourceService` |
| `/resources/{resource_id}` | `/resources/{resource_id:int}` | 保留 v0.6 详情，限制为整数动态段，避免抢占静态路径 | 否 | `UnifiedResourceService` |
| `/resources/new` | `/resources/new` | 保留发布页，新写入统一资源主模型 | 否 | `UnifiedResourceService` |
| 旧资源列表 `/resources` | `/resources/legacy` | 迁至 legacy 数据资源入口 | 否 | 旧资源服务 |
| 旧资源详情 `/resources/{item_id}` | `/resources/legacy/{item_id:int}` | 迁至 legacy 数据资源入口 | 否 | 旧资源服务 |
| `/api/v1/resources` | `/api/v1/resources` | 新增统一资源 API | 否 | `UnifiedResourceService` |
| `/opportunities` | `/opportunities` | 保留合作机会列表，按统一机会权限过滤 | 否 | `UnifiedOpportunityService` |
| `/api/v1/opportunities` | `/api/v1/opportunities` | 新增统一机会 API | 否 | `UnifiedOpportunityService` |
| `/search` | `/search` | 保留全局搜索，底层改为 canonical 搜索 | 否 | `UnifiedSearchService` |
| `/platform/search` | `/platform/search` | 平台内搜索入口迁出全局 `/search` 冲突 | 否 | `UnifiedSearchService` |
| `/api/v1/search` | `/api/v1/search` | 保留 API 搜索，同源服务 | 否 | `UnifiedSearchService` |
| `/review`、`/collection`、`/processing`、`/reports` | 原路径 | 保留旧情报后台治理链 | 否 | 旧后台服务 |
| `/club/*` | 原路径 | 保留 Q-BAY 旧页面，供需通过资源适配器进入统一市场读取 | 否 | `UnifiedResourceService` legacy adapter |
