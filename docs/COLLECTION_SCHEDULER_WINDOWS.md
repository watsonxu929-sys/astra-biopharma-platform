# v0.5F Windows Collection Scheduler

This project does not include an always-on background scheduler in v0.5F. Use Windows Task Scheduler to run a single local worker pass at a controlled interval.

## Command

Use this root-level script:

```bat
run_collection_once_windows.bat
```

It runs:

```bat
python scripts\run_collection_worker.py --once --due-only
```

Logs are written to:

```text
logs\collection_worker_latest.log
```

## Suggested Schedule

1. Open Windows Task Scheduler.
2. Create a basic task named `Biopharma Collection Once`.
3. Trigger every 30-60 minutes during working hours, or daily for conservative sources.
4. Action: start a program.
5. Program: full path to `run_collection_once_windows.bat`.
6. Start in: project root directory.

Use conservative intervals. Do not schedule high-frequency whole-site scans.

## Manual Commands

```bat
run_collection_once_windows.bat
run_collection_worker_windows.bat
python scripts\run_collection_worker.py --source-id 8
python scripts\run_collection_worker.py --job-id 12
python scripts\run_collection_worker.py --limit 20
```

## Safety Notes

- The worker only processes configured public sources.
- Playwright mode is optional and returns `playwright_unavailable` unless the environment is explicitly prepared.
- The worker does not bypass login, captcha, paywalls or robots restrictions.
- Collected items enter the processing queue; formal subjects are not updated automatically.
- Repeated source failures auto-pause the source and require manual recovery.
