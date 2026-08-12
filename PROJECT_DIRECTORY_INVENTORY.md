# PROJECT DIRECTORY INVENTORY

盘点日期：2026-08-10（Asia/Shanghai）
父目录：`E:\Codex项目设计\招商一体化平台系统`
正式基线：`release/mvp-rc1` / `6bc4186840ad0fc0beb607e601b5b24707c349ce` / `checkpoint-mvp-rc1-deliverable`

## 结论

唯一正式项目目录确定为：

`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1`

普通开发只在该目录内使用 Git branch。不得再复制整个项目作为常规开发目录。高风险实验确需 worktree 时，只能放在 `E:\Codex项目设计\招商一体化平台系统\.worktrees\`，任务结束后清理；`C:\tmp` 不得作为正式工作树。

## 一级目录盘点

大小为首次只读盘点时的磁盘占用（包含 Git、本地数据库及既有生成物；在本轮创建 `.venv` 之前）。

| 目录 | 大小 | Git / branch / HEAD | Git status | `data/app.db` / SHA256 | `.env` | RC1 不存在的相对路径 | 与正式 RC1 的关系 | 结论 |
|---|---:|---|---|---|---|---|---|---|
| `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1` | 349,355,414 B（333.17 MiB） | 是 / `release/mvp-rc1` / `6bc4186840ad0fc0beb607e601b5b24707c349ce` | 初始干净：`## release/mvp-rc1` | 有 / `A28E2DE7B71E608931088B262D6304B0426954CE0C064185C4133A38ED63D138` | 有 | 不适用 | 唯一正式项目与正式数据库所在目录 | **KEEP** |
| `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-starter` | 450,505,731 B（429.64 MiB） | 是 / `rescue/trae-4day-usable-mvp` / `ba8d653523beffcf916f7cb14ae22e46dd6bab4d` | 52 项：4 modified + 48 untracked | 有 / `504BB67DED8468A53F5BD898E772FFA56BCD1C3C1591D3D5D9E2A371E9489BD5` | 有 | 排除生成物/数据库后为 0；836 个相关路径均在 RC1 存在，813 个同内容、23 个内容不同 | 旧主项目/rescue 工作树；本轮未修改 | **DO_NOT_DELETE** |
| `E:\Codex项目设计\招商一体化平台系统\MVP_RC1_RECOVERY` | 83,346,001 B（79.48 MiB） | 否 | 不适用 | 无 `data/app.db` | 无 | 30 个（数据库副本、WAL/SHM、JUnit、浏览器日志、源码快照） | RC1 制作过程的回滚与验收证据，不是运行目录 | **ARCHIVE** |
| `E:\Codex项目设计\招商一体化平台系统\生物医药产业情报Agent初版文件包_V1.0` | 428,758 B（0.41 MiB） | 否 | 不适用 | 无 | 无 | 8 个源文档/表格/压缩包 | 上游需求与数据架构原始资料，不是项目副本 | **KEEP** |
| `E:\Codex项目设计\招商一体化平台系统\生物医药产业情报Agent第二轮校准包_V1.1` | 318,635 B（0.30 MiB） | 否 | 不适用 | 无 | 无 | 8 个校准文档/表格/压缩包（含 1 个 Office 临时文件） | 上游校准资料，不是项目副本 | **KEEP** |

## rescue 工作树保护记录

`biopharma-intelligence-starter` 的 52 项未提交状态已只读确认，未执行 checkout、stash、reset、clean、写入或删除。

- 已跟踪修改（4）：`.gitignore`、`app/templates/base.html`、`app/templates/v05e_dashboard.html`、`app/templates/v05e_signals.html`。
- 未跟踪（48）：`acceptance_report_v06L_corrected.md`；`app/capability_guard.py`；`app/services/schema_preflight.py`；`app/templates/capability_unavailable.html`；`docs/AI_CONTEXT.md`、`AI_WORKFLOW.md`、`CODEX_TASK_TEMPLATE.md`、`DATABASE_PROTECTION.md`、`DECISION_LOG.md`、`DO_NOT_TOUCH.md`、`FUTURE_MODULES.md`、`HANDOFF_TEMPLATE.md`、`KNOWN_ISSUES.md`、`PDP_v1.0.md`、`PROJECT_ARCHITECTURE.md`、`PROJECT_CHARTER.md`、`PROJECT_MEMORY.md`、`PROJECT_ROADMAP.md`、`README.md`、`ROLE_MATRIX.md`、`RULE_ZERO.md`、`TASK_CHECKLIST.md`、`TRAE_TASK_TEMPLATE.md`、`v06i_runtime_baseline.md`、`v06j_migration_audit.md`、`v06k_p4_operations_contract.md`；`export_routes.py`；`run_rehearsal_auth.bat`；`scripts/check_db_tables.py`、`check_intelligence_data.py`、`check_membership_application.py`、`check_people_data.py`、`check_recommendations.py`、`check_rehearsal_status.py`、`check_rehearsal_version.py`、`check_server_logs.py`、`check_tables.py`、`clean_test_data.py`、`clean_test_opp.py`、`export_routes.py`、`migrate_db.py`、`migrations/000_legacy_runtime_baseline.py`、`restore_test_opp.py`、`runtime_info.py`、`test_workspace.py`；`tests/test_v06i_runtime_baseline.py`、`test_v06j_migration_chain.py`、`test_v06k_p4_operations_contract.py`。

两个 Git 对象库无法直接计算 merge-base；未通过复制对象或 fetch 改变任何仓库。路径级比较显示旧目录没有 RC1 缺失的相关文件，但仍有 23 个同路径内容差异，且 52 项未提交工作必须由用户另行确认，因此当前绝不能删除。

## 独立运行证据

| 项目 | 实测结果 |
|---|---|
| 其他实例 | 运行前无相关 Web/Worker/Scheduler 进程，无 8000–8099 监听，无需终止进程 |
| Python | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\.venv\Scripts\python.exe` |
| 工作目录 | 正式 RC1 根目录 |
| `.env` | 正式 RC1 根目录下 `.env` |
| 模板 / static | 正式 RC1 的 `app\templates` / `app\static` |
| Web 数据库 | 浏览器验收显式使用 RC1 内 `data\acceptance` 隔离副本；正式库未写入 |
| 启动 | `start_web_windows.bat` 成功，Uvicorn 仅监听 `127.0.0.1:8000`，Scheduler/Worker 均未嵌入 Web |
| 停止 | `web_service_windows.bat stop` 成功停止完整 PID 树；端口监听数归零 |
| Worker 状态 | `scripts/runtime_info.py Worker` 返回 0，并打印隔离库的脱敏绝对路径 |
| 浏览器 | Edge 实测 `/login`、`/platform`、`/network`、`/intelligence`、`/resources`、`/collaboration`、`/club`、`/platform/golden-loop` 均为 200；Console/Page/Network 错误均为 0 |
| Golden Loop | 独立副本上达成/未成交/暂停三分支、权限、幂等、重启持久化、清理、外键及完整性全部通过 |

运行时代码和正式 Windows 启动入口没有读取旧项目目录。三个历史/可选 pilot 脚本仍把 `C:\tmp` 用作临时数据库默认值，另有一个诊断脚本硬编码旧 starter 日志目录；这些脚本未被正式 Web、Worker 状态或 Golden Loop 路径调用，故不是 RC1 运行依赖，作为后续 C/D 类工程债务记录，不在本轮扩修。

## 归档与删除建议

- `biopharma-intelligence-starter`：当前 **DO_NOT_DELETE**。待用户先处理/保存 52 项未提交内容后，可压缩为 `archive\biopharma-intelligence-pre-mvp-rc1-20260810.zip`；压缩包校验通过前不得删除源目录。
- `MVP_RC1_RECOVERY`：建议 **ARCHIVE** 为 `archive\biopharma-intelligence-mvp-rc1-recovery-evidence-20260810.zip`。确认压缩包可读且 SHA256 已记录后，才可另行申请删除原目录。
- 两个 Agent 文件包：**KEEP**，它们是源资料，不参与运行，也不构成第二项目目录。
- 当前没有任何一级目录可直接判定为 **DELETE_SAFE**；本轮不删除任何目录。

- Known C-class tooling debt: `status_windows.bat` produced a nested `powershell -NoProfile` parsing error in this automation host. The dedicated `scripts/runtime_info.py Worker` command and `web_service_windows.bat status` both passed, so this is recorded but is not a standalone-runtime blocker.
