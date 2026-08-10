# v0.6J 统一迁移链审计与副本演练报告

## 1. 迁移审计摘要

- 原入口 `scripts/migrate_all.py` 混合旧 v0.4/v0.5 脚本，只登记005、006，遗漏001—004、007、008；以少量表是否存在代替版本历史，并在空库调用 `Base.metadata.create_all`。
- 原库迁移历史只有 `001_core_domain_unification` 一条成功记录；实际结构为001完整、003结构完整但无历史、004缺失，不能按连续版本宣称已到004。
- 005—007各自是默认 dry-run 的独立脚本；008只有可导入函数，且既有实现不补已有线索/机会/跟进/任务所需字段，因此此前没有进入正式统一链。
- 现在唯一注册表和执行实现位于 `scripts/migrate_db.py`；`scripts/migrate_all.py`与`migrate_all_windows.bat`仅转发参数，无隐式迁移。
- 新增000仅为空数据库提供显式、无业务数据的旧运行基线；不调用ORM `create_all`，正式库副本只做结构校验后采纳。
- 每个迁移源文件记录SHA-256；结构完整才允许采纳，部分结构或历史/校验和不一致立即停止，不静默修复漂移。
- 每步使用独立 `BEGIN IMMEDIATE` 事务，失败回滚后单独记录 `failed`；成功后执行 `wal_checkpoint(TRUNCATE)`，自动备份用于文件级回滚。

## 2. 修改文件清单

| 文件 | 修改内容 | 原因 | 风险 |
|---|---|---|---|
| `scripts/migrate_db.py` | 唯一注册表；status/plan/upgrade/target/显式数据库；历史、校验和、事务、漂移、备份、WAL checkpoint | 建立唯一可重复迁移链 | 中：迁移核心，已在空库和正式副本验证 |
| `scripts/migrations/000_legacy_runtime_baseline.py` | 空库所需最小显式基础DDL，不写业务数据 | 消除对ORM create_all和测试夹具依赖 | 中：只在真正空库执行 |
| `scripts/migrations/001_core_domain_unification.py` | 暴露支持表DDL供统一事务执行 | 复用既有001，不复制逻辑 | 低 |
| `scripts/migrations/008_business_collaboration_mvp.py` | 声明前置表、P5表和实际服务所需兼容字段 | 修复已有表不补列导致的迁移失败/读500 | 中：仅加表、列、索引 |
| `scripts/migrate_all.py`、`migrate_all_windows.bat` | 收敛为显式CLI兼容转发器 | 移除第二套列表和隐式执行 | 低 |
| `app/services/schema_preflight.py` | 按完整表、关键字段和索引判定P2.3—P5 | 防止“有表但字段不完整”误报enabled | 低 |
| `tests/test_v06j_migration_chain.py` | 发现、计划、空库、副本、幂等、失败、启动隔离测试 | 自动化迁移安全证据 | 低 |
| `tests/test_v06i_runtime_baseline.py` | 完整Schema夹具加入必需字段/索引 | 匹配增强后的Preflight定义 | 低 |

## 3. 迁移矩阵

| 编号 | 文件/目标 | 新增表 | 新增字段 | 索引/其他 | 前置依赖 | 原是否注册 | 幂等与风险 |
|---|---|---|---|---|---|---|---|
| 001 | `001_core_domain_unification.py` / 核心域统一 | `platform_entity_mappings`、`platform_migration_conflicts`、历史表 | 情报3、市场资源5、机会8 | 主体映射索引；映射/冲突写入 | 000基础主体与v06表 | 否（旧入口不含001） | 结构幂等；匹配冲突只记录不自动合并 |
| 002 | `002_repair_domain_integrity.py` / 完整性审计 | 无 | 无 | 只分析孤儿与冲突 | 001支持表 | 否 | 不自动修复；统一链记录审计完成 |
| 003 | `003_intelligence_evidence_pipeline.py` / 证据链 | 6张P2证据/审计表 | 6组采集、快照、原始情报、候选字段 | 5索引、快照不可变触发器 | 监测、快照、候选、v06情报 | 否 | 原库结构完整，校验后采纳 |
| 004 | `004_real_source_quality_evaluation.py` / 真实来源质量 | `p2_2_evaluation_runs`、`p2_2_fact_conflicts` | 5组质量、解析、成本字段 | 2索引 | 003各表 | 否 | 原库完全缺失，正常执行 |
| 005 | `005_research_fusion_engine.py` / P2.3研究融合 | 15张P2.3事件、事实、研究、报告表 | `research_topics` 5；报告8 | 8索引 | 003证据、研究专题、报告 | 旧入口仅独立调用 | 加法迁移；部分结构会阻断 |
| 006 | `006_entity_relationship_network.py` / P3主体治理与关系 | 12张主体治理、关系、推荐表 | 候选可见性1 | 12索引；43条关系类型参考字典 | 人物、机构、项目、原始情报、证据 | 旧入口仅独立调用 | 参考字典UPSERT；不自动合并主体 |
| 007 | `007_club_operations_mvp.py` / P4俱乐部与资源匹配 | 9张会员历史、签到、反馈、匹配候选、审计表 | 6组既有表共45个兼容字段 | 4索引 | 会员、活动、报名、市场资源 | 否 | 加法迁移；不生成活动/会员/匹配数据 |
| 008 | `008_business_collaboration_mvp.py` / P5业务协同 | 8张参与方、阶段、来源、会议、材料、风险、事件、审计表 | 线索、机会、跟进、任务、时间线、材料共42个兼容字段 | 10索引 | v04f线索与v06机会/跟进/任务/时间线 | 否 | 加法迁移；不创建线索或机会数据 |

000位于同一注册表最前，仅为空库显式建立001—008依赖的基础表；不代表新增业务阶段。

## 4. 模块结构映射

| 能力 | 关键结构 | 来源 |
|---|---|---|
| P2.3主体研究融合 | 15张`p2_3_*`表、专题/报告扩展、事件/事实/报告索引 | 005 |
| P3主体治理与产业关系 | 12张`p3_*`表、关系类型字典、候选可见性及关系索引 | 006 |
| P4俱乐部运营 | 会员历史、反馈、签到、活动关系候选、领域事件和审计；活动/报名扩展字段 | 007 |
| P4资源匹配 | `p4_resource_match_candidates`、`p4_club_lead_candidates`及`v06_market_resources`扩展 | 007 |
| P5业务协同 | 8张`p5_*`表；v04f线索、v06机会/跟进/任务/时间线兼容字段 | 008 |

## 5. 重复DDL与非正式入口

- `scripts/run_acceptance_migrations.py`复制008 DDL，并逐列捕获后继续；仅属验收历史脚本，不得作为正式入口。
- `scripts/manual_recovery/add_p5_opportunity_columns_DEPRECATED.py`和`add_p5_follow_up_columns_DEPRECATED.py`固定写验收库，且任务字段补丁存在定义丢失；仅保留为历史恢复痕迹。
- `tests/conftest.py`会复制正式库并注入P2测试来源；它是测试夹具，不是空库或正式迁移依赖。
- `scripts/migrate_v04f.py`只负责旧线索基础结构；008在其上做兼容扩展，不重复建立第二套线索模型。
- `apply_*`、`patch/fix/repair`、`create_acceptance_db.py`及各验证脚本均未登记为001—008正式迁移。

## 6. 数据库副本演练

| 数据库 | 起始/目标 | 结果 | 完整性 | 原数据状态 |
|---|---|---|---|---|
| `data/rehearsal/v06j_app_before.db` | 原库一致快照/001记录、003结构 | 只读基线 | integrity=ok；30条既有FK异常 | 165表；SHA-256 `A86E13C0...2922` |
| `data/rehearsal/v06j_app_migrated.db` | 基线 → 008 | 成功；9条成功历史 | integrity=ok；30条FK异常且集合不变 | 211表；旧业务表行数无差异；SHA-256 `560A4007...339` |
| `data/rehearsal/v06j_app_rollback_verified.db` | 自动备份恢复 | 回滚验证成功 | integrity=ok；表/FK集合与基线一致 | 行数和SHA-256与基线一致 |

执行耗时：000—003采纳约7.9/2.0/1.2/2.6 ms；004—008约218.5/154.3/63.1/397.3/281.5 ms。第二次upgrade返回`up_to_date`，步骤为空；稳定主文件哈希不变。

旧数据证明：除迁移历史外164张旧表行数全部一致；人物、机构、项目、资源、原始情报、市场资源、机会、线索的主键范围、关键字段非空数和前20条原字段样本哈希一致。新增P2.3/P3/P4/P5业务表均为0行，006仅写入43条关系类型参考字典。

## 7. 能力与Smoke结果

| 模块 | 迁移前 | 迁移后 | 仍缺内容 |
|---|---|---|---|
| P2.3研究融合 | disabled | enabled | 无业务数据；指定不存在专题返回404 |
| P3产业关系/主体治理 | disabled | enabled | 无关系和推荐数据 |
| P4俱乐部运营 | disabled | enabled | 旧`/club/operations`错误读取活动档案`event_date`而500，API正常 |
| P4资源匹配 | enabled（旧表） | enabled（含P4候选结构） | 无新匹配候选数据 |
| P5业务协同 | disabled | enabled | 无新线索、参与方、会议、材料或风险数据 |

只读HTTP Smoke共21个入口：18个200；`/research/findings`缺必填参数为422；不存在的专题1为404；`/club/operations`为代码字段错误500。无缺表503，演练库Smoke前后SHA-256不变。

## 8. 原始数据库保护声明

- `data/app.db`初始/结束SHA-256均为：`3EB3C405BE2B426B3F96090DC933FD76EE8766ABAC5DB59A005BC2A9F5972151`。
- 初始大小4,173,824 bytes；165张表；迁移历史仍仅001一条。
- 最终修改时间仍为 `2026-07-14T09:26:29.2039738Z`，`PRAGMA integrity_check=ok`。
- 本轮未对原库执行DDL、DML、迁移历史写入、账号创建、测试数据或业务数据写入；只用SQLite `mode=ro`读取并通过backup API创建演练快照。

定向自动化回归共82项，覆盖v0.6I/v0.6J迁移链、领域完整性、P2、P2.2、P2.3、P3和P4，结果为82/82通过。未运行全量历史测试，也未执行本报告第10节的任何历史/辅助脚本。

## 9. 正式迁移与回滚建议（未执行）

1. 停止所有Web、Scheduler和Worker，确保没有新的业务写入；用SQLite在线备份同时保存主库一致快照，并校验SHA-256、`integrity_check`和既有30条FK异常基线。
2. 运行 `python -m scripts.migrate_db plan --database data/app.db --target 008`；仅当计划为采纳000—003、执行004—008且`has_drift=false`时继续。
3. 维护窗口内显式运行 `python -m scripts.migrate_db upgrade --database data/app.db --target 008 --confirm-formal`。副本纯迁移不足2秒，建议预留5分钟及验证时间。
4. 迁移后核对status、Preflight、integrity/FK增量、旧表行数，并复测本报告的P2.3/P3/P4/P5入口。
5. 回滚只做停机后的文件级恢复：保留失败库及WAL用于审计，从执行器生成的迁移前备份恢复；不要对业务表做DROP式downgrade。

## 10. 现有历史/辅助脚本，本轮未处理

以下10个文件未修改、未移动、未重命名、未执行，也未作为正式迁移入口：

`check_db_tables.py`、`check_intelligence_data.py`、`check_people_data.py`、`check_recommendations.py`、`check_server_logs.py`、`check_tables.py`、`clean_test_data.py`、`clean_test_opp.py`、`restore_test_opp.py`、`test_workspace.py`（均位于`scripts/`）。

## 11. 未解决问题

- 原库已有30条外键异常，本轮证明迁移未新增；其治理不属于v0.6J。
- 旧页面`/club/operations`查询不存在的`v05c_club_event_profiles.event_date`而500；API和其余P4结构正常，按任务约束未顺手修复。
- 真实浏览器ACL问题按本轮额度控制明确不处理；本轮结论基于数据库、自动化测试及独立Web HTTP Smoke。
