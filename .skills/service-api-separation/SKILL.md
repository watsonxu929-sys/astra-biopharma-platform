---
name: service-api-separation
description: Workflow for separating web routes, JSON API endpoints and shared services in this biopharma intelligence system. Use when adding or refactoring /api/v1 endpoints, moving business logic out of templates/routes, or checking that web pages and APIs reuse the same service layer without duplicate tables or rules.
---

# Service API Separation

Use this Skill when work touches web/API boundaries. Read `AGENTS.md` and `docs/API_V1_GUIDE.md` before changing behavior.

## Inputs

- Target page route, API route, or shared behavior.
- Current web implementation in `app/main.py` or version modules.
- Current API implementation in `app/api/v1/`.
- Candidate service modules in `app/services/`.

## Workflow

1. Identify the existing web route, template and service call chain.
2. Identify the matching or desired API endpoint under `app/api/v1/`.
3. Move reusable business rules into `app/services/` only when they are not already there.
4. Keep service functions free of `Request`, `TemplateResponse`, cookies and rendered HTML. Services may accept DB sessions, typed parameters and explicit user/permission context.
5. Make web routes handle rendering, redirects, flash-style page state and form parsing.
6. Make API routes handle JSON schema, pagination, status codes, JSON errors and privacy filtering.
7. Keep both surfaces calling the same service for subject lookup, search, dashboard, intelligence, relationship, signal or watchlist behavior.
8. Do not create API-only duplicate business tables. API routes should reuse existing models and service outputs.

## API Rules

- Use `/api/v1` conventions from `docs/API_V1_GUIDE.md`.
- Preserve JSON `401` for unauthenticated internal API requests.
- Use list pagination with `page`, `page_size`, total counts and whitelisted sorting where relevant.
- Return unified JSON errors without SQL, database paths, passwords, tokens or stack traces.
- Apply existing permissions such as `view_internal`, `review_data` and `edit_data`.
- Filter full raw source text, private contact fields and internal notes unless an explicit authorized endpoint exists.

## Refactor Order

Start with the smallest high-value slice:

1. `app/services/api_common.py`
2. `app/services/api_subject_service.py`
3. domain service already used by the page
4. matching route in `app/api/v1/`
5. page route/template only if needed

Do not rewrite all pages in one pass.

## Verification

- Compare one representative web result with the API result for the same subject/search/list.
- Exercise `/api/v1/health` when only API wiring changes.
- Run the closest feature verification script if one exists, otherwise run:

```bat
verify_all_windows.bat
```

## Completion Reply

Report the shared service used, web routes touched, API routes touched, privacy and permission checks, and verification results.

## Failure Handling

If web and API behavior diverge because existing data is incomplete, keep the service conservative and document the difference. If a service would need database changes, switch to `safe-database-migration` before editing schema.
