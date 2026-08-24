# MVP-R4 Root Cleanup Inventory

扫描日期：2026-08-24。扫描口径为项目根目录一级普通文件（包含本地 `.env`，不包含目录）。

## Inventory

| File | Type | Referenced By | Runtime Required | Historical Only | Decision |
| --- | --- | --- | --- | --- | --- |
| `.env` | local config | current settings/startup | optional local runtime | no | KEEP_ROOT |
| `.env.example` | config example | README/setup | delivery | no | KEEP_ROOT |
| `.gitignore` | Git config | Git | engineering | no | KEEP_ROOT |
| `AGENTS.md` | repository rules | Codex/repository | engineering | no | KEEP_ROOT |
| `README.md` | product docs | users | delivery | no | KEEP_ROOT |
| `pytest.ini` | test config | pytest | test | no | KEEP_ROOT |
| `requirements.txt` | dependency manifest | setup/runtime | runtime | no | KEEP_ROOT |
| `requirements-dev.txt` | optional dependency manifest | development docs/tests | development | no | KEEP_ROOT |
| `requirements-docling.txt` | optional dependency manifest | document ingestion code/docs | optional capability | no | KEEP_ROOT |
| `requirements-playwright.txt` | optional dependency manifest | browser acceptance code/docs | acceptance | no | KEEP_ROOT |
| `run_windows.bat` | user launcher | README/users | formal startup | no | KEEP_ROOT |
| `backup_windows.bat` | maintenance launcher | README/AGENTS | maintenance | no | MOVE_TO_SCRIPTS |
| `collection_worker_windows.bat` | lifecycle launcher | RC1 lifecycle tests | worker lifecycle | no | MOVE_TO_SCRIPTS |
| `migrate_all_windows.bat` | maintenance launcher | README/AGENTS | migration | no | MOVE_TO_SCRIPTS |
| `setup_windows.bat` | setup launcher | README/AGENTS | setup | no | MOVE_TO_SCRIPTS |
| `start_all_windows.bat` | lifecycle launcher | operator maintenance | explicit lifecycle | no | MOVE_TO_SCRIPTS |
| `start_scheduler_windows.bat` | lifecycle launcher | explicit scheduler | optional lifecycle | no | MOVE_TO_SCRIPTS |
| `start_web_windows.bat` | internal web launcher | run_windows/lifecycle tests | startup implementation | no | MOVE_TO_SCRIPTS |
| `start_worker_windows.bat` | internal worker launcher | worker wrapper | worker lifecycle | no | MOVE_TO_SCRIPTS |
| `status_windows.bat` | lifecycle launcher | run_windows | lifecycle | no | MOVE_TO_SCRIPTS |
| `stop_all_windows.bat` | lifecycle launcher | operator maintenance | lifecycle | no | MOVE_TO_SCRIPTS |
| `verify_all_windows.bat` | maintenance launcher | README/AGENTS | verification | no | MOVE_TO_SCRIPTS |
| `web_service_windows.bat` | lifecycle launcher | RC1 lifecycle tests | web lifecycle | no | MOVE_TO_SCRIPTS |
| `acceptance_report_v06L_corrected.md` | old audit | Git history only | no | yes | DELETE |
| `ARCHIVE_MANIFEST.md` | old archive report | Git history only | no | yes | DELETE |
| `CANONICAL_DATA_CONTRACT.md` | superseded contract | R2/R3 audits | no | yes | DELETE |
| `DATA_LOCATION.md` | superseded location report | AGENTS before R4 | no | yes | DELETE |
| `KNOWN_ISSUES.md` | old issue report | README before R4 | no | yes | DELETE |
| `MIGRATION_RECOVERY_MANIFEST.md` | old migration report | Git history only | no | yes | DELETE |
| `MVP_RC1_2_USER_FLOW.md` | superseded product report | Git history only | no | yes | DELETE |
| `MVP_RC1_BASELINE.md` | superseded baseline | Git history only | no | yes | DELETE |
| `MVP_RC1_DELIVERY.md` | superseded delivery report | Git history only | no | yes | DELETE |
| `PROJECT_DIRECTORY_INVENTORY.md` | superseded inventory | AGENTS before R4 | no | yes | DELETE |
| `PROJECT_EXECUTION_ROADMAP.md` | old roadmap | Git history only | no | yes | DELETE |
| `PROJECT_STATUS.md` | old status | README before R4 | no | yes | DELETE |
| `TEST_DEBT_CLASSIFICATION.md` | old test report | Git history only | no | yes | DELETE |
| `check_account.py` | one-off diagnostic | paired root BAT only | no | yes | DELETE |
| `check_account_windows.bat` | one-off diagnostic | no current caller | no | yes | DELETE |
| `export_routes.py` | old route exporter | superseded by `scripts/export_routes.py` | no | yes | DELETE |
| `migrate_platform_mvp_v1.bat` | one-off migration | no current caller | no | yes | DELETE |
| `migrate_v05c_windows.bat` | v05 migration launcher | no current caller | no | yes | DELETE |
| `migrate_v05d_windows.bat` | v05 migration launcher | no current caller | no | yes | DELETE |
| `migrate_v05e_windows.bat` | v05 migration launcher | no current caller | no | yes | DELETE |
| `migrate_v05f_windows.bat` | v05 migration launcher | historical docs only | no | yes | DELETE |
| `migrate_v05g_windows.bat` | v05 migration launcher | historical docs only | no | yes | DELETE |
| `migrate_v05h_windows.bat` | v05 migration launcher | historical docs only | no | yes | DELETE |
| `migrate_v05i_windows.bat` | v05 migration launcher | historical docs only | no | yes | DELETE |
| `migrate_v05j_windows.bat` | v05 migration launcher | historical docs only | no | yes | DELETE |
| `migrate_v05kl_windows.bat` | v05 migration launcher | no current caller | no | yes | DELETE |
| `project_tools_windows.bat` | legacy menu | historical launchers/docs | no | yes | DELETE |
| `run_acceptance_windows.bat` | one-off acceptance | historical docs only | no | yes | DELETE |
| `run_collection_once_windows.bat` | v05 collection launcher | legacy menu/docs | no | yes | DELETE |
| `run_collection_worker_windows.bat` | v05 collection launcher | legacy menu/docs | no | yes | DELETE |
| `run_monitoring_once_windows.bat` | old monitoring launcher | AGENTS/legacy menu before R4 | no | yes | DELETE |
| `run_pipeline_once_windows.bat` | v05 pipeline launcher | legacy menu/docs | no | yes | DELETE |
| `run_pipeline_worker_windows.bat` | v05 pipeline launcher | legacy menu/docs | no | yes | DELETE |
| `run_processing_once_windows.bat` | v05 processing launcher | legacy menu/docs | no | yes | DELETE |
| `run_processing_worker_windows.bat` | v05 processing launcher | legacy menu/docs | no | yes | DELETE |
| `run_rehearsal_auth.bat` | one-off rehearsal | old inventory only | no | yes | DELETE |
| `run_report_once_windows.bat` | v05 report launcher | legacy menu/docs | no | yes | DELETE |
| `run_signal_once_windows.bat` | v05 signal launcher | legacy menu/docs | no | yes | DELETE |
| `seed_demo_platform_v1.bat` | demo seed launcher | no current caller | no | yes | DELETE |
| `start_windows.bat` | obsolete reload launcher | historical docs/old verify only | no | yes | DELETE |
| `verify_intelligence_full_chain_windows.bat` | one-off verify | historical docs only | no | yes | DELETE |
| `verify_platform_mvp_v1.bat` | one-off verify | no current caller | no | yes | DELETE |
| `verify_v05c_windows.bat` | v05 verify launcher | no current caller | no | yes | DELETE |
| `verify_v05d_windows.bat` | v05 verify launcher | no current caller | no | yes | DELETE |
| `verify_v05e_windows.bat` | v05 verify launcher | no current caller | no | yes | DELETE |
| `verify_v05f_windows.bat` | v05 verify launcher | historical docs only | no | yes | DELETE |
| `verify_v05g_windows.bat` | v05 verify launcher | historical docs only | no | yes | DELETE |
| `verify_v05h_windows.bat` | v05 verify launcher | historical docs only | no | yes | DELETE |
| `verify_v05i_windows.bat` | v05 verify launcher | historical docs only | no | yes | DELETE |
| `verify_v05j_windows.bat` | v05 verify launcher | historical docs/legacy menu | no | yes | DELETE |
| `verify_v05kl_windows.bat` | v05 verify launcher | historical docs/legacy menu | no | yes | DELETE |
| `verify_v05m_windows.bat` | v05 verify launcher | historical docs only | no | yes | DELETE |

## Safety evidence before cleanup

- 全仓引用搜索已逐项执行；DELETE脚本仅被同批历史脚本、历史安装文档或已被R4替代的根目录报告引用。
- 当前 `app/`、`tests/`、`scripts/migrate_all.py`、`scripts/verify_all.py` 不调用这些根BAT作为运行依赖。
- `export_routes.py` 在 `scripts/export_routes.py` 有当前脚本版本。
- `.env` 含本地配置，保持忽略，不读取或复制凭据。
- `requirements-dev.txt`、`requirements-docling.txt`、`requirements-playwright.txt` 对应能力仍存在，全部保留。
- `data/migration_backup/pre_mvp_r3_20260824_093559.db` 被Git忽略，不是runtime DB，承担R3回滚，保持不动。

## Result

| Metric | Count |
| --- | ---: |
| Root files BEFORE | 75 |
| Moved to `scripts/windows/` | 12 |
| Deleted historical root files | 52 |
| Root files AFTER | 11 |

根目录最终保留：`.env`、`.env.example`、`.gitignore`、`AGENTS.md`、`README.md`、`pytest.ini`、四个requirements文件、`run_windows.bat`。其中根目录唯一用户启动入口为 `run_windows.bat`。

删除均由Git历史可恢复；没有删除正式数据库、R3迁移备份、源代码目录、测试目录或依赖清单。
