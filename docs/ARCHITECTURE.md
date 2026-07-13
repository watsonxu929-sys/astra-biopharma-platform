# 实际架构

## P4 俱乐部运营层

`club_operations_service.py` 为网页与 `/api/v1/club/*` 提供共享会员、活动、签到、反馈、资源匹配和运营看板逻辑。Q-BAY 复用既有 User/Person/Organization/Membership/Event/MarketResource；007 只增加历史、反馈、Token/审计、匹配/关系/线索候选和内部领域事件，不建立第二套主档。旧供需表只读，ClubLead 候选不自动进入 Opportunity。


## P3 主体与关系网络层

`entity_governance_service.py` 统一别名、外部标识、解析候选、合并预览、重定向和回滚；`canonical_relationship_service.py` 统一类型化关系、证据、时态冲突、受限 BFS 路径和连接候选。Web `app/p3_network.py` 与 API `/api/v1/entity-network` 调用同一服务层。旧 `relations` 保持兼容读取，P3 新写入进入 006 的增量表，不引入第二套人物/机构主档或图数据库。


## P2.2 真实来源质量层

受控来源继续复用 `v04g/v05f CollectionJob → v04g_source_snapshots EvidenceSnapshot → raw_intelligence → v05g_extraction_candidates`。HTTP/RSS和Playwright只负责采集，ParsingService按MIME选择HTML/Text/可选Docling；统一质量门在AI前阻断低质量内容。004只增加观测、解析、质量、评测和冲突登记字段/表，不建立第二套主体或产品模型。AI结果只能进入候选与人工审核。

## 应用与路由

FastAPI 入口是 `app/main.py:app`。同一单体进程注册 v04/v05 兼容路由、`app/identity.py`、`app/routes_platform.py` 与 `/api/v1` 聚合路由。Jinja2 模板位于 `app/templates/`，静态文件位于 `app/static/`。

## 数据访问

核心主体 ORM 位于 `app/models.py`，平台正式模型位于 `app/models_platform.py`；旧模块仍有 SQLite `sqlite3` 访问。数据库路径由 `app/core/config.py`/`app/database.py` 统一解析。开发环境使用 SQLite；普通请求不迁移结构，迁移由 `scripts/migrate_*.py` 显式执行。PostgreSQL 仅保留未来边界：服务接口、枚举和稳定 ID 先统一，本任务不切换数据库。

## 业务链

- identity/community：`v05a_users` 是登录身份，`people` 是现实人物，`v04f_club_memberships` 是会员资格，`organizations` 是机构，人物机构关系复用现有关系服务。
- intelligence：采集 `v04g/v05f` → 加工 `v05g` → 候选/审核 `v04c/v04d` → 信号/报告/研究 `v05e/v05h/v05j`，正式发布视图由统一情报服务读取。
- marketplace：正式写入 `v06_market_resources`，兼容读取 `resources`、`v04f_club_needs`、`v04f_club_offerings`。
- opportunity：统一机会、跟进、时间线和任务模型位于 `app/models_platform.py`，旧 Lead/Action/Recommendation 通过兼容服务映射。
- scheduling：任务队列、Worker 与 Scheduler 位于 `app/services/tasks/` 和 `scripts/run_*worker.py`。

## 权限与审计

`app/security.py` 提供登录、权限和中间件；API 与网页复用授权服务。敏感联系方式、机会和会员数据必须经过权限检查。身份、会员、机会状态和迁移保留审计或映射记录。


## P2.3 研究融合层

app/services/research/fusion_service.py 负责事件关系分类、正式事件、证据、事实断言和冲突；research_engine_service.py 负责专题工作区、研究发现、企业/赛道对比、引用报告、版本与 ResearchAgent。Web 和 /api/v1/research-fusion 复用同一服务层。005 只扩展既有专题/报告并增加关联表，不重复企业、人物、项目、候选、RawIntelligence 或 EvidenceSnapshot。
