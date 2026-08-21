# MVP-R2 Canonical Single Write 基线

核验时间：2026-08-21（Asia/Shanghai）

## Git与项目现场

| 项目 | 实测值 |
|---|---|
| 唯一项目绝对路径 | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1` |
| Git branch | `release/mvp-rc1.2` |
| Git HEAD | `b54ad1339504baaed2ac71dbfa4c74edf946acd1` |
| HEAD说明 | `MVP-R1 product surface consolidation` |
| git status | clean |
| 当前未提交文件 | 无；本文件创建前为clean |
| R1状态 | `PARTIAL / manual_browser_acceptance_pending / TOOLING_BLOCKED`，作为已知债务保留，本任务不重开R1页面改造 |

## 正式数据库只读基线

| 项目 | 实测值 |
|---|---|
| 绝对路径 | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db` |
| SHA256 | `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402` |
| `PRAGMA integrity_check` | `ok` |
| 非SQLite内部表数量 | 187 |

### 八张Canonical表行数

| Domain | Canonical Table | Rows |
|---|---|---:|
| Intelligence | `v06_intelligence_items` | 25 |
| Resource | `v06_market_resources` | 20 |
| Match | `p4_resource_match_candidates` | 0 |
| Opportunity | `v06_opportunities` | 11 |
| FollowUp | `v06_follow_ups` | 4 |
| Task | `v06_collab_tasks` | 4 |
| Relationship | `p3_canonical_relationships` | 0 |
| Relationship Evidence | `p3_relationship_evidence` | 0 |

### 对应Legacy表保护计数

| Legacy Table | Rows |
|---|---:|
| `raw_intelligence` | 1 |
| `resources` | 8 |
| `v04f_club_needs` | 0 |
| `v04f_club_offerings` | 1 |
| `v04f_club_matches` | 0 |
| `v04f_lead_records` | 0 |
| `v06_follows` | 0 |
| `task_queue` | 0 |
| `task_runs` | 0 |
| `actions` | 7 |
| `relations` | 26 |
| `v04c1_canonical_relations` | 0 |
| `v04c1_fact_evidence` | 0 |

## R1临时账号事实

- 正式数据库中 `mvp_r1_operator_20260821`：0。
- 正式数据库中 `mvp_r1_viewer_20260821`：0。
- 两个账号仅存在于Windows OS临时验收库 `mvp_r1_browser_acceptance_20260821.db`；记录时共2条。
- 记录事实后已停止R1临时Web实例并删除该OS临时数据库及其两个临时日志；未对正式数据库执行删除或写入。

本文件的数据库查询全部使用SQLite `mode=ro`。R2开发、Golden Loop、HTTP/session验收和任何写入测试只能使用OS临时测试数据库。
