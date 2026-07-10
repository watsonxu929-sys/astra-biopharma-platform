# v0.5K-L 生产化基础与持续运营说明

## 环境配置

复制 `.env.example` 为 `.env` 后配置运行环境。开发环境默认使用 `sqlite:///data/app.db`。生产环境必须设置 `SECRET_KEY` 和 `SESSION_SECRET`，否则配置校验会失败。

当前版本保留 SQLite 默认运行，同时识别 PostgreSQL 连接串。PostgreSQL 迁移工具只在显式 `--confirm` 时尝试写入目标库，不会自动切换业务系统数据库。

## 启停入口

- `start_web_windows.bat`：启动 Web 服务。
- `start_worker_windows.bat`：启动统一 Worker。
- `start_scheduler_windows.bat`：启动调度器。
- `start_all_windows.bat`：启动 Web、Worker 和调度器。
- `stop_all_windows.bat`：只停止本项目 `runtime/*.pid` 中记录的进程。
- `status_windows.bat`：查看本项目进程状态。

## 任务与调度

统一任务队列使用 `task_queue`、`task_runs` 和 `worker_heartbeats`。首版复用既有采集、加工、流水线、信号、报告、备份和质量服务，不复制业务逻辑。

调度器只负责将到期的 `scheduler_jobs` 转为任务队列记录。默认种子任务均为停用状态，需要管理员确认后启用。

## 备份与恢复

备份包保存在 `data/backups/v05kl/`，包含 SQLite 数据库副本、配置模板和 manifest。恢复工具默认 dry-run，必须使用 `--confirm` 才会写入目标数据库。

常用命令：

```bat
python scripts\restore_backup.py --list
python scripts\restore_backup.py --backup-id BKP-... --dry-run
python scripts\restore_backup.py --backup-id BKP-... --confirm
```

## 真实来源试运行

`scripts/pilot_real_sources.py` 默认只列清单或 dry-run，不联网。只有同时配置 `allow_real_run: true` 并传入 `--confirm` 时，才会把来源接入既有采集与流水线试运行。

```bat
python scripts\pilot_real_sources.py --list
python scripts\pilot_real_sources.py --dry-run --group pilot
```

## 质量与健康

系统运行中心页面：

- `/system/operations`
- `/system/health`
- `/system/tasks`
- `/system/backups`
- `/system/sources`

API：

- `/api/v1/system/health`
- `/api/v1/system/readiness`
- `/api/v1/system/tasks`
- `/api/v1/system/task-metrics`

健康检查只向未登录用户暴露基础状态；详细运行信息需要内部权限。
