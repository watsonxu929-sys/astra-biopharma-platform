# v0.5H 产业信号、自动摘要、报告中心与导航重构

## 目标

v0.5H 在现有 v0.5E 信号、v0.5F 采集、v0.5G 语义处理能力之上，补齐三条面向运营的工作流：

- 产业信号规则化：从已确认事件和已审核候选中生成正式信号。
- 自动摘要与报告中心：生成日报、周报、月报、主体报告、赛道报告和 Q-BAY 资源报告草稿。
- 全站导航配置化：用统一导航配置服务替代散落在模板里的菜单。

本阶段不重写业务代码，不绕过人工审核，不自动创建行动项。

## 主要入口

- 信号仪表盘：`/signals/dashboard`
- 重要信号：`/signals/alerts`
- 信号规则：`/signals/rules`
- 关注清单：`/signals/watchlists`
- 报告中心：`/reports`
- 报告任务：`/reports/jobs`
- 健康检查：`/v05h/health`

## API 入口

- `GET /api/v1/navigation`
- `GET /api/v1/signals/dashboard`
- `GET /api/v1/signals/rules`
- `POST /api/v1/signals/generate-from-events`
- `POST /api/v1/signals/{id}/read`
- `POST /api/v1/signals/{id}/important`
- `POST /api/v1/signals/{id}/ignore`
- `GET /api/v1/reports`
- `POST /api/v1/reports/jobs`
- `GET /api/v1/reports/jobs/{id}`
- `GET /api/v1/reports/{id}`
- `PATCH /api/v1/reports/{id}`
- `POST /api/v1/reports/{id}/submit`
- `POST /api/v1/reports/{id}/approve`
- `POST /api/v1/reports/{id}/archive`
- `GET /api/v1/reports/{id}/citations`

## 规则与安全边界

- 信号规则存放在 `v05h_signal_rules`，可启停，不需要改代码。
- 信号证据存放在 `v05h_signal_evidence`，保留来源、摘要和哈希。
- 只处理已确认事件或已审核候选，未审核数据不会进入正式信号。
- 信号生成只生成信号，不生成行动项。
- 报告默认生成草稿，需提交和审核后才进入已批准状态。
- 页面浏览需要 `view_internal`；报告、规则和生成类写操作需要 `review_data`。

## 数据表

- `v05h_signal_rules`
- `v05h_signal_evidence`
- `v05h_report_templates`
- `v05h_report_jobs`
- `v05h_generated_reports`

v0.5H 同时扩展：

- `v05e_industry_signals`
- `v05e_watchlist_items`

## Windows 脚本

- `migrate_v05h_windows.bat`
- `verify_v05h_windows.bat`
- `run_signal_once_windows.bat`
- `run_report_once_windows.bat`
- `start_windows.bat`
- `run_windows.bat`

`start_windows.bat` 默认使用 `127.0.0.1:8000`，可通过 `.env` 中的 `APP_HOST`、`APP_PORT`、`APP_RELOAD`、`APP_OPEN_BROWSER` 调整。端口占用时脚本只提示 PID，不会杀进程。
