# 生物医药产业情报与协同平台

本项目是 Windows 本地部署的生物医药产业情报系统。主系统覆盖公开情报沉淀、主体档案、人物、项目、资源、事件、关系、行动任务、审核、监测、推荐和机会协同；Q-BAY 俱乐部是 community 业务板块，不单独建设第二套主体模型。

## 技术栈与模块

- FastAPI、SQLAlchemy、Jinja2、SQLite、原生 JavaScript/CSS。
- identity：用户、人物、机构、会员与身份映射。
- intelligence：采集、加工、审核、信号、报告与研究。
- marketplace：资源、需求与供给。
- opportunity：推荐、线索、合作机会、跟进与协同任务。
- community：俱乐部、活动、会员门户和通知。
- platform operations：任务、调度、备份、恢复和系统健康。

## 目录

`app/` 为应用与服务，`app/api/v1/` 为 API，`app/templates/` 和 `app/static/` 为页面资源，`scripts/` 为迁移与验证，`tools/windows/` 为历史 Windows 入口，`docs/` 为项目文档，`data/` 为不纳入 Git 的本地数据。

## 本地安装与启动

1. 双击 `setup_windows.bat` 安装依赖。
2. 在迁移前运行 `backup_windows.bat`。
3. 按需运行 `migrate_all_windows.bat`；普通页面请求不会自动执行结构迁移。
4. 双击 `run_windows.bat` 或 `start_web_windows.bat`，默认访问 `http://127.0.0.1:8000/`。

数据库默认位于 `data/app.db`，不得删除或重建；备份位于 `data/backups/`，发布包不包含数据库、备份、`.env`、日志和虚拟环境。

## 验证

```bat
.venv\Scripts\python.exe -m compileall app scripts
.venv\Scripts\python.exe scripts\check_source_encoding.py
.venv\Scripts\python.exe scriptserify_p0_baseline.py
verify_all_windows.bat
```

当前状态与风险见 [PROJECT_STATUS.md](PROJECT_STATUS.md)、[KNOWN_ISSUES.md](KNOWN_ISSUES.md)、[架构](docs/ARCHITECTURE.md)、[数据模型](docs/DATA_MODEL.md)、[启动与验证](docs/STARTUP_AND_VERIFICATION.md)。

## P1 领域迁移

先运行 `.venv\Scripts\python.exe scripts\migrations\001_core_domain_unification.py --dry-run`，确认冲突后再运行 `--apply`。迁移自动创建一致性备份。
