# WORKTREE_MANIFEST

Branch release/mvp-rc1.2；HEAD 3a491a5b61632b9531f08f5453e66978444398e5；CLOSEOUT-03开始92项，CONTINUE开始95项，当前98项。UNKNOWN=0；INCLUDE=98；EXCLUDE=0（Git可见清单）。这是逐文件候选范围，不是提交授权；K01已封堵，K12已解除，等待用户人工确认与基线提交/Tag授权。
混合来源文件按本轮修改/主要来源归类，PURPOSE保留既有来源说明；不按文件切块拆掉G/H/R1/R2/R3有效代码。核对了status、diff/hunk、既有阶段记录和新文件职责，未reset/restore/clean/stash/暂存/commit。

|PATH|STATUS|ORIGIN|PURPOSE|IN_PC_V1_BASELINE|ACTION|
|---|---|---|---|---|---|
|app/api/v1/intelligence.py| M|CLOSEOUT_01|CLOSEOUT-01 private证据权限和同DB依赖|YES (candidate only)|INCLUDE|
|app/main.py| M|PRE_EXISTING_VALID_CHANGE|G/H现有知识与会议室路由注册|YES (candidate only)|INCLUDE|
|app/p3_network.py| M|PRE_EXISTING_VALID_CHANGE|G主体清理返回链、关系归档与知识上下文|YES (candidate only)|INCLUDE|
|app/platform/capability_registry.py| M|PRE_EXISTING_VALID_CHANGE|G/H与R2既有能力和审核入口登记|YES (candidate only)|INCLUDE|
|app/routes_club_facilities.py|??|PRE_EXISTING_VALID_CHANGE|H会议室/会员服务既有实现/迁移/隔离验证|YES (candidate only)|INCLUDE|
|app/routes_knowledge.py|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|app/routes_platform.py| M|PRE_EXISTING_VALID_CHANGE|G/H主体清理及知识关联；R3阅读筛选/view变量修复|YES (candidate only)|INCLUDE|
|app/security.py| M|PRE_EXISTING_VALID_CHANGE|G/H管理权限和关系归档后端权限|YES (candidate only)|INCLUDE|
|app/services/canonical_relationship_service.py| M|PRE_EXISTING_VALID_CHANGE|G关系归档复用调用方事务|YES (candidate only)|INCLUDE|
|app/services/club_facility_service.py|??|PRE_EXISTING_VALID_CHANGE|H会议室/会员服务既有实现/迁移/隔离验证|YES (candidate only)|INCLUDE|
|app/services/club_operations_service.py| M|CLOSEOUT_03_CONTINUE + PRE_EXISTING_VALID_CHANGE|G会员解除绑定保留历史；03父保护/FK ON；CONTINUE审批/签到会员校验与幂等|YES (candidate only)|INCLUDE|
|app/services/collection_scheduler.py| M|PRE_EXISTING_VALID_CHANGE|R3来源下次运行频率一致性|YES (candidate only)|INCLUDE|
|app/services/collection_service.py| M|PRE_EXISTING_VALID_CHANGE|R1健康与启用分离；R2/R3采集正文/日期/去重保护|YES (candidate only)|INCLUDE|
|app/services/collectors/playwright_adapter.py| M|PRE_EXISTING_VALID_CHANGE|R2采集正文提取适配，非本轮新增采集|YES (candidate only)|INCLUDE|
|app/services/data_quality.py| M|PRE_EXISTING_VALID_CHANGE|G主体删除引用明细、可安全清理及事务保护|YES (candidate only)|INCLUDE|
|app/services/golden_loop_service.py| M|PRE_EXISTING_VALID_CHANGE|R1避免代建商机；R3事实阅读与工作台时效|YES (candidate only)|INCLUDE|
|app/services/intelligence_flow_service.py| M|PRE_EXISTING_VALID_CHANGE|R3按来源频率排队，防重复tick|YES (candidate only)|INCLUDE|
|app/services/intelligence_product_service.py| M|PRE_EXISTING_VALID_CHANGE|R2/R3审核文章发布和证据/日期校验|YES (candidate only)|INCLUDE|
|app/services/intelligence_review_service.py| M|PRE_EXISTING_VALID_CHANGE|R2人工补充与忽略状态保护|YES (candidate only)|INCLUDE|
|app/services/knowledge_service.py|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|app/services/membership_access_service.py| M|PRE_EXISTING_VALID_CHANGE|H复用会员身份映射提供服务上下文|YES (candidate only)|INCLUDE|
|app/services/navigation_service.py| M|PRE_EXISTING_VALID_CHANGE|G/H/R2既有知识、服务与审核导航|YES (candidate only)|INCLUDE|
|app/services/processing/article_facts.py|??|CLOSEOUT_02|R3确定性事实与日期；本轮event地点词边界P1|YES (candidate only)|INCLUDE|
|app/services/processing/content_quality_service.py| M|PRE_EXISTING_VALID_CHANGE|R2/R3质量门槛；恢复reading_use契约|YES (candidate only)|INCLUDE|
|app/services/processing/processing_job_service.py| M|PRE_EXISTING_VALID_CHANGE|R2/R3文章候选和facts.view审核筛选|YES (candidate only)|INCLUDE|
|app/services/unified_intelligence_service.py| M|PRE_EXISTING_VALID_CHANGE|R3正式阅读过滤；CLOSEOUT-01 private详情保护|YES (candidate only)|INCLUDE|
|app/services/unified_resource_service.py| M|PRE_EXISTING_VALID_CHANGE|G仅草稿且无引用资源解绑|YES (candidate only)|INCLUDE|
|app/templates/base.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/club_home.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/p3_network.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/_article_facts.html|??|ASTRA_R3|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/_bulk_delete_results.html|??|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/_knowledge_annotations.html|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|app/templates/platform/_knowledge_path_progress.html|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|app/templates/platform/_knowledge_training_fields.html|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|app/templates/platform/_reference_protection.html|??|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/_related_knowledge.html|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|app/templates/platform/_review_facts.html|??|CLOSEOUT_02|本轮审核展示宏，去重与事实不足提示|YES (candidate only)|INCLUDE|
|app/templates/platform/admin.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/admin_organizations.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/admin_people.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/club_facilities.html|??|PRE_EXISTING_VALID_CHANGE|H会议室/会员服务既有实现/迁移/隔离验证|YES (candidate only)|INCLUDE|
|app/templates/platform/home.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/intelligence.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/intelligence_detail.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/platform/knowledge.html|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|app/templates/platform/knowledge_training.html|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|app/templates/platform/person_card.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/v05f_collection.html| M|PRE_EXISTING_VALID_CHANGE|G/H主体引用清理或R2/R3阅读事实与入口现有展示；非新功能|YES (candidate only)|INCLUDE|
|app/templates/v05g_processing.html| M|CLOSEOUT_02|R2/R3审核展示；本轮去重/不足提示/动作清晰P1|YES (candidate only)|INCLUDE|
|app/v04c_review.py| M|PRE_EXISTING_VALID_CHANGE|R1正式路径识别及连接FK启用确认|YES (candidate only)|INCLUDE|
|app/v05f_collection.py| M|PRE_EXISTING_VALID_CHANGE|R1来源启用不伪造healthy|YES (candidate only)|INCLUDE|
|app/v05g_processing.py| M|PRE_EXISTING_VALID_CHANGE|R2/R3审核发布、编辑、视图筛选入口|YES (candidate only)|INCLUDE|
|docs/CURRENT_BASELINE.md|??|CLOSEOUT_02|当前任务基线/结果/精确计划|YES (candidate only)|INCLUDE|
|docs/KNOWN_ISSUES.md| M|CLOSEOUT_02|当前任务基线/结果/精确计划|YES (candidate only)|INCLUDE|
|docs/audit/ACTIVE_RUNTIME_MAP.md|??|CLOSEOUT_02|当前任务基线/结果/精确计划|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R1_DATA_CHANGES.csv|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R1_GROUP01_CLEANUP_RESULT.md|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_MAPPING.csv|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_REPAIR_PLAN.md|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_REPAIR_RESULT.md|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R1_REMAINING_FK_25_RAW.csv|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R1_REMAINING_FK_ANALYSIS.md|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R1_REMAINING_FK_DECISIONS.csv|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R2_MAINLINE_RESULT.md|??|PRE_EXISTING_VALID_CHANGE|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/ASTRA_R3_RESULT.md|??|ASTRA_R3|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/BACKUP_ARCHIVE_PLAN.md|??|CLOSEOUT_02|当前任务基线/结果/精确计划|YES (candidate only)|INCLUDE|
|docs/audit/CLOSEOUT_01_RESULT.md|??|CLOSEOUT_01|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/CLOSEOUT_02_RESULT.md|??|CLOSEOUT_02|当前任务基线/结果/精确计划|YES (candidate only)|INCLUDE|
|docs/audit/COMMIT_PLAN.md|??|CLOSEOUT_02|当前任务基线/结果/精确计划|YES (candidate only)|INCLUDE|
|docs/audit/DEFERRED_BACKLOG.md|??|CLOSEOUT_02|当前任务基线/结果/精确计划|YES (candidate only)|INCLUDE|
|docs/audit/DOCS_CLEANUP_PLAN.md|??|CLOSEOUT_01|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/MINIPROGRAM_READINESS.md|??|CLOSEOUT_01|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/PROJECT_BASELINE_INVENTORY.md|??|CLOSEOUT_01|既有阶段审计证据与恢复决策（不当作当前新验收）|YES (candidate only)|INCLUDE|
|docs/audit/WORKTREE_MANIFEST.md|??|CLOSEOUT_02|当前任务基线/结果/精确计划|YES (candidate only)|INCLUDE|
|scripts/clean_test_data.py| M|PRE_EXISTING_VALID_CHANGE|R1废弃危险入口显式拒绝|YES (candidate only)|INCLUDE|
|scripts/clean_test_opp.py| M|PRE_EXISTING_VALID_CHANGE|R1正式库识别、隔离测试清理与事务/FK保护|YES (candidate only)|INCLUDE|
|scripts/cleanup_identity_test_accounts.py| M|PRE_EXISTING_VALID_CHANGE|R1废弃危险入口显式拒绝|YES (candidate only)|INCLUDE|
|scripts/cleanup_test_data.py| M|PRE_EXISTING_VALID_CHANGE|R1废弃危险入口显式拒绝|YES (candidate only)|INCLUDE|
|scripts/migrate_db.py| M|PRE_EXISTING_VALID_CHANGE|G/H既有012/013迁移注册；本轮不执行|YES (candidate only)|INCLUDE|
|scripts/migrations/012_industry_knowledge.py|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|scripts/migrations/013_knowledge_training_and_rooms.py|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|scripts/restore_test_opp.py| M|PRE_EXISTING_VALID_CHANGE|R1禁止恢复测试商机进入正式库|YES (candidate only)|INCLUDE|
|tests/conftest.py| M|PRE_EXISTING_VALID_CHANGE|G/H隔离测试迁移到013|YES (candidate only)|INCLUDE|
|tests/test_astra_r2_mainline.py|??|PRE_EXISTING_VALID_CHANGE|既有主体清理/会员/情报主链定向回归，保留安全隔离|YES (candidate only)|INCLUDE|
|tests/test_astra_r3_facts.py|??|ASTRA_R3|既有主体清理/会员/情报主链定向回归，保留安全隔离|YES (candidate only)|INCLUDE|
|tests/test_astra_r3_runtime.py|??|ASTRA_R3|既有主体清理/会员/情报主链定向回归，保留安全隔离|YES (candidate only)|INCLUDE|
|tests/test_closeout_intelligence_visibility.py|??|CLOSEOUT_01|既有主体清理/会员/情报主链定向回归，保留安全隔离|YES (candidate only)|INCLUDE|
|tests/test_closeout_review_display.py|??|CLOSEOUT_02|本轮6项展示/地点串联回归|YES (candidate only)|INCLUDE|
|tests/test_mvp_rc1_2f_admin_and_membership.py| M|PRE_EXISTING_VALID_CHANGE|既有主体清理/会员/情报主链定向回归，保留安全隔离|YES (candidate only)|INCLUDE|
|tests/test_rc12g_subject_cleanup_and_knowledge.py|??|PRE_EXISTING_VALID_CHANGE|G/H产业知识学习培训既有实现/模板/隔离验证|YES (candidate only)|INCLUDE|
|tests/test_rc12h_training_and_rooms.py|??|PRE_EXISTING_VALID_CHANGE|H会议室/会员服务既有实现/迁移/隔离验证|YES (candidate only)|INCLUDE|
|docs/audit/CLOSEOUT_03_RESULT.md|??|CLOSEOUT_03|本轮最小结果/备份/参与表边界|YES (candidate only)|INCLUDE|
|scripts/repair_club_registration_fk_v1.py|??|CLOSEOUT_03_CONTINUE|保留原报名入口；参与升级复用固定两表定义白名单的事务引擎|YES (candidate only)|INCLUDE|
|tests/test_closeout_event_write_guard.py|??|CLOSEOUT_03|六组要求共11项离线隔离检查|YES (candidate only)|INCLUDE|
|app/v05c_club_events.py| M|CLOSEOUT_03_CONTINUE|我的报名真实身份/参与状态；批量签到失败不假成功|YES (candidate only)|INCLUDE|
|scripts/repair_club_participation_fk_v1.py|??|CLOSEOUT_03_CONTINUE|仅参与表显式幂等升级入口，不在业务请求改Schema|YES (candidate only)|INCLUDE|
|tests/test_closeout_activity_chain.py|??|CLOSEOUT_03_CONTINUE|7项完整活动链/权限/事务/迁移/初始化隔离检查|YES (candidate only)|INCLUDE|

## 不进入提交的ignored范围

data/app.db及辅助文件、.env、.venv、logs、runtime、data/backups、data/acceptance/astra_r2/trial.db：GENERATED/既有正式运行资产，IN_PC_V1_BASELINE=NO（指Git文件），ACTION=EXCLUDE/KEEP_UNCOMMITTED，绝不删除正式库或恢复点。
data/acceptance/closeout_02/本轮显式创建的隔离库/会话/工具/JSON：TEMPORARY，IN_PC_V1_BASELINE=NO，ACTION=DELETE_GENERATED（完成验证后清理）。不使用*.db通配。
UNKNOWN只对上述当前Git候选及本轮临时范围为0，不宣称全部历史ignored资产已逐一审计。

CLOSEOUT-03：data/acceptance/closeout_03的6个本轮临时副本/辅助文件/JSON及空目录已按精确白名单清理，指纹JSON已保存在工作区保全ZIP；data/backups/ASTRA_CLOSEOUT_03_PRE_*、POST_*及WORKTREE_*属于恢复点，KEEP/EXCLUDE，不提交、不删除。其余旧文件指纹已比对。

CONTINUE：data/acceptance/closeout_03_continue的18个已核实临时文件（隔离DB及辅助文件、临时账号配置/会话密钥、浏览器工具/JSON、日志）和空目录已清理，8776已停止。before/migration/browser_result证据存入既有CONTINUE工作区保全ZIP；本轮PRE/POST及保全ZIP KEEP/EXCLUDE。正式8000恢复；正式库与已有运行资产不提交。
