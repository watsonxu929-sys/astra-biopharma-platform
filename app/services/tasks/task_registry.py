from __future__ import annotations

from typing import Any, Callable

TaskHandler = Callable[[dict[str, Any], str | None], dict[str, Any]]


def _collection(payload: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    from app.services.collection_service import create_job
    from app.services.intelligence_flow_service import (
        run_collection_worker_with_cascade,
        schedule_due_collection_jobs,
    )

    limit = int(payload.get("limit") or 10)
    if payload.get("source_id"):
        create_job(int(payload["source_id"]), trigger_type="worker", operator="unified-worker", db_path=db_path)
    scheduled = {"created": 0, "skipped": 0}
    if payload.get("due_only") or payload.get("schedule_due"):
        scheduled = schedule_due_collection_jobs(limit=limit, db_path=db_path, operator="scheduler")
    result = run_collection_worker_with_cascade(once=True, limit=limit, db_path=db_path, operator="unified-worker")
    result["scheduled_collection_jobs"] = scheduled
    return result


def _processing(payload: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    from app.services.processing import run_worker

    return run_worker(once=True, queued_only=True, limit=int(payload.get("limit") or 10), operator="unified-worker", db_path=db_path)


def _pipeline(payload: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    from app.services.pipeline import run_pipeline_once

    return run_pipeline_once(source_id=payload.get("source_id"), pipeline_run_id=payload.get("pipeline_run_id"), created_by="unified-worker", pilot=True, dry_run=not bool(payload.get("confirm")), db_path=db_path)


def _signal(payload: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    from app.services.signals import generate_signals

    return generate_signals(limit=int(payload.get("limit") or 50), dry_run=not bool(payload.get("confirm")), db_path=db_path)


def _report(payload: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    from app.services.reports import create_report_job, generate_report

    job = create_report_job(report_type=payload.get("report_type") or "daily", generated_by="unified-worker", db_path=db_path)
    return generate_report(int(job["id"]), db_path=db_path)


def _backup(payload: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    from app.services.operations.backup_service import create_backup

    return create_backup(backup_type=payload.get("backup_type") or "manual", created_by="unified-worker", db_path=db_path)


def _quality_sample(payload: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    from app.services.operations.source_quality_service import create_quality_report

    return create_quality_report(created_by="unified-worker", db_path=db_path)


def _source_health(payload: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    from app.services.operations.source_quality_service import calculate_source_health_scores

    return calculate_source_health_scores(db_path=db_path)


TASK_HANDLERS: dict[str, TaskHandler] = {
    "collection": _collection,
    "processing": _processing,
    "pipeline": _pipeline,
    "signal": _signal,
    "report": _report,
    "backup": _backup,
    "quality_sample": _quality_sample,
    "source_health_check": _source_health,
    "cleanup": lambda payload, db_path=None: {"cleaned": 0, "note": "首版仅记录清理任务，不自动删除数据"},
}


def handler_for(task_type: str) -> TaskHandler:
    if task_type not in TASK_HANDLERS:
        raise ValueError("不支持的任务类型")
    return TASK_HANDLERS[task_type]
