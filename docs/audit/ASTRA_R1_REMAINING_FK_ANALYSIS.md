# ASTRA-R1 剩余 25 条 FK 分类与修复决策

日期：2026-09-14。仅 READ ONLY + CLASSIFICATION；本轮未执行修复、测试、迁移或 Git 提交。
正式库：E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db
Branch：release/mvp-rc1.2；HEAD：3a491a5b61632b9531f08f5453e66978444398e5。

## 1. 25 条 FK 分布

| 子表 | 违规数 | 缺失父对象 |
| --- | ---: | --- |
| v06_collab_tasks | 4 | v06_opportunities #1、12、13、14 |
| v06_follow_ups | 4 | 同上 |
| v06_timeline_entries | 16 | 同上，每个父对象 4 条 |
| v05c_club_event_profiles | 1 | events #7 |

四个已修复的 Membership 表各 0；本轮违规没有 Membership、Relationship 或 Resource 链。
开始/结束均 integrity_check=ok、foreign_key_check=25，违规集合完全不变。
正式 DB 前/后 SHA256 均为 d0dd10b1f7135cb06804cc1a91c99fcce50ab90f55d7d4f9d7aecff87f039267；全部表逻辑摘要及 Schema 摘要相同。
原 39 项 G/H 修改及此前 4 份 ASTRA 审计文件保持；本轮只新增本文件与两份 CSV。

## 2. 根因组

**2 个根因组，5 个父对象业务链实例；不是 25 个独立问题。**

### GROUP-01：验证 Opportunity 的父记录缺失，测试子链残留（24 条）

| 链 | Task ID | FollowUp ID | Timeline ID | 创建时间 |
| --- | --- | --- | --- | --- |
| OPP-1 | 1 | 1 | 1–4 | 2026-07-03 17:05:10 |
| OPP-12 | 2 | 2 | 23–26 | 2026-07-03 22:11:05 |
| OPP-13 | 3 | 3 | 27–30 | 2026-07-03 22:28:33 |
| OPP-14 | 4 | 4 | 31–34 | 2026-07-05 08:26:32–33 |

强证据为组合指纹：scripts/verify_platform_mvp_v1.py:148–153 固定创建 Test Opp，lead→contacted，再创建 test follow-up 与 Test Task；四条链均具备同顺序四类 Timeline、同父 ID、actor/created_by=0 及紧邻时间。并非仅凭英文名称判断。Task is_demo=0，故不能使用 is_demo 单字段判真，也不能用宽泛名称批量删除。

只读检查 data/backups 的 144 份现有 DB：未找到父 #1/12/13 的原行，但 created Timeline 与完整链保留；父 #14 在备份中存在，title=Test Opp、stage=contacted、is_demo=0、created_at=2026-07-05 08:26:32.992843。下列关键备份完整性均 ok：
- app_before_001_core_domain_unification_20260710_110104_386155.db：全部 24 条子记录历史列与当前完全一致，且保留父 #14。SHA256：0e9743f46294fdacfe39f88074686704d08ee0e88ff0ec74025f5d0ab2455f45。
- app_v06c_fk_audit_20260704_171951.db：前 3 条链共 18 条子记录历史列与当前一致。SHA256：673c0df7c1441fe039f86e3a982bf2f3c39d37496aa12ab349d5ce712ad22071。

scripts/clean_test_opp.py:3,16 直接连接 data/app.db，未开启 FK，只按 title LIKE 'Test%' 删除父表，遗漏所有子链。该代码可解释孤儿机制；未找到历史执行日志，不能断言具体运行人、时间或每次删除均由该脚本执行。
当前正式 Opportunity 共 11 条且全为 is_demo=1；这些存活父对象不在本轮 25 条清单内，禁止一并清理。

CURRENT_WRITE_PATH：platform_service.py:711–739 已转 UnifiedOpportunityService；其 detail/create_follow_up/create_task 校验父对象，app/database.py:18 开启 FK。verify_platform_mvp_v1.py:187 的正常 CLI main 已隔离临时 DB，scripts/test_db_utils.py:17 拒绝正式库，tests/conftest.py 将测试会话指向副本。本轮未运行这些测试。
REPRODUCIBLE_RISK=YES：clean_test_opp.py 仍是可手工执行的无保护写路径；默认 sqlite3 连接 FK=0 已在只读连接核实。未发现它被现行 app/scripts/tools 调用或调度的引用，不等于正在后台运行。
restore_test_opp.py:3–23 也仍可手工向正式库制造 Test Opp，应禁止使用，但它不是解决这些孤儿的方法；本轮未修改上述代码。

### GROUP-02：管理员删除 Event #7 后，Club Profile #1 残留（1 条）

原父可定位但业务用途和删除意图未解决，不能自动恢复或删除：
- 当前 profile #1：event_id=7，event_no=QBE-20260630-0001，draft，创建于 2026-06-30T16:37:32。
- app_before_migrate_all_20260701_093703.db：events #7，external_id=EVT-20260630-000001，name=Q BAY，source_type=v0.5C Q-BAY活动，创建时间与 profile 一致；profile 历史列完整匹配。SHA256：c35ff931fa0b4639aeece64659b90525fd150497540a2bd4131d27947db00bfb；integrity_check=ok。
- 正式 v05a_audit_logs #44：2026-07-01T13:57:15，POST /manage/events/7/delete，success/303。这是明确的历史删除动作，不可将有备份等同于应撤销该动作。
- 未找到 is_test/is_demo、seed/fixture 固定来源等强测试证据；draft、短标题、无活动日期不足以证明是测试，也不足以证明是真实已运营活动。因此分类 F，不把可找回历史行误报为 B 类可恢复真实引用。
- event_id 为 NOT NULL，不能 SAFE_DETACH。下游报名、参与、反馈、签到及关系候选共 6 类当前计数均 0；零引用不是删除授权。

CURRENT_WRITE_PATH：app/v05c_club_events.py 创建入口→ClubEventService.create_event，父子同一事务；delete_safe_draft 子先父后。旧 app/main.py:889 generic_delete 仍存在、缺少 Event 专项友好提示，但 app/database.py 开启 FK 后会拒绝删除被 profile 引用的父记录；本轮只做静态检查，不以真实写入复现。
REPRODUCIBLE_RISK：受检 FK ON 正式路径未发现同类新增孤儿通路。绕过正式连接、关闭 FK 的维护脚本仍是一般风险，不能据此认定当前 UI 正在制造孤儿。

## 3. 各分类数量

| classification | 数量 |
| --- | ---: |
| CONFIRMED_TEST_DEMO_ORPHAN | 24 |
| REAL_PARENT_RECOVERABLE | 0 |
| SAFE_DETACH | 0 |
| SCHEMA_REFERENCE_BUG | 0 |
| REAL_HISTORY_PARENT_MISSING | 0 |
| AMBIGUOUS_DO_NOT_TOUCH | 1 |
| 总计 | 25 |

E 类为 0 不代表排除真实历史；Event 用途仍未证实，按更保守的 F 保留。CSV 的 parent_recoverable 区分“仅有历史快照”与“已批准真实恢复”。

## 4. 哪些可以安全修

GROUP-01 可在另行授权、重新备份及逐行重核后，按 OPP-1/12/13/14 分别清理明确测试链，保留取证记录；不恢复 Test Parent，不置 NULL 掩盖问题。
每链精确限定 1 Task + 1 FollowUp + 4 Timeline。当前未发现指向这三类子记录的入向 FK，按命名字段检索亦未发现其他 Opportunity 子链；正式执行仍须重查显式及多态引用。
v04d_structure_items / v04d_task_actions / v04db_extraction_runs 的同值 task_id 指向 v04d_structuring_tasks，并非 v06_collab_tasks，绝不能据数值相同连带处理。

## 5. 哪些必须继续阻断

GROUP-02 保留。需业务负责人确认 Event #7 原本是试建/错误活动还是应保留的真实草稿，并解释 2026-07-01 删除意图，再决定是否删除残留 Profile 或恢复原父记录。
不得制造替代 Parent、改绑任意现有 Event、忽略审计恢复旧数据，或因下游为 0 直接删除。

## 6. 哪些需要 Schema

本轮 0 条。四类 FK 的目标均是存在且语义正确的父表，问题是对应父行不存在；未发现类似 Membership 的错误目标表。无需 ALTER/DROP 或 nullable 变更来处理本清单。

## 7. 下一步建议执行顺序（仅设计）

1. 单独授权阻断 clean_test_opp.py 等手工正式写风险；不恢复 Demo Parent，不批量执行历史清理脚本。
2. BATCH 1：新维护窗口和一致性备份后，GROUP-01 按四条父链分别事务处理并验证。若基线仍完全一致，预计 FK 数按 25→19→13→7→1 变化；任一集合差异即回滚本链并停下。
3. BATCH 2（可恢复真实引用）、BATCH 3（安全解绑）、BATCH 4（Schema）：当前均无获证候选，不执行。
4. BLOCKED：GROUP-02 等待业务确认，不能为了 FK=0 自动处理。
5. 本轮只读结果停在 FK=25。未修改正式库、备份、产品代码或 G/H 文件；未进入 ASTRA-R2。

原始逐条记录见 ASTRA_R1_REMAINING_FK_25_RAW.csv；分类、证据和写路径见 ASTRA_R1_REMAINING_FK_DECISIONS.csv。每份 CSV 恰好 25 行，violation_id 一一对应。
