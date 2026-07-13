# 生物医药产业情报与协同平台

## P3 主体治理与产业关系网络

P3 增加类型化主体别名与公开标识、解析候选、可回滚合并、43 类证据化时态关系、1—3 跳路径和连接候选。正式 Person/Organization/Project 继续复用既有主档；ProductAsset 使用必要的 P3 兼容主档。迁移 006 默认 dry-run，本轮试点只在 `C:\tmp` 数据库副本执行。详见 `docs/p3/`。


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

## P2.2 受控真实来源试点

P2.2 已加入真实静态网页、RSS、单一动态网页、PDF/XLSX解析、内容质量门和规则/AI评测框架。来源配置见 `config/p2_2_source_pilot.json`，试点必须在数据库副本运行：先对副本执行004迁移，再运行 `scripts/run_p2_2_real_source_pilot.py --db <副本路径>`。Playwright和Docling分别使用可选依赖文件，未安装不影响主应用。真实结果与限制见 `docs/p2/P2_2_PILOT_RESULTS.md`.

当前状态与风险见 [PROJECT_STATUS.md](PROJECT_STATUS.md)、[KNOWN_ISSUES.md](KNOWN_ISSUES.md)、[架构](docs/ARCHITECTURE.md)、[数据模型](docs/DATA_MODEL.md)、[启动与验证](docs/STARTUP_AND_VERIFICATION.md)。

## P1 领域迁移

先运行 `.venv\Scripts\python.exe scripts\migrations\001_core_domain_unification.py --dry-run`，确认冲突后再运行 `--apply`。迁移自动创建一致性备份。


## P2.3 多来源研究融合

P2.3 增加经人工审核的产业事件、事实断言、来源冲突、专题工作区、企业/赛道对比、结构化引用报告和只生成草稿的 ResearchAgent。005 默认 dry-run；受控试点必须在数据库副本运行。详见 docs/p2/P2_3_RESEARCH_FUSION_MODEL.md、docs/p2/P2_3_PILOT_RESULTS.md 和 docs/p2/P2_3_TRAE_HANDOFF.md。
