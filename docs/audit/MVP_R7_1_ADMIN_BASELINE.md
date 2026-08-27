# MVP-R7.1 管理员可运营性基线

记录日期：2026-08-27（Asia/Shanghai）

## 代码与数据库

- 唯一正式项目目录：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1`
- Branch：`release/mvp-rc1.2`
- HEAD：`05abc5b11619a40271bf8cf2a39c4dadeb000ef8`
- Git status：clean
- 正式数据库：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`
- SHA256：`F8EB52A538F12E73EFAC47F989E04FD907E6864BF2D61A56A9D71550E6DDCE0D`
- `PRAGMA integrity_check`：`ok`

本基线只通过只读连接查询正式库。R7.1 的CRUD、删除、报名、导入和浏览器写验收必须使用隔离数据库副本。

## Source

| 指标 | 数量 |
|---|---:|
| 总数（未退役） | 15 |
| ACTIVE | 6 |
| CANDIDATE | 4 |
| DISABLED | 5 |
| 有历史采集记录 | 9 |
| 从未成功采集（`last_success_at IS NULL`） | 5 |

Source状态沿用现有 `v04g_monitoring_sources`：ACTIVE为启用且未退役，CANDIDATE为停用且`health_status='candidate'`，其余停用来源归为DISABLED；不新增状态表或Source V2。

## Event

| 指标 | 数量 |
|---|---:|
| Event | 1 |
| Draft | 1 |
| Published/报名中/进行中 | 0 |
| Ended（completed/archived） | 0 |
| Cancelled | 0 |
| Registration | 0 |

活动继续复用 `events` + `v05c_club_event_profiles` 和既有报名表，不新增Event模型。

## Resource

| 指标 | 数量 |
|---|---:|
| 总数 | 30 |
| demand | 8 |
| supply | 22 |
| active（published/matched） | 30 |
| closed（expired/archived） | 0 |
| 有Match引用 | 0 |
| 有Opportunity引用 | 0 |
| 无Match/Opportunity下游引用 | 30 |

Resource继续使用 `v06_market_resources` 与 `UnifiedResourceService` Canonical Writer。正式库现有记录无论看起来是否像测试数据，本任务均不自动删除。

## 当前产品缺口

- Source网页只有列表与窄栏新增表单，缺少编辑、启停、退役确认、批量Preview和主动发现。
- Event已有创建和生命周期服务，但创建入口不够明确，缺少编辑和安全草稿删除；创建路由仍直接写表。
- Resource已有Canonical创建与状态更新，但缺少字段编辑、安全删除、批量部分成功和按权限隐藏操作。
