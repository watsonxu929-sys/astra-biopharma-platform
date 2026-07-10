from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.config import ROOT, get_settings
from app.core.database_compat import database_health
from app.services.tasks.task_common import db_connection, dumps, now


def health_snapshot(*, detailed: bool = False, db_path: str | Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    db = database_health(settings)
    runtime = ROOT / "runtime"
    data_dir = ROOT / "data"
    logs = ROOT / "logs"
    checks = {
        "web": {"ok": True, "label": "Web 服务可响应"},
        "database": db,
        "worker": _last_worker(db_path),
        "scheduler": _last_scheduler(db_path),
        "backup": _last_backup(db_path),
        "writable": {"data": os.access(data_dir, os.W_OK), "logs": os.access(logs, os.W_OK) or not logs.exists(), "runtime": os.access(runtime, os.W_OK) or not runtime.exists()},
        "queue": _queue_status(db_path),
    }
    ok = bool(db.get("ok")) and all(checks["writable"].values())
    result = {"ok": ok, "status": "healthy" if ok else "degraded", "environment": settings.app_env, "server_time": now(), "checks": checks if detailed else {"web": checks["web"], "database": {"ok": db.get("ok"), "backend": db.get("backend")}}}
    with db_connection(db_path) as conn:
        conn.execute("INSERT INTO system_health_snapshots(snapshot_at,status,metrics_json,created_at) VALUES (?, ?, ?, ?)", (now(), result["status"], dumps(result), now()))
    return result


def readiness(*, db_path: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    result = health_snapshot(detailed=True, db_path=db_path)
    return (200 if result["ok"] else 503), result


def _last_worker(db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM worker_heartbeats ORDER BY heartbeat_at DESC LIMIT 1").fetchone()
    return {"ok": bool(row), "last_heartbeat": row["heartbeat_at"] if row else None}


def _last_scheduler(db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM scheduler_runs ORDER BY created_at DESC LIMIT 1").fetchone()
    return {"ok": True, "last_run": row["created_at"] if row else None}


def _last_backup(db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM backup_records WHERE status='success' ORDER BY created_at DESC LIMIT 1").fetchone()
    return {"ok": bool(row), "last_backup": row["created_at"] if row else None}


def _queue_status(db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        pending = conn.execute("SELECT COUNT(*) FROM task_queue WHERE status IN ('pending','retrying')").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM task_queue WHERE status IN ('failed','dead')").fetchone()[0]
    return {"pending": pending, "failed": failed}
