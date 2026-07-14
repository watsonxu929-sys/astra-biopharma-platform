from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.services.intelligence_flow_service import (
    run_collection_worker_with_cascade,
    schedule_due_collection_jobs,
)
from app.services.collection_service import list_sources

_settings = get_settings()
_logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def _scheduler_enabled() -> bool:
    return _settings.scheduler_enabled


def _schedule_collection_job():
    try:
        scheduled = schedule_due_collection_jobs(limit=10, operator="scheduler")
        _logger.info(f"Scheduled {scheduled['created']} collection jobs, skipped {scheduled['skipped']}")
    except Exception as exc:
        _logger.error(f"Scheduler failed to schedule jobs: {exc}", exc_info=True)


def _run_collection_worker():
    try:
        result = run_collection_worker_with_cascade(once=False, limit=5, operator="scheduler-worker")
        _logger.info(f"Collection worker processed {result['processed']} jobs")
    except Exception as exc:
        _logger.error(f"Collection worker failed: {exc}", exc_info=True)


def start_scheduler() -> bool:
    global _scheduler
    if not _scheduler_enabled():
        _logger.info("Scheduler is disabled in config (SCHEDULER_ENABLED=False)")
        return False
    with _lock:
        if _scheduler is not None:
            _logger.warning("Scheduler already running")
            return True
        try:
            _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
            _scheduler.add_job(
                _schedule_collection_job,
                CronTrigger(minute="*/15"),
                id="collection_scheduler",
                name="Schedule due collection jobs",
                misfire_grace_time=60,
            )
            _scheduler.add_job(
                _run_collection_worker,
                CronTrigger(minute="*/20"),
                id="collection_worker",
                name="Process pending collection jobs",
                misfire_grace_time=60,
            )
            _scheduler.start()
            _logger.info("Collection scheduler started successfully")
            return True
        except Exception as exc:
            _logger.error(f"Failed to start scheduler: {exc}", exc_info=True)
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


def run_scheduler_once() -> dict[str, Any]:
    _schedule_collection_job()
    return run_collection_worker_with_cascade(once=False, limit=20, operator="manual-run")


def get_sources_with_next_run() -> list[dict[str, Any]]:
    rows, _ = list_sources(page=1, page_size=50)
    result = []
    now = datetime.now()
    frequency_map = {
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
    }
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
