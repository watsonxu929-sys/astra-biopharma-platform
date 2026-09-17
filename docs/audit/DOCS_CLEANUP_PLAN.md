# 文档瘦身计划

原docs文件404：CURRENT 2、REFERENCE 168、HISTORICAL 84、EVIDENCE 150。分类是阅读优先级，不证明旧内容正确，也不等于授权删除。REDUNDANT=0个经核实可删除文档；不凭标题相似判重。
新增本轮7文件均CURRENT。以后先读docs/CURRENT_BASELINE.md，再按链接读运行地图/当前任务；R1证据与旧审计仅按需查阅，不继续把每个历史阶段当并行正式规格。
长期目标README + PRODUCT_SCOPE/ARCHITECTURE/DATA_MODEL/API_CONTRACT/OPERATIONS/CURRENT_BASELINE/KNOWN_ISSUES + archive。本轮只建立CURRENT_BASELINE与要求的审计文件，不复制七套已有内容，不批量搬迁，不新截图集。
HISTORICAL/EVIDENCE建议将来MOVE_TO_EXTERNAL_ARCHIVE或docs/archive，先修引用、保留恢复证据并取得确认。当前安全快照与FK修复证据保留。

## 原docs逐文件分类

|路径|分类|动作|
|---|---|---|
|docs/01_INSTALLATION.md|REFERENCE|KEEP|
|docs/01_手动替换步骤.md|REFERENCE|KEEP|
|docs/02_QUICK_START.md|REFERENCE|KEEP|
|docs/02_功能与验收清单.md|REFERENCE|KEEP|
|docs/02_功能验收清单.md|REFERENCE|KEEP|
|docs/03_USER_GUIDE.md|REFERENCE|KEEP|
|docs/03_故障排查.md|REFERENCE|KEEP|
|docs/03_离线提取规则说明.md|REFERENCE|KEEP|
|docs/03_算法与安全边界.md|REFERENCE|KEEP|
|docs/04_DATA_MODEL.md|REFERENCE|KEEP|
|docs/04_故障排查.md|REFERENCE|KEEP|
|docs/05_REVIEW_WORKFLOW.md|REFERENCE|KEEP|
|docs/06_DATA_INGESTION.md|REFERENCE|KEEP|
|docs/07_DEVELOPMENT.md|REFERENCE|KEEP|
|docs/08_TROUBLESHOOTING.md|REFERENCE|KEEP|
|docs/09_CHANGELOG.md|REFERENCE|KEEP|
|docs/10_V04D_STRUCTURING.md|REFERENCE|KEEP|
|docs/11_V04H_RECOMMENDATIONS.md|REFERENCE|KEEP|
|docs/12_V05A_SECURITY.md|REFERENCE|KEEP|
|docs/13_V05A_PATCH_INSTALL.md|REFERENCE|KEEP|
|docs/14_V05B_MEMBER_IMPORT.md|REFERENCE|KEEP|
|docs/15_V05B_PATCH_INSTALL.md|REFERENCE|KEEP|
|docs/16_V05B_QUICK_ACCEPTANCE.md|REFERENCE|KEEP|
|docs/AI_CONTEXT.md|REFERENCE|KEEP|
|docs/AI_WORKFLOW.md|REFERENCE|KEEP|
|docs/API_V1_GUIDE.md|REFERENCE|KEEP|
|docs/ARCHITECTURE.md|REFERENCE|KEEP|
|docs/CAPABILITY_MAP.md|REFERENCE|KEEP|
|docs/CAPABILITY_REUSE_MAP.md|REFERENCE|KEEP|
|docs/capability_route_mapping_v1.md|REFERENCE|KEEP|
|docs/client_api_contract_v1.md|REFERENCE|KEEP|
|docs/CODEX_TASK_TEMPLATE.md|REFERENCE|KEEP|
|docs/COLLECTION_SCHEDULER_WINDOWS.md|REFERENCE|KEEP|
|docs/CURRENT_DOMAIN_MODEL_MAP.md|REFERENCE|KEEP|
|docs/DATABASE_PROTECTION.md|REFERENCE|KEEP|
|docs/DATA_INTEGRITY_REPAIR_REPORT.md|REFERENCE|KEEP|
|docs/DATA_MIGRATION_REPORT.md|REFERENCE|KEEP|
|docs/DATA_MODEL.md|REFERENCE|KEEP|
|docs/DECISION_LOG.md|REFERENCE|KEEP|
|docs/DELETION_MANIFEST.md|REFERENCE|KEEP|
|docs/DOCUMENT_CLEANUP_REPORT.md|REFERENCE|KEEP|
|docs/DOCUMENT_INDEX.md|REFERENCE|KEEP|
|docs/DO_NOT_TOUCH.md|REFERENCE|KEEP|
|docs/FUTURE_MODULES.md|REFERENCE|KEEP|
|docs/HANDOFF_TEMPLATE.md|REFERENCE|KEEP|
|docs/IDENTITY_COMPATIBILITY_LAYER_DESIGN.md|REFERENCE|KEEP|
|docs/KNOWN_ISSUES.md|REFERENCE|KEEP|
|docs/LEGACY_COMPATIBILITY_PLAN.md|REFERENCE|KEEP|
|docs/LEGACY_WRITE_ENTRYPOINTS.md|REFERENCE|KEEP|
|docs/network_people_traceback_v06b.md|REFERENCE|KEEP|
|docs/P1_FINAL_ACCEPTANCE.md|REFERENCE|KEEP|
|docs/PDP_v1.0.md|REFERENCE|KEEP|
|docs/PLATFORM_ARCHITECTURE.md|REFERENCE|KEEP|
|docs/platform_capability_mapping_v06b.md|REFERENCE|KEEP|
|docs/PROJECT_ARCHITECTURE.md|REFERENCE|KEEP|
|docs/PROJECT_CHARTER.md|REFERENCE|KEEP|
|docs/PROJECT_INVENTORY.md|REFERENCE|KEEP|
|docs/PROJECT_MEMORY.md|REFERENCE|KEEP|
|docs/PROJECT_ROADMAP.md|REFERENCE|KEEP|
|docs/README.md|REFERENCE|KEEP|
|docs/REDUNDANCY_REVIEW.md|REFERENCE|KEEP|
|docs/ROLE_MATRIX.md|REFERENCE|KEEP|
|docs/route_compatibility_v1.md|REFERENCE|KEEP|
|docs/RULE_ZERO.md|REFERENCE|KEEP|
|docs/SKILLS_GUIDE.md|REFERENCE|KEEP|
|docs/STARTUP_AND_VERIFICATION.md|REFERENCE|KEEP|
|docs/TASK_CHECKLIST.md|REFERENCE|KEEP|
|docs/TESTING_GUIDE.md|REFERENCE|KEEP|
|docs/TRAE_TASK_TEMPLATE.md|REFERENCE|KEEP|
|docs/V04H_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05A_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05B_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05F_COLLECTION.md|REFERENCE|KEEP|
|docs/V05F_PATCH_INSTALL.md|REFERENCE|KEEP|
|docs/V05F_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05G_PATCH_INSTALL.md|REFERENCE|KEEP|
|docs/V05G_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05G_PROCESSING.md|REFERENCE|KEEP|
|docs/V05H_PATCH_INSTALL.md|REFERENCE|KEEP|
|docs/V05H_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05H_REPORTS_SIGNALS_NAVIGATION.md|REFERENCE|KEEP|
|docs/V05I_PATCH_INSTALL.md|REFERENCE|KEEP|
|docs/V05I_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05I_PIPELINE_QUALITY_CENTER.md|REFERENCE|KEEP|
|docs/V05I_REAL_SOURCE_ACCEPTANCE.md|REFERENCE|KEEP|
|docs/V05J_PATCH_INSTALL.md|REFERENCE|KEEP|
|docs/V05J_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05J_RESEARCH_I18N_INVESTMENT.md|REFERENCE|KEEP|
|docs/V05KL_PATCH_INSTALL.md|REFERENCE|KEEP|
|docs/V05KL_PATCH_MANIFEST.txt|REFERENCE|KEEP|
|docs/V05KL_PRODUCTION_OPERATIONS.md|REFERENCE|KEEP|
|docs/v05M-R_recovery_acceptance_and_rollback.md|REFERENCE|KEEP|
|docs/v05M_人工验收与回滚说明.md|REFERENCE|KEEP|
|docs/V05_REAL_INTELLIGENCE_CHAIN_ACCEPTANCE_AND_ROLLBACK.md|REFERENCE|KEEP|
|docs/v06i_runtime_baseline.md|REFERENCE|KEEP|
|docs/v06j_migration_audit.md|REFERENCE|KEEP|
|docs/v06k_p4_operations_contract.md|REFERENCE|KEEP|
|docs/archive/01_手动替换步骤.md|REFERENCE|KEEP|
|docs/archive/02_JSON数据格式.md|REFERENCE|KEEP|
|docs/archive/02_功能验收清单.md|REFERENCE|KEEP|
|docs/archive/03_故障排查.md|REFERENCE|KEEP|
|docs/archive/03_正式同步与业务表映射.md|REFERENCE|KEEP|
|docs/archive/04_验收清单.md|REFERENCE|KEEP|
|docs/archive/05_故障排查.md|REFERENCE|KEEP|
|docs/audit/ASTRA_R1_DATA_CHANGES.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/ASTRA_R1_GROUP01_CLEANUP_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_MAPPING.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_REPAIR_PLAN.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_REPAIR_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/ASTRA_R1_REMAINING_FK_25_RAW.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/ASTRA_R1_REMAINING_FK_ANALYSIS.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/ASTRA_R1_REMAINING_FK_DECISIONS.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/ASTRA_R2_MAINLINE_RESULT.md|CURRENT|KEEP|
|docs/audit/ASTRA_R3_RESULT.md|CURRENT|KEEP|
|docs/audit/MVP_R1_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R1_PRODUCT_SURFACE_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R2_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R2_SINGLE_WRITE_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R2_WRITE_MAP_AFTER.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R2_WRITE_MAP_BEFORE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R3_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R3_DRY_RUN.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R3_LEGACY_INVENTORY.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R3_LEGACY_MIGRATION_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R3_LEGACY_READ_MAP_AFTER.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R3_R2_DIFF_CHECK.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R4_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R4_GOLDEN_PATH_PRODUCT_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R4_ROOT_CLEANUP.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R4_USER_ACCEPTANCE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5A_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5A_EXTRACTION_COMPARISON.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5A_OSS_FOUNDATION_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5A_OSS_LICENSES.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5A_REPLACEMENT_MAP_AFTER.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5A_REPLACEMENT_MAP_BEFORE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5B_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5B_DYNAMIC_COLLECTION_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5B_R5A_COLLECTION_REVIEW.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R5B_SOURCE_CAPABILITY_MATRIX.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R6_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R6_DATA_QUALITY.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R6_REAL_DATA_OPERATION_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R6_SOURCE_REGISTRY.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R6_SOURCE_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_1_ADMIN_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_1_ADMIN_OPERABILITY_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_2_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_2_INTELLIGENCE_REVIEW.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_2_OPPORTUNITY_DISCOVERY_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_2_PRIORITY_SUBJECTS.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_3_COVERAGE_GAP.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_3_PRIORITY_MONITORING_MATRIX.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_3_PRIORITY_SOURCE_COVERAGE_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_4_WEB_DISCOVERY_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_5_PRIORITY_SUBJECT_MASTER_MATRIX.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_5_SUBJECT_IDENTITY_AUDIT.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_5_SUBJECT_MASTER_DATA_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_AI_READINESS.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_BASELINE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_INTELLIGENCE_REVIEW.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_R7_VALUE_ACTIVATION_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_1_RUN_ACCEPTANCE.json|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_1_RUN_AND_TRANSLATION_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_1_RUN_ROOT_CAUSE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2A_CURRENT_NAVIGATION.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2A_PAGE_DECISION_MATRIX.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2A_PRODUCT_INFORMATION_ARCHITECTURE_AUDIT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2A_TARGET_NAVIGATION.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2B_PRODUCT_UI_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2C_INTELLIGENCE_DELETE_MATRIX.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2C_INTELLIGENCE_LIFECYCLE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2C_INTELLIGENCE_LIFECYCLE_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2D_PROCESSING_AUTOMATION_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_2D_PROCESSING_AUTOMATION_ROOT_CAUSE.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_DELIVERABLE_PRODUCT_RESULT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/MVP_RC1_PRODUCT_ACCEPTANCE.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_BACKUP_PATCH_AUDIT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_DELETION_CANDIDATES.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_DUAL_WRITE_RISK.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_DUPLICATE_FILE_AUDIT.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_DUPLICATE_SUMMARY.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_OFFICIAL_ENTRYPOINTS.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_PYTHON_MODULE_AUDIT.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_RECOMMENDATION.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_ROUTE_AUDIT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/p1_2_route_inventory.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_STATIC_ASSET_AUDIT.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/P1_2_TEMPLATE_AUDIT.md|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/p1_2_template_inventory.csv|HISTORICAL|KEEP / archive建议；未移动|
|docs/audit/evidence/MVP_R3_RELATIONSHIP_MAPPING.csv|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/MVP_R3_RESOURCE_MAPPING.csv|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/01_workspace.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/02_intelligence.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/03_subject.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/04_formal_resource.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/04_resource_match_candidates.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/05_formal_opportunity.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/05_match_confirmed.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/06_opportunity.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/07_follow_up.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/08_outcome.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/09_relationship.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/10_qbay.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/11_search.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r4/browser_result.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/00_login.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/01_workspace_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/02_intelligence_list.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/03_subject_candidate.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/04_subject_confirmed.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/05_organization_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/06_person_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/07_resource_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/08_opportunities.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/09_opportunity_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/10_qbay.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/11_collection.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/12_search.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r6/13_workspace_1600.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/02_workbench.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/03_intelligence.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/04_intelligence_detail_policy.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/05_subject_candidate.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/06_organization.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/08_resource.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/09_opportunity_list.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/10_opportunity_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/11_qbay.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/12_sources.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7/13_search.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/01_workbench.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/02_sources.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/03_events.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/04_resources.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/05_source_created.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/06_source_import_preview.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/07_source_discovery.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/07_source_discovery_dedup.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/08_event_draft.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/09_event_open.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/10_event_viewer_registered.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/11_resources_operator.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/12_resource_created.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/13_resource_protected_archived.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/14_resource_bulk_partial.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/15_candidate_enable_ignore.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/16_source_retired_history.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/17_viewer_readonly_ui.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/18_viewer_source_readonly.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_1/browser_result.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/browser_acceptance.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/global-search.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/intelligence-list.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/opportunity-detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/opportunity-list.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/organization-context.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/priority-intelligence.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/qbay.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/resource-context.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/resource-list.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/source-management.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/subject-candidate.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/viewer-intelligence.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_2/workbench.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/01_organization_active.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/02_domain_candidate.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/03_discovery_result.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/04_source_candidate.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/05_source_management.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/06_priority_monitoring.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/07_intelligence.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/08_qbay.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/09_viewer_monitoring.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_3/browser_acceptance.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/01_priority_subjects.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/02_organization_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/03_monitoring_candidate.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/05_alias_search.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/06_website_import_preview.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/07_source_candidate.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/08_qbay_alignment.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/10_viewer_context.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_r7_5/browser_acceptance.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1/01_workbench_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1/02_intelligence_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1/03_organization_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1/04_follow_up_created_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1/05_workbench_1920.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1/06_restart_persistence.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1/browser_acceptance.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1/restart_persistence.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_1/01_workbench_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_1/02_intelligence_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_1/03_organization_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_1/04_follow_up_created_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_1/05_workbench_1920.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_1/06_restart_persistence.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_1/browser_acceptance.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_1/restart_persistence.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/01_workbench.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/02_intelligence_list.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/03_intelligence_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/04_enterprise_people.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/05_organization.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/06_club.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/07_followup.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/08_reports.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/09_admin_processing.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/after/10_admin_console.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/01_workbench.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/02_intelligence_list.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/03_intelligence_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/04_enterprise_people.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/05_organization.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/06_club.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/07_followup.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/08_reports.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/09_admin_processing.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2b/before/10_admin_console.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/01_admin_intelligence_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/02_safe_delete_preview.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/03_protected_delete_preview.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/04_archived_history.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/05_bulk_partial_success.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/06_collection_overview.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/07_source_list.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/08_raw_collection.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/09_operator_controls.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/10_viewer_detail.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2c/browser_acceptance.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/01_source_before_collection_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/02_collection_auto_processing_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/03_processing_failure_recovery_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/04_processing_candidates_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/05_restart_recovery_1024.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/06_viewer_processing_readonly_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/07_intelligence_detail_1366.png|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/browser_acceptance.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/audit/evidence/mvp_rc1_2d/intelligence_detail_acceptance.json|EVIDENCE|KEEP / archive建议；未移动|
|docs/manual_review/p1_resource_conflict_review.csv|REFERENCE|KEEP|
|docs/manual_review/P1_RESOURCE_CONFLICT_REVIEW.md|REFERENCE|KEEP|
|docs/p2/P2_1_AI_PROVIDER.md|REFERENCE|KEEP|
|docs/p2/P2_1_COMPLETION_AUDIT.md|REFERENCE|KEEP|
|docs/p2/P2_1_CURRENT_INTELLIGENCE_FLOW.md|REFERENCE|KEEP|
|docs/p2/P2_1_EVIDENCE_MODEL.md|REFERENCE|KEEP|
|docs/p2/P2_1_FINAL_ACCEPTANCE.md|REFERENCE|KEEP|
|docs/p2/P2_1_INFORMATION_ARCHITECTURE.md|REFERENCE|KEEP|
|docs/p2/P2_1_PILOT_REPORT.md|REFERENCE|KEEP|
|docs/p2/P2_1_TARGET_ARCHITECTURE.md|REFERENCE|KEEP|
|docs/p2/P2_2_AI_EVALUATION_DESIGN.md|REFERENCE|KEEP|
|docs/p2/P2_2_COST_AND_LIMITS.md|REFERENCE|KEEP|
|docs/p2/P2_2_DOCLING_ADAPTER.md|REFERENCE|KEEP|
|docs/p2/P2_2_ERROR_ANALYSIS.md|REFERENCE|KEEP|
|docs/p2/P2_2_PILOT_RESULTS.md|REFERENCE|KEEP|
|docs/p2/P2_2_PLAYWRIGHT_ADAPTER.md|REFERENCE|KEEP|
|docs/p2/P2_2_SOURCE_PILOT_PLAN.md|REFERENCE|KEEP|
|docs/p2/P2_2_TRAE_HANDOFF.md|REFERENCE|KEEP|
|docs/p2/P2_3_CURRENT_RESEARCH_CAPABILITY.md|REFERENCE|KEEP|
|docs/p2/P2_3_ERROR_ANALYSIS.md|REFERENCE|KEEP|
|docs/p2/P2_3_PILOT_RESULTS.md|REFERENCE|KEEP|
|docs/p2/P2_3_RESEARCH_FUSION_MODEL.md|REFERENCE|KEEP|
|docs/p2/P2_3_TRAE_HANDOFF.md|REFERENCE|KEEP|
|docs/p3/P3_CURRENT_ENTITY_RELATIONSHIP_AUDIT.md|REFERENCE|KEEP|
|docs/p3/P3_ENTITY_RESOLUTION_RULES.md|REFERENCE|KEEP|
|docs/p3/P3_MERGE_AND_ROLLBACK.md|REFERENCE|KEEP|
|docs/p3/P3_PILOT_REPORT.md|REFERENCE|KEEP|
|docs/p3/P3_PILOT_RUN.json|REFERENCE|KEEP|
|docs/p3/P3_PRIVACY_AND_VISIBILITY.md|REFERENCE|KEEP|
|docs/p3/P3_RELATIONSHIP_PATH_ENGINE.md|REFERENCE|KEEP|
|docs/p3/P3_RELATIONSHIP_TYPE_REGISTRY.md|REFERENCE|KEEP|
|docs/p3/P3_TARGET_ENTITY_MODEL.md|REFERENCE|KEEP|
|docs/p3/P3_TRAE_HANDOFF.md|REFERENCE|KEEP|
|docs/p3/P3_VERIFICATION_REPORT.json|REFERENCE|KEEP|
|docs/p4/P4_CURRENT_CLUB_CAPABILITY_AUDIT.md|REFERENCE|KEEP|
|docs/p4/P4_DOMAIN_EVENTS.md|REFERENCE|KEEP|
|docs/p4/P4_EVENT_LIFECYCLE.md|REFERENCE|KEEP|
|docs/p4/P4_EVENT_RELATIONSHIP_DEPOSITION.md|REFERENCE|KEEP|
|docs/p4/P4_MEMBERSHIP_LIFECYCLE.md|REFERENCE|KEEP|
|docs/p4/P4_PERMISSIONS.md|REFERENCE|KEEP|
|docs/p4/P4_PILOT_REPORT.md|REFERENCE|KEEP|
|docs/p4/P4_RESOURCE_MATCHING.md|REFERENCE|KEEP|
|docs/p4/P4_TARGET_CLUB_MODEL.md|REFERENCE|KEEP|
|docs/p4/P4_TRAE_HANDOFF.md|REFERENCE|KEEP|
|docs/tasks/TASK-P0-P1-STABILITY-DOMAIN-UNIFICATION.md|REFERENCE|KEEP|
|docs/tasks/TASK-P1-1-DATA-INTEGRITY-TESTS.md|REFERENCE|KEEP|
|docs/tasks/TASK-P1-2-A-REDUNDANCY-AUDIT.md|REFERENCE|KEEP|
|docs/tasks/TASK-P1-2B-CLEANUP-WRITE-CONSOLIDATION.md|REFERENCE|KEEP|
|docs/tasks/TASK-P2-1-INTELLIGENCE-PIPELINE.md|REFERENCE|KEEP|
|docs/tasks/TASK-P2-2-REAL-SOURCE-QUALITY.md|REFERENCE|KEEP|
|docs/tasks/TASK-P3-ENTITY-RELATIONSHIP-NETWORK.md|REFERENCE|KEEP|
|docs/tasks/TASK-P4-CLUB-OPERATIONS-MVP.md|REFERENCE|KEEP|
|docs/trae/DAY1_VISIBLE_CAPABILITY_AUDIT.md|REFERENCE|KEEP|
|docs/trae/P5_ACTUAL_STATUS_AUDIT.md|REFERENCE|KEEP|
|docs/trae/T1_COLLECTION_RUNTIME_AUDIT.md|REFERENCE|KEEP|
|docs/trae/T1_THREE_RUN_ACCEPTANCE.md|REFERENCE|KEEP|
|docs/trae/T2_INTELLIGENCE_QUALITY_AUDIT.md|REFERENCE|KEEP|
|docs/trae/T2_QUALITY_ACCEPTANCE.md|REFERENCE|KEEP|
|docs/trae/T3_RELATIONSHIP_UI_AUDIT.md|REFERENCE|KEEP|
|docs/trae/T4_CLUB_UI_AUDIT.md|REFERENCE|KEEP|
|docs/trae/T5_1_WRITE_CLOSURE_AUDIT.md|REFERENCE|KEEP|
|docs/trae/T5_COLLABORATION_UI_AUDIT.md|REFERENCE|KEEP|
|docs/trae/T6_FULL_MVP_ACCEPTANCE.md|REFERENCE|KEEP|
|docs/trae/T6_SCRIPT_AND_MIGRATION_AUDIT.md|REFERENCE|KEEP|
