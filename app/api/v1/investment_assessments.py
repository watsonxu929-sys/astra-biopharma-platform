from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services.api_common import require_permission, single
from app.services.research import approve_assessment, convert_assessment_to_lead, generate_assessment, get_assessment, list_assessments, reject_assessment

router = APIRouter(prefix="/investment-assessments")


class AssessmentIn(BaseModel):
    organization_id: str = Field(..., min_length=1)
    topic_id: int | None = None
    assessment_type: str = "single_company"


@router.get("")
def api_list(request: Request, status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    return list_assessments(page=page, page_size=page_size, status=status)


@router.post("")
def api_create(request: Request, payload: AssessmentIn):
    require_permission(request, "edit_data")
    try:
        return single(generate_assessment(payload.organization_id, topic_id=payload.topic_id, assessment_type=payload.assessment_type))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "ORGANIZATION_NOT_FOUND", "message": "请求的企业不存在", "details": {}}) from exc


@router.get("/{assessment_id}")
def api_get(request: Request, assessment_id: int):
    require_permission(request, "view_internal")
    row = get_assessment(assessment_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "ASSESSMENT_NOT_FOUND", "message": "请求的研判不存在", "details": {}})
    return single(row)


@router.post("/{assessment_id}/generate")
def api_generate(request: Request, assessment_id: int):
    require_permission(request, "edit_data")
    row = get_assessment(assessment_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "ASSESSMENT_NOT_FOUND", "message": "请求的研判不存在", "details": {}})
    return single(generate_assessment(row["organization_id"], topic_id=row.get("topic_id"), assessment_type=row.get("assessment_type") or "single_company"))


@router.post("/{assessment_id}/approve")
def api_approve(request: Request, assessment_id: int):
    user = require_permission(request, "review_data")
    return single(approve_assessment(assessment_id, actor=str(user.get("username") or "api")))


@router.post("/{assessment_id}/reject")
def api_reject(request: Request, assessment_id: int):
    user = require_permission(request, "review_data")
    return single(reject_assessment(assessment_id, actor=str(user.get("username") or "api")))


@router.post("/{assessment_id}/convert-lead")
def api_convert(request: Request, assessment_id: int):
    user = require_permission(request, "review_data")
    try:
        return single(convert_assessment_to_lead(assessment_id, actor=str(user.get("username") or "api")))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"code": "ASSESSMENT_NOT_APPROVED", "message": "招商研判批准后才能转为线索", "details": {}}) from exc
