# 当前项目资产基线

2026-09-16；Branch release/mvp-rc1.2；HEAD 3a491a5b61632b9531f08f5453e66978444398e5；未提交工作区也是基线的一部分。
全项目递归元数据盘点，包含 .git、.venv、历史代码副本、数据库与证据；不跟随符号链接。盘点错误：0。
计数是文件而非目录；目录大小包括全部子目录，Top20不可相加。mtime不等于业务事件日期。首次扫描含临时盘点脚本一个；最终会清理。

## 文件和空间

总文件 10926；总字节 1034612637。分类可能重叠；缓存按文件数，非目录数。
|类型|数量|
|---|---|
|markdown|418|
|python|4042|
|cache_files|1451|
|pyc|1446|
|tests|97|
|images|185|
|logs|7|
|databases|163|

Python数量含第三方环境；排除 .venv 后仍含 backups/patches 的历史源码，共 1290，不可当作正式生产源码规模。
|一级目录|文件数|字节|
|---|---|---|
|(root files)|11|10838|
|.agents|8|20803|
|.git|263|28704673|
|.pytest_cache|5|2787|
|.skills|38|62671|
|.venv|7382|246511225|
|.workbuddy|5|21601|
|app|508|6735713|
|artifacts|52|3176097|
|backups|980|5673766|
|config|2|6395|
|data|506|710762038|
|docs|404|25296007|
|evaluation|4|8526|
|examples|2|1454|
|logs|4|438262|
|patches|425|4849594|
|reference_documents|12|391636|
|reports|3|6062|
|runtime|2|91|
|scripts|219|1317133|
|tests|49|565727|
|tools|42|49538|

## 最大20目录

|目录|文件数|字节|
|---|---|---|
|data|506|710762038|
|data/backups|450|578742734|
|.venv|7382|246511225|
|.venv/Lib/site-packages|7350|243690605|
|.venv/Lib|7350|243690605|
|.venv/Lib/site-packages/playwright|238|110526672|
|.venv/Lib/site-packages/playwright/driver|114|106142234|
|data/.migration_backups|6|37224448|
|.venv/Lib/site-packages/babel|1117|30921802|
|.venv/Lib/site-packages/babel/locale-data|1084|29880343|
|.git|263|28704673|
|.git/objects|217|28381066|
|data/acceptance|7|26511266|
|.git/objects/pack|8|25759303|
|docs|404|25296007|
|docs/audit|236|24611629|
|docs/audit/evidence|150|22697514|
|data/acceptance/astra_r2|3|22466560|
|data/rehearsal|6|17838080|
|.venv/Lib/site-packages/sqlalchemy|395|15417872|

## 最大50文件

|文件|字节|
|---|---|
|.venv/Lib/site-packages/playwright/driver/node.exe|92540232|
|data/app.db|27918336|
|.git/objects/pack/pack-9c8f4da30787b7cd2fa71e6230f8aeb9ce51409a.pack|22749241|
|data/backups/ASTRA_R3_PRE_COLLECTION_20260916_165414.db|22577152|
|data/acceptance/astra_r2/trial.db|22433792|
|data/backups/ASTRA_R2_PRE_COLUMN_RETRY_20260916.db|20807680|
|data/backups/ASTRA_R1_POST_GROUP01_CLEANUP_20260914_090701.db|19599360|
|data/backups/ASTRA_R1_POST_MEMBERSHIP_FK_REPAIR_20260913_232331.db|19599360|
|data/backups/ASTRA_R1_POST_SOURCE_HEALTH_20260916_112556.db|19599360|
|data/backups/ASTRA_R1_PRE_GROUP01_CLEANUP_20260914_090701.db|19599360|
|data/backups/ASTRA_R1_PRE_SOURCE_HEALTH_20260916_112556.db|19599360|
|data/backups/ASTRA_R2_PRE_COLLECTION_20260916.db|19599360|
|data/backups/ASTRA_R1_PRE_DATA_TRUST_20260913_225006.db|19578880|
|data/backups/ASTRA_R1_PRE_MEMBERSHIP_FK_REPAIR_20260913_232331.db|19578880|
|data/.migration_backups/app_before_013_20260908_205520_245535.db|19275776|
|data/.migration_backups/app_before_012_20260905_195414_414497.db|17883136|
|data/backups/app_20260830_140841.db|15720448|
|data/backups/MVP_R7_5_PRE_TEST_POLLUTION_REPAIR_20260828_233911.db|15720448|
|data/backups/MVP_RC1_PRE_AUDIT_CLEANUP_20260829.db|15720448|
|data/backups/MVP_R7_3_PRE_COLLECTION_20260828.db|15319040|
|data/backups/MVP_R7_2_PREWRITE_20260828.db|14811136|
|data/backups/app_mvp_r7_before_operation_20260824_170539.db|14462976|
|.venv/Lib/site-packages/PIL/_avif.cp314-win_amd64.pyd|7833600|
|data/backups/app_20260824_151429.db|6864896|
|data/migration_backup/pre_mvp_r3_20260824_093559.db|6156288|
|data/backups/app_before_011_feedback_outcome_loop_20260724_144522_546223.db|5808128|
|.venv/Lib/site-packages/pydantic_core/_pydantic_core.cp314-win_amd64.pyd|5261824|
|data/rehearsal/v06j_app_migrated.db|4890624|
|data/backups/app_before_010_intelligence_opportunity_loop_20260722_092905_088188.db|4620288|
|data/backups/app_before_009_intelligence_production_loop_20260718_162433_584807.db|4579328|
|data/backups/app_before_007_club_operations_mvp_20260716_162442_640832.db|4468736|
|data/backups/app_before_007_club_operations_mvp_20260717_091330_185710.db|4460544|
|data/backups/app_before_006_entity_relationship_network_20260716_162408_299764.db|4313088|
|data/backups/app_before_006_entity_relationship_network_20260717_091329_665926.db|4304896|
|data/rehearsal/v06j_app_before.db|4304896|
|data/rehearsal/v06j_app_rollback_verified.db|4304896|
|data/rehearsal/.migration_backups/v06j_app_migrated_before_008_20260715_112039_977610.db|4304896|
|.venv/Lib/site-packages/lxml/etree.cp314-win_amd64.pyd|4084224|
|data/acceptance/t5_1_mvp.db|4005888|
|.venv/Lib/site-packages/playwright/driver/package/lib/coreBundle.js|3425217|
|.venv/Lib/site-packages/playwright/driver/package/lib/utilsBundle.js|3239355|
|.git/objects/pack/pack-f19b82bb9a3d88bcb70bc2def8da3640cb670ffe.pack|2855678|
|data/t1_test.db|2572288|
|data/backups/app_before_003_intelligence_evidence_pipeline_20260710_235411_651552.db|2564096|
|data/backups/app_before_003_intelligence_evidence_pipeline_20260710_235400_868530.db|2498560|
|data/backups/app_before_p2_003_20260710-232500.db|2498560|
|data/backups/app_before_p2_003_20260710-235313.db|2498560|
|data/backups/app_before_001_core_domain_unification_20260710_110104_386155.db|2494464|
|data/backups/app_before_v06i_intelligence_20260706_151858.db|2494464|
|data/backups/app_before_v06e_20260706_115352.db|2486272|

## 历史资产处置

|目录|文件数|字节|最早mtime|最新mtime|直接字面引用|
|---|---|---|---|---|---|
|data/backups|450|578742734|2026-06-26T16:00:59|2026-09-16T20:39:49|scripts/build_release_v1.py; scripts/audit/audit_redundancy.py|
|data/.migration_backups|6|37224448|2026-09-05T19:54:14|2026-09-08T20:56:08|无字面命中|
|data/migration_backup|3|6189056|2026-08-24T09:35:59|2026-08-24T10:12:18|无字面命中|
|data/rehearsal|6|17838080|2026-07-15T11:19:41|2026-08-30T20:32:08|scripts/check_membership_application.py; scripts/check_rehearsal_status.py; scripts/check_rehearsal_version.py; scripts/export_routes.py|
|data/acceptance|7|26511266|2026-08-21T09:29:08|2026-09-16T21:23:45|scripts/check_db_tables.py; scripts/create_additional_test_data.py; scripts/run_acceptance_migrations.py; scripts/test_business_closure.py; scripts/manual_recovery/add_p5_follow_up_columns_DEPRECATED.py; scripts/manual_recovery/add_p5_opportunity_columns_DEPRECATED.py|
|docs/audit/evidence|150|22697514|2026-08-24T09:39:26|2026-08-30T14:16:42|无字面命中|
|logs|4|438262|2026-06-30T10:45:25|2026-09-16T21:23:45|app/models.py; app/security.py; app/v04c1_ingestion.py; app/v04g_monitoring.py; app/v05a_security.py; app/services/authorization_service.py|
|runtime|2|91|2026-08-13T12:45:06|2026-09-16T20:51:28|app/services/collectors/playwright_adapter.py; app/services/operations/system_health_service.py; scripts/check_mojibake.py; scripts/migrate_db.py; scripts/runtime_info.py; scripts/migrations/000_legacy_runtime_baseline.py|

字面引用不证明未使用：路径拼接、配置、人工恢复不一定出现完整字符串。版本明细见逐库表；user_version通常0，不代表没有迁移；schema_version是SQLite计数，不是产品版本。

- ACTIVE_REQUIRED：data/app.db、.venv、app、当前 scripts/tests；data/acceptance/astra_r2/trial.db 是 ASTRA_R2_TEST_DB 隔离种子，不能按临时库删除。runtime PID对应存活的Python实例，运行凭据/日志保留。
- RECOVERY_REQUIRED：所有 ASTRA_* 当前恢复库、工作区快照、R3材料ZIP，data/.migration_backups（012/013），data/migration_backup，及 rehearsal 的迁移前/后/回滚证据。本轮不移动。
- HISTORICAL_ARCHIVE：data/backups 中非 ASTRA_ 前缀的 421 个文件，共 377540608 字节；精确集合定义为本基线扫描路径前缀 data/backups/ 且文件basename不以 ASTRA_ 开头。建议 MOVE_TO_EXTERNAL_ARCHIVE，先验证恢复包和相关历史文档链接、得到用户确认；未移动，未删除。
- docs/audit/evidence、根 backups、patches 为历史审计/源码参考，暂KEEP。未逐一满足8项代码删除证明，不能删代码。
- DUPLICATE：本轮未证明内容相同且恢复职责可替代，因此0个获准删除的重复资产；同大小/同Schema绝非重复证明。
- SAFE_TO_REMOVE：原清单1446个pyc及.pytest_cache的5个缓存文件，已删除，28865662字节，可重建；空缓存目录不影响运行。本轮隔离库/账号/日志/工具结束清理。
- 首轮mode=ro检查部分WAL备份时生成10个SHM/空WAL辅助文件；后续历史库改用immutable只读。这10个新增辅助文件按与扫描前差集确认后清理；原有辅助文件不碰。历史immutable读取仅用于库分类，不宣称其WAL事务已经恢复验证。

## 唯一正式数据库

DB_PATH = E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db
DB_SHA256 = c96c47012013a25135ea316d54bf78f3da090a6fb4e4e503bfd500bb9ec60c9d
DB_SIZE = 27918336；TABLE_COUNT = 200（含sqlite_sequence）；VIEW_COUNT = 0；INDEX_COUNT = 384。
FK_CHECK = [(v05c_club_event_profiles, 1, events, 0)]，历史Event #7未处理。INTEGRITY_CHECK = ok。
配置解析结果为本项目data/app.db；测试覆盖APP_DB_PATH及DATABASE_URL指向隔离库，关闭scheduler/worker。
全部200表行数、逐表内容指纹、Schema指纹与DB SHA已在检查后比较一致；来源142、采集728、任务100、候选389、正式情报记录2。当前记录数量不同于旧报告不意味着自动恢复旧库；本轮不改人工操作结果。

## 全部163个原有数据库逐个分类

本表不含本轮后来建立并清理的isolated.db。表数/user_version/schema_version只读读取；UNKNOWN不得升级为正式源。正式源仅1个。
|路径|用途|字节|表/u/s版本|静态引用|
|---|---|---|---|---|
|data/app.db|PRODUCTION_CURRENT|27918336|200/0/842|app/core/config.py,scripts/backup_database.py,scripts/check_db_tables.py,scripts/check_intelligence_data.py,scripts/check_p4_tables.py,scripts/check_people_data.py,scripts/check_recommendations.py,scripts/check_tables.py,scripts/collect_v04d_context.py,scripts/init_database.py,scripts/update_source_frequency.py,scripts/verify_product_usability_v1.py,scripts/verify_v04d4_links_and_review.py,tests/test_p4_club_operations_mvp.py,tests/test_rc12g_subject_cleanup_and_knowledge.py|
|data/t1_test.db|TEST|2572288|164/0/633|scripts/run_t1_three_runs.py,scripts/run_t2_quality_acceptance.py,tests/conftest.py|
|data/.migration_backups/app_before_012_20260905_195414_414497.db|MIGRATION_BACKUP|17883136|188/0/1|无字面命中|
|data/.migration_backups/app_before_013_20260908_205520_245535.db|MIGRATION_BACKUP|19275776|193/0/1|无字面命中|
|data/acceptance/t5_1_mvp.db|ACCEPTANCE|4005888|173/0/693|scripts/check_db_tables.py,scripts/create_acceptance_db.py,scripts/create_additional_test_data.py,scripts/run_acceptance_migrations.py,scripts/test_business_closure.py,scripts/manual_recovery/add_p5_follow_up_columns_DEPRECATED.py,scripts/manual_recovery/add_p5_opportunity_columns_DEPRECATED.py|
|data/acceptance/astra_r2/trial.db|ACCEPTANCE|22433792|200/0/1|无字面命中|
|data/backups/app_20260630_104850.db|HISTORICAL|798720|52/0/241|无字面命中|
|data/backups/app_20260824_151429.db|HISTORICAL|6864896|188/0/790|无字面命中|
|data/backups/app_20260830_140841.db|HISTORICAL|15720448|188/0/790|无字面命中|
|data/backups/app_before_001_core_domain_unification_20260710_110104_386155.db|MIGRATION_BACKUP|2494464|156/0/1|无字面命中|
|data/backups/app_before_003_intelligence_evidence_pipeline_20260710_235400_868530.db|MIGRATION_BACKUP|2498560|158/0/1|无字面命中|
|data/backups/app_before_003_intelligence_evidence_pipeline_20260710_235411_651552.db|MIGRATION_BACKUP|2564096|164/0/1|无字面命中|
|data/backups/app_before_006_entity_relationship_network_20260716_162408_299764.db|MIGRATION_BACKUP|4313088|165/0/1|无字面命中|
|data/backups/app_before_006_entity_relationship_network_20260717_091329_665926.db|MIGRATION_BACKUP|4304896|165/0/1|无字面命中|
|data/backups/app_before_007_club_operations_mvp_20260716_162442_640832.db|MIGRATION_BACKUP|4468736|177/0/1|无字面命中|
|data/backups/app_before_007_club_operations_mvp_20260717_091330_185710.db|MIGRATION_BACKUP|4460544|177/0/1|无字面命中|
|data/backups/app_before_009_intelligence_production_loop_20260718_162433_584807.db|MIGRATION_BACKUP|4579328|186/0/1|无字面命中|
|data/backups/app_before_010_intelligence_opportunity_loop_20260722_092905_088188.db|MIGRATION_BACKUP|4620288|188/0/1|无字面命中|
|data/backups/app_before_011_feedback_outcome_loop_20260724_144522_546223.db|MIGRATION_BACKUP|5808128|188/0/1|无字面命中|
|data/backups/app_before_domain_consolidation_20260704_203003.db|MIGRATION_BACKUP|2400256|154/0/568|无字面命中|
|data/backups/app_before_domain_consolidation_20260704_203022.db|MIGRATION_BACKUP|2400256|154/0/568|无字面命中|
|data/backups/app_before_identity_link_v1_20260703_091455.db|MIGRATION_BACKUP|1835008|126/0/457|无字面命中|
|data/backups/app_before_identity_link_v1_20260703_091525.db|MIGRATION_BACKUP|1855488|127/0/463|无字面命中|
|data/backups/app_before_identity_link_v1_20260703_091811.db|MIGRATION_BACKUP|1855488|127/0/463|无字面命中|
|data/backups/app_before_membership_person_link_v1_20260703_113136.db|MIGRATION_BACKUP|1859584|127/0/465|无字面命中|
|data/backups/app_before_membership_person_link_v1_20260703_113239.db|MIGRATION_BACKUP|1859584|127/0/465|无字面命中|
|data/backups/app_before_membership_person_link_v1_20260703_154138.db|MIGRATION_BACKUP|1953792|130/0/481|无字面命中|
|data/backups/app_before_migrate_all_20260630_104806.db|MIGRATION_BACKUP|798720|52/0/241|无字面命中|
|data/backups/app_before_migrate_all_20260630_104850.db|MIGRATION_BACKUP|798720|52/0/241|无字面命中|
|data/backups/app_before_migrate_all_20260630_113453.db|MIGRATION_BACKUP|798720|52/0/241|无字面命中|
|data/backups/app_before_migrate_all_20260630_115443.db|MIGRATION_BACKUP|843776|55/0/248|无字面命中|
|data/backups/app_before_migrate_all_20260630_141417.db|MIGRATION_BACKUP|872448|57/0/254|无字面命中|
|data/backups/app_before_migrate_all_20260630_155453.db|MIGRATION_BACKUP|1044480|68/0/282|无字面命中|
|data/backups/app_before_migrate_all_20260630_163245.db|MIGRATION_BACKUP|1200128|78/0/301|无字面命中|
|data/backups/app_before_migrate_all_20260630_171536.db|MIGRATION_BACKUP|1200128|78/0/301|无字面命中|
|data/backups/app_before_migrate_all_20260701_093703.db|MIGRATION_BACKUP|1265664|82/0/311|无字面命中|
|data/backups/app_before_migrate_all_20260701_093723.db|MIGRATION_BACKUP|1265664|82/0/311|无字面命中|
|data/backups/app_before_migrate_all_20260701_113715.db|MIGRATION_BACKUP|1351680|88/0/373|无字面命中|
|data/backups/app_before_migrate_all_20260701_120110.db|MIGRATION_BACKUP|1462272|95/0/392|无字面命中|
|data/backups/app_before_migrate_all_20260701_141654.db|MIGRATION_BACKUP|1515520|100/0/418|无字面命中|
|data/backups/app_before_migrate_all_20260701_144925.db|MIGRATION_BACKUP|1515520|100/0/418|无字面命中|
|data/backups/app_before_migrate_all_20260701_145304.db|MIGRATION_BACKUP|1515520|100/0/418|无字面命中|
|data/backups/app_before_migrate_all_20260701_160003.db|MIGRATION_BACKUP|1662976|110/0/437|无字面命中|
|data/backups/app_before_migrate_all_20260701_162312.db|MIGRATION_BACKUP|1662976|110/0/437|无字面命中|
|data/backups/app_before_organization_core_v1_20260703_161131.db|MIGRATION_BACKUP|1953792|130/0/481|无字面命中|
|data/backups/app_before_p2_003_20260710-232500.db|MIGRATION_BACKUP|2498560|158/0/589|无字面命中|
|data/backups/app_before_p2_003_20260710-235313.db|MIGRATION_BACKUP|2498560|158/0/589|无字面命中|
|data/backups/app_before_rbac_core_v1_20260703_162509.db|MIGRATION_BACKUP|2031616|133/0/508|无字面命中|
|data/backups/app_before_user_membership_link_20260703_124735.db|MIGRATION_BACKUP|1912832|128/0/474|无字面命中|
|data/backups/app_before_user_membership_link_20260703_124753.db|MIGRATION_BACKUP|1912832|128/0/474|无字面命中|
|data/backups/app_before_user_membership_link_20260703_125541.db|MIGRATION_BACKUP|1912832|128/0/474|无字面命中|
|data/backups/app_before_v04c1_20260629_105548.db|MIGRATION_BACKUP|217088|16/0/159|无字面命中|
|data/backups/app_before_v04c1_20260629_111230.db|MIGRATION_BACKUP|323584|24/0/177|无字面命中|
|data/backups/app_before_v04c_20260629_094558.db|MIGRATION_BACKUP|139264|9/0/146|无字面命中|
|data/backups/app_before_v04c_20260629_111230.db|MIGRATION_BACKUP|323584|24/0/177|无字面命中|
|data/backups/app_before_v04c_20260704_201530.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04c_20260704_201725.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04c_20260704_201805.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04c_20260704_202003.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04db_20260629_151258.db|MIGRATION_BACKUP|413696|29/0/195|无字面命中|
|data/backups/app_before_v04d_20260629_115727.db|MIGRATION_BACKUP|323584|24/0/177|无字面命中|
|data/backups/app_before_v04eA_20260629_153451.db|MIGRATION_BACKUP|413696|29/0/195|无字面命中|
|data/backups/app_before_v04f_20260630_100110.db|MIGRATION_BACKUP|712704|46/0/228|无字面命中|
|data/backups/app_before_v04f_20260704_201534.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04f_20260704_201730.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04f_20260704_201809.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04f_20260704_202007.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04g_20260630_103921.db|MIGRATION_BACKUP|712704|46/0/228|无字面命中|
|data/backups/app_before_v04g_20260704_201534.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04g_20260704_201730.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04g_20260704_201809.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04g_20260704_202007.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04h_20260630_113453.db|MIGRATION_BACKUP|798720|52/0/241|无字面命中|
|data/backups/app_before_v04h_20260704_201534.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04h_20260704_201730.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04h_20260704_201810.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v04h_20260704_202007.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05a_20260630_115444.db|MIGRATION_BACKUP|843776|55/0/248|无字面命中|
|data/backups/app_before_v05a_20260704_201535.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05a_20260704_201731.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05a_20260704_201810.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05a_20260704_202008.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05b_20260630_141417.db|MIGRATION_BACKUP|872448|57/0/254|无字面命中|
|data/backups/app_before_v05b_20260704_201535.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05b_20260704_201731.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05b_20260704_201810.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05b_20260704_202008.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05c_20260630_153945.db|MIGRATION_BACKUP|966656|62/0/266|无字面命中|
|data/backups/app_before_v05c_20260630_153958.db|MIGRATION_BACKUP|1044480|68/0/282|无字面命中|
|data/backups/app_before_v05c_20260704_201535.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05c_20260704_201731.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05c_20260704_201811.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05c_20260704_202008.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05d_20260630_163138.db|MIGRATION_BACKUP|1077248|68/0/282|无字面命中|
|data/backups/app_before_v05d_20260630_163146.db|MIGRATION_BACKUP|1200128|78/0/301|无字面命中|
|data/backups/app_before_v05d_20260704_201536.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05d_20260704_201732.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05d_20260704_201811.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05d_20260704_202009.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05e_20260630_171400.db|MIGRATION_BACKUP|1200128|78/0/301|无字面命中|
|data/backups/app_before_v05e_20260630_171425.db|MIGRATION_BACKUP|1200128|78/0/301|无字面命中|
|data/backups/app_before_v05e_20260704_201536.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05e_20260704_201732.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05e_20260704_201811.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05e_20260704_202009.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05f_20260701_093723.db|MIGRATION_BACKUP|1265664|82/0/311|无字面命中|
|data/backups/app_before_v05f_20260704_201536.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05f_20260704_201732.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05f_20260704_201811.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05f_20260704_202009.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05g_20260701_113715.db|MIGRATION_BACKUP|1351680|88/0/373|无字面命中|
|data/backups/app_before_v05g_20260704_201536.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05g_20260704_201732.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05g_20260704_201811.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05g_20260704_202009.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05h_20260701_120110.db|MIGRATION_BACKUP|1462272|95/0/392|无字面命中|
|data/backups/app_before_v05h_20260704_201536.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05h_20260704_201732.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05h_20260704_201811.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05h_20260704_202009.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05i_20260701_141655.db|MIGRATION_BACKUP|1515520|100/0/418|无字面命中|
|data/backups/app_before_v05i_20260701_145555.db|MIGRATION_BACKUP|1515520|100/0/418|无字面命中|
|data/backups/app_before_v05i_20260704_201536.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05i_20260704_201732.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05i_20260704_201811.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05i_20260704_202009.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05j_20260701_160011.db|MIGRATION_BACKUP|1662976|110/0/437|无字面命中|
|data/backups/app_before_v05j_20260704_201536.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05j_20260704_201733.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05j_20260704_201812.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05j_20260704_202010.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05kl_20260701_165009.db|MIGRATION_BACKUP|1662976|110/0/437|无字面命中|
|data/backups/app_before_v05kl_20260704_201537.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05kl_20260704_201733.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05kl_20260704_201812.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v05kl_20260704_202010.db|MIGRATION_BACKUP|2400256|153/0/566|无字面命中|
|data/backups/app_before_v06e_20260706_115352.db|MIGRATION_BACKUP|2486272|156/0/571|无字面命中|
|data/backups/app_before_v06i_intelligence_20260706_151858.db|MIGRATION_BACKUP|2494464|156/0/571|无字面命中|
|data/backups/app_mvp_r7_before_operation_20260824_170539.db|HISTORICAL|14462976|188/0/790|无字面命中|
|data/backups/app_v06c_fk_audit_20260704_171951.db|HISTORICAL|2400256|153/0/566|无字面命中|
|data/backups/app_v06c_fk_audit_20260704_172005.db|HISTORICAL|2400256|153/0/566|无字面命中|
|data/backups/app_v06c_fk_audit_20260705_090152.db|HISTORICAL|2445312|154/0/568|无字面命中|
|data/backups/app_v06d_fk_repair_20260705_091728.db|HISTORICAL|2445312|154/0/568|无字面命中|
|data/backups/ASTRA_R1_POST_GROUP01_CLEANUP_20260914_090701.db|HISTORICAL|19599360|200/0/1|无字面命中|
|data/backups/ASTRA_R1_POST_MEMBERSHIP_FK_REPAIR_20260913_232331.db|HISTORICAL|19599360|200/0/1|无字面命中|
|data/backups/ASTRA_R1_POST_SOURCE_HEALTH_20260916_112556.db|HISTORICAL|19599360|200/0/1|无字面命中|
|data/backups/ASTRA_R1_PRE_DATA_TRUST_20260913_225006.db|HISTORICAL|19578880|200/0/1|无字面命中|
|data/backups/ASTRA_R1_PRE_GROUP01_CLEANUP_20260914_090701.db|HISTORICAL|19599360|200/0/1|无字面命中|
|data/backups/ASTRA_R1_PRE_MEMBERSHIP_FK_REPAIR_20260913_232331.db|HISTORICAL|19578880|200/0/1|无字面命中|
|data/backups/ASTRA_R1_PRE_SOURCE_HEALTH_20260916_112556.db|HISTORICAL|19599360|200/0/1|无字面命中|
|data/backups/ASTRA_R2_PRE_COLLECTION_20260916.db|HISTORICAL|19599360|200/0/1|无字面命中|
|data/backups/ASTRA_R2_PRE_COLUMN_RETRY_20260916.db|HISTORICAL|20807680|200/0/1|无字面命中|
|data/backups/ASTRA_R3_PRE_COLLECTION_20260916_165414.db|HISTORICAL|22577152|200/0/1|无字面命中|
|data/backups/MVP_R7_2_PREWRITE_20260828.db|HISTORICAL|14811136|188/0/1|无字面命中|
|data/backups/MVP_R7_3_PRE_COLLECTION_20260828.db|HISTORICAL|15319040|188/0/1|无字面命中|
|data/backups/MVP_R7_5_PRE_TEST_POLLUTION_REPAIR_20260828_233911.db|TEST|15720448|188/0/1|无字面命中|
|data/backups/MVP_RC1_PRE_AUDIT_CLEANUP_20260829.db|HISTORICAL|15720448|188/0/1|无字面命中|
|data/migration_backup/pre_mvp_r3_20260824_093559.db|MIGRATION_BACKUP|6156288|188/0/1|无字面命中|
|data/rehearsal/v06j_app_before.db|ACCEPTANCE|4304896|165/0/1|无字面命中|
|data/rehearsal/v06j_app_migrated.db|ACCEPTANCE|4890624|211/0/228|scripts/check_membership_application.py,scripts/check_rehearsal_status.py,scripts/check_rehearsal_version.py,scripts/export_routes.py,tests/test_v06k_p4_operations_contract.py|
|data/rehearsal/v06j_app_rollback_verified.db|ACCEPTANCE|4304896|165/0/1|无字面命中|
|data/rehearsal/.migration_backups/v06j_app_migrated_before_008_20260715_112039_977610.db|MIGRATION_BACKUP|4304896|165/0/1|无字面命中|
|tests/test_app.db|TEST|0|0/0/0|无字面命中|

## 开始时dirty清单

76项按已授权G/H、R1、R2、R3来源归为EXPECTED_CURRENT_CHANGE，非默认垃圾。HISTORICAL_RESIDUE/GENERATED_FILE/UNKNOWN=0（仅Git可见清单，不含ignored运行资产）。除本轮P1必需的unified_intelligence_service.py外，其余75文件保持逐文件SHA相同。未reset/restore/clean/stash/commit。
|文件|Git状态|分类|
|---|---|---|
|app/main.py| M|EXPECTED_CURRENT_CHANGE|
|app/p3_network.py| M|EXPECTED_CURRENT_CHANGE|
|app/platform/capability_registry.py| M|EXPECTED_CURRENT_CHANGE|
|app/routes_platform.py| M|EXPECTED_CURRENT_CHANGE|
|app/security.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/canonical_relationship_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/club_operations_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/collection_scheduler.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/collection_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/collectors/playwright_adapter.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/data_quality.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/golden_loop_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/intelligence_flow_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/intelligence_product_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/intelligence_review_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/membership_access_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/navigation_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/processing/content_quality_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/processing/processing_job_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/unified_intelligence_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/services/unified_resource_service.py| M|EXPECTED_CURRENT_CHANGE|
|app/templates/base.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/club_home.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/p3_network.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/admin.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/admin_organizations.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/admin_people.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/home.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/intelligence.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/intelligence_detail.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/person_card.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/v05f_collection.html| M|EXPECTED_CURRENT_CHANGE|
|app/templates/v05g_processing.html| M|EXPECTED_CURRENT_CHANGE|
|app/v04c_review.py| M|EXPECTED_CURRENT_CHANGE|
|app/v05f_collection.py| M|EXPECTED_CURRENT_CHANGE|
|app/v05g_processing.py| M|EXPECTED_CURRENT_CHANGE|
|scripts/clean_test_data.py| M|EXPECTED_CURRENT_CHANGE|
|scripts/clean_test_opp.py| M|EXPECTED_CURRENT_CHANGE|
|scripts/cleanup_identity_test_accounts.py| M|EXPECTED_CURRENT_CHANGE|
|scripts/cleanup_test_data.py| M|EXPECTED_CURRENT_CHANGE|
|scripts/migrate_db.py| M|EXPECTED_CURRENT_CHANGE|
|scripts/restore_test_opp.py| M|EXPECTED_CURRENT_CHANGE|
|tests/conftest.py| M|EXPECTED_CURRENT_CHANGE|
|tests/test_mvp_rc1_2f_admin_and_membership.py| M|EXPECTED_CURRENT_CHANGE|
|app/routes_club_facilities.py|??|EXPECTED_CURRENT_CHANGE|
|app/routes_knowledge.py|??|EXPECTED_CURRENT_CHANGE|
|app/services/club_facility_service.py|??|EXPECTED_CURRENT_CHANGE|
|app/services/knowledge_service.py|??|EXPECTED_CURRENT_CHANGE|
|app/services/processing/article_facts.py|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/_article_facts.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/_bulk_delete_results.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/_knowledge_annotations.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/_knowledge_path_progress.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/_knowledge_training_fields.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/_reference_protection.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/_related_knowledge.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/club_facilities.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/knowledge.html|??|EXPECTED_CURRENT_CHANGE|
|app/templates/platform/knowledge_training.html|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R1_DATA_CHANGES.csv|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R1_GROUP01_CLEANUP_RESULT.md|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_MAPPING.csv|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_REPAIR_PLAN.md|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R1_MEMBERSHIP_FK_REPAIR_RESULT.md|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R1_REMAINING_FK_25_RAW.csv|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R1_REMAINING_FK_ANALYSIS.md|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R1_REMAINING_FK_DECISIONS.csv|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R2_MAINLINE_RESULT.md|??|EXPECTED_CURRENT_CHANGE|
|docs/audit/ASTRA_R3_RESULT.md|??|EXPECTED_CURRENT_CHANGE|
|scripts/migrations/012_industry_knowledge.py|??|EXPECTED_CURRENT_CHANGE|
|scripts/migrations/013_knowledge_training_and_rooms.py|??|EXPECTED_CURRENT_CHANGE|
|tests/test_astra_r2_mainline.py|??|EXPECTED_CURRENT_CHANGE|
|tests/test_astra_r3_facts.py|??|EXPECTED_CURRENT_CHANGE|
|tests/test_astra_r3_runtime.py|??|EXPECTED_CURRENT_CHANGE|
|tests/test_rc12g_subject_cleanup_and_knowledge.py|??|EXPECTED_CURRENT_CHANGE|
|tests/test_rc12h_training_and_rooms.py|??|EXPECTED_CURRENT_CHANGE|
