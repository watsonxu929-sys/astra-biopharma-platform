---
name: intelligence-processing
description: Workflow for processing collected or pasted intelligence in this biopharma intelligence system. Use for page-structure judgment, single/multi-subject splitting, candidate extraction for organizations, people, projects, events and resources, evidence/confidence handling, review routing, entity matching, and explainable industry signals.
---

# Intelligence Processing

Use this Skill when raw or collected intelligence must become structured candidates. Read `AGENTS.md`, `docs/03_算法与安全边界.md`, `docs/06_DATA_INGESTION.md`, and `docs/10_V04D_STRUCTURING.md` when relevant.

## Inputs

- Raw page text, pasted content, source record or monitoring proposal.
- Source URL, publication date and evidence excerpts when available.
- Target output: structuring task, review candidate, signal, or manual plan.

## Workflow

1. Judge page structure:
   - single subject profile
   - multi-subject list
   - news/event article
   - resource/policy/data source
   - mixed or uncertain page
2. Split multi-subject content before extraction. Do not merge unrelated organizations, people, projects or events.
3. Extract candidates for:
   - organizations
   - people
   - projects
   - events
   - resources
   - relationships and actions
4. Attach evidence excerpts, source URLs, field names, confidence and fact/speculation status.
5. Match candidate subjects conservatively using existing subject matching and review flows.
6. Route uncertain content to review or structuring queues.
7. Do not automatically overwrite canonical fields or merge same-name subjects.
8. Classify needs, resources, risks and opportunities only when the source supports the label.
9. Make industry signals explainable and traceable to evidence.

## Existing Files

- `app/entity_analyzer.py`
- `app/analyzer.py`
- `app/paste_router.py`
- `app/v04d_structuring.py`
- `app/v04db_prestructure.py`
- `app/v04e_entity_resolution.py`
- `app/services/manual_ingestion.py`
- `app/services/signal_service.py`
- `scripts/test_entity_analyzer.py`
- `scripts/test_paste_analyzer.py`
- `scripts/verify_manual_ingestion.py`

## Verification

- Test representative single-subject and multi-subject samples.
- Verify duplicate content does not create duplicate review tasks.
- Verify uncertain content stays in candidate/review state.
- Verify canonical tables are not overwritten without manual approval.
- Run the closest script, such as:

```bat
python scripts\test_entity_analyzer.py
python scripts\test_paste_analyzer.py
python scripts\verify_manual_ingestion.py
verify_all_windows.bat
```

## Completion Reply

Report page type, extracted candidate types, evidence policy, confidence/review routing, scripts run and any unresolved ambiguity.

## Failure Handling

If evidence is missing or the page structure is ambiguous, do not fabricate facts. Preserve raw content, mark uncertainty and route to manual review.
