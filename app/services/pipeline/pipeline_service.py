from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from app.services.collection_service import create_job as create_collection_job
from app.services.collection_service import process_job as process_collection_job
from app.services.processing import apply_candidate, create_processing_job, process_job as process_processing_job
from app.services.reports import create_report_job, generate_report
from app.services.signals import generate_signals

from .pipeline_common import StageTimer, db_connection, dumps, ensure_schema, next_no, now, stage_finish, stage_start
from .pipeline_state_service import get_pipeline_run

ACTIVE_STATUSES = {"pending", "collecting", "collected", "processing", "waiting_review", "applying", "signaling", "reporting"}


def _scope_for_source(conn, source_id: int, pilot: bool) -> dict[str, Any]:
    source = conn.execute("SELECT id, name, url, collection_source_type, collection_mode, max_links, crawl_detail_pages FROM v04g_monitoring_sources WHERE id=?", (source_id,)).fetchone()
    if not source:
        raise ValueError("source_not_found")
    max_items = min(int(source["max_links"] or 20), 20) if pilot else int(source["max_links"] or 20)
    return {"source_id": source_id, "source_name": source["name"], "url": source["url"], "source_type": source["collection_source_type"], "collection_mode": source["collection_mode"], "max_items": max_items, "crawl_detail_pages": bool(source["crawl_detail_pages"]), "pilot": pilot}


def create_pipeline_run(source_id: int, *, created_by: str = "", pilot: bool = True, dry_run: bool = True, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    ts = now()
    with db_connection(db_path) as conn:
        active = conn.execute("SELECT * FROM v05i_pipeline_runs WHERE source_id=? AND status IN ('pending','collecting','collected','processing','waiting_review','applying','signaling','reporting')", (source_id,)).fetchone()
        if active:
            raise RuntimeError("active_pipeline_exists")
        scope = _scope_for_source(conn, source_id, pilot)
        cur = conn.execute(
            """
            INSERT INTO v05i_pipeline_runs(pipeline_run_no, source_id, status, current_stage, pilot_mode, dry_run, actual_scope_json, created_by, created_at, updated_at)
            VALUES (?, ?, 'pending', 'pending', ?, ?, ?, ?, ?, ?)
            """,
            (next_no(conn, "PIPE"), source_id, int(pilot), int(dry_run), dumps(scope), created_by or None, ts, ts),
        )
        return dict(conn.execute("SELECT * FROM v05i_pipeline_runs WHERE id=?", (cur.lastrowid,)).fetchone())


def run_pipeline_once(*, source_id: int | None = None, pipeline_run_id: int | None = None, created_by: str = "worker", pilot: bool = True, dry_run: bool = True, db_path: str | Path | None = None) -> dict[str, Any]:
    if pipeline_run_id:
        run = get_pipeline_run(pipeline_run_id, db_path=db_path)
        if not run:
            raise ValueError("pipeline_run_not_found")
    elif source_id:
        run = create_pipeline_run(source_id, created_by=created_by, pilot=pilot, dry_run=dry_run, db_path=db_path)
    else:
        run = _next_pending_run(db_path=db_path)
        if not run:
            return {"processed": 0, "result": None}
    result = continue_pipeline(int(run["id"]), actor=created_by, db_path=db_path)
    return {"processed": 1, "result": result}


def _next_pending_run(db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05i_pipeline_runs WHERE status IN ('pending','collected','applying','signaling','reporting') ORDER BY id LIMIT 1").fetchone()
        return dict(row) if row else None


def continue_pipeline(run_id: int, *, actor: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    run = get_pipeline_run(run_id, db_path=db_path)
    if not run:
        raise ValueError("pipeline_run_not_found")
    if run["status"] in {"failed", "cancelled", "completed", "partial"}:
        return run
    try:
        if run["current_stage"] in {"pending", "collecting"}:
            _run_collection(run_id, actor=actor, db_path=db_path)
        run = get_pipeline_run(run_id, db_path=db_path)
        if run and run["current_stage"] in {"collected", "processing"}:
            _run_processing(run_id, actor=actor, db_path=db_path)
        run = get_pipeline_run(run_id, db_path=db_path)
        if run and run["status"] == "waiting_review":
            return run
        if run and run["current_stage"] in {"applying", "signaling", "reporting"}:
            _run_apply_signal_report(run_id, actor=actor, db_path=db_path)
        return get_pipeline_run(run_id, db_path=db_path) or {}
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            time.sleep(0.2)
            try:
                return continue_pipeline(run_id, actor=actor, db_path=db_path)
            except sqlite3.OperationalError:
                _fail(run_id, "sqlite_locked", "SQLite lock retry exhausted", db_path=db_path)
                return get_pipeline_run(run_id, db_path=db_path) or {}
        _fail(run_id, exc.__class__.__name__, str(exc), db_path=db_path)
        return get_pipeline_run(run_id, db_path=db_path) or {}
    except Exception as exc:
        _fail(run_id, exc.__class__.__name__, str(exc), db_path=db_path)
        return get_pipeline_run(run_id, db_path=db_path) or {}


def _run_collection(run_id: int, *, actor: str, db_path: str | Path | None) -> None:
    timer = StageTimer()
    with db_connection(db_path) as conn:
        run = conn.execute("SELECT * FROM v05i_pipeline_runs WHERE id=?", (run_id,)).fetchone()
        conn.execute("UPDATE v05i_pipeline_runs SET status='collecting', current_stage='collecting', started_at=COALESCE(started_at, ?), updated_at=? WHERE id=?", (now(), now(), run_id))
        stage_start(conn, run_id, "collecting")
    job = create_collection_job(int(run["source_id"]), trigger_type="pipeline", operator=actor or "pipeline", db_path=db_path)
    result = process_collection_job(int(job["id"]), db_path=db_path)
    with db_connection(db_path) as conn:
        item_count = conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE monitoring_run_id=?", (job["id"],)).fetchone()[0]
        status = "collected" if result.get("status") in {"success", "partial", "unchanged"} else "failed"
        stage_finish(conn, run_id, "collecting", "success" if status == "collected" else "failed", related_table="v04g_monitoring_runs", related_id=int(job["id"]), count_value=int(item_count), duration_ms=timer.duration_ms, metadata=result)
        conn.execute(
            """
            UPDATE v05i_pipeline_runs
            SET collection_job_id=?, collection_item_count=?, status=?, current_stage=?, failed_stage=CASE WHEN ?='failed' THEN 'collecting' ELSE failed_stage END,
                error_code=CASE WHEN ?='failed' THEN ? ELSE NULL END, error_summary=CASE WHEN ?='failed' THEN ? ELSE NULL END, updated_at=?
            WHERE id=?
            """,
            (job["id"], item_count, status, "collected" if status == "collected" else "failed", status, status, result.get("error_type"), status, result.get("error", ""), now(), run_id),
        )


def _run_processing(run_id: int, *, actor: str, db_path: str | Path | None) -> None:
    timer = StageTimer()
    with db_connection(db_path) as conn:
        run = conn.execute("SELECT * FROM v05i_pipeline_runs WHERE id=?", (run_id,)).fetchone()
        conn.execute("UPDATE v05i_pipeline_runs SET status='processing', current_stage='processing', updated_at=? WHERE id=?", (now(), run_id))
        stage_start(conn, run_id, "processing")
        items = [dict(r) for r in conn.execute("SELECT id FROM v05f_collection_items WHERE monitoring_run_id=? AND processing_status IN ('queued','failed','needs_review','new') ORDER BY id LIMIT 20", (run["collection_job_id"],)).fetchall()]
    job_count = 0
    for item in items:
        try:
            job = create_processing_job(item_id=int(item["id"]), trigger_type="pipeline", operator=actor or "pipeline", queued_only=False, db_path=db_path)
            process_processing_job(int(job["id"]), db_path=db_path)
            job_count += 1
        except RuntimeError:
            continue
    with db_connection(db_path) as conn:
        candidate_count = conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE processing_job_id IN (SELECT id FROM v05g_processing_jobs WHERE collection_item_id IN (SELECT id FROM v05f_collection_items WHERE monitoring_run_id=?))", (run["collection_job_id"],)).fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE review_status IN ('pending','needs_review') AND processing_job_id IN (SELECT id FROM v05g_processing_jobs WHERE collection_item_id IN (SELECT id FROM v05f_collection_items WHERE monitoring_run_id=?))", (run["collection_job_id"],)).fetchone()[0]
        next_status = "waiting_review" if pending else "applying"
        stage_finish(conn, run_id, "processing", "waiting_review" if pending else "success", count_value=int(candidate_count), duration_ms=timer.duration_ms, metadata={"processing_jobs": job_count, "pending_candidates": pending})
        conn.execute("UPDATE v05i_pipeline_runs SET processing_job_count=?, candidate_count=?, status=?, current_stage=?, updated_at=? WHERE id=?", (job_count, candidate_count, next_status, next_status, now(), run_id))


def _run_apply_signal_report(run_id: int, *, actor: str, db_path: str | Path | None) -> None:
    with db_connection(db_path) as conn:
        run = conn.execute("SELECT * FROM v05i_pipeline_runs WHERE id=?", (run_id,)).fetchone()
        collection_job_id = run["collection_job_id"]
        pending = conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE review_status IN ('pending','needs_review') AND processing_job_id IN (SELECT id FROM v05g_processing_jobs WHERE collection_item_id IN (SELECT id FROM v05f_collection_items WHERE monitoring_run_id=?))", (collection_job_id,)).fetchone()[0]
        if pending:
            conn.execute("UPDATE v05i_pipeline_runs SET status='waiting_review', current_stage='waiting_review', updated_at=? WHERE id=?", (now(), run_id))
            return
        approved = [dict(r) for r in conn.execute("SELECT id FROM v05g_extraction_candidates WHERE review_status='approved' AND processing_job_id IN (SELECT id FROM v05g_processing_jobs WHERE collection_item_id IN (SELECT id FROM v05f_collection_items WHERE monitoring_run_id=?))", (collection_job_id,)).fetchall()]
    timer = StageTimer()
    applied = 0
    for candidate in approved:
        try:
            log = apply_candidate(int(candidate["id"]), actor=actor or "pipeline", db_path=db_path)
            if log.get("result") == "success":
                applied += 1
        except Exception:
            continue
    with db_connection(db_path) as conn:
        stage_start(conn, run_id, "applying")
        stage_finish(conn, run_id, "applying", "success", count_value=applied, duration_ms=timer.duration_ms, metadata={"approved": len(approved)})
        conn.execute("UPDATE v05i_pipeline_runs SET status='signaling', current_stage='signaling', approved_candidate_count=?, applied_count=?, updated_at=? WHERE id=?", (len(approved), applied, now(), run_id))
    timer = StageTimer()
    try:
        signals = generate_signals(limit=100, dry_run=bool(run["dry_run"]), db_path=db_path)
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        signals = {"created": 0, "candidates": 0, "skipped": 0, "dry_run": bool(run["dry_run"]), "warning": str(exc)}
    with db_connection(db_path) as conn:
        stage_start(conn, run_id, "signaling")
        stage_finish(conn, run_id, "signaling", "success", count_value=int(signals.get("created") or 0), duration_ms=timer.duration_ms, metadata=signals)
        conn.execute("UPDATE v05i_pipeline_runs SET status='reporting', current_stage='reporting', signal_count=?, updated_at=? WHERE id=?", (int(signals.get("created") or 0), now(), run_id))
    timer = StageTimer()
    report_job_id = None
    report_status = "skipped"
    report_meta: dict[str, Any] = {"reason": "dry_run"}
    if not bool(run["dry_run"]):
        report_job = create_report_job(report_type="daily", generated_by=actor or "pipeline", db_path=db_path)
        report = generate_report(int(report_job["id"]), db_path=db_path)
        report_job_id = int(report_job["id"])
        report_status = "success"
        report_meta = {"report_id": report["id"], "report_no": report["report_no"]}
    with db_connection(db_path) as conn:
        stage_start(conn, run_id, "reporting")
        stage_finish(conn, run_id, "reporting", report_status, related_table="v05h_report_jobs" if report_job_id else "", related_id=report_job_id, count_value=1 if report_job_id else 0, duration_ms=timer.duration_ms, metadata=report_meta)
        final_status = "completed" if not run["dry_run"] else "partial"
        conn.execute("UPDATE v05i_pipeline_runs SET status=?, current_stage='completed', report_job_id=?, finished_at=?, updated_at=? WHERE id=?", (final_status, report_job_id, now(), now(), run_id))


def retry_pipeline(run_id: int, *, actor: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05i_pipeline_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise ValueError("pipeline_run_not_found")
        if row["status"] not in {"failed", "partial", "waiting_review"}:
            raise RuntimeError("pipeline_not_retryable")
        stage = row["failed_stage"] or row["current_stage"] or "pending"
        resume_stage = "applying" if stage == "waiting_review" else stage
        conn.execute("UPDATE v05i_pipeline_runs SET status=?, current_stage=?, failed_stage=NULL, error_code=NULL, error_summary=NULL, retry_count=retry_count+1, updated_at=? WHERE id=?", (resume_stage, resume_stage, now(), run_id))
    return continue_pipeline(run_id, actor=actor, db_path=db_path)


def cancel_pipeline(run_id: int, *, actor: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05i_pipeline_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise ValueError("pipeline_run_not_found")
        if row["status"] in {"completed", "cancelled"}:
            return dict(row)
        conn.execute("UPDATE v05i_pipeline_runs SET status='cancelled', current_stage='cancelled', finished_at=?, updated_at=? WHERE id=?", (now(), now(), run_id))
        return dict(conn.execute("SELECT * FROM v05i_pipeline_runs WHERE id=?", (run_id,)).fetchone())


def _fail(run_id: int, code: str, summary: str, db_path: str | Path | None) -> None:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT current_stage FROM v05i_pipeline_runs WHERE id=?", (run_id,)).fetchone()
        stage = row["current_stage"] if row else "unknown"
        conn.execute("UPDATE v05i_pipeline_runs SET status='failed', failed_stage=?, error_code=?, error_summary=?, finished_at=?, updated_at=? WHERE id=?", (stage, code[:80], summary[:800], now(), now(), run_id))
