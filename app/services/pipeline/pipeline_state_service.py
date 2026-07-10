from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.api_common import Pagination, normalize_page, paginated

from .pipeline_common import db_connection, ensure_schema, loads


def list_pipeline_runs(*, page: int = 1, page_size: int = 20, status: str = "", source_id: int | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    page, page_size = normalize_page(page, page_size)
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("p.status=?")
        params.append(status)
    if source_id:
        clauses.append("p.source_id=?")
        params.append(source_id)
    where = " AND ".join(clauses)
    with db_connection(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM v05i_pipeline_runs p WHERE {where}", params).fetchone()[0]
        rows = [dict(r) for r in conn.execute(
            f"""
            SELECT p.*, s.name AS source_name, s.source_no, s.url AS source_url
            FROM v05i_pipeline_runs p
            LEFT JOIN v04g_monitoring_sources s ON s.id=p.source_id
            WHERE {where}
            ORDER BY p.id DESC LIMIT ? OFFSET ?
            """,
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()]
    for row in rows:
        row["actual_scope"] = loads(row.get("actual_scope_json"), {})
        row.pop("actual_scope_json", None)
    return paginated(rows, Pagination(page, page_size, int(total)))


def get_pipeline_run(run_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT p.*, s.name AS source_name, s.source_no, s.url AS source_url
            FROM v05i_pipeline_runs p
            LEFT JOIN v04g_monitoring_sources s ON s.id=p.source_id
            WHERE p.id=?
            """,
            (run_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["actual_scope"] = loads(data.get("actual_scope_json"), {})
    data.pop("actual_scope_json", None)
    return data


def pipeline_detail(run_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    run = get_pipeline_run(run_id, db_path=db_path)
    if not run:
        return None
    with db_connection(db_path) as conn:
        stages = [dict(r) for r in conn.execute("SELECT * FROM v05i_pipeline_stage_runs WHERE pipeline_run_id=? ORDER BY id", (run_id,)).fetchall()]
        collection_items = [dict(r) for r in conn.execute("SELECT * FROM v05f_collection_items WHERE monitoring_run_id=? ORDER BY id", (run.get("collection_job_id"),)).fetchall()] if run.get("collection_job_id") else []
        processing_jobs = [dict(r) for r in conn.execute("SELECT * FROM v05g_processing_jobs WHERE collection_item_id IN (SELECT id FROM v05f_collection_items WHERE monitoring_run_id=?) ORDER BY id", (run.get("collection_job_id"),)).fetchall()] if run.get("collection_job_id") else []
        candidates = [dict(r) for r in conn.execute("SELECT * FROM v05g_extraction_candidates WHERE processing_job_id IN (SELECT id FROM v05g_processing_jobs WHERE collection_item_id IN (SELECT id FROM v05f_collection_items WHERE monitoring_run_id=?)) ORDER BY id", (run.get("collection_job_id"),)).fetchall()] if run.get("collection_job_id") else []
        signals = [dict(r) for r in conn.execute("SELECT * FROM v05e_industry_signals WHERE discovered_at>=COALESCE(?, discovered_at) ORDER BY id DESC LIMIT 50", (run.get("started_at"),)).fetchall()]
        reports = [dict(r) for r in conn.execute("SELECT * FROM v05h_generated_reports WHERE report_job_id=? ORDER BY id DESC", (run.get("report_job_id"),)).fetchall()] if run.get("report_job_id") else []
        samples = [dict(r) for r in conn.execute("SELECT * FROM v05i_pipeline_quality_samples WHERE pipeline_run_id=? ORDER BY id DESC", (run_id,)).fetchall()]
    return {"run": run, "stages": stages, "collection_items": collection_items, "processing_jobs": processing_jobs, "candidates": candidates, "signals": signals, "reports": reports, "samples": samples}


def dashboard(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        counts = {
            "today_runs": conn.execute("SELECT COUNT(*) FROM v05i_pipeline_runs WHERE date(created_at)=date('now','localtime')").fetchone()[0],
            "completed": conn.execute("SELECT COUNT(*) FROM v05i_pipeline_runs WHERE status='completed'").fetchone()[0],
            "waiting_review": conn.execute("SELECT COUNT(*) FROM v05i_pipeline_runs WHERE status='waiting_review'").fetchone()[0],
            "partial": conn.execute("SELECT COUNT(*) FROM v05i_pipeline_runs WHERE status='partial'").fetchone()[0],
            "failed": conn.execute("SELECT COUNT(*) FROM v05i_pipeline_runs WHERE status='failed'").fetchone()[0],
        }
        latest = [dict(r) for r in conn.execute(
            """
            SELECT p.*, s.name AS source_name
            FROM v05i_pipeline_runs p LEFT JOIN v04g_monitoring_sources s ON s.id=p.source_id
            ORDER BY p.id DESC LIMIT 10
            """
        ).fetchall()]
        stage_rows = [dict(r) for r in conn.execute(
            """
            SELECT stage_name,
                   AVG(CASE WHEN duration_ms>0 THEN duration_ms END) AS avg_duration_ms,
                   SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success_count,
                   COUNT(*) AS total_count
            FROM v05i_pipeline_stage_runs GROUP BY stage_name ORDER BY stage_name
            """
        ).fetchall()]
    return {"counts": counts, "latest": latest, "stage_metrics": stage_rows}
