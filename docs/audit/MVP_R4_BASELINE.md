# MVP-R4 基线与正式现场

记录日期：2026-08-24（Asia/Shanghai）

## 正式基线

| 项目 | 值 |
| --- | --- |
| Project absolute path | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1` |
| Branch | `release/mvp-rc1.2` |
| HEAD | `9b16c75d074fabec3197106d941d45b16c370ad7` |
| Preflight git status | clean |
| Formal DB | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db` |
| DB SHA256（Preflight） | `7A36C67B16925C69C708E7DD7B3040A6B8C3C48C02E956D76CDA291871A980E7` |
| integrity_check | `ok` |

正式数据库仅用于只读基线和页面回归。R4 自动写验收只使用 `tests/conftest.py` 从专用 `data/t1_test.db` 复制到操作系统临时目录的测试数据库；测试目标与正式库绝对路径不相同。

## 核心表数量

| Table | Rows |
| --- | ---: |
| people | 44 |
| organizations | 24 |
| projects | 5 |
| v06_intelligence_items | 25 |
| core_intelligence_subject_links | 0 |
| v06_market_resources | 29 |
| p4_resource_match_candidates | 0 |
| v06_opportunities | 11 |
| v06_follow_ups | 4 |
| v06_collab_tasks | 4 |
| p3_canonical_relationships | 25 |
| p3_relationship_evidence | 25 |

## R3 MANUAL_REVIEW 核对

| 项目 | 结果 |
| --- | --- |
| Legacy 来源 | `relations.id=18` / `REL-20260630-000010` |
| Legacy 关系类型 | 任职 |
| 来源主体 | 文本指向“陈金玲博士，高级副总裁，制剂研发和生产业务部”；当前 people 中不存在可安全匹配的人物 |
| 目标主体 | `ORG-20260629-000003`，名称为“标题：首页 \| 药明康德”，当前主体已失效且名称明显不是可接受正式机构名 |
| Evidence | Wuxi AppTec 公开领导页面来源文本；能支持公开履历语义，但不足以把不存在的正式人物主体自动映射到当前Canonical实体 |
| Canonical 目标 | 未创建；当前没有 `legacy_relation_id=18` 的Canonical Relationship |
| 冲突 | 人物主体缺失；目标机构失效/名称异常；自动接受会制造未经证实的主体关系 |
| 决定 | **EXCLUDE** |

EXCLUDE 表示该条Legacy记录不应迁移成正式Canonical关系。R4不伪造人物、不补造Evidence、不修改正式业务数据；正式Canonical Relationship仍为25条。

## R3迁移回滚备份

- 文件：`data/migration_backup/pre_mvp_r3_20260824_093559.db`
- SHA256：`E2C8ABB64D55A143829293B3005E9D6D846B9F84FAD674392D717C5F9071C11C`
- Git状态：被 `.gitignore` 的 `data/**` 规则忽略。
- Runtime依赖：无；正式配置仍指向 `data/app.db`。
- R4决定：KEEP，不删除。

## 现场注意事项

Preflight之后发现一个在R4之前由旧 `start_windows.bat --reload` 启动的本项目实例仍占用 `127.0.0.1:8000`。其PID文件已陈旧，强制终止未获额外进程操作授权，因此R4不会绕过审批停止它。候选版本HTTP/浏览器验收使用独立端口，且不把该旧实例当作R4证据。

## R4 验收后数据库复核

| 项目 | 值 |
| --- | --- |
| DB SHA256（最终测试复核后） | `F5185791D660895E351FC49D0B38DDEDDCDB4F7011D099ECD8A048202B1AACE9` |
| integrity_check | `ok` |
| 核心表数量 | 与Preflight逐表完全一致 |
| 正式验收数据写入 | `0` |

正式库在只读Uvicorn连接和SQLite WAL/checkpoint后文件级SHA256发生技术性变化；逐表业务快照没有变化，`integrity_check=ok`。所有会创建Resource、Match、Opportunity、FollowUp、Outcome、Evidence和Relationship的浏览器操作均在操作系统临时测试数据库中完成，临时目录已删除。
