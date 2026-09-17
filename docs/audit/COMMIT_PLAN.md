# COMMIT_PLAN（ASTRA-K1已授权本次PC V1基线提交）

STATUS = AUTHORIZED_BY_ASTRA_K1_FOR_PC_V1_CODE_BASELINE
TECHNICAL_FREEZE_BLOCKER_CLEARED = YES
PC_V1_FREEZE_READY = PENDING_USER_CONFIRMATION
COMMIT_1_MESSAGE = PC V1 baseline after activity chain closeout
COMMIT_1_FILES_COUNT = 98
建议单一逻辑快照：共享文件含G/H/R1/R2/R3多阶段增量，贸然按阶段拆提交易制造中间不可运行状态。所有文件来源已识别，不含未知文件；不是git add .。

COMMIT_1_FILES（与WORKTREE_MANIFEST的INCLUDE逐项相同）：

- app/api/v1/intelligence.py
- app/main.py
- app/p3_network.py
- app/platform/capability_registry.py
- app/routes_club_facilities.py
- app/routes_knowledge.py
- app/routes_platform.py
- app/security.py
- app/services/canonical_relationship_service.py
- app/services/club_facility_service.py
- app/services/club_operations_service.py
- app/services/collection_scheduler.py
- app/services/collection_service.py
- app/services/collectors/playwright_adapter.py
- app/services/data_quality.py
- app/services/golden_loop_service.py
- app/services/intelligence_flow_service.py
- app/services/intelligence_product_service.py
- app/services/intelligence_review_service.py
- app/services/knowledge_service.py
- app/services/membership_access_service.py
- app/services/navigation_service.py
- app/services/processing/article_facts.py
- app/services/processing/content_quality_service.py
- app/services/processing/processing_job_service.py
- app/services/unified_intelligence_service.py
- app/services/unified_resource_service.py
- app/templates/base.html
- app/templates/club_home.html
- app/templates/p3_network.html
- app/templates/platform/_article_facts.html
- app/templates/platform/_bulk_delete_results.html
- app/templates/platform/_knowledge_annotations.html
- app/templates/platform/_knowledge_path_progress.html
- app/templates/platform/_knowledge_training_fields.html
- app/templates/platform/_reference_protection.html
- app/templates/platform/_related_knowledge.html
- app/templates/platform/_review_facts.html
- app/templates/platform/admin.html
- app/templates/platform/admin_organizations.html
- app/templates/platform/admin_people.html
- app/templates/platform/club_facilities.html
- app/templates/platform/home.html
- app/templates/platform/intelligence.html
- app/templates/platform/intelligence_detail.html
- app/templates/platform/knowledge.html
- app/templates/platform/knowledge_training.html
- app/templates/platform/person_card.html
- app/templates/v05f_collection.html
- app/templates/v05g_processing.html
- app/v04c_review.py
- app/v05f_collection.py
- app/v05g_processing.py
- docs/CURRENT_BASELINE.md
- docs/KNOWN_ISSUES.md
- docs/audit/ACTIVE_RUNTIME_MAP.md
- docs/audit/ASTRA_R1_DATA_CHANGES.csv
- docs/audit/ASTRA_R1_GROUP01_CLEANUP_RESULT.md
- docs/audit/ASTRA_R1_MEMBERSHIP_FK_MAPPING.csv
- docs/audit/ASTRA_R1_MEMBERSHIP_FK_REPAIR_PLAN.md
- docs/audit/ASTRA_R1_MEMBERSHIP_FK_REPAIR_RESULT.md
- docs/audit/ASTRA_R1_REMAINING_FK_25_RAW.csv
- docs/audit/ASTRA_R1_REMAINING_FK_ANALYSIS.md
- docs/audit/ASTRA_R1_REMAINING_FK_DECISIONS.csv
- docs/audit/ASTRA_R2_MAINLINE_RESULT.md
- docs/audit/ASTRA_R3_RESULT.md
- docs/audit/BACKUP_ARCHIVE_PLAN.md
- docs/audit/CLOSEOUT_01_RESULT.md
- docs/audit/CLOSEOUT_02_RESULT.md
- docs/audit/COMMIT_PLAN.md
- docs/audit/DEFERRED_BACKLOG.md
- docs/audit/DOCS_CLEANUP_PLAN.md
- docs/audit/MINIPROGRAM_READINESS.md
- docs/audit/PROJECT_BASELINE_INVENTORY.md
- docs/audit/WORKTREE_MANIFEST.md
- scripts/clean_test_data.py
- scripts/clean_test_opp.py
- scripts/cleanup_identity_test_accounts.py
- scripts/cleanup_test_data.py
- scripts/migrate_db.py
- scripts/migrations/012_industry_knowledge.py
- scripts/migrations/013_knowledge_training_and_rooms.py
- scripts/restore_test_opp.py
- tests/conftest.py
- tests/test_astra_r2_mainline.py
- tests/test_astra_r3_facts.py
- tests/test_astra_r3_runtime.py
- tests/test_closeout_intelligence_visibility.py
- tests/test_closeout_review_display.py
- tests/test_mvp_rc1_2f_admin_and_membership.py
- tests/test_rc12g_subject_cleanup_and_knowledge.py
- tests/test_rc12h_training_and_rooms.py

- docs/audit/CLOSEOUT_03_RESULT.md
- scripts/repair_club_registration_fk_v1.py
- tests/test_closeout_event_write_guard.py
- app/v05c_club_events.py
- scripts/repair_club_participation_fk_v1.py
- tests/test_closeout_activity_chain.py

COMMIT_2_FILES = NONE
COMMIT_3_FILES = NONE
TAG_AFTER_APPROVAL = pc-v1-baseline

执行门槛：K01/K12活动链技术阻断已解除，18项定向检查及Chromium连续链/刷新/重启通过，正式业务数据未变，历史FK例外保留。等待用户人工确认，再核对逐文件diff、正式DB指纹与98项候选清单，无测试产物/凭据后按明确路径暂存、复查cached diff；仅用户批准后commit，tag只能指向最终验证HEAD。当前未暂存、未提交、未tag，不应将当前HEAD误标冻结版本。
