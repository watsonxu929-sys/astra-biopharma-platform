---
name: safe-database-migration
description: Safe SQLite migration workflow for this biopharma intelligence system. Use for any requested database schema or data-storage change, migration script update, table/index/field addition, backup concern, rollback plan, or review of existing migrate_* scripts.
---

# Safe Database Migration

Use this Skill before any database change. Read `AGENTS.md`, `docs/07_DEVELOPMENT.md`, and the closest existing migration script in `scripts/`.

## Inputs

- Required schema or storage change.
- Existing table/model/service affected.
- Migration script to add or update.
- Verification script to add or update.

## Allowed Changes

- Add new tables with `CREATE TABLE IF NOT EXISTS`.
- Add indexes with `CREATE INDEX IF NOT EXISTS`.
- Add safe nullable fields or fields with conservative defaults.
- Add idempotent seed or sequence metadata when required.

## Forbidden Changes

- Do not delete, recreate, truncate or overwrite `data/app.db`.
- Do not `DROP TABLE` existing business tables.
- Do not clear production data.
- Do not rewrite primary keys, business IDs or confirmed canonical fields.
- Do not auto-merge people, organizations or projects.

## Workflow

1. Inspect current scripts:
   - root entry: `migrate_all_windows.bat`
   - orchestrator: `scripts/migrate_all.py`
   - latest examples: `scripts/migrate_v05c.py`, `scripts/migrate_v05d.py`, `scripts/migrate_v05e.py`
   - backup helper: `scripts/backup_database.py`, `backup_windows.bat`
2. Design the migration to be idempotent and safe on repeated runs.
3. Create or update a versioned migration script in `scripts/`.
4. Ensure `scripts/migrate_all.py` and the relevant root or archived Windows wrapper call the migration when appropriate.
5. Back up before touching `data/app.db`; existing scripts write backups under `data/backups/`.
6. Test the migration against a temporary SQLite copy or temporary database first.
7. Add or update a verification script that proves the schema exists and no formal data was polluted.
8. Preserve logs and fail fast on migration errors.

## Existing Commands

```bat
backup_windows.bat
migrate_all_windows.bat
verify_all_windows.bat
project_tools_windows.bat
```

Use version-specific wrappers such as `migrate_v05e_windows.bat` only when they match the target version.

## Verification

- Run the version-specific verification script on a temporary database when possible.
- Run `verify_all_windows.bat` for broad regression after migration logic changes.
- Confirm formal `data/app.db` was not polluted by test data.
- Report backup location if a real migration was run.

## Completion Reply

Report migration file, orchestrator updates, backup behavior, idempotency check, verification run, rollback path and any manual acceptance steps.

## Failure Handling

If a requested schema change requires destructive modification, stop and propose an additive compatibility layer, manual export/import plan, or explicit human-approved maintenance window.
