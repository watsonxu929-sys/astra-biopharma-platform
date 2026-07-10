from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.i18n.helpers import add_labels
from app.services.api_common import require_permission, single
from app.services.pipeline import cancel_pipeline, continue_pipeline, create_pipeline_run, dashboard, get_pipeline_run, list_pipeline_runs, pipeline_detail, quality_metrics, retry_pipeline, review_quality_sample

router = APIRouter(prefix="/pipeline")


class PipelineRunIn(BaseModel):
    source_id: int = Field(..., ge=1)
    pilot: bool = True
    dry_run: bool = True
    run_now: bool = False


class SampleReviewIn(BaseModel):
    correctness: str = Field(..., pattern="^(correct|incorrect|partial)$")
    error_type: str = ""
    note: str = ""


@router.get("/runs")
def runs(request: Request, status: str = "", source_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    return add_labels(list_pipeline_runs(page=page, page_size=page_size, status=status, source_id=source_id))


@router.post("/runs")
def create_run(request: Request, payload: PipelineRunIn):
    user = require_permission(request, "manage_monitoring")
    try:
        run = create_pipeline_run(payload.source_id, created_by=str(user.get("username") or "api"), pilot=payload.pilot, dry_run=payload.dry_run)
        if payload.run_now:
            run = continue_pipeline(run["id"], actor=str(user.get("username") or "api"))
        return single(add_labels(run))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"code": "ACTIVE_PIPELINE_EXISTS", "message": str(exc), "details": {}}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "PIPELINE_SOURCE_NOT_FOUND", "message": str(exc), "details": {}}) from exc


@router.get("/runs/{run_id}")
def run_detail(request: Request, run_id: int):
    require_permission(request, "view_internal")
    data = pipeline_detail(run_id)
    if not data:
        raise HTTPException(status_code=404, detail={"code": "PIPELINE_RUN_NOT_FOUND", "message": "pipeline run not found", "details": {}})
    return single(data)


@router.post("/runs/{run_id}/continue")
def continue_run(request: Request, run_id: int):
    user = require_permission(request, "review_data")
    data = get_pipeline_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail={"code": "PIPELINE_RUN_NOT_FOUND", "message": "pipeline run not found", "details": {}})
    return single(add_labels(continue_pipeline(run_id, actor=str(user.get("username") or "api"))))


@router.post("/runs/{run_id}/retry")
def retry_run(request: Request, run_id: int):
    user = require_permission(request, "review_data")
    try:
        return single(add_labels(retry_pipeline(run_id, actor=str(user.get("username") or "api"))))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"code": "PIPELINE_NOT_RETRYABLE", "message": str(exc), "details": {}}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "PIPELINE_RUN_NOT_FOUND", "message": str(exc), "details": {}}) from exc


@router.post("/runs/{run_id}/cancel")
def cancel_run(request: Request, run_id: int):
    user = require_permission(request, "manage_monitoring")
    try:
        return single(add_labels(cancel_pipeline(run_id, actor=str(user.get("username") or "api"))))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "PIPELINE_RUN_NOT_FOUND", "message": str(exc), "details": {}}) from exc


@router.get("/dashboard")
def pipeline_dashboard(request: Request):
    require_permission(request, "view_internal")
    return single(add_labels(dashboard()))


@router.get("/quality")
def pipeline_quality(request: Request):
    require_permission(request, "view_internal")
    return single(add_labels(quality_metrics()))


@router.post("/samples/{sample_id}/review")
def sample_review(request: Request, sample_id: int, payload: SampleReviewIn):
    user = require_permission(request, "review_data")
    try:
        return single(add_labels(review_quality_sample(sample_id, correctness=payload.correctness, error_type=payload.error_type, reviewer=str(user.get("username") or "api"), note=payload.note)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "QUALITY_SAMPLE_REVIEW_FAILED", "message": str(exc), "details": {}}) from exc


