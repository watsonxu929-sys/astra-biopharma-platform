# ASTRA-CLOSEOUT-03

## 当前结论：CONTINUE / 2026-09-17

STATUS = CODE_COMPLETE / MANUAL_ACCEPTANCE_PENDING。ACTIVITY_CHAIN_RESULT=通过；TECHNICAL_FREEZE_BLOCKER_CLEARED=YES（本轮活动参与链）；PC_V1_BASELINE_COMMITTED=NO。等待用户人工确认，不自动暂存/提交/Tag。

- 同一正常活动、同一有效普通会员，经正式UI连续完成创建→发布→开放→报名→管理员批准→参与→签到→双方查看；没有手工补参与或批准状态。隔离库Profile #3→events #8、registration #3、membership #539，普通会员角色viewer，审批使用独立admin。实际参与的membership_id与canonical_membership_id均为539，不是User ID。刷新和临时服务重启后双方仍显示已签到。
- 真实Chromium 151.0.7922.34 / 1440×900，从工作台菜单进入俱乐部与活动；Console、Page Error、Network Failure、HTTP错误均0，横向溢出0。隔离服务重启首次探测早于就绪出现连接拒绝；待健康检查200后完整查看检查通过，不计为产品故障。未做全站截图验收。
- 正常链业务请求FK OFF路径=0（限定本轮调用链）；复用db_connection事务前开启并回读1。父事件不存在时发布、开放、报名、批准、单个/批量签到及签到凭据入口拒绝，未改变正式Profile #1，也未向正式孤儿发送写请求。校验与成功状态/领域事件在同一事务。
- 审批/签到复核会员身份、有效期、活动归属及凭据对应关系；重复批准/签到不增加有效参与或成功签到领域事件；参与插入失败或成功事件写入失败均整笔回滚。批量签到不再吞掉全部失败后假成功跳转。我的报名复用当前登录身份并读取真实参与状态。
- 定向检查18/18：原11项报名/孤儿/迁移回归 + 新7项全链、权限、幂等、事务失败、取消、参与迁移回滚及初始化检查。均使用显式隔离库，不联网、不运行正式Scheduler；未跑全量pytest。编译和diff检查通过。

### 本轮唯一结构变更与恢复点

SAME_ROOT_FK_TABLES=v05c_club_event_participation。仅membership_id FK从退役v04f_club_memberships_old改为v04f_club_memberships(id)；迁移前0行，其余报名/签到表已正确直接跳过。保留全部字段/约束、显式索引、内建UNIQUE与sqlite_sequence(rowid=88,seq=3)；无触发器/入向FK。没有修改正式会员主表。
复用原最小维护引擎，新增独立升级入口：`.venv/Scripts/python.exe scripts/repair_club_participation_fk_v1.py --db <现有绝对数据库路径> --apply`；不加--apply只检查，缺参数拒绝，导入不连接。仅两个已核实定义的固定白名单；未知DDL/非空旧表拒绝，正确目标跳过。本轮总事务仅这一张待修表，正式重复执行确认无变化；隔离强制中途失败回滚通过。
FRESH_SCHEMA_PATH=通过（当前Windows初始化调用的scripts/migrate_v05c.py活动DDL + scripts/migrations/007_club_operations_mvp.py活动升级路径）；报名、参与、签到表不生成旧会员FK。未重跑全项目历史迁移，未声称所有历史bootstrap全量验收。

- PRE：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_CLOSEOUT_03_CONTINUE_PRE_20260917_141940.db`
- PRE SHA256：`5c98e24dde2ecb626b4c449c309ae3aa5844e2182ef86f10936be690c6850063`
- POST：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_CLOSEOUT_03_CONTINUE_POST_20260917_141940.db`
- POST SHA256：`7cea3e74d280b6a10299f3f1a8207da8c8259bf6f5ec66bca9d263329756e99e`
- 正式库前SHA256：`23aff4ebe3a17ce327c04118b7a262a831b0df6b97fba2eba43f8594c639374e`；结构修复/正式Web恢复后：`6ed8cbe98be93d4b793326fe05703e25ee8af727a5b8009a6730d0f25452c417`。
- FORMAL_BUSINESS_DATA_CHANGED=NO；EVENT_7_DATA_CHANGED=NO；200表全部行数及内容指纹一致，包括原审计与序列；唯一完整FK集合仍为`[(v05c_club_event_profiles, 1, events, 0)]`；integrity_check=ok。仅获准FK目标改变，无临时重建表。
- 正式迁移前停本项目Web并确认无Worker/Scheduler，SQLite Backup API生成新PRE；单事务核对数据/结构后提交，新FK开启连接复核并备份POST。原8000/reload由既有launcher恢复，RUN_STATUS=READY、/login=200，scheduler/worker均false；启动后指纹复核仍一致。未执行任何正式采集或其他生产任务。
- `data/backups/ASTRA_CLOSEOUT_03_CONTINUE_WORKTREE_20260917_135642.zip`保留原95项工作区文件和before指纹，追加migration.json/browser_result.json证据并验证可读；不含本轮临时密码、会话密钥。18个精确列明临时文件及空目录已清理，8776实例已停止；正式运行日志/PID仍为既有运行资产不提交。正式库没有测试账号/报名/参与/签到新增。

本轮实际修改：app/services/club_operations_service.py、app/v05c_club_events.py、scripts/repair_club_registration_fk_v1.py；新增scripts/repair_club_participation_fk_v1.py、tests/test_closeout_activity_chain.py；同步现有CLOSEOUT_03_RESULT、KNOWN_ISSUES、WORKTREE_MANIFEST、COMMIT_PLAN、CURRENT_BASELINE、ACTIVE_RUNTIME_MAP。其余既有修改保留。本轮开始95项，结束98项候选未暂存；Branch release/mvp-rc1.2，HEAD 3a491a5b61632b9531f08f5453e66978444398e5。P0/P1已核实台账无未解决项，8个P2/2个P3及Event #7历史例外不在本轮处理范围；未声明全系统无缺陷。

## CONTINUE执行白名单（2026-09-17）

实际写链：Web/API状态动作→ClubEventService.transition_event→Profile/审计/领域事件；报名→register→registrations；批准→review_registration→registrations/participation/审计/领域事件；签到码→issue_checkin_token→p4_checkin_tokens；签到→check_in→registrations/participation/tokens/checkin_audit/领域事件。注册与参与membership_id承接正式v04f_club_memberships.id；签到凭据通过registration_id关联，不是会员ID。
白名单仅v05c_club_event_participation：批准/签到实际写入，0行，旧会员FK→v04f_club_memberships(id)，seq=3；其余字段/约束/索引不变、事务前再次确认空表及完整FK集合才允许迁移。报名表已正确直接跳过；p4_checkin_tokens、p4_checkin_audit、p4_operation_audit、p4_domain_events没有退役会员FK。参与表无触发器/入向FK，1个显式索引及内建UNIQUE保留。会员主表不修改。

## 原CLOSEOUT-03历史时点（下文保留原证据，不覆盖顶部CONTINUE结论）

2026-09-17。原STATUS = CODE_COMPLETE / MANUAL_ACCEPTANCE_PENDING（当时限定报名与孤儿写保护）；当时存在下述参与表阻断，已在本轮CONTINUE解除。

- EVENT_PARENT_WRITE_GUARD = 已修复。club_event_id为Profile主键，统一在BEGIN IMMEDIATE之后查Profile及父events；状态迁移、报名、审核/签到/反馈等关联写入复用。无ID=7特例。父不存在返回404，成功审计/领域事件与业务一起回滚。
- REQUEST_FK_DISABLE_PATH = 已移除。现有db_connection在事务前FK=ON并读取1；原5个兼容调用全部删除。只有专用离线迁移连接临时关闭FK，finally恢复1并关闭。
- REGISTRATION_FK_TARGET = v04f_club_memberships(id)。membership_id和canonical_membership_id均存该正式会员主键；失效/过期会员400，冒用会员403；公开非会员报名制度未改为统一会员限定。
- NORMAL_EVENT_REGISTRATION = 通过；ORPHAN_EVENT_WRITES = 已阻断（仅本轮识别入口）。真实Web/API处理函数隔离调用使用Profile #1；没有对正式Event残留发POST。
- EVENT_7_DATA_CHANGED = NO。200张表全部行数/内容指纹不变，Profile #1全字段、缺失events #7事实与历史管理员审计不变。
- REMAINING_FK_EXCEPTION = (v05c_club_event_profiles, 1, events, 0)。integrity_check=ok。
- MIGRATION_IDEMPOTENT = 通过。空表seq=2及sqlite_sequence原rowid=87保留；3显式索引、内建UNIQUE、CHECK/默认值/非空与入向FK保留；无触发器；无临时表。实际初始化scripts/migrate_v05c.py已经正确，不改写。

## 剩余技术阻断（不扩权修第二张表）

TECHNICAL_FREEZE_BLOCKER_CLEARED = NO。
直接关联v05c_club_event_participation.membership_id仍指向不存在的v04f_club_memberships_old。SQLite即使插入NULL也需解析父表，原关闭FK兼容曾掩盖它。移除兼容后，正常报名提交/查询已恢复，但报名批准需要生成参与记录、签到需要写参与表，当前返回503“活动参与数据约束待维护”，事务不写任何成功状态。容量已满按既有规则转waitlisted仍可用。没有修改参与表Schema，也没有造旧会员表或关闭FK绕过。K01活跃孤儿风险已解除，K12明确记录此新确认阻断；不把空表foreign_key_check未报错说成Schema健康。

## 定向证据

11项unittest全部通过，覆盖A–F六组：孤儿publish/open Web/API 404；开放孤儿拒绝有效会员；正常Service新建→发布→开放→HTTP报名→新连接持久查询/重复幂等；无效/冒用/匿名/无权限、过期及状态/期限限制；事务注入故障回滚；迁移成功、重复无操作、未知/非空拒绝、迁移失败回滚及现有初始化DDL。附加参与表503无成功写入与容量waitlist检查通过。连接逐次断言FK=1且无OFF语句。
编译、git diff --check通过；未跑全量pytest，未联网、未采集。身份由隔离测试中间件注入后经过真实现有权限函数；不把它描述成浏览器登录验收。没有启动临时Web或生成截图，本轮真实浏览器人工操作待用户完成。
复现：从PRE备份用SQLite Backup API复制到data/acceptance下隔离种子，设置CLOSEOUT_TEST_DB为该绝对路径，运行 `.venv/Scripts/python.exe tests/test_closeout_event_write_guard.py -v`；测试拒绝正式库种子，自动清理子副本。
迁移入口：`.venv/Scripts/python.exe scripts/repair_club_registration_fk_v1.py --db <绝对路径> --apply`。缺少--db拒绝；不加--apply只检查；导入不连接。正式执行必须停写、先一致性备份；未知定义/非空旧表拒绝。不能用于其他表。

## 正式维护与恢复点

- 执行前报名0条，正式会员Service表/主键已确认；完整违规集合严格核对。已检查真实DDL、3显式索引、无触发器及3个入向表，不展开全库治理。
- 原Web根PID15600/reloader4112，127.0.0.1:8000 --reload；未发现Worker/Scheduler。通过既有launcher stop暂停此项目进程树，端口释放后才维护。维护完成后按同一launcher、端口/reload方式恢复，SCHEDULER_ENABLED=false、WORKER_ENABLED=false；RUN_STATUS=READY，启动后数据指纹再次全量一致。
- PRE：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_CLOSEOUT_03_PRE_20260917_100826.db`
- PRE SHA256：`60088771757737db3827543c0e669358b3be870a3a47ca8902fbfce143ef303d`
- POST：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_CLOSEOUT_03_POST_20260917_100826.db`
- POST SHA256：`5c98e24dde2ecb626b4c449c309ae3aa5844e2182ef86f10936be690c6850063`
- 工作区保全：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_CLOSEOUT_03_WORKTREE_20260917_100826.zip`（不含.env/密钥；保存当前候选及本轮维护指纹）。
- 正式DB前SHA256：`c96c47012013a25135ea316d54bf78f3da090a6fb4e4e503bfd500bb9ec60c9d`
- 正式DB后SHA256：`23aff4ebe3a17ce327c04118b7a262a831b0df6b97fba2eba43f8594c639374e`（仅批准的Schema变化；备份容器hash不同不表示业务数据不同）。
- 单事务新表替换，未rename原表为_old，未writable_schema，未executescript拆事务；提交前对200表行指纹和全Schema逐项验证，唯一区别为批准FK目标（表名引号为SQLite规范化）。新连接FK=1、integrity=ok，POST可读取。

## 工作区边界

本轮生产代码仅app/services/club_operations_service.py，新增scripts/repair_club_registration_fk_v1.py及tests/test_closeout_event_write_guard.py；其他增量为现有CURRENT_BASELINE、KNOWN_ISSUES、ACTIVE_RUNTIME_MAP、WORKTREE_MANIFEST、COMMIT_PLAN、CLOSEOUT_02_RESULT及本文件。原92项中，文档更新前仅既有club_operations_service有授权增量，其他91文件hash保持。
本轮closeout_03的6个隔离数据库/辅助文件/指纹JSON及空目录已按精确白名单清理，JSON证据先存入保全ZIP；正式库、PRE/POST、工作区快照、R2既有种子保留。没有正式测试账号，没有临时Web；运行日志仍为正式launcher既有资产，不纳入Git。
Branch release/mvp-rc1.2；HEAD 3a491a5b61632b9531f08f5453e66978444398e5；工作区95项候选，来源明确、未暂存。PC_V1_BASELINE_COMMITTED=NO。不执行commit/tag/API Freeze，不安排下一任务。
