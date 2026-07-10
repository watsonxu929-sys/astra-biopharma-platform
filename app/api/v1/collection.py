from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.i18n.helpers import add_labels
from app.services.api_common import Pagination, normalize_page, paginated, require_permission, single
from app.services.collection_service import (
    create_collection_source,
    create_job,
    cancel_job,
    dashboard,
    list_items,
    list_jobs,
    list_sources,
    process_job,
    queue_item,
    run_worker,
    snapshot_detail,
)

router = APIRouter(prefix="/collection")


class SourceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_type: str = "webpage"
    url: str = Field(..., min_length=1, max_length=2000)
    collection_mode: str = "auto"
    allowed_domains: str = ""
    subject_type: str = ""
    subject_id: str = ""
    compliance_note: str = ""
    max_links: int = Field(20, ge=1, le=100)
    crawl_detail_pages: bool = False


class JobIn(BaseModel):
    source_id: int | None = None
    trigger_type: str = "api"
    force: bool = False


@router.get("/sources", summary="List collection sources")
def api_sources(request: Request, q: str = "", status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    rows, total = list_sources(page=page, page_size=page_size, status=status, q=q)
    return paginated(add_labels(rows), Pagination(page, page_size, total))


@router.post("/sources", summary="Create collection source")
def api_create_source(request: Request, payload: SourceIn):
    user = require_permission(request, "manage_monitoring")
    row = create_collection_source(
        name=payload.name,
        source_type=payload.source_type,
        url=payload.url,
        collection_mode=payload.collection_mode,
        allowed_domains=payload.allowed_domains,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        owner=str(user.get("username") or "api"),
        compliance_note=payload.compliance_note,
        max_links=payload.max_links,
        crawl_detail_pages=payload.crawl_detail_pages,
    )
    return single(add_labels(row))


@router.get("/sources/{source_id}", summary="Get collection source")
def api_source_detail(request: Request, source_id: int):
    require_permission(request, "view_internal")
    rows, _ = list_sources(page=1, page_size=1, q="")
    for row in rows:
        if row["id"] == source_id:
            return single(add_labels(row))
    # Fallback without broad payload: page list may not contain the requested id.
    all_rows, _ = list_sources(page=1, page_size=100, q="")
    for row in all_rows:
        if row["id"] == source_id:
            return single(add_labels(row))
    raise HTTPException(status_code=404, detail={"code": "COLLECTION_SOURCE_NOT_FOUND", "message": "collection source not found", "details": {}})


@router.patch("/sources/{source_id}", summary="Update collection source")
def api_update_source(request: Request, source_id: int, payload: SourceIn):
    require_permission(request, "manage_monitoring")
    # v0.5F keeps update conservative: create_collection_source reuses the active source row by URL/scope.
    row = create_collection_source(
        name=payload.name,
        source_type=payload.source_type,
        url=payload.url,
        collection_mode=payload.collection_mode,
        allowed_domains=payload.allowed_domains,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        owner="api",
        compliance_note=payload.compliance_note,
        max_links=payload.max_links,
        crawl_detail_pages=payload.crawl_detail_pages,
    )
    if row["id"] != source_id:
        raise HTTPException(status_code=409, detail={"code": "COLLECTION_SOURCE_SCOPE_CONFLICT", "message": "source scope maps to another active source", "details": {"existing_id": row["id"]}})
    return single(add_labels(row))


@router.post("/sources/{source_id}/run", summary="Create a collection job for one source")
def api_run_source(request: Request, source_id: int, force: bool = False):
    user = require_permission(request, "manage_monitoring")
    try:
        job = create_job(source_id, trigger_type="api", operator=str(user.get("username") or "api"), force=force)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_RUNNING_JOB", "message": str(exc), "details": {}}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "COLLECTION_SOURCE_NOT_FOUND", "message": str(exc), "details": {}}) from exc
    return single(add_labels(job))


@router.post("/sources/batch-run", summary="Create jobs for multiple sources")
def api_batch_run(request: Request, payload: JobIn):
    user = require_permission(request, "manage_monitoring")
    if payload.source_id is None:
        raise HTTPException(status_code=422, detail={"code": "SOURCE_ID_REQUIRED", "message": "source_id is required", "details": {}})
    return single(create_job(payload.source_id, trigger_type=payload.trigger_type, operator=str(user.get("username") or "api"), force=payload.force))


@router.get("/jobs", summary="List collection jobs")
def api_jobs(request: Request, status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    rows, total = list_jobs(page=page, page_size=page_size, status=status)
    return paginated(add_labels(rows), Pagination(page, page_size, total))


@router.post("/jobs", summary="Create collection job")
def api_create_job(request: Request, payload: JobIn):
    user = require_permission(request, "manage_monitoring")
    if payload.source_id is None:
        raise HTTPException(status_code=422, detail={"code": "SOURCE_ID_REQUIRED", "message": "source_id is required", "details": {}})
    try:
        return single(create_job(payload.source_id, trigger_type=payload.trigger_type, operator=str(user.get("username") or "api"), force=payload.force))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_RUNNING_JOB", "message": str(exc), "details": {}}) from exc


@router.get("/jobs/{job_id}", summary="Get collection job")
def api_job_detail(request: Request, job_id: int):
    require_permission(request, "view_internal")
    rows, _ = list_jobs(page=1, page_size=100)
    for row in rows:
        if row["id"] == job_id:
            return single(add_labels(row))
    raise HTTPException(status_code=404, detail={"code": "COLLECTION_JOB_NOT_FOUND", "message": "collection job not found", "details": {}})


@router.post("/jobs/{job_id}/retry", summary="Process or retry a job")
def api_retry_job(request: Request, job_id: int):
    require_permission(request, "manage_monitoring")
    user = require_permission(request, "manage_monitoring")
    return single(add_labels(retry_job(job_id, operator=str(user.get("username") or "api"))))


@router.post("/jobs/{job_id}/cancel", summary="Cancel a pending collection job")
def api_cancel_job(request: Request, job_id: int):
    require_permission(request, "manage_monitoring")
    try:
        return single(cancel_job(job_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"code": "RUNNING_JOB_CANNOT_BE_CANCELLED", "message": str(exc), "details": {}}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "COLLECTION_JOB_NOT_FOUND", "message": str(exc), "details": {}}) from exc


@router.get("/items", summary="List collection items")
def api_items(request: Request, processing_status: str = "", dedup_status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    rows, total = list_items(page=page, page_size=page_size, processing_status=processing_status, dedup_status=dedup_status)
    return paginated(add_labels(rows), Pagination(page, page_size, total))


@router.get("/items/{item_id}", summary="Get collection item")
def api_item_detail(request: Request, item_id: int):
    require_permission(request, "view_internal")
    rows, _ = list_items(page=1, page_size=100)
    for row in rows:
        if row["id"] == item_id:
            return single(add_labels(row))
    raise HTTPException(status_code=404, detail={"code": "COLLECTION_ITEM_NOT_FOUND", "message": "collection item not found", "details": {}})


@router.post("/items/{item_id}/queue", summary="Queue one collection item for later processing")
def api_queue_item(request: Request, item_id: int):
    require_permission(request, "review_data")
    try:
        return single(queue_item(item_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "COLLECTION_ITEM_NOT_FOUND", "message": str(exc), "details": {}}) from exc


@router.post("/items/batch-queue", summary="Queue one collection item")
def api_batch_queue(request: Request, item_id: int):
    require_permission(request, "review_data")
    return single(queue_item(item_id))


@router.get("/snapshots/{snapshot_id}", summary="Get controlled collection snapshot")
def api_snapshot(request: Request, snapshot_id: int, include_raw: bool = False):
    require_permission(request, "view_sensitive" if include_raw else "view_internal")
    row = snapshot_detail(snapshot_id, include_raw=include_raw)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "SNAPSHOT_NOT_FOUND", "message": "snapshot not found", "details": {}})
    return single(add_labels(row))


@router.get("/dashboard", summary="Collection dashboard")
def api_dashboard(request: Request):
    require_permission(request, "view_internal")
    return single(add_labels(dashboard()))



