# MVP-RC1.1 历史恢复归档清单

## 归档标识

- 创建日期：2026-08-12（Asia/Shanghai）
- 归档文件：`E:\Codex项目设计\招商一体化平台系统\archive\MVP_RC1_RECOVERY_20260812.zip`
- ZIP 大小：11,674,784 B（11.13 MiB）
- ZIP SHA256：`75DA301EA5F44A7C5DB51AA162C327394AE41C332B9724874D1B2E1F69CBE483`
- 归档用途：在不保留旧项目为运行依赖的前提下，保存 MVP-RC1 之前的 rescue Git 历史、未提交工作和必要恢复证据。

## Rescue 基线与未提交内容

- 来源：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-starter`
- 分支：`rescue/trae-4day-usable-mvp`
- HEAD：`ba8d653523beffcf916f7cb14ae22e46dd6bab4d`
- 归档时状态：52 项，其中 4 项 tracked modified、48 项 untracked。
- 保存方式：
  - 已验证的 Git bundle：`rescue_git/biopharma-intelligence-starter-rescue.bundle`；
  - branch、HEAD、human/porcelain status、recent log；
  - tracked 与 staged diff；
  - `rescue_uncommitted/current_files/` 下与 52 项状态逐一对应的当前文件快照；
  - `rescue_uncommitted/SNAPSHOT_INDEX.txt` 快照索引。

结论：52 项 rescue 未提交内容已完整保存，原 `biopharma-intelligence-starter` 未被写入、清理或删除。

## 归档内容

- 两个原始 Agent 文件包：
  - `生物医药产业情报Agent初版文件包_V1.0`；
  - `生物医药产业情报Agent第二轮校准包_V1.1`。
- 当前正式项目的 `PROJECT_DIRECTORY_INVENTORY.md`。
- 旧项目必要历史说明文件 `README.md`、`AGENTS.md`。
- `MVP_RC1_RECOVERY` 中 17 个必要数据库恢复副本、XML/JSON 验收证据。
- 包内恢复说明 `RECOVERY_README.md`。
- 98 个内容文件的包内 SHA256 清单 `CONTENTS_SHA256.txt`。

## 明确排除

- 旧项目 `.env`：仅记录其存在，不复制任何凭据值。
- `.venv`、`venv`、`node_modules`。
- 浏览器缓存、`__pycache__`、`.pytest_cache`。
- 大日志和 `.log` 文件。
- SQLite `-wal`、`-shm` 活跃旁路文件。
- `MVP_RC1_RECOVERY` 中重复的嵌套源码 ZIP；正式 Git bundle 与 52 项快照已作为可核验恢复来源。

## 验证结果

- ZIP 打开测试：通过。
- ZIP 文件 SHA256：已记录。
- ZIP 内容条目：99 个，其中 `CONTENTS_SHA256.txt` 记录并校验其余 98 个内容文件。
- 内容逐文件 SHA256：98/98 通过。
- Rescue status 条目：52；对应文件快照：52；数量与路径核对通过。
- Git bundle：`git bundle verify` 通过。
- 关键历史文件随机读取：通过（7 个文本/Markdown 文件）。
- 两个原始 Agent 内嵌 ZIP：均已打开检查。
- 禁止内容扫描：0 项 `.env`、虚拟环境、依赖目录、缓存、日志或 SQLite WAL/SHM。

## 目录处置结论

### KEEP

- `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1`：唯一正式项目目录。
- `E:\Codex项目设计\招商一体化平台系统\生物医药产业情报Agent初版文件包_V1.0`：上游原始资料。
- `E:\Codex项目设计\招商一体化平台系统\生物医药产业情报Agent第二轮校准包_V1.1`：上游校准资料。
- `E:\Codex项目设计\招商一体化平台系统\archive\MVP_RC1_RECOVERY_20260812.zip`：经验证的唯一历史恢复包。

### ARCHIVE_COMPLETED

- `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-starter` 的 Git 历史、52 项未提交内容及必要说明。
- `E:\Codex项目设计\招商一体化平台系统\MVP_RC1_RECOVERY` 的必要恢复与验收证据。

### DELETE_SAFE_AFTER_USER_CONFIRMATION

- `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-starter`：Git bundle、状态、差异和 52 项文件快照均已验证保存；RC1 独立运行不依赖此目录。
- `E:\Codex项目设计\招商一体化平台系统\MVP_RC1_RECOVERY`：必要证据已进入经逐文件校验的恢复包；RC1 运行不依赖此目录。

本任务未删除任何旧项目一级目录。上述两个目录只有在用户最终确认后才可实际删除。
