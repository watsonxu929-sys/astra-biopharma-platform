# v0.6I runtime baseline

## Configuration source

All runtime code resolves configuration through `app.settings.get_settings()`. `app.core.config` is a compatibility facade. Database priority is:

1. `DATABASE_URL`
2. `APP_DB_PATH`
3. `<project>/data/app.db`

Startup output shows the environment, database backend, resolved SQLite path, authentication state, and whether the embedded Web scheduler is enabled. It never prints passwords, tokens, API keys, or a full sensitive non-SQLite connection string.

## Environments

- `development`: local Web development. Authentication is enabled by default. `APP_AUTH_DISABLED=true` is an explicit diagnostic bypass and prints a warning.
- `testing`: must use a temporary database or an explicitly named acceptance database; it refuses the formal `data/app.db`.
- `production`: requires `SECRET_KEY` and `SESSION_SECRET`; authentication bypass and an embedded Web scheduler are rejected.
- Acceptance uses `run_acceptance_windows.bat`, port 8001, and its named acceptance database.

## Process entry points

- Web (recommended daily entry): `run_windows.bat` or `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Scheduler: `start_scheduler_windows.bat` or `python -m scripts.run_scheduler`
- Worker: `start_worker_windows.bat` or `python -m scripts.run_worker`
- Explicit all-process helper: `start_all_windows.bat`

Web does not start a scheduler by default. `ENABLE_SCHEDULER_IN_WEB=true` is a development-only compatibility switch. Scheduler and Worker never run migrations on startup.

## Database readiness

Startup runs a read-only schema preflight. It does not create files, tables, columns, or data and does not execute migrations. `/health` exposes only safe readiness flags. An authenticated administrator can inspect table-level capability details at `/health/schema`.

Missing extension tables keep the registered routes but return a clear unavailable page; API requests return HTTP 503 with `capability_unavailable`. The matching menu entries are hidden until the required schema exists.
