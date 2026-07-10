from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.i18n.helpers import add_labels
from app.services.api_common import Pagination, normalize_page, paginated, require_permission, single
from app.services.intelligence_review_service import IntelligenceReviewService
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.processing import (
    apply_candidate,
    candidate_detail,
    create_processing_job,
    dashboard,
    list_candidates,
    list_jobs,
    list_subject_matches,
    process_job,
    run_worker,
)

router = APIRouter(prefix="/processing")


class JobIn(BaseModel):
    item_id: int | None = None
    snapshot_id: int | None = None
    trigger_type: str = "api"
    queued_only: bool = True
    reprocess: bool = False
    priority: str = "medium"
    run_now: bool = False


class ReviewIn(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected|needs_review)$")
    note: str = ""
    final_value: str = ""


@router.get("/dashboard", summary="Processing dashboard")
def api_dashboard(request: Request):
    require_permission(request, "view_internal")
    return single(add_labels(dashboard()))


@router.get("/jobs", summary="List processing jobs")
def api_jobs(request: Request, status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    rows, total = list_jobs(page=page, page_size=page_size, status=status)
    return paginated(add_labels(rows), Pagination(page, page_size, total))


@router.post("/jobs", summary="Create processing job")
def api_create_job(request: Request, payload: JobIn):
    user = require_permission(request, "review_data")
    try:
        job = create_processing_job(
            item_id=payload.item_id,
            snapshot_id=payload.snapshot_id,
            trigger_type=payload.trigger_type,
            operator=str(user.get("username") or "api"),
            queued_only=payload.queued_only,
            reprocess=payload.reprocess,
            priority=payload.priority,
        )
        if payload.run_now:
            return single(add_labels(process_job(job["id"])))
        return single(add_labels(job))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"code": "PROCESSING_JOB_CONFLICT", "message": str(exc), "details": {}}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "PROCESSING_SOURCE_NOT_FOUND", "message": str(exc), "details": {}}) from exc


@router.post("/jobs/{job_id}/run", summary="Run a processing job")
def api_run_job(request: Request, job_id: int):
    require_permission(request, "review_data")
    return single(add_labels(process_job(job_id)))


@router.post("/worker/run-once", summary="Run processing worker once")
def api_worker_once(request: Request, item_id: int | None = None, queued_only: bool = True, limit: int = 20, reprocess: bool = False):
    user = require_permission(request, "review_data")
    return single(add_labels(run_worker(once=True, item_id=item_id, queued_only=queued_only, limit=limit, reprocess=reprocess, operator=str(user.get("username") or "api"))))


@router.get("/candidates", summary="List extraction candidates")
def api_candidates(
    request: Request,
    review_status: str = "",
    candidate_type: str = "",
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    rows, total = list_candidates(page=page, page_size=page_size, review_status=review_status, candidate_type=candidate_type, q=q)
    return paginated(add_labels(rows), Pagination(page, page_size, total))


@router.get("/candidates/{candidate_id}", summary="Candidate detail")
def api_candidate_detail(request: Request, candidate_id: int):
    require_permission(request, "view_internal")
    detail = candidate_detail(candidate_id)
    if not detail:
        raise HTTPException(status_code=404, detail={"code": "CANDIDATE_NOT_FOUND", "message": "candidate not found", "details": {}})
    return single(add_labels(detail))


@router.post("/candidates/{candidate_id}/review", summary="Review a candidate")
def api_review_candidate(request: Request, candidate_id: int, payload: ReviewIn):
    user = require_permission(request, "review_data")
    try:
        row = IntelligenceReviewService().review_candidate(
            candidate_id, decision=payload.decision, actor=str(user.get("username") or "api"),
            permissions={"review_data"}, note=payload.note, final_value=payload.final_value,
        )
        return single(add_labels(row))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "CANDIDATE_REVIEW_FAILED", "message": str(exc), "details": {}}) from exc


@router.post("/candidates/{candidate_id}/apply", summary="Apply an approved field candidate")
def api_apply_candidate(request: Request, candidate_id: int):
    user = require_permission(request, "review_data")
    return single(add_labels(apply_candidate(candidate_id, actor=str(user.get("username") or "api"))))


@router.get("/subject-matches", summary="List subject match candidates")
def api_subject_matches(request: Request, status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    rows, total = list_subject_matches(page=page, page_size=page_size, status=status)
    return paginated(add_labels(rows), Pagination(page, page_size, total))

@router.post("/candidates/{candidate_id}/publish", summary="Publish an approved evidence-backed candidate")
def api_publish_candidate(request: Request, candidate_id: int):
    user = require_permission(request, "review_data")
    try:
        product = IntelligenceProductService().publish_candidate(
            candidate_id,
            actor=str(user.get("username") or "api"),
            permissions={"review_data"},
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail={"code": "CANDIDATE_PUBLISH_FAILED", "message": str(exc), "details": {}}) from exc
    return single(add_labels(product))
