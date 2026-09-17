# ASTRA-R1 GROUP-01 清理结果

执行日期：2026-09-14。审计补录与只读复核：2026-09-16。
本轮目标已满足；ASTRA-R1 尚有 GROUP-02 CONTROLLED_BLOCKER，不代表整体完成。

## 清理范围与结果

BEFORE foreign_key_check = 25；精确删除 = 24；AFTER foreign_key_check = 1。
PRE、POST、正式库 integrity_check 均为 ok。

| 缺失的测试 Opportunity | v06_collab_tasks ID | v06_follow_ups ID | v06_timeline_entries ID | 删除数 |
| --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 1,2,3,4 | 6 |
| 12 | 2 | 2 | 23,24,25,26 | 6 |
| 13 | 3 | 3 | 27,28,29,30 | 6 |
| 14 | 4 | 4 | 31,32,33,34 | 6 |

白名单来自 ASTRA_R1_REMAINING_FK_DECISIONS.csv。执行前 25 条 FK 与该表逐条一致，24 条完整字段与先前审计快照一致。
四个父 Opportunity 保持不存在，未恢复；其他 11 个 Demo Opportunity 未动。
唯一剩余：v05c_club_event_profiles #1 → events #7（FK id 0）。
Event #7 本来已不存在；其 profile #1、相关删除审计及全部未授权数据保持原样，未删除、恢复、置空或改 FK。

维护前未发现正式 Web/Worker/Scheduler/采集写入进程、8000 监听或相关计划任务；Restart Manager 两次未发现 DB/WAL/SHM 占用进程。未终止或重启运行实例。
维护连接 foreign_keys=1；BEGIN IMMEDIATE；按四链在一个总事务内删除；COMMIT 前核验剩余 FK、完整性、全表全部行值和 Schema。
读取真实 FK 拓扑确认三个目标子表无入向 FK；新增依赖即拒绝，不允许隐式级联。
正式库没有执行回滚；回滚能力已在隔离副本故障注入测试验证。
本次续办只读比对：PRE 减去白名单 24 行 = POST = 当前正式库；其余行值（含 sqlite_sequence）及 Schema 全部一致。
新增表/修改表/字段/FK/Migration 均为 0；产品业务代码未改。

## 备份与恢复

备份均使用 SQLite Backup API。恢复须另行明确授权；本轮没有执行恢复。

PRE：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_R1_PRE_GROUP01_CLEANUP_20260914_090701.db`
SHA256：`5efd6c6cbee310f09a82b6a2100c6a6cd392077f3492c33ed4a5deeafe80bfef`
integrity_check=ok，FK=25。

POST：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_R1_POST_GROUP01_CLEANUP_20260914_090701.db`
SHA256：`891c9a47c5e94a4b83173972aa7370bf4e4f76310ea1d68ef96040eb77a3eff7`
integrity_check=ok，FK=1。

正式库删除前 SHA256：`d0dd10b1f7135cb06804cc1a91c99fcce50ab90f55d7d4f9d7aecff87f039267`
删除后及本次只读复核 SHA256：`940f65e0ab58566717e96906c3d526041c4078bcc753a5644b2fc3ead8eb6c6f`

## 脚本保护与验证

scripts/clean_test_opp.py 仅接受明确 --db 和独立 --reference-db，默认 dry-run。
正式库（含同文件别名）必须 --allow-formal-db 与 --confirm-db 双重确认，执行另需 --apply。
非正式目标复用 assert_not_live_db。全程 FK ON、严格 24 条白名单、逐字段快照比较、完整链检查和全库差异验证。
父记录若存在则拒绝；已移除按标题删除 Opportunity 父记录的旧路径。再次运行因 FK 基线不再为 25 而拒绝。
维护窗口及验证过的新备份是正式执行前提，不由脚本自动创建。

2026-09-14 隔离验证 12 项通过：默认拒绝、正式未授权拒绝、错误确认拒绝、dry-run 不变、测试副本执行 FK=1、FK ON、重复执行拒绝、快照行被改拒绝、第二链故障时全事务回滚、新入向 FK 拒绝、正式库 SHA 不变、临时副本目录清除。
本次未重复清理，未运行全量 pytest 或浏览器验收（无业务/UI 修改）。无正式测试 Seed。
快速静态检查发现以下其他风险入口，仅记录，未修改：

- scripts/clean_test_data.py
- scripts/cleanup_test_data.py
- scripts/cleanup_identity_test_accounts.py
- scripts/restore_test_opp.py（测试父记录恢复入口）

## 文件与 Git 边界

ASTRA_R1_THIS_TASK_CHANGES / ASTRA_CHANGED_FILES：

- scripts/clean_test_opp.py
- docs/audit/ASTRA_R1_DATA_CHANGES.csv（保留原 5 条、追加本轮 24 条 DELETE）
- docs/audit/ASTRA_R1_GROUP01_CLEANUP_RESULT.md

此前 7 份 ASTRA 审计文件中，仅 DATA_CHANGES.csv 本轮追加；其他 6 份保持原样。
PREEXISTING_GH_CHANGES / PREEXISTING_CHANGED_FILES 共 39 项，与原安全清单逐文件 SHA256 一致：

```text
app/main.py
app/p3_network.py
app/platform/capability_registry.py
app/routes_club_facilities.py
app/routes_knowledge.py
app/routes_platform.py
app/security.py
app/services/canonical_relationship_service.py
app/services/club_facility_service.py
app/services/club_operations_service.py
app/services/data_quality.py
app/services/intelligence_product_service.py
app/services/knowledge_service.py
app/services/membership_access_service.py
app/services/navigation_service.py
app/services/unified_resource_service.py
app/templates/club_home.html
app/templates/p3_network.html
app/templates/platform/_bulk_delete_results.html
app/templates/platform/_knowledge_annotations.html
app/templates/platform/_knowledge_path_progress.html
app/templates/platform/_knowledge_training_fields.html
app/templates/platform/_reference_protection.html
app/templates/platform/_related_knowledge.html
app/templates/platform/admin.html
app/templates/platform/admin_organizations.html
app/templates/platform/admin_people.html
app/templates/platform/club_facilities.html
app/templates/platform/intelligence_detail.html
app/templates/platform/knowledge.html
app/templates/platform/knowledge_training.html
app/templates/platform/person_card.html
scripts/migrate_db.py
scripts/migrations/012_industry_knowledge.py
scripts/migrations/013_knowledge_training_and_rooms.py
tests/conftest.py
tests/test_mvp_rc1_2f_admin_and_membership.py
tests/test_rc12g_subject_cleanup_and_knowledge.py
tests/test_rc12h_training_and_rooms.py
```

Branch：release/mvp-rc1.2
HEAD：3a491a5b61632b9531f08f5453e66978444398e5
Working Tree：dirty，39 项 G/H + 8 份 ASTRA 审计文件 + 1 个维护脚本，共 48 项；未暂存、未提交。
GROUP-02 保持 CONTROLLED_BLOCKER。停止于本轮，不处理 Event #7，不进入 ASTRA-R2。

## CONTINUE-5｜Source 修正执行前白名单（2026-09-16）

仅健康字段，禁止修改启用、URL、名称、主体、last_checked_at/last_success_at。现有中性值 unknown 可用。
证据范围：全部现存运行记录、快照、采集项、source_rule_test_runs、source_health_scores、compliance_note/发现探测记录及时间字段。界面即时测试不持久化，不能把未保留的探测当作成功证据。

| source_id | 原状态 | 拟改状态 | 现有证据 | 原因 |
| --- | --- | --- | --- | --- |
| 2 | healthy | degraded | runs #2/#3 robots_denied; #4 skipped; no success/snapshot/item/probe | Only failed access evidence; enabling cannot override failure |
| 20 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 21 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 22 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 23 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 24 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 25 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 93 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 110 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 116 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 128 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 129 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 130 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 131 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 132 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 133 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 134 | healthy | unknown | runs=0 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 135 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 136 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 137 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 138 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 139 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 140 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 141 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 142 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 143 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |
| 144 | healthy | unknown | runs=1 (only pending if any); snapshots/items/rule tests/health scores=0; no stored probe or success timestamp | No valid success evidence; enabling is not a probe |

共 27 条，执行结果将在下方补录。待核对 1 条：Source #3，last_success_at 与 Snapshot #2 的“正在进行安全检测”页面冲突；存储保持，展示“历史成功记录与内容冲突，待核对”。其余具有成功快照的 #4/#10/#11/#16/#19 不本轮改写，不宣称其现在仍健康。

### CONTINUE-5 执行结果与检查

执行时间 2026-09-16T11:25:58；27 条白名单已完成（26 unknown、1 degraded），待核对 1 条 #3，未改其历史存储。未新增采集、联网探测或启停来源。
FK 前后完整集合均为 (v05c_club_event_profiles,1,events,0)，integrity_check=ok。单一事务、FK=1，全表行值比较确认仅白名单 health_status 改变；Schema=0。GROUP-01 未重跑。
PRE：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_R1_PRE_SOURCE_HEALTH_20260916_112556.db`；SHA256 `891c9a47c5e94a4b83173972aa7370bf4e4f76310ea1d68ef96040eb77a3eff7`。
POST：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_R1_POST_SOURCE_HEALTH_20260916_112556.db`；SHA256 `dd086f7231ac8c582dff74ac8f7bec2a61a0665c770c72457c53a7cbbe0f3416`。
正式库 SHA256：940f65e0ab58566717e96906c3d526041c4078bcc753a5644b2fc3ead8eb6c6f → c22e61b5ee08450ad9c0f9cb040b305e51da933e5a70c896ae7aec859fb1af67。两份 Backup API 备份均 integrity=ok、FK 集合一致。

四个历史脚本已无现行调用者且不具备安全完整链判断，保留显式 --db 参数及拒绝提示，移除所有数据库执行入口：clean_test_data（资源标题筛选删除）、cleanup_test_data（会员/人物父先删且 FK OFF）、cleanup_identity_test_accounts（清空全部绑定申请且 FK OFF）、restore_test_opp（向正式库插入 Test Opp）。任何目标均拒绝，不提供强制参数；导入不连接。没有复制四套 guard，也没有重建清理框架。
Source 既有 db_connection 在事务前开启并读回 FK=1；显式空路径拒绝、规范化解析路径、失败不回退。启用/停用只控制调度，不覆盖真实健康/错误记录；候选启用为 unknown。新建/批量导入复用原创建服务。
有效响应通过既有 RSS/JSON/HTML 解析与访问障碍校验后才可成功；重复/304/有效空 RSS/API 不误判失败。失败记录保留 HTTP 403/412 或超时原因。已有存储状态中性值 unknown 可用，不变更枚举或 Schema。
未覆盖：app/database.py:18 的 SQLAlchemy 连接已有 FK ON、未读回；仅记录未扩大修改。另发现 scripts/verify_identity_link_e2e.py:95、verify_membership_person_link_ui_v1.py:80、verify_membership_person_link_v1.py:85 内部清理 FK OFF，未执行、未改写。这不是“所有应用连接已加固”的声明。

直接相关隔离检查通过：4 脚本无参/导入/正式及隔离路径拒绝，连接 FK=1/空路径/失败不回退，单建/导入/启停语义，有效与重复/304，HTTP200 登录/验证码/错误页，403/412/超时，有效空 RSS/API 与无效响应。正式库在测试期间 SHA 不变，隔离目录已清理。未运行全量 pytest、真实采集或截图集；无浏览器验收声明。

### 剩余 Demo/Test 精确候选（只读）

范围仅现存标记及已知 seed/restore 指纹；59 条候选，不是全库真实性审计。A=46、B=13、C=0。B 保守包括与正式身份/审计混用且真实性未核实的关联，不把关联记录自动判为真实。未检查记录不算已核实真实。以下范围包含两端且每个 ID 连续存在。

| 类别 | 表、ID | 证据 | 下游影响 | 建议 |
| --- | --- | --- | --- | --- |
| A | people #32–39（8） | source_type=演示数据，匹配 seed_demo_platform_v1 人物 | 每人4条标签及1条Demo Profile；已查直接/主体/关系两端未见真实业务引用 | 保留；另行授权才可按整链清理 |
| A | v06_person_profiles #8–15（8） | is_demo=1，分别关联上述人物 | 随人物页展示；没有独立下游FK | 保留，与父人物共同决策 |
| A | v06_market_resources #3–22（20） | is_demo=1，匹配固定 seed 资源标题与类型 | 已查资源引用列、FK及多态引用无下游，主体关联空 | 保留；另行授权清理 |
| A | v06_opportunities #2–11（10） | is_demo=1、固定seed内容和阶段 | Timeline #5–22 共18条，符合seed阶段指纹；无FollowUp/Task | 保留；未来须连同已证实测试子链评估 |
| B | people #26–31（6） | source_type=演示数据、seed人物 | 与 membership_person_link_audit 混用：person_id引用16/38/29/21/12/2条，old_person_id引用8/21/18/13/8/2条；每人标签4、Profile1 | 冻结，先解释身份绑定历史 |
| B | v06_person_profiles #2–7（6） | is_demo=1，关联上述6人 | 随混用人物档案显示 | 随人物冻结，不拆解 |
| B | v06_opportunities #15（1） | is_demo=1，内容符合旧 restore_test_opp 的 Test Opp | initiator_id=1、owner_id=1，关联正式身份；无任务/跟进/时间线 | 冻结，核对操作者用途 |
| C | 本次受检候选0 | 未仅用名字/英文/数量归类 | 不涵盖未检查对象；Event #7 不归为测试 | 不自动清理 |

### Event #7 事实卡（冻结）

活动名 Q BAY；原活动日期/时间未记录（备份 event_date=NULL）；创建于2026-06-30T16:37:32，地点蔡伦路88号，主办Q-BAY。
当前残留 v05c_club_event_profiles #1，event_no=QBE-20260630-0001，draft，父 events #7 不存在。
现存报名/参与/反馈/签到/关系候选及跟进的事件引用未见；不能由此断言从未发生。删除审计 #44：2026-07-01T13:57:15，POST /manage/events/7/delete，success/303，理由未记录（detail_json={}）。
删残留将失去活动草稿编号、配置、地点/主办等信息并消除原FK证据；恢复父活动仅能恢复备份中的名称、身份与原草稿关联，不会证明活动真实发生，也不自动恢复报名或运营历史。两者均未执行，继续 CONTROLLED_BLOCKER。

### 本轮文件边界

本轮实际修改9个文件：

- scripts/clean_test_data.py
- scripts/cleanup_test_data.py
- scripts/cleanup_identity_test_accounts.py
- scripts/restore_test_opp.py
- app/v04c_review.py
- app/services/collection_service.py
- app/templates/v05f_collection.html（仅状态中文提示）
- docs/audit/ASTRA_R1_DATA_CHANGES.csv（原29条保留，新增27条UPDATE）
- docs/audit/ASTRA_R1_GROUP01_CLEANUP_RESULT.md（仅追加本节）

原39项G/H及clean_test_opp.py保持；未暂存、未提交。Branch release/mvp-rc1.2 / HEAD 3a491a5b61632b9531f08f5453e66978444398e5；Working Tree dirty。本轮停止，不进入ASTRA-R2。
