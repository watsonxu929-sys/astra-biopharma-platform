from __future__ import annotations

import os
import socket
from pathlib import Path

from .task_common import db_connection, dumps, now


def heartbeat(worker_id: str, *, queue_name: str = "default", task_type: str = "", status: str = "online", metadata: dict | None = None, db_path: str | Path | None = None) -> dict:
    ts = now()
    with db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO worker_heartbeats(worker_id,queue_name,task_type,pid,hostname,status,started_at,heartbeat_at,metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(worker_id) DO UPDATE SET
              queue_name=excluded.queue_name, task_type=excluded.task_type, pid=excluded.pid,
              hostname=excluded.hostname, status=excluded.status, heartbeat_at=excluded.heartbeat_at,
              metadata_json=excluded.metadata_json
            """,
            (worker_id, queue_name, task_type or None, os.getpid(), socket.gethostname(), status, ts, ts, dumps(metadata or {})),
        )
        return dict(conn.execute("SELECT * FROM worker_heartbeats WHERE worker_id=?", (worker_id,)).fetchone())
