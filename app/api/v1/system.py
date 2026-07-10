from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.services.api_common import require_permission, single
from app.services.operations import health_snapshot, readiness
from app.services.tasks import list_tasks, task_metrics

router = APIRouter(prefix="/system")


@router.get("/health")
def api_system_health(request: Request):
    detailed = bool(getattr(request.state, "current_user", None))
    return single(health_snapshot(detailed=detailed))


@router.get("/readiness")
def api_system_readiness(request: Request, response: Response):
    status_code, data = readiness()
    response.status_code = status_code
    return single(data)


@router.get("/tasks")
def api_tasks(request: Request, status: str = "", task_type: str = "", page: int = 1, page_size: int = 20):
    require_permission(request, "view_internal")
    return list_tasks(status=status, task_type=task_type, page=page, page_size=page_size)


@router.get("/task-metrics")
def api_task_metrics(request: Request):
    require_permission(request, "view_internal")
    return single(task_metrics())
