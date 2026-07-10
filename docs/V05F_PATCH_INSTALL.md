# v0.5F Patch Install

## Included Areas

- Collection service, API and pages.
- Additive migration and verification scripts.
- Windows worker and scheduler entry scripts.
- API and scheduler documentation.

## Install Order

```bat
setup_windows.bat
migrate_all_windows.bat
verify_all_windows.bat
run_windows.bat
```

Optional worker commands:

```bat
run_collection_once_windows.bat
run_collection_worker_windows.bat
```

## Manual Acceptance

1. Open `http://127.0.0.1:8000/collection`.
2. Create an RSS or static page source.
3. Create a collection job.
4. Run `run_collection_worker_windows.bat` or process the job from the page.
5. Confirm items appear under `/collection/items`.
6. Confirm duplicate runs do not create repeated queued items.
7. Confirm formal subject records are unchanged until later manual processing.

## Rollback

Restore the previous project files from backup. If a real migration was run, restore the database backup created under `data/backups/`.
