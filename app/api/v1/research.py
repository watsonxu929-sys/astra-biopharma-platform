from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services.api_common import require_permission, single
from app.services.research import (
    add_topic_subject,
    compare_companies,
    create_company_compare_report,
    create_topic,
    create_topic_report,
    get_topic,
    list_topics,
    refresh_topic,
    remove_topic_subject,
    topic_dashboard,
    topic_network,
    topic_signals,
    topic_timeline,
    track_detail,
    tracks,
)

router = APIRouter(prefix="/research")


class TopicIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    topic_type: str = "custom"
    track_tags: str = ""
    region_filters: str = ""
    period_start: str = ""
    period_end: str = ""


class TopicSubjectIn(BaseModel):
    subject_type: str
    subject_id: str
    inclusion_type: str = "manual"
    reason: str = ""


class CompareIn(BaseModel):
    organization_ids: list[str] = Field(..., min_length=2, max_length=8)


@router.get("/topics")
def api_topics(request: Request, status: str = "", topic_type: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    return list_topics(page=page, page_size=page_size, status=status, topic_type=topic_type)


@router.post("/topics")
def api_create_topic(request: Request, payload: TopicIn):
    user = require_permission(request, "edit_data")
    return single(create_topic(name=payload.name, description=payload.description, topic_type=payload.topic_type, track_tags=payload.track_tags, region_filters=payload.region_filters, period_start=payload.period_start, period_end=payload.period_end, owner_id=user.get("id")))


@router.get("/topics/{topic_id:int}")
def api_topic(request: Request, topic_id: int):
    require_permission(request, "view_internal")
    row = get_topic(topic_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "TOPIC_NOT_FOUND", "message": "璇锋眰鐨勪笓棰樹笉瀛樺湪", "details": {}})
    return single(row)


@router.patch("/topics/{topic_id:int}")
def api_patch_topic(request: Request, topic_id: int, payload: TopicIn):
    require_permission(request, "edit_data")
    row = get_topic(topic_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "TOPIC_NOT_FOUND", "message": "璇锋眰鐨勪笓棰樹笉瀛樺湪", "details": {}})
    # v0.5J keeps topic update conservative; create a refreshed snapshot instead of broad field mutation.
    return single(row)


@router.post("/topics/{topic_id:int}/refresh")
def api_refresh_topic(request: Request, topic_id: int):
    require_permission(request, "review_data")
    return single(refresh_topic(topic_id))


@router.post("/topics/{topic_id:int}/subjects")
def api_add_subject(request: Request, topic_id: int, payload: TopicSubjectIn):
    user = require_permission(request, "edit_data")
    try:
        return single(add_topic_subject(topic_id, payload.subject_type, payload.subject_id, inclusion_type=payload.inclusion_type, reason=payload.reason, added_by=str(user.get("username") or "api")))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "TOPIC_SUBJECT_FAILED", "message": str(exc), "details": {}}) from exc


@router.delete("/topics/{topic_id:int}/subjects/{subject_type}/{subject_id}")
def api_remove_subject(request: Request, topic_id: int, subject_type: str, subject_id: str):
    require_permission(request, "edit_data")
    return single(remove_topic_subject(topic_id, subject_type, subject_id))


@router.get("/topics/{topic_id:int}/dashboard")
def api_topic_dashboard(request: Request, topic_id: int):
    require_permission(request, "view_internal")
    return single(topic_dashboard(topic_id))


@router.get("/topics/{topic_id:int}/timeline")
def api_topic_timeline(request: Request, topic_id: int, event_type: str = "", signal_level: str = ""):
    require_permission(request, "view_internal")
    return topic_timeline(topic_id, event_type=event_type, signal_level=signal_level)


@router.get("/topics/{topic_id:int}/signals")
def api_topic_signals(request: Request, topic_id: int):
    require_permission(request, "view_internal")
    return topic_signals(topic_id)


@router.get("/topics/{topic_id:int}/network")
def api_topic_network(request: Request, topic_id: int, limit: int = Query(120, ge=1, le=300)):
    require_permission(request, "view_internal")
    return single(topic_network(topic_id, limit=limit))


@router.post("/topics/{topic_id:int}/reports")
def api_topic_report(request: Request, topic_id: int):
    user = require_permission(request, "edit_data")
    try:
        return single(create_topic_report(topic_id, created_by=str(user.get("username") or "api")))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "TOPIC_REPORT_FAILED", "message": str(exc), "details": {}}) from exc


@router.post("/companies/compare")
def api_compare(request: Request, payload: CompareIn):
    require_permission(request, "view_internal")
    try:
        return single(compare_companies(payload.organization_ids))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "COMPARE_FAILED", "message": str(exc), "details": {}}) from exc


@router.post("/companies/compare/report")
def api_compare_report(request: Request, payload: CompareIn):
    user = require_permission(request, "edit_data")
    try:
        return single(create_company_compare_report(payload.organization_ids, created_by=str(user.get("username") or "api")))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "COMPARE_REPORT_FAILED", "message": str(exc), "details": {}}) from exc


@router.get("/tracks")
def api_tracks(request: Request, window: str = "30d"):
    require_permission(request, "view_internal")
    return tracks(window=window)


@router.get("/tracks/{track_key}")
def api_track_detail(request: Request, track_key: str, window: str = "30d"):
    require_permission(request, "view_internal")
    return single(track_detail(track_key, window=window))

