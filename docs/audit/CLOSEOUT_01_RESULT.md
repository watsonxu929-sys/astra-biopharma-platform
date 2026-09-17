# ASTRA-CLOSEOUT-01 收口结果

唯一成果：可依据当前实际工作区、正式库指纹和唯一运行地图决定PC V1冻结范围，而不继续按历史阶段报告扩大开发。

## 状态与计量

TASK_NAME = ASTRA-CLOSEOUT-01
STATUS = CODE_COMPLETE / MANUAL_ACCEPTANCE_PENDING
BRANCH = release/mvp-rc1.2
HEAD_BEFORE = 3a491a5b61632b9531f08f5453e66978444398e5
HEAD_AFTER = 3a491a5b61632b9531f08f5453e66978444398e5
PROJECT_SIZE_BEFORE = 1034612637 bytes
PROJECT_SIZE_AFTER = 001005830079 bytes
FILE_COUNT_BEFORE = 10926
FILE_COUNT_AFTER = 000000009482
DB_PATH = E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db
DB_SHA256 = c96c47012013a25135ea316d54bf78f3da090a6fb4e4e503bfd500bb9ec60c9d
TABLE_COUNT = 200
DB_INTEGRITY = ok
P0_FOUND = 0（本轮范围内，非全站安全背书）
P0_FIXED = 0
P1_FOUND = 1
P1_FIXED = 1
P2_DEFERRED = 10
P3_DEFERRED = 3
ACTIVE_MODULE_COUNT = 13（指定主链目标中的ACTIVE/ACTIVE_SHARED）
DEAD_MODULE_COUNT = 0（未有满足8项删除证明者）
ARCHIVE_CANDIDATE_COUNT = 421（基线data/backups非ASTRA_ basename文件，尚未移动）
CORE_PIPELINE_STATUS = VERIFIED_IN_ISOLATION / FORMAL_COLLECTION_NOT_RERUN
ASTRA_R3_STATUS = VERIFIED / MANUAL_VALUE_ACCEPTANCE_PENDING
MINIPROGRAM_READINESS = NEEDS_SMALL_FIX；微信认证契约MISSING
FULL_PYTEST_RUN = NO
TARGETED_TEST_RESULT = 28个不同测试通过；实际37次执行均通过，含9次发现式加载重复用例
WORKTREE_STATUS = dirty，原76项有效修改保留；本轮新增/修改10文件；未暂存、未提交

统计口径：全目录含.git/.venv/历史资产，按文件逻辑字节计量，不等于磁盘分配块；before含当时盘点脚本1个，after已清本轮临时目录文件。报告新增抵消部分缓存释放。新旧目录与数据库均未删除。

## A. 必须修（仅P0/P1）

|路径|问题|影响|修复状态|
|---|---|---|---|
|app/services/unified_intelligence_service.py；app/api/v1/intelligence.py|列表排除private，但详情和证据未使用同一可见性校验|已登录viewer按ID可读取不可见的已发布情报及关联证据|FIXED：复用published+public/organization规则；证据使用同一DB依赖，先校验后trace|

隔离副本真实复现：私有条目列表不可见，API详情/证据及HTML原均200；修复后三者404。恢复隔离条目原visibility后公开读取200。原API路径未改名，不改Schema、角色或正式记录。4个新增边界测试覆盖允许、private/缺失/未知visibility、未发布、不存在；启动/API/Chromium脚本另验证真实路由行为。

## B. 可以删除 / 移出主工程

|路径/精确集合|基线大小|原因|风险|实际/建议动作|
|---|---|---|---|---|
|全项目1446个pyc及.pytest_cache的5个文件|28865662 bytes|运行可重建缓存|低；下次启动重新生成|已按路径白名单删除；不是删除业务源码|
|data/backups内非ASTRA_前缀basename的421文件|377540608 bytes|历史备份/恢复附属材料，不是当前正式源|中高；须保留完整恢复包和引用|MOVE_TO_EXTERNAL_ARCHIVE；本轮未移动、未删除|
|data/.migration_backups|37224448 bytes|012/013迁移恢复证据|高|RECOVERY_REQUIRED，KEEP|
|data/migration_backup|6189056 bytes|历史Canonical读切换前恢复材料|高|RECOVERY_REQUIRED，KEEP|
|data/rehearsal|17838080 bytes|迁移与回滚验证样本，有脚本引用|中|KEEP，不能凭年代删除|
|data/acceptance/astra_r2/trial.db|22433792 bytes|现有离线定向检查的种子|高|ACTIVE_REQUIRED，KEEP|
|docs/audit/evidence|22697514 bytes|历史审计图片/证据|中|KEEP；以后经引用核验再归档|
|本轮closeout_01隔离库、临时工具/JSON/会话材料|临时产物，非基线业务资产|验证结束|低；已停止8774实例|结束清理；未删除原安全快照/备份|

原runtime的PID对应存活Python；不删除运行凭据/PID，不停止用户服务。不批量删除日志/浏览器共享运行时。SQLite只读检查历史WAL库曾生成10个新SHM/空WAL：确认扫描前不存在、WAL为空且连接关闭后定点清理；正式库辅助文件不动。

## C. 现在坚决不要做

不补基金/人物/采购/科研-IP来源；不重跑正式采集/加工/发布；不修全部历史pytest；不全面重构200表/服务/旧模块；不建第二套业务架构；不做全站UI美化；不接AI、翻译、新搜索、推荐或OSS。审核重复摘要与占位、操作措辞只列P2/P3，不以可读性名义再开大重构。详见DEFERRED_BACKLOG。

## 验证与数据库

- R3事实13 + R2主链9 + R3运行边界2 + 新可见性4 = 28个不同测试。发现式加载R3Runtime时同时加载其导入的R2测试类，额外执行9次，全部通过。不把37写成37个不同用例。
- R2隔离检查覆盖采集→重复→失败重试→加工→审核→发布→阅读/生命周期；外部网络拦截，不跑正式Source。正式采集重跑NO、正式写入0、自动发布0、Schema变更0。
- 200表行数和内容指纹、Schema、正式SHA前后相同，integrity_check=ok；FK完整集合仍[(v05c_club_event_profiles,1,events,0)]，未处置Event #7。Collection728、Processing100不变。
- AST语法、git diff --check通过；历史15 failed/3 errors未全量重测，不能宣称集合已比较不扩大。无当前定向失败，故本轮不为历史噪声启动全量pytest。
- Chromium151.0.7922.34，隔离Web8774、1440×900；从工作台情报菜单进入，检查实际标题、详情事实/原文、资本筛选、明确空结果、审核42条队列。Console/PageError/HTTP错误/Network Failure/横向溢出均0。不是用户对业务价值的最终认可。
- API列表、公开详情/证据、企业/人物目录、搜索、bootstrap实际200；无效分页422，viewer加工写403。802个真正展开route，805个HTTP method绑定，不使用lazy-router顶层对象数冒充路由规模。
- 既有75个其他dirty文件逐字节指纹不变；unified_intelligence_service既有R3修改保留并只加本轮可见性条件。没有删除历史业务代码。

## 本轮实际交付文件（10）

1. app/services/unified_intelligence_service.py
2. app/api/v1/intelligence.py
3. tests/test_closeout_intelligence_visibility.py
4. docs/audit/PROJECT_BASELINE_INVENTORY.md
5. docs/audit/ACTIVE_RUNTIME_MAP.md
6. docs/audit/DEFERRED_BACKLOG.md
7. docs/audit/DOCS_CLEANUP_PLAN.md
8. docs/CURRENT_BASELINE.md
9. docs/audit/MINIPROGRAM_READINESS.md
10. docs/audit/CLOSEOUT_01_RESULT.md

## 距离冻结只保留4项

1. 用户人工验收PC阅读/审核：以真实待审材料检查“谁、何事、时间、价值、来源、下一步”；只把确实无法完成动作的问题升级P0/P1。
2. 用户确认现有G/H/R1/R2/R3工作区及本轮修复的版本收口与恢复点；对Event #7形成继续冻结或单独授权决策，然后PC V1 Baseline Freeze。此处不自动提交。
3. API Freeze前仅解决微信认证接入契约、组织权限边界、R3筛选与收藏/错误返回的最小接口差异；复用现有后端，不增加业务平台。
4. API Freeze后进入微信V0.1：只读为主的首页、情报、搜索、主体详情、个人收藏/关注与我的；审核和采集仍在PC。

路线：以上PC收口 → PC V1 Baseline Freeze → API Freeze → 微信小程序V0.1。本轮到此停止。
