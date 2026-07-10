from __future__ import annotations

from pathlib import Path
from typing import Any

from .task_common import db_connection


def task_metrics(db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        counts = {row["status"]: row["c"] for row in conn.execute("SELECT status, COUNT(*) AS c FROM task_queue GROUP BY status").fetchall()}
        failed = [dict(r) for r in conn.execute("SELECT * FROM task_queue WHERE status IN ('failed','dead') ORDER BY updated_at DESC LIMIT 10").fetchall()]
        workers = [dict(r) for r in conn.execute("SELECT * FROM worker_heartbeats ORDER BY heartbeat_at DESC LIMIT 20").fetchall()]
    return {"counts": counts, "failed": failed, "workers": workers}
