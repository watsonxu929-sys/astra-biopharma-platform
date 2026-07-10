# P2.1 情报信息架构

情报中心二级菜单以 `app/platform/capability_registry.py` 为唯一配置源，模板通过 `navigation_service` 消费，不单独硬编码全局菜单。

| 菜单 | 正式入口 | 主链阶段 | 说明 |
|---|---|---|---|
| 情报动态 | `/intelligence` | 产品 | 已发布 IntelligenceProduct。 |
| 我的订阅 | `/intelligence/subscriptions` | 分发 | 当前用户订阅。 |
| 我的收藏 | `/workspace?tab=intelligence_favorites` | 分发 | 当前用户收藏。 |
| 企业动态 | `/watchlists` | 监测 | 重点企业关注清单；旧 `/signals/watchlists` 保留跳转。 |
| 专题研究 | `/research` | 研究 | 专题、比较与研究材料。 |
| 情报运营 | `/intelligence/operations` | 总览 | 采集、处理、审核、发布主链总览。 |
| 自动采集 | `/collection` | 采集 | 来源运行入口。 |
| 采集任务 | `/collection/jobs` | 采集 | CollectionJob 状态、计数与错误。 |
| 原始情报 | `/collection/items` | 快照/标准化 | 采集条目和 EvidenceSnapshot。 |
| 数据处理 | `/processing/jobs` | 解析 | 解析、拆块、规则/AI 分析任务。 |
| 候选匹配 | `/processing/candidates` | 候选 | FactCandidate 及证据。 |
| 情报审核 | `/admin/intelligence` | 审核/发布 | 正式运营管理；旧 `/review` 保留兼容。 |
| 产业信号 | `/signals` | 派生产品 | 经确认事件和规则生成的信号。 |
| 报告中心 | `/reports` | 派生产品 | 报告、引用和审批。 |
| 数据源管理 | `/collection/sources` | 来源 | IntelligenceSource 配置和健康度。 |

治理后，情报二级菜单子项不存在重复 `capability_key` 或重复正式 `web_route`；`/signals` 只属于产业信号，企业动态改用 `/watchlists`。管理控制台仍可提供跨一级模块的管理快捷入口，但不作为第二个情报二级正式入口。
