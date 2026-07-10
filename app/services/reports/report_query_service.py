from __future__ import annotations

from pathlib import Path
from typing import Any

from app.v04c_review import db_connection
from scripts.migrate_v05h import migrate as migrate_v05h


def ensure_schema(db_path: str | Path | None = None) -> None:
    migrate_v05h(Path(db_path) if db_path else None, backup=False) if db_path else migrate_v05h(backup=False)


def report_data(report_type: str, period_start: str = "", period_end: str = "", filters: dict[str, Any] | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    filters = filters or {}
    date_clause = "1=1"
    params: list[Any] = []
    if period_start:
        date_clause += " AND COALESCE(occurred_at, discovered_at)>=?"
        params.append(period_start)
    if period_end:
        date_clause += " AND COALESCE(occurred_at, discovered_at)<=?"
        params.append(period_end)
    subject_type = filters.get("subject_type") or ""
    subject_id = filters.get("subject_id") or ""
    if subject_type:
        date_clause += " AND subject_type=?"
        params.append(subject_type)
    if subject_id:
        date_clause += " AND subject_id=?"
        params.append(subject_id)
    with db_connection(db_path) as conn:
        signals = [dict(r) for r in conn.execute(f"SELECT * FROM v05e_industry_signals WHERE {date_clause} ORDER BY signal_level, discovered_at DESC LIMIT 100", params).fetchall()]
        events = []
        if _table_exists(conn, "events"):
            events = [dict(r) for r in conn.execute(
                """
                SELECT * FROM events
                WHERE COALESCE(is_active,1)=1
                  AND (?='' OR COALESCE(event_date, created_at)>=?)
                  AND (?='' OR COALESCE(event_date, created_at)<=?)
                ORDER BY COALESCE(event_date, created_at) DESC LIMIT 80
                """,
                (period_start, period_start, period_end, period_end),
            ).fetchall()]
        reviews = []
        if _table_exists(conn, "v04c_review_items"):
            reviews = [dict(r) for r in conn.execute("SELECT * FROM v04c_review_items WHERE status IN ('pending','in_review','deferred') ORDER BY id DESC LIMIT 30").fetchall()]
        queued = conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE processing_status='queued'").fetchone()[0] if _table_exists(conn, "v05f_collection_items") else 0
    return {"signals": signals, "events": events, "reviews": reviews, "queued_processing": queued, "filters": filters}


def _table_exists(conn, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())
