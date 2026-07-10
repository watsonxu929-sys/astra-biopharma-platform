from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.api_common import require_permission, single
from app.services.api_subject_service import get_subject, list_subjects, subject_collection

router = APIRouter(prefix="/subjects")


@router.get("", summary="List subjects", description="List organizations, people and projects with database pagination and whitelist sorting.")
def subjects_list(
    request: Request,
    subject_type: str = "",
    q: str = Query("", max_length=200),
    status: str = "",
    region: str = "",
    industry: str = "",
    inactive: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = "name",
    order: str = "asc",
):
    require_permission(request, "view_internal")
    try:
        return list_subjects(subject_type=subject_type, q=q, status=status, region=region, industry=industry, inactive=inactive, page=page, page_size=page_size, sort=sort, order=order)
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "INVALID_SUBJECT_TYPE", "message": "不支持的主体类型", "details": {"subject_type": subject_type}})


@router.get("/{subject_type}/{subject_id}", summary="Get subject detail", description="Return a safe subject profile summary without raw full text or private contacts.")
def subject_detail(request: Request, subject_type: str, subject_id: str):
    require_permission(request, "view_internal")
    try:
        data = get_subject(subject_type, subject_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "INVALID_SUBJECT_TYPE", "message": "不支持的主体类型", "details": {"subject_type": subject_type}})
    if not data:
        raise HTTPException(status_code=404, detail={"code": "SUBJECT_NOT_FOUND", "message": "主体不存在", "details": {}})
    return single(data)


def _collection(request: Request, subject_type: str, subject_id: str, kind: str, page: int, page_size: int):
    require_permission(request, "view_internal")
    data = subject_collection(subject_type, subject_id, kind, page=page, page_size=page_size)
    if not data["meta"].get("subject_found", True):
        raise HTTPException(status_code=404, detail={"code": "SUBJECT_NOT_FOUND", "message": "主体不存在", "details": {}})
    return data


@router.get("/{subject_type}/{subject_id}/relationships", summary="Subject relationships")
def subject_relationships(request: Request, subject_type: str, subject_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return _collection(request, subject_type, subject_id, "relationships", page, page_size)


@router.get("/{subject_type}/{subject_id}/timeline", summary="Subject event timeline")
def subject_timeline(request: Request, subject_type: str, subject_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return _collection(request, subject_type, subject_id, "timeline", page, page_size)


@router.get("/{subject_type}/{subject_id}/sources", summary="Subject sources")
def subject_sources(request: Request, subject_type: str, subject_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return _collection(request, subject_type, subject_id, "sources", page, page_size)


@router.get("/{subject_type}/{subject_id}/actions", summary="Subject actions")
def subject_actions(request: Request, subject_type: str, subject_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return _collection(request, subject_type, subject_id, "actions", page, page_size)


@router.get("/{subject_type}/{subject_id}/reviews", summary="Subject review summary")
def subject_reviews(request: Request, subject_type: str, subject_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return _collection(request, subject_type, subject_id, "reviews", page, page_size)
