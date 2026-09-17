from __future__ import annotations

import logging
import os
import threading
import time
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
_FORMAL_DATABASE = (Path(__file__).resolve().parents[2] / "data" / "app.db").resolve()


def _pytest_database_is_safe(db_path: str | Path | None) -> bool:
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if db_path is None:
        return False
    return Path(db_path).resolve() != _FORMAL_DATABASE


def _scheduler_enabled() -> bool:
    return get_settings().scheduler_enabled


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
    global _scheduler
    if not _pytest_database_is_safe(db_path):
        _logger.warning("Scheduler refused: pytest requires an explicit non-formal database")
        return False
    if not force and not _scheduler_enabled():
        _logger.info("Scheduler is disabled in config (SCHEDULER_ENABLED=False)")
        return False
    with _lock:
        if _scheduler is not None:
            _logger.warning("Scheduler already running")
            return True
        try:
            _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
            _scheduler.add_job(
                run_collection_cycle,
                CronTrigger(minute="*/15"),
                id="collection_cycle",
                name="Schedule and process due collection jobs",
                misfire_grace_time=60,
                kwargs={"db_path": db_path},
            )
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
