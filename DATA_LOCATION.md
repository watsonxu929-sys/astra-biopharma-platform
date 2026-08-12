# DATA LOCATION

核验日期：2026-08-10（Asia/Shanghai）

## 唯一正式数据库

产业情报系统今后的唯一正式 SQLite 数据库位置是：

`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`

不得把旧项目、rescue、recovery、`C:\tmp`、worktree 或测试副本中的 SQLite 文件作为正式运行库。旧库只可用于只读核对、归档或经审批的恢复演练。

## 只读核验结果

| 项目 | 结果 |
|---|---|
| 绝对路径 | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db` |
| 任务开始 SHA256 | `A28E2DE7B71E608931088B262D6304B0426954CE0C064185C4133A38ED63D138` |
| 全部运行/测试后 SHA256 | `A28E2DE7B71E608931088B262D6304B0426954CE0C064185C4133A38ED63D138` |
| SHA256 是否变化 | 否 |
| `PRAGMA integrity_check` | `ok` |
| 非 SQLite 内部表数量 | 187 |
| Canonical 核心表 | 10 / 10 存在 |
| 核心表清单 | `v05a_users`、`v06_intelligence_items`、`organizations`、`people`、`projects`、`resources`、`events`、`p3_canonical_relationships`、`v06_market_resources`、`v06_opportunities` |

## 路径解析证据

- 实际 Python：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\.venv\Scripts\python.exe`。
- 实际工作目录与 `PROJECT_ROOT` 都是正式 RC1 根目录。
- 实际 `.env` 是正式 RC1 根目录下的 `.env`。
- `app/settings.py` 以当前文件所在项目根为基准解析 `DATABASE_URL` / `APP_DB_PATH`；实测解析结果就是上述正式库。
- `app/database.py` 只使用 `resolved_database_url()` 和 `resolved_db_path()` 创建引擎。
- 模板和静态文件分别解析到正式 RC1 的 `app\templates` 与 `app\static`。
- 正式 Web 启动脚本把 Scheduler 和 Worker 显式关闭，避免 Web 进程产生后台写入。

## 本轮验收数据库

为遵守“不得修改正式业务数据”，Web 浏览器、Golden Loop 和全量 pytest 均在 `data\acceptance` 下的独立副本上执行。副本由 SQLite backup API 从正式库只读创建；Golden Loop 在副本上完成写入、重启持久化和清理，marker 残留为 0，外键状态前后不变。

这些副本不是正式数据库，不得被 `.env`、启动脚本或后续普通开发长期引用；它们位于 Git 忽略范围内，不得交付或提交。

## 数据安全规则

1. 正式运行只允许使用上述唯一 `data\app.db`。
2. 测试、浏览器写操作、迁移演练、恢复演练和 pilot 必须显式使用带 `test`、`acceptance`、`copy` 或 `rehearsal` 标识的副本。
3. 正式库变更前必须先备份并记录 SHA256；禁止 `DROP TABLE`、清空或破坏性重建。
4. 新 worktree 不得共享可写正式数据库；高风险实验只能使用自己的数据库副本。
5. `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-starter\data\app.db` 的 SHA256 为 `504BB67DED8468A53F5BD898E772FFA56BCD1C3C1591D3D5D9E2A371E9489BD5`，它与正式库不同，且明确不是 RC1 运行依赖。
