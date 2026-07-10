from __future__ import annotations

from pathlib import Path
from typing import Any

from .task_common import db_connection, dumps, next_uid, now


def create_task(task_type: str, *, payload: dict[str, Any] | None = None, queue_name: str = "default", idempotency_key: str | None = None, created_by: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    ts = now()
    with db_connection(db_path) as conn:
        if idempotency_key:
            row = conn.execute(
                "SELECT * FROM task_queue WHERE task_type=? AND idempotency_key=? AND status IN ('pending','running','retrying','success') ORDER BY id DESC LIMIT 1",
                (task_type, idempotency_key),
            ).fetchone()
            if row:
                return dict(row)
        task_uid = next_uid(conn, "TASK")
        cur = conn.execute(
            """
            INSERT INTO task_queue(task_uid,task_type,queue_name,payload_json,idempotency_key,created_by,created_at,updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_uid, task_type, queue_name, dumps(payload or {}), idempotency_key, created_by, ts, ts),
        )
        return dict(conn.execute("SELECT * FROM task_queue WHERE id=?", (cur.lastrowid,)).fetchone())


def list_tasks(*, status: str = "", task_type: str = "", page: int = 1, page_size: int = 20, db_path: str | Path | None = None) -> dict[str, Any]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("status=?")
        params.append(status)
    if task_type:
        clauses.append("task_type=?")
        params.append(task_type)
    where = " AND ".join(clauses)
    with db_connection(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM task_queue WHERE {where}", params).fetchone()[0]
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM task_queue WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()]
    return {"data": rows, "pagination": {"page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size}}
