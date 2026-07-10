from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.collection_service import create_job as create_collection_job
from app.services.collection_service import ensure_schema as ensure_collection_schema
from app.services.collection_service import process_job as process_collection_job
from app.services.processing import create_processing_job, process_job as process_processing_job
from app.services.processing.processing_job_service import review_candidate
from app.services.reports import create_report_job, generate_report
from app.services.signals import generate_signals
from app.services.signal_service import ensure_schema as ensure_signal_schema
from app.services.signal_service import _next_no
from app.v04c_review import db_connection


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None) -> None:
    ensure_collection_schema(db_path)
    ensure_signal_schema(db_path)


def schedule_due_collection_jobs(*, limit: int = 20, db_path: str | Path | None = None, operator: str = "scheduler") -> dict[str, Any]:
    """Create collection jobs for enabled sources that are due to be checked."""
    ensure_schema(db_path)
    created: list[dict[str, Any]] = []
    skipped = 0
    threshold = (datetime.now().replace(microsecond=0)).isoformat()
    with db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM v04g_monitoring_sources
            WHERE is_enabled=1 AND deactivated_at IS NULL
              AND COALESCE(auto_paused,0)=0
              AND check_frequency<>'manual'
              AND (last_checked_at IS NULL OR last_checked_at<?)
            ORDER BY COALESCE(last_checked_at,''), id
            LIMIT ?
            """,
            (threshold, max(1, min(int(limit or 20), 200))),
        ).fetchall()
    for row in rows:
        try:
            created.append(create_collection_job(int(row["id"]), trigger_type="scheduler", operator=operator, db_path=db_path))
        except RuntimeError:
            skipped += 1
    return {"created": len(created), "skipped": skipped, "jobs": created}


def run_collection_worker_with_cascade(
    *,
    once: bool = True,
    limit: int = 20,
    db_path: str | Path | None = None,
    operator: str = "worker",
) -> dict[str, Any]:
    """Claim pending collection jobs, then immediately enqueue processing for new items."""
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        jobs = [dict(r) for r in conn.execute(
            """
            SELECT id FROM v04g_monitoring_runs
            WHERE status='pending' AND COALESCE(job_type,'collection')='collection'
            ORDER BY COALESCE(scheduled_at, created_at), id
            LIMIT ?
            """,
            (max(1, min(int(limit or 20), 200)),),
        ).fetchall()]
    results: list[dict[str, Any]] = []
    processing_jobs = 0
    for job in jobs:
        result = process_collection_job(int(job["id"]), db_path=db_path)
        created = create_processing_jobs_for_collection_run(int(job["id"]), db_path=db_path, operator=operator)
        processing_jobs += int(created["created"])
        results.append({**result, "processing_jobs_created": created["created"]})
        if once:
            break
    return {"processed": len(results), "processing_jobs_created": processing_jobs, "results": results}


def create_processing_jobs_for_collection_run(run_id: int, *, db_path: str | Path | None = None, operator: str = "worker") -> dict[str, Any]:
    ensure_schema(db_path)
    created: list[dict[str, Any]] = []
    skipped = 0
    with db_connection(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT id FROM v05f_collection_items
            WHERE monitoring_run_id=? AND processing_status='queued'
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()]
    for row in rows:
        try:
            created.append(create_processing_job(item_id=int(row["id"]), trigger_type="collection_worker", operator=operator, db_path=db_path))
        except RuntimeError:
            skipped += 1
    return {"created": len(created), "skipped": skipped, "jobs": created}


def run_processing_worker_once(*, limit: int = 20, db_path: str | Path | None = None, operator: str = "worker") -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT id FROM v05g_processing_jobs
            WHERE status='pending'
            ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, id
            LIMIT ?
            """,
            (max(1, min(int(limit or 20), 200)),),
        ).fetchall()]
    results = [process_processing_job(int(row["id"]), db_path=db_path) for row in rows]
    return {"processed": len(results), "results": results}


def approve_candidate_to_formal_store(candidate_id: int, *, actor: str = "reviewer", note: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    review = review_candidate(candidate_id, decision="approved", actor=actor, note=note, db_path=db_path)
    applied = apply_candidate_to_formal_store(candidate_id, actor=actor, db_path=db_path)
    return {"review": review, "applied": applied}


def apply_candidate_to_formal_store(candidate_id: int, *, actor: str = "system", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("candidate_not_found")
        candidate = dict(row)
        if candidate["review_status"] not in {"approved", "applied"}:
            raise ValueError("candidate_not_approved")
        if candidate["candidate_type"] == "event":
            return _apply_event_candidate(conn, candidate, actor)
        if candidate["candidate_type"] in {"organization", "person", "project"}:
            return _apply_subject_candidate(conn, candidate, actor)
        return {"result": "skipped", "reason": "candidate_type_not_formal_store", "candidate_type": candidate["candidate_type"]}


def _apply_subject_candidate(conn, candidate: dict[str, Any], actor: str) -> dict[str, Any]:
    subject_type = str(candidate.get("subject_type") or candidate.get("candidate_type") or "")
    label = (candidate.get("subject_label") or candidate.get("normalized_value") or "").strip()
    if not label:
        return {"result": "skipped", "reason": "empty_subject_label"}
    config = {
        "organization": ("organizations", "standard_name", "ORG"),
        "person": ("people", "name", "PER"),
        "project": ("projects", "name", "PRJ"),
    }.get(subject_type)
    if not config:
        return {"result": "skipped", "reason": "unsupported_subject_type"}
    table, name_field, prefix = config
    existing = None
    if candidate.get("matched_subject_id"):
        existing = conn.execute(f"SELECT * FROM {table} WHERE external_id=?", (candidate["matched_subject_id"],)).fetchone()
    if not existing:
        existing = conn.execute(f"SELECT * FROM {table} WHERE {name_field}=? ORDER BY id LIMIT 1", (label,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE v05g_extraction_candidates SET subject_id=?, matched_subject_id=?, matched_subject_label=?, review_status='applied', applied_at=?, updated_at=? WHERE id=?",
            (existing["external_id"], existing["external_id"], label, now(), now(), candidate["id"]),
        )
        return {"result": "success", "created": False, "subject_type": subject_type, "subject_id": existing["external_id"]}
    external_id = _next_no(conn, prefix)
    ts = now()
    if subject_type == "organization":
        conn.execute(
            """
            INSERT INTO organizations(external_id,standard_name,visibility,verification_status,source_url,source_type,source_title,source_text,manually_confirmed,created_at)
            VALUES (?,?,'内部','已确认',?,?,?, ?,1,?)
            """,
            (external_id, label, candidate.get("source_url"), "processing_candidate", candidate.get("source_title"), candidate.get("evidence_excerpt"), ts),
        )
    elif subject_type == "person":
        conn.execute(
            """
            INSERT INTO people(external_id,name,visibility,verification_status,source_url,source_type,source_title,source_text,manually_confirmed,created_at)
            VALUES (?,?,'内部','已确认',?,?,?, ?,1,?)
            """,
            (external_id, label, candidate.get("source_url"), "processing_candidate", candidate.get("source_title"), candidate.get("evidence_excerpt"), ts),
        )
    else:
        conn.execute(
            """
            INSERT INTO projects(external_id,name,visibility,status,source_url,source_type,source_title,source_text,manually_confirmed,created_at)
            VALUES (?,?,'内部','已确认',?,?,?, ?,1,?)
            """,
            (external_id, label, candidate.get("source_url"), "processing_candidate", candidate.get("source_title"), candidate.get("evidence_excerpt"), ts),
        )
    conn.execute(
        "UPDATE v05g_extraction_candidates SET subject_id=?, matched_subject_id=?, matched_subject_label=?, review_status='applied', applied_at=?, updated_at=? WHERE id=?",
        (external_id, external_id, label, ts, ts, candidate["id"]),
    )
    return {"result": "success", "created": True, "subject_type": subject_type, "subject_id": external_id}


def _apply_event_candidate(conn, candidate: dict[str, Any], actor: str) -> dict[str, Any]:
    payload = _loads(candidate.get("payload_json"), {})
    subject_id = candidate.get("subject_id") or candidate.get("matched_subject_id")
    subject_label = candidate.get("matched_subject_label") or candidate.get("subject_label") or ""
    if not subject_id and candidate.get("collection_item_id"):
        item = conn.execute("SELECT subject_type_candidate, subject_id_candidate FROM v05f_collection_items WHERE id=?", (candidate["collection_item_id"],)).fetchone()
        if item and item["subject_type_candidate"] == "organization" and item["subject_id_candidate"]:
            subject_id = item["subject_id_candidate"]
    org_row = conn.execute("SELECT * FROM organizations WHERE external_id=? ORDER BY id LIMIT 1", (subject_id,)).fetchone() if subject_id else None
    if org_row and not subject_label:
        subject_label = org_row["standard_name"]
    summary = candidate.get("evidence_excerpt") or candidate.get("raw_value") or candidate.get("normalized_value") or ""
    event_type = payload.get("event_type") or candidate.get("normalized_value") or "industry_event"
    title = _event_title(event_type, subject_label, summary)
    existing = conn.execute(
        """
        SELECT * FROM events
        WHERE COALESCE(related_entity,'')=COALESCE(?, '')
          AND COALESCE(event_type,'')=COALESCE(?, '')
          AND COALESCE(source_url,'')=COALESCE(?, '')
          AND COALESCE(fact_summary,'')=COALESCE(?, '')
        ORDER BY id LIMIT 1
        """,
        (subject_id, event_type, candidate.get("source_url") or "", summary[:1000]),
    ).fetchone()
    ts = now()
    if existing:
        conn.execute("UPDATE v05g_extraction_candidates SET review_status='applied', applied_at=?, updated_at=? WHERE id=?", (ts, ts, candidate["id"]))
        return {"result": "success", "created": False, "event_id": existing["id"], "external_id": existing["external_id"]}
    external_id = _next_no(conn, "EVT")
    cur = conn.execute(
        """
        INSERT INTO events(
            external_id,event_date,name,event_type,related_entity,related_organization_id,fact_summary,
            system_use,visibility,verification_status,source_url,source_type,source_title,source_text,
            manually_confirmed,created_at
        ) VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, '??', '???', ?, 'processing_candidate', ?, ?, 1, ?)
        """,
        (
            external_id,
            title[:400],
            event_type,
            subject_id,
            org_row["id"] if org_row else None,
            summary[:4000],
            json.dumps({"source_snapshot_id": candidate.get("snapshot_id"), "source_candidate_id": candidate.get("id")}, ensure_ascii=False),
            candidate.get("source_url"),
            candidate.get("source_title"),
            summary[:4000],
            ts,
        ),
    )
    conn.execute("UPDATE v05g_extraction_candidates SET review_status='applied', applied_at=?, updated_at=? WHERE id=?", (ts, ts, candidate["id"]))
    return {"result": "success", "created": True, "event_id": int(cur.lastrowid), "external_id": external_id}


def _event_title(event_type: str, subject_label: str, summary: str) -> str:
    labels = {
        "financing": "????",
        "approval": "??????",
        "cooperation": "????",
        "strategic_cooperation": "????",
        "clinical": "????",
        "clinical_progress": "????",
        "recruitment": "????",
    }
    prefix = labels.get(event_type, "????")
    if subject_label:
        return f"{subject_label}{prefix}"
    return (summary[:80] or prefix).strip()


def generate_daily_and_weekly_reports(*, db_path: str | Path | None = None, actor: str = "system") -> dict[str, Any]:
    generated: list[dict[str, Any]] = []
    for report_type in ("daily", "weekly"):
        job = create_report_job(report_type=report_type, generated_by=actor, db_path=db_path)
        report = generate_report(int(job["id"]), db_path=db_path)
        generated.append({"report_type": report_type, "job_id": job["id"], "report_id": report["id"], "status": report["status"]})
    return {"generated": len(generated), "reports": generated}


def convert_signal_to_investment_lead(signal_id: int, *, owner: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    from app.v04f_operations import get_or_create_lead

    with db_connection(db_path) as conn:
        signal = conn.execute("SELECT * FROM v05e_industry_signals WHERE id=?", (signal_id,)).fetchone()
        if not signal:
            return {"created": False, "reason": "signal_not_found"}
        if signal["subject_type"] not in {"organization", "project"} or not signal["subject_id"]:
            return {"created": False, "reason": "signal_without_convertible_subject"}
    lead = get_or_create_lead(signal["subject_type"], signal["subject_id"], owner=owner, db_path=db_path)
    with db_connection(db_path) as conn:
        conn.execute("UPDATE v05e_industry_signals SET status='converted', is_read=1, updated_at=? WHERE id=?", (now(), signal_id))
    return {"created": True, "lead_id": lead["id"], "lead_no": lead["lead_no"]}


def report_snapshot_trace(report_id: int, *, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(db_path) as conn:
        report = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            return []
        citations = _loads(report["citations_json"], [])
        traces: list[dict[str, Any]] = []
        for item in citations:
            if item.get("type") == "snapshot":
                traces.append(dict(item))
            if item.get("type") == "signal":
                evidence = conn.execute("SELECT * FROM v05h_signal_evidence WHERE signal_id=?", (item.get("id"),)).fetchall()
                for ev in evidence:
                    if ev["snapshot_id"]:
                        traces.append({"type": "snapshot", "id": str(ev["snapshot_id"]), "via": item.get("ref")})
        return traces


def _loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return default
