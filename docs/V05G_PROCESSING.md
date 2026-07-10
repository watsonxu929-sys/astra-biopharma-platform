# v0.5G Semantic Processing

v0.5G turns v0.5F collection items into structured, reviewable intelligence candidates.

## Reused Capabilities

- v0.5F collection items and source snapshots are the input queue.
- v0.4C review items and pending relations remain the manual approval lane.
- Existing organization, person and project tables are used for subject matching.
- Existing permissions and audit middleware protect page and API writes.

## Flow

1. Classify page structure: team page, product pipeline, news/event article, policy/resource, multi-subject list, single-subject profile or mixed/uncertain.
2. Split content into evidence blocks before extraction.
3. Extract candidates for organizations, people, projects, events, needs, resources, risks, opportunities and fields.
4. Match candidate subjects conservatively against existing subject tables.
5. Store candidates, evidence excerpts, confidence and warning flags.
6. Route approved field/event/resource candidates into review or safe field application.

Formal event, relation or new-subject creation is intentionally not automatic in v0.5G.

## Pages

- `/processing`
- `/processing/jobs`
- `/processing/candidates`
- `/processing/subject-matches`

## API

- `GET /api/v1/processing/dashboard`
- `GET /api/v1/processing/jobs`
- `POST /api/v1/processing/jobs`
- `POST /api/v1/processing/jobs/{job_id}/run`
- `POST /api/v1/processing/worker/run-once`
- `GET /api/v1/processing/candidates`
- `GET /api/v1/processing/candidates/{candidate_id}`
- `POST /api/v1/processing/candidates/{candidate_id}/review`
- `POST /api/v1/processing/candidates/{candidate_id}/apply`
- `GET /api/v1/processing/subject-matches`

## Commands

```bat
migrate_v05g_windows.bat
verify_v05g_windows.bat
run_processing_once_windows.bat
run_processing_worker_windows.bat
```

Historical v0.5F items can be inspected before queuing:

```bat
python scripts\queue_historical_processing.py --limit 100
python scripts\queue_historical_processing.py --limit 100 --confirm
```

## Safety

Approved field candidates can only apply to a small whitelist of subject fields. Event and relationship candidates are sent to review queues instead of directly writing formal tables.
