from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services.api_common import require_permission, single
from app.services.research import (
    ResearchAgentService,
    add_research_question,
    classify_event_relation,
    compare_companies_research,
    compare_track_research,
    create_finding,
    create_research_report,
    event_timeline,
    get_event,
    get_research_report,
    list_conflicts,
    publish_research_report,
    resolve_conflict,
    review_finding,
    review_research_report,
    submit_finding,
    submit_research_report,
    topic_workspace,
)

router = APIRouter(prefix="/research-fusion", tags=["P2.3 research fusion"])


class EventPairIn(BaseModel):
    left: dict
    right: dict


class QuestionIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


class FindingIn(BaseModel):
    finding_type: str
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=10000)
    assertion_ids: list[int] = Field(default_factory=list)
    confidence: int | None = Field(None, ge=0, le=100)


class ReviewIn(BaseModel):
    decision: str
    note: str = ""


class ConflictResolveIn(BaseModel):
    adopted_value: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=2)


class CompareIn(BaseModel):
    organization_ids: list[str] = Field(..., min_length=2, max_length=8)


class ReportIn(BaseModel):
    report_type: str = "topic_report"


class AgentIn(BaseModel):
    provider_name: str = "rule"


@router.get("/topics/{topic_id}/workspace")
def api_workspace(request: Request, topic_id: int):
    require_permission(request, "view_internal")
    try:
        return single(topic_workspace(topic_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "TOPIC_NOT_FOUND", "message": str(exc), "details": {}}) from exc


@router.post("/topics/{topic_id}/questions")
def api_question(request: Request, topic_id: int, payload: QuestionIn):
    user = require_permission(request, "edit_data")
    return single(add_research_question(topic_id, payload.question, actor=str(user.get("username") or "api")))


@router.get("/events")
def api_events(
    request: Request,
    topic_id: int = 0,
    subject_type: str = "",
    subject_id: str = "",
    event_type: str = "",
):
    require_permission(request, "view_internal")
    return {"data": event_timeline(topic_id=topic_id or None, subject_type=subject_type, subject_id=subject_id, event_type=event_type)}


@router.get("/events/{event_id}")
def api_event(request: Request, event_id: int):
    require_permission(request, "view_internal")
    row = get_event(event_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": "产业事件不存在", "details": {}})
    return single(row)


@router.post("/events/classify-relation")
def api_classify_relation(request: Request, payload: EventPairIn):
    require_permission(request, "review_data")
    return single(classify_event_relation(payload.left, payload.right))


@router.get("/conflicts")
def api_conflicts(request: Request, topic_id: int = 0, status: str = ""):
    require_permission(request, "view_internal")
    return {"data": list_conflicts(topic_id=topic_id or None, status=status)}


@router.post("/conflicts/{conflict_id}/resolve")
def api_resolve_conflict(request: Request, conflict_id: int, payload: ConflictResolveIn):
    user = require_permission(request, "review_data")
    return single(resolve_conflict(
        conflict_id,
        adopted_value=payload.adopted_value,
        reason=payload.reason,
        actor=str(user.get("username") or "api"),
    ))


@router.post("/topics/{topic_id}/findings")
def api_finding(request: Request, topic_id: int, payload: FindingIn):
    user = require_permission(request, "edit_data")
    return single(create_finding(
        topic_id,
        finding_type=payload.finding_type,
        title=payload.title,
        content=payload.content,
        assertion_ids=payload.assertion_ids,
        confidence=payload.confidence,
        actor=str(user.get("username") or "api"),
    ))


@router.post("/findings/{finding_id}/submit")
def api_submit_finding(request: Request, finding_id: int):
    user = require_permission(request, "edit_data")
    return single(submit_finding(finding_id, actor=str(user.get("username") or "api")))


@router.post("/findings/{finding_id}/review")
def api_review_finding(request: Request, finding_id: int, payload: ReviewIn):
    user = require_permission(request, "review_data")
    return single(review_finding(
        finding_id,
        decision=payload.decision,
        actor=str(user.get("username") or "api"),
        note=payload.note,
    ))


@router.post("/topics/{topic_id}/agent-draft")
def api_agent_draft(request: Request, topic_id: int, payload: AgentIn):
    user = require_permission(request, "edit_data")
    return single(ResearchAgentService().generate_draft(
        topic_id,
        provider_name=payload.provider_name,
        actor=str(user.get("username") or "api"),
    ))


@router.post("/topics/{topic_id}/reports")
def api_report_create(request: Request, topic_id: int, payload: ReportIn):
    user = require_permission(request, "edit_data")
    return single(create_research_report(
        topic_id,
        report_type=payload.report_type,
        created_by=str(user.get("username") or "api"),
    ))


@router.get("/reports/{report_id}")
def api_report(request: Request, report_id: int):
    require_permission(request, "view_internal")
    row = get_research_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND", "message": "研究报告不存在", "details": {}})
    return single(row)


@router.post("/reports/{report_id}/submit")
def api_report_submit(request: Request, report_id: int):
    user = require_permission(request, "edit_data")
    return single(submit_research_report(report_id, actor=str(user.get("username") or "api")))


@router.post("/reports/{report_id}/review")
def api_report_review(request: Request, report_id: int, payload: ReviewIn):
    user = require_permission(request, "review_data")
    return single(review_research_report(
        report_id,
        decision=payload.decision,
        actor=str(user.get("username") or "api"),
        note=payload.note,
    ))


@router.post("/reports/{report_id}/publish")
def api_report_publish(request: Request, report_id: int):
    user = require_permission(request, "review_data")
    return single(publish_research_report(report_id, actor=str(user.get("username") or "api")))


@router.post("/companies/compare")
def api_compare(request: Request, payload: CompareIn):
    require_permission(request, "view_internal")
    return single(compare_companies_research(payload.organization_ids))


@router.get("/tracks/{track_key}")
def api_track(request: Request, track_key: str):
    require_permission(request, "view_internal")
    return single(compare_track_research(track_key))
