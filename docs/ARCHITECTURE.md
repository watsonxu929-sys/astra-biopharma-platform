# 实际架构

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
