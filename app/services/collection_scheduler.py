from __future__ import annotations

import logging
import os
import threading
import time
import json
import socket
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.services.collection_service import list_sources
from app.services.intelligence_flow_service import (
    run_collection_worker_with_cascade,
    schedule_due_collection_jobs,
)

_logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()
_instance_token = uuid.uuid4().hex
_active_db = None
_FORMAL_DATABASE = (Path(__file__).resolve().parents[2] / "data" / "app.db").resolve()


def _pytest_database_is_safe(db_path: str | Path | None) -> bool:
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if db_path is None:
        return False
    return Path(db_path).resolve() != _FORMAL_DATABASE


def _scheduler_enabled() -> bool:
    return get_settings().scheduler_enabled


def runtime_status(db_path=None):
    """Read-only persisted evidence; a page load never makes a heartbeat."""
    from app.v04c_review import db_connection
    with db_connection(db_path) as conn:
        row=conn.execute("SELECT * FROM worker_heartbeats WHERE worker_id='collection-scheduler'").fetchone()
        enabled_sources=conn.execute('SELECT COUNT(*) FROM v04g_monitoring_sources WHERE is_enabled=1 AND deactivated_at IS NULL').fetchone()[0]
        last=conn.execute("SELECT MAX(created_at) FROM v04g_monitoring_runs WHERE trigger_type='scheduler'").fetchone()[0]
        success=conn.execute("SELECT MAX(finished_at) FROM v04g_monitoring_runs WHERE status IN ('success','unchanged')").fetchone()[0]
    if not row:
        return {'state':'已停止','heartbeat':None,'jobs':[],'enabled_sources':enabled_sources,'last_scheduled':last,'last_success':success}
    row=dict(row); meta=json.loads(row['metadata_json'] or '{}')
    try:fresh=(datetime.now()-datetime.fromisoformat(row['heartbeat_at'])).total_seconds()<60
    except (TypeError,ValueError):fresh=False
    state='已暂停' if not meta.get('enabled',False) else '运行中' if fresh and row['status']=='online' else '已停止' if row['status']=='stopped' else '状态未知'
    return {'state':state,'heartbeat':row['heartbeat_at'],'jobs':meta.get('jobs',[]),'enabled_sources':enabled_sources,'last_scheduled':last,'last_success':success,'enabled':meta.get('enabled',False)}


def set_automatic_collection(enabled, db_path=None):
    from app.v04c_review import db_connection
    with db_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute("SELECT metadata_json FROM worker_heartbeats WHERE worker_id='collection-scheduler'").fetchone()
        if row:
            meta=json.loads(row[0]);meta['enabled']=bool(enabled)
            conn.execute("UPDATE worker_heartbeats SET metadata_json=? WHERE worker_id='collection-scheduler'",(json.dumps(meta),))
        elif not enabled:
            return
    if enabled:start_scheduler(force=True,db_path=db_path)


def _heartbeat(db_path=None, *, claim=False, enabled=True):
    from app.v04c_review import db_connection
    with db_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute("SELECT * FROM worker_heartbeats WHERE worker_id='collection-scheduler'").fetchone()
        meta=json.loads(row['metadata_json']) if row else {'enabled':enabled}
        if row and meta.get('token')!=_instance_token:
            if not claim or (row['status']=='online' and datetime.fromisoformat(row['heartbeat_at'])>datetime.now()-timedelta(seconds=60)):
                return False
        jobs=[{'id':j.id,'name':j.name,'next_run_time':j.next_run_time.isoformat() if j.next_run_time else None} for j in _scheduler.get_jobs()] if _scheduler else []
        meta.update(token=_instance_token,jobs=jobs)
        ts=datetime.now().isoformat()
        conn.execute("INSERT INTO worker_heartbeats(worker_id,queue_name,task_type,pid,hostname,status,started_at,heartbeat_at,metadata_json) VALUES ('collection-scheduler','knowledge','scheduler',?,?,'online',?,?,?) ON CONFLICT(worker_id) DO UPDATE SET pid=excluded.pid,hostname=excluded.hostname,status=excluded.status,heartbeat_at=excluded.heartbeat_at,metadata_json=excluded.metadata_json",(os.getpid(),socket.gethostname(),ts,ts,json.dumps(meta)))
    return True


def _knowledge_tick(db_path=None):
    from app.v04c_review import db_connection
    from app.services.tasks import create_task,run_once
    from app.services.tasks.task_runner import recover_stale_tasks
    if not _heartbeat(db_path) or runtime_status(db_path)['state']!='运行中':return
    recover_stale_tasks(task_type='knowledge_material',db_path=db_path)
    with db_connection(db_path) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='knowledge_materials'").fetchone():return
        rows=conn.execute("SELECT id,owner_user_id FROM knowledge_materials WHERE tracking=1 AND (next_check_at IS NULL OR next_check_at<=?) ORDER BY COALESCE(next_check_at,''),id LIMIT 5",(datetime.now().isoformat(),)).fetchall()
    for row in rows:
        create_task('knowledge_material',queue_name='knowledge',payload={'material_id':row['id'],'owner_user_id':row['owner_user_id'],'fetch':True},idempotency_key=f"material:{row['id']}:{datetime.now().strftime('%Y%m%d%H')}",created_by='scheduler',db_path=db_path)
    for _ in range(3):
        if not run_once(worker_id='knowledge:'+_instance_token,queue_name='knowledge',task_type='knowledge_material',db_path=db_path)['processed']:break


def run_collection_cycle(
    *,
    limit: int = 20,
    operator: str = "scheduler",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Use the same collection callable for scheduled and manual runs."""
    if not _pytest_database_is_safe(db_path):
        raise RuntimeError("pytest_scheduler_requires_explicit_non_formal_database")
    started = time.perf_counter()
    scheduled = schedule_due_collection_jobs(limit=limit, db_path=db_path, operator=operator)
    worker = run_collection_worker_with_cascade(
        once=False,
        limit=limit,
        db_path=db_path,
        operator=operator,
    )
    result = {"scheduled": scheduled, "worker": worker}
    _logger.info(
        "collection_cycle result=SUCCESS operator=%s scheduled=%s processed=%s elapsed_ms=%s",
        operator,
        scheduled["created"],
        worker["processed"],
        round((time.perf_counter() - started) * 1000),
    )
    return result


def start_scheduler(*, force: bool = False, db_path: str | Path | None = None) -> bool:
    global _scheduler, _active_db
    if not _pytest_database_is_safe(db_path):
        _logger.warning("Scheduler refused: pytest requires an explicit non-formal database")
        return False
    persisted=runtime_status(db_path)
    if not force and not persisted.get('enabled',_scheduler_enabled()):
        _logger.info("Scheduler is disabled in config (SCHEDULER_ENABLED=False)")
        return False
    with _lock:
        if _scheduler is not None:
            _logger.warning("Scheduler already running")
            return True
        try:
            # A standby uses the same scheduler but cannot dispatch while another
            # process holds the lease. It can acquire an expired lease after restart.
            _heartbeat(db_path,claim=True,enabled=True)
            _active_db=db_path
            _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
            _scheduler.add_job(
                _scheduled_collection,
                CronTrigger(minute="*/15"),
                id="collection_cycle",
                name="Schedule and process due collection jobs",
                misfire_grace_time=60,
                kwargs={"db_path": db_path},
                coalesce=True, max_instances=1,
            )
            _scheduler.add_job(_heartbeat,'interval',seconds=10,id='scheduler_heartbeat',kwargs={'db_path':db_path,'claim':True},coalesce=True,max_instances=1)
            _scheduler.add_job(_knowledge_tick,'interval',seconds=30,id='knowledge_materials',name='资料拆解及更新检查',kwargs={'db_path':db_path},coalesce=True,max_instances=1)
            _scheduler.start()
            _logger.info("Collection scheduler started successfully")
            return True
        except Exception as exc:
            _logger.error("Failed to start scheduler: %s", exc, exc_info=True)
            _scheduler = None
            return False


def stop_scheduler() -> None:
    global _scheduler
    with _lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=True)
            _logger.info("Collection scheduler stopped")
            _scheduler = None
            from app.v04c_review import db_connection
            with db_connection(_active_db) as conn:
                conn.execute("UPDATE worker_heartbeats SET status='stopped' WHERE worker_id='collection-scheduler' AND json_extract(metadata_json,'$.token')=?",(_instance_token,))


def _scheduled_collection(db_path=None):
    if _heartbeat(db_path) and runtime_status(db_path)['state']=='运行中':
        return run_collection_cycle(db_path=db_path)


def is_scheduler_running() -> bool:
    with _lock:
        return _scheduler is not None and _scheduler.running


def get_scheduler_info() -> dict[str, Any]:
    if not _scheduler:
        return {"running": False, "jobs": [], "next_run_times": {}}
    jobs = []
    next_run_times = {}
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })
        if job.next_run_time:
            next_run_times[job.id] = job.next_run_time.isoformat()
    return {"running": _scheduler.running, "jobs": jobs, "next_run_times": next_run_times}


def run_scheduler_once(db_path: str | Path | None = None) -> dict[str, Any]:
    return run_collection_cycle(limit=20, operator="manual-run", db_path=db_path)


def get_sources_with_next_run() -> list[dict[str, Any]]:
    rows, _ = list_sources(page=1, page_size=50)
    result = []
    from app.services.collection_service import FREQUENCY_HOURS
    frequency_map = {key:timedelta(hours=value) for key,value in FREQUENCY_HOURS.items()}
    for row in rows:
        freq = row.get("check_frequency", "manual")
        last_checked = row.get("last_checked_at")
        next_run = None
        if freq in frequency_map and last_checked:
            try:
                last_dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
                next_run = (last_dt + frequency_map[freq]).replace(microsecond=0).isoformat()
            except Exception:
                pass
        result.append({
            "id": row["id"],
            "name": row["name"],
            "source_type": row["source_type"],
            "is_enabled": row["is_enabled"],
            "check_frequency": freq,
            "last_checked_at": last_checked,
            "next_run_time": next_run,
            "status_label": row.get("source_status_label", ""),
            "latest_job_status_label": row.get("latest_job_status_label", ""),
        })
    return result
