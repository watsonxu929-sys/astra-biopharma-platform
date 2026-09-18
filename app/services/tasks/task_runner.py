from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from .task_common import db_connection, dumps, loads, next_uid, now
from .task_heartbeat_service import heartbeat
from .task_registry import handler_for
from .task_retry_service import next_retry_at


def recover_stale_tasks(*, worker_id: str = "recovery", stale_seconds: int = 1800, db_path: str | Path | None = None, task_type: str = "") -> int:
    with db_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute(
            "SELECT id, attempts, max_attempts FROM task_queue WHERE status='running' AND (heartbeat_at IS NULL OR datetime(heartbeat_at) < datetime('now','localtime', ?)) AND (?='' OR task_type=?) LIMIT 20",
            (f"-{int(stale_seconds)} seconds", task_type, task_type),
        ).fetchall()
        count = 0
        for row in rows:
            status = "retrying" if int(row["attempts"]) < int(row["max_attempts"]) else "dead"
            conn.execute("UPDATE task_queue SET status=?, locked_by=NULL, locked_at=NULL, not_before=?, updated_at=? WHERE id=?", (status, next_retry_at(int(row["attempts"])), now(), row["id"]))
            if task_type=='knowledge_material':
                conn.execute("UPDATE task_queue SET payload_json=json_set(payload_json,'$.trigger_reason','restart_recovery') WHERE id=?",(row['id'],))
            count += 1
        return count


def claim_task(*, worker_id: str, queue_name: str = "default", task_type: str = "", db_path: str | Path | None = None) -> dict[str, Any] | None:
    ts = now()
    with db_connection(db_path) as conn:
        clauses = ["queue_name=?", "status IN ('pending','retrying')", "(not_before IS NULL OR not_before<=?)"]
        conn.execute('BEGIN IMMEDIATE')
        params: list[Any] = [queue_name, ts]
        if task_type:
            clauses.append("task_type=?")
            params.append(task_type)
        row = conn.execute(f"SELECT * FROM task_queue WHERE {' AND '.join(clauses)} ORDER BY priority ASC, id ASC LIMIT 1", params).fetchone()
        if not row:
            return None
        conn.execute("UPDATE task_queue SET status='running', locked_by=?, locked_at=?, heartbeat_at=?, attempts=attempts+1, updated_at=? WHERE id=? AND status IN ('pending','retrying')", (worker_id, ts, ts, ts, row["id"]))
        return dict(conn.execute("SELECT * FROM task_queue WHERE id=?", (row["id"],)).fetchone())


def run_once(*, worker_id: str | None = None, queue_name: str = "default", task_type: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    heartbeat(worker_id, queue_name=queue_name, task_type=task_type, db_path=db_path)
    task = claim_task(worker_id=worker_id, queue_name=queue_name, task_type=task_type, db_path=db_path)
    if not task:
        return {"processed": 0, "task": None}
    run_uid = ""
    started = time.perf_counter()
    with db_connection(db_path) as conn:
        run_uid = next_uid(conn, "TRUN")
        conn.execute("INSERT INTO task_runs(task_id,run_uid,worker_id,status,started_at) VALUES (?, ?, ?, 'running', ?)", (task["id"], run_uid, worker_id, now()))
    try:
        payload = loads(task.get("payload_json"), {})
        result = handler_for(str(task["task_type"]))(payload, str(db_path) if db_path else None)
        if task['task_type']=='knowledge_material':
            result={**result,'trigger_reason':payload.get('trigger_reason') or ('failure_retry' if int(task['attempts'])>1 else 'scheduled' if task.get('created_by')=='scheduler' else 'manual')}
        duration = int((time.perf_counter() - started) * 1000)
        with db_connection(db_path) as conn:
            conn.execute("UPDATE task_queue SET status='success', result_json=?, finished_at=?, updated_at=?, locked_by=NULL WHERE id=?", (dumps(result), now(), now(), task["id"]))
            conn.execute("UPDATE task_runs SET status='success', result_json=?, finished_at=?, duration_ms=? WHERE run_uid=?", (dumps(result), now(), duration, run_uid))
        return {"processed": 1, "task": task["task_uid"], "status": "success", "result": result}
    except Exception as exc:
        duration = int((time.perf_counter() - started) * 1000)
        attempts = int(task["attempts"])
        max_attempts = int(task["max_attempts"])
        next_status = "retrying" if attempts < max_attempts else "failed"
        with db_connection(db_path) as conn:
            conn.execute(
                "UPDATE task_queue SET status=?, error_code=?, error_summary=?, not_before=?, updated_at=?, locked_by=NULL WHERE id=?",
                (next_status, exc.__class__.__name__, str(exc)[:500], next_retry_at(attempts), now(), task["id"]),
            )
            conn.execute("UPDATE task_runs SET status='failed', error_code=?, error_summary=?, finished_at=?, duration_ms=? WHERE run_uid=?", (exc.__class__.__name__, str(exc)[:500], now(), duration, run_uid))
        return {"processed": 1, "task": task["task_uid"], "status": next_status, "error": str(exc)[:500]}
