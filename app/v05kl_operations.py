from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.operations import calculate_source_health_scores, create_backup, create_quality_report, health_snapshot, list_backups, quality_metrics
from app.services.operations.restore_service import list_restore_records
from app.services.tasks import create_task, list_tasks, task_metrics

router = APIRouter(tags=["v0.5K-L operations"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/system/operations", response_class=HTMLResponse)
def operations_home(request: Request):
    return templates.TemplateResponse(request, "v05kl_operations.html", {"mode": "home", "health": health_snapshot(detailed=True), "tasks": task_metrics(), "quality": quality_metrics()})


@router.get("/system/health", response_class=HTMLResponse)
def system_health_page(request: Request):
    return templates.TemplateResponse(request, "v05kl_operations.html", {"mode": "health", "health": health_snapshot(detailed=True)})


@router.get("/system/tasks", response_class=HTMLResponse)
def system_tasks_page(request: Request, status: str = "", task_type: str = ""):
    return templates.TemplateResponse(request, "v05kl_operations.html", {"mode": "tasks", "result": list_tasks(status=status, task_type=task_type), "metrics": task_metrics()})


@router.post("/system/tasks")
def system_task_create(request: Request, task_type: str = Form(...)):
    create_task(task_type, created_by=current_username(request), idempotency_key=f"manual:{task_type}:{current_username(request)}")
    return RedirectResponse("/system/tasks?message=created", status_code=303)


@router.get("/system/backups", response_class=HTMLResponse)
def system_backups_page(request: Request):
    return templates.TemplateResponse(request, "v05kl_operations.html", {"mode": "backups", "backups": list_backups(), "restores": list_restore_records()})


@router.post("/system/backups")
def system_backup_create(request: Request, backup_type: str = Form("manual")):
    create_backup(backup_type=backup_type, created_by=current_username(request))
    return RedirectResponse("/system/backups?message=created", status_code=303)


@router.get("/system/sources", response_class=HTMLResponse)
def system_sources_page(request: Request):
    return templates.TemplateResponse(request, "v05kl_operations.html", {"mode": "sources", "quality": quality_metrics()})


@router.post("/system/sources/health")
def source_health_run(request: Request):
    calculate_source_health_scores()
    return RedirectResponse("/system/sources?message=source-health-updated", status_code=303)


@router.post("/system/quality-report")
def quality_report_create(request: Request):
    create_quality_report(created_by=current_username(request))
    return RedirectResponse("/system/sources?message=quality-report-created", status_code=303)


@router.get("/system/errors", response_class=HTMLResponse)
def system_errors_page(request: Request):
    return templates.TemplateResponse(request, "v05kl_operations.html", {"mode": "errors", "metrics": task_metrics()})


@router.get("/v05kl/health")
def health():
    return {"ok": True, "version": "v0.5K-L"}
