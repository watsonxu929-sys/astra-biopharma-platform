from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models_platform import IntelligenceItem
from app.services.collection_service import (
    create_collection_source,
    create_job as create_collection_job,
    process_job as process_collection_job,
)
from app.services.intelligence_flow_service import create_processing_jobs_for_collection_run
from app.services.processing import process_job as process_processing_job
from app.v04c_review import db_connection, default_db_path


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _path(db_path: str | Path | None = None) -> Path:
    return Path(db_path) if db_path else default_db_path()


def pipeline_counts(db_path: str | Path | None = None) -> dict[str, int]:
    path = _path(db_path)
    with db_connection(path) as conn:
        def count(sql: str) -> int:
            try:
                return int(conn.execute(sql).fetchone()[0] or 0)
            except sqlite3.Error:
                return 0
        return {
            "sources": count("SELECT COUNT(*) FROM v04g_monitoring_sources WHERE deactivated_at IS NULL"),
            "enabled_sources": count("SELECT COUNT(*) FROM v04g_monitoring_sources WHERE is_enabled=1 AND deactivated_at IS NULL"),
            "collection_jobs": count("SELECT COUNT(*) FROM v04g_monitoring_runs WHERE COALESCE(job_type,'collection')='collection'"),
            "raw_items": count("SELECT COUNT(*) FROM v05f_collection_items"),
            "queued_items": count("SELECT COUNT(*) FROM v05f_collection_items WHERE processing_status='queued'"),
            "processing_jobs": count("SELECT COUNT(*) FROM v05g_processing_jobs"),
            "candidates": count("SELECT COUNT(*) FROM v05g_extraction_candidates"),
            "pending_candidates": count("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE review_status IN ('pending','needs_review')"),
            "published_items": count("SELECT COUNT(*) FROM v06_intelligence_items WHERE status='published'"),
            "signals": count("SELECT COUNT(*) FROM v05e_industry_signals"),
            "reports": count("SELECT COUNT(*) FROM v05h_generated_reports"),
        }


def latest_pipeline_records(db_path: str | Path | None = None, limit: int = 8) -> dict[str, list[dict[str, Any]]]:
    path = _path(db_path)
    with db_connection(path) as conn:
        def rows(sql: str) -> list[dict[str, Any]]:
            try:
                return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
            except sqlite3.Error:
                return []
        return {
            "sources": rows("SELECT id,name,url,is_enabled,updated_at FROM v04g_monitoring_sources ORDER BY id DESC LIMIT ?"),
            "items": rows("SELECT id,item_no,title,processing_status,dedup_status,created_at FROM v05f_collection_items ORDER BY id DESC LIMIT ?"),
            "jobs": rows("SELECT id,job_no,status,collection_item_id,candidate_count,created_at FROM v05g_processing_jobs ORDER BY id DESC LIMIT ?"),
            "candidates": rows("SELECT id,candidate_no,candidate_type,subject_label,normalized_value,review_status,created_at FROM v05g_extraction_candidates ORDER BY id DESC LIMIT ?"),
        }


def publish_collection_item(db: Session, collection_item_id: int, *, actor_user_id: int | None = None, status: str = "published") -> IntelligenceItem:
    item_row: dict[str, Any] | None = None
    snapshot_row: dict[str, Any] | None = None
    with db_connection(default_db_path()) as conn:
        item = conn.execute("SELECT * FROM v05f_collection_items WHERE id=?", (int(collection_item_id),)).fetchone()
        if item:
            item_row = dict(item)
            if item["snapshot_id"]:
                snap = conn.execute("SELECT * FROM v04g_source_snapshots WHERE id=?", (int(item["snapshot_id"]),)).fetchone()
                snapshot_row = dict(snap) if snap else None
    if not item_row:
        raise ValueError("collection_item_not_found")
    source_url = item_row.get("normalized_url") or item_row.get("original_url") or ""
    existing = db.scalar(select(IntelligenceItem).where(IntelligenceItem.source_name == "v05f_collection_items", IntelligenceItem.source_url == source_url))
    if existing:
        return existing
    text = (snapshot_row or {}).get("cleaned_text") or (snapshot_row or {}).get("raw_content") or item_row.get("title") or ""
    title = item_row.get("title") or (snapshot_row or {}).get("page_title") or f"Collection item #{collection_item_id}"
    published_at = datetime.now() if status == "published" else None
    record = IntelligenceItem(
        title=title[:400],
        summary=(text or title)[:300],
        content=text,
        intel_type=(item_row.get("page_structure") or "article")[:50],
        source_name="v05f_collection_items",
        source_url=source_url,
        published_at=published_at,
        visibility="public",
        status=status,
        credibility=3,
        importance=2,
        created_by=actor_user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def run_inline_intelligence_flow(*, html: str, title: str = "v06e recovery source", db_path: str | Path | None = None, operator: str = "v06e_verify") -> dict[str, Any]:
    path = _path(db_path)
    source = create_collection_source(
        name=title,
        source_type="webpage",
        url="inline:" + html,
        collection_mode="http",
        owner=operator,
        compliance_note="local inline verification source",
        db_path=path,
    )
    job = create_collection_job(int(source["id"]), trigger_type="manual", operator=operator, db_path=path, force=True)
    collection = process_collection_job(int(job["id"]), db_path=path)
    processing_created = create_processing_jobs_for_collection_run(int(job["id"]), db_path=path, operator=operator)
    processed_jobs = []
    for proc in processing_created.get("jobs", []):
        processed_jobs.append(process_processing_job(int(proc["id"]), db_path=path))
    with db_connection(path) as conn:
        item = conn.execute("SELECT * FROM v05f_collection_items WHERE monitoring_run_id=? ORDER BY id DESC LIMIT 1", (int(job["id"]),)).fetchone()
        candidates = conn.execute(
            "SELECT COUNT(*) FROM v05g_extraction_candidates WHERE collection_item_id=?",
            (int(item["id"]),) if item else (0,),
        ).fetchone()[0]
    return {
        "source": source,
        "collection_job": job,
        "collection_result": collection,
        "processing_jobs_created": processing_created,
        "processed_jobs": processed_jobs,
        "collection_item_id": int(item["id"]) if item else None,
        "candidate_count": int(candidates or 0),
    }
