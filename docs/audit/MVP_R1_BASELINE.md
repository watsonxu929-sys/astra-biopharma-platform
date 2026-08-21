# MVP-R1 正式产品表面基线

核验时间：2026-08-21（Asia/Shanghai）

## 运行与 Git 基线

| 项目 | 实测值 |
|---|---|
| 唯一项目根目录 | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1` |
| Git branch | `release/mvp-rc1.2` |
| Git HEAD | `b79efabcec4e5a58d4490f076efb8ceb042a7cbd` |
| git status | clean |
| 正式启动入口 | `run_windows.bat`（内部调用 `start_web_windows.bat`） |
| 实际 Web 命令 | `.venv\Scripts\python.exe -m uvicorn app.main:app --host <APP_HOST> --port <APP_PORT>` |

## 正式数据库只读基线

| 项目 | 实测值 |
|---|---:|
| 绝对路径 | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db` |
| SHA256 | `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402` |
| `PRAGMA integrity_check` | `ok` |
| 非 SQLite 内部表数量 | 187 |
| `people` | 44 |
| `organizations` | 24 |
| `v06_intelligence_items` | 25 |
| `v06_market_resources` | 20 |
| `v06_opportunities` | 11 |
| `v06_follow_ups` | 4 |
| `p4_resource_match_candidates` | 0 |
| `p3_canonical_relationships` | 0 |

## 产品表面规模基线

| 项目 | 修改前 |
|---|---:|
| Capability 定义 | 62 |
| viewer 可见 Capability | 41 |
| operator 可见 Capability | 56 |
| 一级导航 | 6 |
| FastAPI 实际展开 Route 上下文 | 700（由当前 704 减去本轮新增的 4 个兼容别名路由可靠反推） |
| FastAPI 实际展开唯一 path | 643（由当前 647 减去本轮新增的 4 个唯一兼容路径可靠反推） |

当前完整加载 `app.main:app` 后的实测值为 704 个 Route 上下文、647 个唯一 path。`len(app.routes)` 当前为 77，它统计的是顶层对象（含 lazy router），不是 FastAPI 实际注册路由数，因此不再作为路由规模口径。修改前的真实展开值只按本轮 Git diff 中明确新增的 `/dashboard`、`/resources/demand`、`/resources/supply`、`/resources/matching` 四个别名路由反推；未使用顶层对象数伪装真实路由数。

说明：`DATA_LOCATION.md` 中保存的是较早任务的 SHA256。本文件记录的是 MVP-R1 开始时再次实测的当前值；本任务以本值及上述核心表行数作为前后零业务数据变化基准，不改写正式业务数据。
