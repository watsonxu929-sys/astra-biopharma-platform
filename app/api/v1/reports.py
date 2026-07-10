from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.i18n.helpers import add_labels
from app.services.api_common import require_permission, single
from app.services.reports import archive_report, approve_report, create_report_job, generate_report, get_report, list_report_jobs, list_reports, report_citations, submit_report, update_report

router = APIRouter(prefix="/reports")


class ReportJobIn(BaseModel):
    report_type: str = "daily"
    period_start: str = ""
    period_end: str = ""
    filters: dict = {}
    run_now: bool = True


class ReportPatch(BaseModel):
    title: str | None = None
    summary: str | None = None
    content_markdown: str | None = None


@router.get("", summary="List reports")
def reports_list(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str = "", report_type: str = ""):
    require_permission(request, "view_internal")
    return add_labels(list_reports(page=page, page_size=page_size, status=status, report_type=report_type))


@router.post("/jobs", summary="Create report generation job")
def reports_create_job(request: Request, payload: ReportJobIn):
    user = require_permission(request, "review_data")
    try:
        job = create_report_job(report_type=payload.report_type, period_start=payload.period_start, period_end=payload.period_end, filters=payload.filters, generated_by=str(user.get("username") or "api"))
        if payload.run_now:
            return single(add_labels(generate_report(job["id"])))
        return single(add_labels(job))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REPORT_JOB", "message": str(exc), "details": {}}) from exc


@router.get("/jobs/{job_id}", summary="Get report job")
def reports_job(request: Request, job_id: int):
    require_permission(request, "view_internal")
    data = list_report_jobs(page=1, page_size=100)
    for row in data["data"]:
        if row["id"] == job_id:
            return single(add_labels(row))
    raise HTTPException(status_code=404, detail={"code": "REPORT_JOB_NOT_FOUND", "message": "report job not found", "details": {}})


@router.get("/{report_id}", summary="Get report")
def report_detail(request: Request, report_id: int):
    require_permission(request, "view_internal")
    row = get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND", "message": "report not found", "details": {}})
    return single(add_labels(row))


@router.patch("/{report_id}", summary="Edit report draft")
def report_update(request: Request, report_id: int, payload: ReportPatch):
    require_permission(request, "review_data")
    row = update_report(report_id, title=payload.title, summary=payload.summary, content_markdown=payload.content_markdown)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND", "message": "report not found", "details": {}})
    return single(add_labels(row))


@router.post("/{report_id}/submit")
def report_submit(request: Request, report_id: int):
    user = require_permission(request, "review_data")
    return single(add_labels(submit_report(report_id, actor=str(user.get("username") or "api"))))


@router.post("/{report_id}/approve")
def report_approve(request: Request, report_id: int):
    user = require_permission(request, "review_data")
    return single(add_labels(approve_report(report_id, actor=str(user.get("username") or "api"))))


@router.post("/{report_id}/archive")
def report_archive(request: Request, report_id: int):
    user = require_permission(request, "review_data")
    return single(add_labels(archive_report(report_id, actor=str(user.get("username") or "api"))))


@router.get("/{report_id}/citations")
def report_refs(request: Request, report_id: int):
    require_permission(request, "view_internal")
    return single({"citations": report_citations(report_id)})


