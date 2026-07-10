# v0.5F Multi-Source Collection

v0.5F upgrades the existing v0.4G monitoring foundation into a controlled public collection pipeline.

## Reused Foundation

- `v04g_monitoring_sources` remains the source registry.
- `v04g_monitoring_runs` remains the job/run ledger.
- `v04g_source_snapshots` remains the evidence snapshot table.
- `app/services/collection_service.py` is the shared service used by pages, API and worker scripts.

## New Tables

- `v05f_collection_items`: normalized collection items and processing queue state.
- `v05f_discovered_links`: list-page discovered links and fetch status.
- `v05f_content_duplicate_links`: duplicate/reprint relationships between items.
- `v05f_collection_job_locks`: lightweight local lock to avoid duplicate running jobs.
- `v05f_collection_templates`: generic source templates.

## Supported Collection Modes

- RSS / Atom through standard XML parsing.
- Static web pages through HTTP and HTML extraction.
- List pages through same-domain link discovery and optional detail fetching.
- Public JSON APIs with simple list payloads.
- Manual URL lists.
- Playwright is recorded as optional mode; missing Playwright does not break HTTP/RSS collection.

## Queue Boundary

New or changed content is queued in `v05f_collection_items`. Duplicate or unchanged content is ignored by default. v0.5F does not perform v0.5G semantic extraction, does not merge subjects, and does not update formal organization/person/project/event/resource records.

## API

Collection API endpoints live under `/api/v1/collection`. List responses are paginated. Mutating source/job endpoints require monitoring management permission. Item queue actions require review permission.

## Verification

Run:

```bat
verify_v05f_windows.bat
verify_all_windows.bat
```

The v0.5F verification uses a temporary SQLite database and inline RSS/HTML fixtures; it does not perform real network collection.
