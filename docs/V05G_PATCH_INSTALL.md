# v0.5G Patch Install Notes

## Install Order

1. Back up the current project and database.
2. Overwrite files from the v0.5G patch package.
3. Run migrations:

```bat
migrate_all_windows.bat
```

4. Run verification:

```bat
verify_v05g_windows.bat
verify_all_windows.bat
```

5. Start the system and open `/processing`.

## Rollback

Restore the previous files from backup. If `migrate_all_windows.bat` was run, restore the database backup created under `data/backups/`.

## Manual Acceptance

- Open `/collection/items?processing_status=queued`.
- Run `/processing/jobs` once for a queued item.
- Check `/processing/candidates` for extracted candidates with evidence.
- Confirm ambiguous same-name people stay ambiguous.
- Approve one safe field candidate, apply it, and confirm an application log exists.
- Confirm event and relationship candidates do not directly create formal records.
