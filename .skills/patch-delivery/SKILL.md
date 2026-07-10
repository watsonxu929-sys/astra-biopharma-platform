---
name: patch-delivery
description: Workflow for preparing manual patch delivery packages for this biopharma intelligence system. Use when Codex is asked to package changes, produce replacement instructions, exclude local data, or provide migration, verification, startup, rollback and manual acceptance steps.
---

# Patch Delivery

Use this Skill when preparing a user-copyable patch or release handoff. Read `AGENTS.md`, `.gitignore`, existing patch manifests in `docs/`, and relevant `tools/patches/` examples first.

## Inputs

- Changed files and feature scope.
- Required migration and verification commands.
- Target delivery form: folder, archive, or manifest.

## Workflow

1. Identify the complete feature file set: app code, templates, static files, scripts, docs and Windows wrappers.
2. Keep a single coherent patch batch when possible; avoid asking the user to copy scattered snippets.
3. Exclude local and generated content:
   - `.venv/`, `venv/`
   - `.env`
   - `data/app.db`, `data/*.db*`, `data/backups/`
   - `logs/`, `*.log`
   - `__pycache__/`, `*.pyc`
   - `.pytest_cache/`, editor metadata
4. Include or reference migration scripts, verification scripts and docs needed for the feature.
5. Provide overwrite steps in order.
6. Provide command order:
   - backup if database changes exist
   - migrate
   - verify
   - run
7. Provide rollback steps: restore previous files and restore database backup when a real migration ran.
8. Provide manual acceptance scenarios for the changed feature.

## Existing Commands

```bat
backup_windows.bat
migrate_all_windows.bat
verify_all_windows.bat
run_windows.bat
project_tools_windows.bat
```

Historical patch notes and manifests live under `docs/*PATCH*` and `tools/patches/archive/`.

## Completion Reply

Report package location or manifest, included files, excluded files, replacement steps, migration/verification/start order, rollback steps and manual acceptance checklist.

## Failure Handling

If the changed file list is incomplete, stop and ask for or generate a diff inventory. If packaging would include formal data or secrets, block the package and remove those files before delivery.
