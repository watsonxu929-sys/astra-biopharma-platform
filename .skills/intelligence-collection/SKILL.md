---
name: intelligence-collection
description: Workflow for public intelligence collection and monitoring tasks in this biopharma intelligence system. Use when adding, reviewing, or planning source collection, monitoring runs, web extraction, RSS/API/HTTP/Playwright strategies, snapshots, deduplication, retry handling, and source logs.
---

# Intelligence Collection

Use this Skill for collection and monitoring tasks. Read `AGENTS.md`, `docs/06_DATA_INGESTION.md`, and monitoring-related code before changing collectors.

## Inputs

- Source type, URL or source list.
- Desired collection mode: one-off intake, scheduled monitoring, or batch import.
- Existing source records, monitoring service or extractor behavior.

## Collection Priority

Prefer the least invasive reliable method:

1. RSS or public API
2. ordinary HTTP fetch
3. column or sitemap traversal
4. Playwright/browser automation only when simpler methods cannot capture public content

## Safety Rules

- Collect only public content.
- Respect robots expectations, site terms, rate limits and retry backoff.
- Do not bypass login, captcha, paywalls or access controls.
- Do not directly overwrite formal subjects from collected content.
- Treat multi-subject pages carefully; preserve raw source, evidence and candidate boundaries.
- Isolate failed tasks and record status/logs rather than blocking the whole batch.

## Workflow

1. Locate existing collection code:
   - `app/web_extractor.py`
   - `app/services/monitoring_service.py`
   - `scripts/run_monitoring_once.py`
   - `run_monitoring_once_windows.bat`
   - `docs/06_DATA_INGESTION.md`
2. Determine whether the task belongs in manual intake, monitoring, or a new source adapter.
3. Store snapshots, source URLs, hashes and timestamps when the existing model supports them.
4. Deduplicate by source key, URL/content hash or existing source rules.
5. Separate task status, retry count, failure reason and collected content.
6. Send uncertain or unstructured content to intake/structuring rather than formal tables.
7. For batch work, make each source independently retryable and auditable.

## Verification

- Use a small public source or fixture.
- Verify deduplication on repeated runs.
- Verify failures are logged and isolated.
- Verify formal business tables are not directly updated.
- Run the closest script, such as:

```bat
run_monitoring_once_windows.bat
verify_all_windows.bat
```

## Completion Reply

Report source method, public-access assumption, deduplication key, snapshot/log behavior, retry behavior, verification run and manual review path.

## Failure Handling

If public access is blocked, stop and report the limitation. If a page contains multiple candidate subjects, keep them separate and route uncertain extraction to review.
