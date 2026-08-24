# MVP-R6 真实运营基线

记录时间：2026-08-24（Asia/Shanghai）

## 工程与数据库

| 项目 | 基线 |
| --- | --- |
| Branch | `release/mvp-rc1.2` |
| HEAD | `064bc7ff842455734a791300e2d41d85c356ea4a` |
| Git status | clean |
| Project path | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1` |
| DB path | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db` |
| DB SHA256 | `53A5C361A861A214C0BFA433EC66DC0831976C99D7E6765C981F5F722C74F6B7` |
| `PRAGMA integrity_check` | `ok` |

基线采集前发现端口 8000 上仍有本仓库的 `uvicorn --reload` 父子进程。核对命令行与工作目录后仅停止这些进程；端口关闭后数据库 SHA256 仍与 R5B 冻结值完全一致，未发生业务数据变化。

## 当前正式记录

| 指标 | 数量 |
| --- | ---: |
| 正式 Source | 6 |
| 启用 Source | 5 |
| Collection Item | 403 |
| Intelligence | 25 |
| People | 44 |
| Organizations | 24 |
| Projects | 5 |
| Intelligence Subject Link | 0 |
| Resource | 29 |
| Match | 0 |
| Opportunity | 11 |
| FollowUp | 4 |
| Canonical Relationship | 25 |

## 过去 7 天

统计窗口：`2026-08-17 00:00:00` 至本基线记录时间。

| 指标 | 数量 |
| --- | ---: |
| 采集次数 | 10 |
| 成功/部分成功/无变化 | 10 |
| 失败 | 0 |
| 抓取记录 | 20 |
| 重复或无变化记录 | 15 |
| 新正式 Intelligence | 0 |
| 无主体关联的 Intelligence | 25 |

## 基线判断

当前系统已经能稳定取得真实网页和 EMA Feed 内容，但过去 7 天没有任何采集结果完成“有证据候选 → 人工审核 → 正式 Intelligence → 主体确认”。R6 的约束性瓶颈是现有处理、发布和主体确认链没有连通，不是 Source 数量不足；因此先打通现有 Canonical 链，再审慎增加高质量来源。
