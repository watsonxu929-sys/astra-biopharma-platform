# Document Cleanup Report

## Keep

- `README.md`: project entry; rewritten as the single concise overview.
- `docs/01_INSTALLATION.md` to `docs/09_CHANGELOG.md`: new canonical documentation set.
- `docs/DOCUMENT_INDEX.md`: document map.
- `examples/v04c1_import_template.json`: kept as the JSON import example referenced by ingestion docs.
- `run_windows.bat`, `setup_windows.bat`, `self_check_windows.bat`: current basic Windows entry scripts.
- `migrate_v04c_windows.cmd`, `verify_v04c_windows.cmd`, `migrate_v04c1_windows.cmd`, `verify_v04c1_windows.cmd`, `seed_v04c1_demo_windows.cmd`: newer Windows scripts with UTF-8, logging, and pause-on-error behavior.
- `scripts/migrate_v04c.py`, `scripts/verify_v04c.py`, `scripts/migrate_v04c1.py`, `scripts/verify_v04c1.py`: required for new-environment initialization and self-checks.
- `data/app.db` and `data/backups/`: retained; production/local data and backups must not be deleted.

## Merge

- `docs/01_手动替换步骤.md` -> merged into `docs/01_INSTALLATION.md`, `docs/07_DEVELOPMENT.md`, and `docs/09_CHANGELOG.md`.
- `docs/02_JSON数据格式.md` -> merged into `docs/06_DATA_INGESTION.md`.
- `docs/02_功能验收清单.md` -> merged into `docs/05_REVIEW_WORKFLOW.md`, `docs/07_DEVELOPMENT.md`, and `docs/09_CHANGELOG.md`.
- `docs/03_故障排查.md` and `docs/05_故障排查.md` -> merged into `docs/08_TROUBLESHOOTING.md`.
- `docs/03_正式同步与业务表映射.md` -> merged into `docs/04_DATA_MODEL.md` and `docs/06_DATA_INGESTION.md`.
- `docs/04_验收清单.md` -> merged into `docs/06_DATA_INGESTION.md` and `docs/07_DEVELOPMENT.md`.
- Root `README.md` and `README_先看这里.txt` -> merged into the new `README.md` and canonical docs.

## Archive

- `docs/archive/01_手动替换步骤.md`: historical v0.4C patch installation note.
- `docs/archive/02_JSON数据格式.md`: historical v0.4C-1 JSON note.
- `docs/archive/02_功能验收清单.md`: historical v0.4C acceptance checklist.
- `docs/archive/03_故障排查.md`: historical v0.4C troubleshooting note.
- `docs/archive/03_正式同步与业务表映射.md`: historical sync/mapping note.
- `docs/archive/04_验收清单.md`: historical v0.4C-1 acceptance checklist.
- `docs/archive/05_故障排查.md`: historical v0.4C-1 troubleshooting note.

## Delete

- `patches/main_py_必须追加.txt`: manual router insertion note; replaced by actual source integration and `docs/07_DEVELOPMENT.md`.
- `patches/review页面增加入口_可选.txt`: optional manual UI note; replaced by actual templates and `docs/05_REVIEW_WORKFLOW.md`.
- `patches/首页导航_可选追加.txt`: optional navigation note; replaced by `base.html` integration and `README.md`.
- `patches/首页导航增加入口_可选.txt`: optional navigation note; replaced by `base.html` integration and `README.md`.
- `README_先看这里.txt`: old patch prompt; replaced by `README.md` and `docs/DOCUMENT_INDEX.md`.
- `migrate_v04c_windows.bat`: duplicate of `migrate_v04c_windows.cmd`; `.cmd` has logging and pause-on-error.
- `verify_v04c_windows.bat`: duplicate of `verify_v04c_windows.cmd`; `.cmd` has logging and pause-on-error.
- `app/**/__pycache__/`, `scripts/__pycache__/`: generated Python bytecode cache; ignored by `.gitignore`.
- `logs/*.log`: temporary run logs; ignored by `.gitignore`.

## Unable To Confirm

- `v04c_diagnose_windows.cmd`: retained. It may still be useful for manual diagnostics even though health checks and verify scripts cover routine validation.
- `apply_v04b_windows.bat`, `apply_v04b.py`, `apply_v03b.py`, `apply_v03c.py`, `apply_v04a.py`: retained for historical/new-environment migration compatibility.
- `backup_windows.bat`, `export_windows.bat`, `import_seed_windows.bat`, `seed_v04c_demo_windows.bat`: retained; not clearly superseded by a verified equivalent.
- `reference_documents/`: retained as source/reference material outside the formal user documentation set.

## Version Control Notes

- `.gitignore` should ignore virtual environments, bytecode, logs, backups, editor caches, and local SQLite files.
- `data/app.db` contains local/formal data and must not be deleted. Recommended version-control policy: keep it ignored and distribute schema through migrations and seed/import scripts.
