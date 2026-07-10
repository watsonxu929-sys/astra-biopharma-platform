---
name: project-development
description: Project workflow for developing or modifying features in the biopharma intelligence system. Use when Codex is asked to add, change, inspect, or plan application behavior across app models, routes, services, templates, API endpoints, scripts, or docs while preserving existing business code and data.
---

# Project Development

Use this Skill for ordinary feature work in this repository. Read `AGENTS.md` first, then use this workflow to keep changes incremental and aligned with the existing FastAPI, SQLAlchemy, Jinja2, SQLite and Windows-script structure.

## Inputs

- User goal, affected business area, and whether the request is implementation, review, planning, or documentation only.
- Relevant files found by targeted `rg` searches.
- Existing docs such as `README.md`, `docs/07_DEVELOPMENT.md`, `docs/API_V1_GUIDE.md`, and feature-specific docs in `docs/`.

## Workflow

1. Locate the current implementation before editing:
   - models and database access: `app/models.py`, `app/database.py`
   - web routes: `app/main.py` and version modules such as `app/v05e_intelligence.py`
   - services: `app/services/`
   - API: `app/api/v1/`
   - templates and static files: `app/templates/`, `app/static/`
   - migration and verification scripts: `scripts/`, root `*_windows.bat`, `tools/windows/`
2. Narrow searches to the feature vocabulary, route path, table name, service name, or template name. Avoid full-repo rewrites when a small scan is enough.
3. Reuse existing services, helpers, ID generators, permission checks, audit patterns, pagination helpers, and templates before creating new modules.
4. Keep web pages, API endpoints and services consistent. When a behavior exists in both web and API surfaces, put shared rules in services and call them from both sides.
5. Avoid duplicate domain models, duplicate subject tables, and route-only business logic.
6. If the feature needs database changes, stop and use `safe-database-migration` before editing migration code.
7. If the feature changes an API or extracts shared service logic, use `service-api-separation`.
8. If the feature needs delivery packaging, use `patch-delivery`.

## Safety Rules

- Do not delete or recreate `data/app.db`.
- Do not run migrations unless the user explicitly asks and the migration is ready.
- Do not move or rewrite large business files without a direct need.
- Do not auto-merge organizations, people or projects.
- Do not overwrite confirmed canonical fields from uncertain intelligence.

## Self-Check

- Check imports for cycles and unused additions.
- Check SQLAlchemy queries for obvious N+1 patterns on list pages.
- Check templates for missing variables and links to routes that exist.
- Check API responses for consistent errors, pagination, permissions and privacy filtering.
- Check Windows commands still point at real scripts.

## Verification

Prefer the smallest relevant verification first, then broader regression when the change affects shared behavior:

```bat
verify_all_windows.bat
```

Use feature-specific scripts in `scripts/verify_*.py` or archived Windows wrappers under `tools/windows/archive/` when they match the changed area. Do not invent test results; report not-run checks clearly.

## Completion Reply

Report changed files, reused services or commands, verification run, skipped checks, and any manual acceptance steps. If no code was changed, state the planned Skill combination and why.

## Failure Handling

If the implementation location is unclear, stop after the inventory and report the candidate files. If a requested change conflicts with `AGENTS.md` data safety rules, explain the conflict and propose a safer candidate-review or manual-approval path.
