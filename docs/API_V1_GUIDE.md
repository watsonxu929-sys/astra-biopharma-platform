# API v1 Guide

## Overview

`/api/v1` is the shared JSON API layer for the current web backend and future mini program/App clients. It reuses the existing FastAPI session, permission, audit, subject, monitoring, recommendation, Q-BAY and review data structures.

Implemented entry points:

- `GET /api/v1/health`
- `GET /api/v1/meta`
- `GET /api/v1/me`
- `GET /api/v1/subjects`
- `GET /api/v1/subjects/{subject_type}/{subject_id}`
- `GET /api/v1/subjects/{subject_type}/{subject_id}/relationships`
- `GET /api/v1/subjects/{subject_type}/{subject_id}/timeline`
- `GET /api/v1/subjects/{subject_type}/{subject_id}/sources`
- `GET /api/v1/subjects/{subject_type}/{subject_id}/actions`
- `GET /api/v1/subjects/{subject_type}/{subject_id}/reviews`
- `GET /api/v1/search`
- `GET /api/v1/intelligence`
- `GET /api/v1/intelligence/{id}`
- `GET /api/v1/monitoring/sources`
- `GET /api/v1/monitoring/runs`
- `GET /api/v1/monitoring/proposals`
- `GET /api/v1/events`
- `GET /api/v1/events/{id}`
- `GET /api/v1/relationships`
- `GET /api/v1/relationships/{id}`
- `GET /api/v1/relationship-paths`
- `GET /api/v1/signals`
- `GET /api/v1/signals/{id}`
- `POST /api/v1/signals/generate-from-events`
- `POST /api/v1/signals/{id}/status`
- `POST /api/v1/signals/{id}/convert-action`
- `GET /api/v1/watchlists`
- `POST /api/v1/watchlists`
- `GET /api/v1/watchlists/{id}/items`
- `POST /api/v1/watchlists/{id}/items`
- `POST /api/v1/watchlists/items/{item_id}/remove`
- `GET /api/v1/dashboard`
- `GET /api/v1/collection/sources`
- `POST /api/v1/collection/sources`
- `GET /api/v1/collection/sources/{id}`
- `PATCH /api/v1/collection/sources/{id}`
- `POST /api/v1/collection/sources/{id}/run`
- `POST /api/v1/collection/sources/batch-run`
- `GET /api/v1/collection/jobs`
- `POST /api/v1/collection/jobs`
- `GET /api/v1/collection/jobs/{id}`
- `POST /api/v1/collection/jobs/{id}/retry`
- `POST /api/v1/collection/jobs/{id}/cancel`
- `GET /api/v1/collection/items`
- `GET /api/v1/collection/items/{id}`
- `POST /api/v1/collection/items/{id}/queue`
- `POST /api/v1/collection/items/batch-queue`
- `GET /api/v1/collection/snapshots/{id}`
- `GET /api/v1/collection/dashboard`
- `GET /api/v1/processing/dashboard`
- `GET /api/v1/processing/jobs`
- `POST /api/v1/processing/jobs`
- `POST /api/v1/processing/jobs/{id}/run`
- `POST /api/v1/processing/worker/run-once`
- `GET /api/v1/processing/candidates`
- `GET /api/v1/processing/candidates/{id}`
- `POST /api/v1/processing/candidates/{id}/review`
- `POST /api/v1/processing/candidates/{id}/apply`
- `GET /api/v1/processing/subject-matches`
- `GET /api/v1/navigation`
- `GET /api/v1/signals/dashboard`
- `GET /api/v1/signals/rules`
- `POST /api/v1/signals/{id}/read`
- `POST /api/v1/signals/{id}/important`
- `POST /api/v1/signals/{id}/ignore`
- `GET /api/v1/reports`
- `POST /api/v1/reports/jobs`
- `GET /api/v1/reports/jobs/{id}`
- `GET /api/v1/reports/{id}`
- `PATCH /api/v1/reports/{id}`
- `POST /api/v1/reports/{id}/submit`
- `POST /api/v1/reports/{id}/approve`
- `POST /api/v1/reports/{id}/archive`
- `GET /api/v1/reports/{id}/citations`
- `GET /api/v1/pipeline/runs`
- `POST /api/v1/pipeline/runs`
- `GET /api/v1/pipeline/runs/{id}`
- `POST /api/v1/pipeline/runs/{id}/continue`
- `POST /api/v1/pipeline/runs/{id}/retry`
- `POST /api/v1/pipeline/runs/{id}/cancel`
- `GET /api/v1/pipeline/dashboard`
- `GET /api/v1/pipeline/quality`
- `POST /api/v1/pipeline/samples/{id}/review`
- `GET /api/v1/research/topics`
- `POST /api/v1/research/topics`
- `GET /api/v1/research/topics/{id}`
- `PATCH /api/v1/research/topics/{id}`
- `POST /api/v1/research/topics/{id}/refresh`
- `POST /api/v1/research/topics/{id}/subjects`
- `DELETE /api/v1/research/topics/{id}/subjects/{subject_type}/{subject_id}`
- `GET /api/v1/research/topics/{id}/dashboard`
- `GET /api/v1/research/topics/{id}/timeline`
- `GET /api/v1/research/topics/{id}/signals`
- `GET /api/v1/research/topics/{id}/network`
- `POST /api/v1/research/topics/{id}/reports`
- `POST /api/v1/research/companies/compare`
- `POST /api/v1/research/companies/compare/report`
- `GET /api/v1/research/tracks`
- `GET /api/v1/research/tracks/{track_key}`
- `GET /api/v1/investment-assessments`
- `POST /api/v1/investment-assessments`
- `GET /api/v1/investment-assessments/{id}`
- `POST /api/v1/investment-assessments/{id}/generate`
- `POST /api/v1/investment-assessments/{id}/approve`
- `POST /api/v1/investment-assessments/{id}/reject`
- `POST /api/v1/investment-assessments/{id}/convert-lead`

## Authentication

The current version uses the existing same-domain web session. Unauthenticated internal API requests return JSON `401` instead of redirecting to an HTML login page.

Bearer token, mini program login and App login are not implemented in v0.5E.

## Pagination

List endpoints use:

- `page`, default `1`
- `page_size`, default `20`, max `100`
- `q`, where supported
- `sort` and `order`, only on whitelist fields

Response shape:

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  },
  "meta": {}
}
```

## Errors

API errors use:

```json
{
  "error": {
    "code": "SUBJECT_NOT_FOUND",
    "message": "主体不存在",
    "details": {}
  }
}
```

The API does not expose SQL, database paths, passwords, activation tokens or stack traces.

## Subject Types

Currently supported:

- `organization`
- `person`
- `project`

Subject responses include API and web URLs, for example:

```json
{
  "api_url": "/api/v1/subjects/organization/ORG-001",
  "web_url": "/subjects/organization/ORG-001"
}
```

## Permissions

Read APIs require the existing `view_internal` permission unless explicitly public, such as `/api/v1/health`.

Write APIs require existing internal permissions such as `review_data` or `edit_data`, and continue to write audit logs.

Collection source and job write APIs require `manage_monitoring`. Collection item queue APIs require `review_data`.

Processing write APIs require `review_data`. Processing reads require `view_internal`.

Report write APIs and signal rule/generation writes require `review_data`. Report, navigation and signal read APIs require `view_internal`.

Pipeline reads require `view_internal`. Pipeline writes require `review_data` or stronger internal roles through the same security middleware. External member accounts cannot access the pipeline center.

Research topic reads require `view_internal`. Topic creation, subject maintenance, refresh and company comparison require `edit_data`. Investment assessment reads require `view_internal`; generation, approval, rejection and lead conversion require `review_data`. External member accounts cannot access internal research, company comparison or investment assessment centers.

System health and task APIs require internal access except public health probes. `GET /api/v1/system/health` returns a basic status for probes and detailed checks for logged-in internal users. `GET /api/v1/system/readiness` returns 200 or 503 with JSON checks. `GET /api/v1/system/tasks` and `GET /api/v1/system/task-metrics` require `view_internal`.

External member accounts are not treated as internal API users.

## Privacy

List and detail APIs avoid returning:

- full raw source text
- private contact fields
- internal notes
- passwords, tokens or sensitive configuration

## Examples

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/api/v1/search?q=药明康德"
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/api/v1/subjects?subject_type=organization&page=1&page_size=20"
```

## Future Mini Program/App Integration

The API response shape, pagination, subject URLs and dashboard data are reusable by future clients. Authentication for mini programs and Apps is intentionally not implemented in this stage; it should be added as a verified token layer on top of this API, not as a duplicate business backend.

## Current Limits

- Signal generation is manual and limited, based on confirmed events.
- Dashboard trends use lightweight SQLite aggregation.
- Full source text requires a future explicit authorization endpoint.
- CSRF hardening for same-domain session write APIs should be expanded when the API write surface grows.
- v0.5F collection creates controlled snapshots and queue items only; semantic extraction and formal subject updates are intentionally left to a later processing stage.
- v0.5G processing creates structured candidates, subject matches, review history and safe application logs. It does not automatically create formal events, relations or new subjects.
- v0.5H adds configurable signal rules, report drafts with citations and centralized navigation. Report generation is deterministic and template based; it is not an LLM authoring pipeline.
- v0.5I adds pipeline orchestration, retry state, quality sampling, pilot source configuration and run-quality metrics. Real network pilot scripts are not part of default regression and require explicit confirmation.
- v0.5J adds research topics, company comparison, track analysis, investment assessment and centralized Chinese labels. API machine fields remain English; display labels are returned through sibling fields such as `status_label`, `type_label`, `grade_label` and `field_label`.
- v0.5K-L adds production configuration, health/readiness, unified task queue, backup/restore records, source quality metrics and safe real-source pilot tooling. SQLite remains the default database; PostgreSQL migration support is explicit and dry-run first.
