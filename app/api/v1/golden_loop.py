from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.api_common import single
from app.services.golden_loop_service import GoldenLoopService


router = APIRouter(prefix="/golden-loop", tags=["MVP-RC1 golden loop"])


class SubjectLinkPayload(BaseModel):
    subject_type: Literal["person", "organization", "project"]
    subject_id: int = Field(gt=0)


class ResourceFromIntelligencePayload(BaseModel):
    direction: Literal["demand", "supply"]
    title: str = ""
    resource_type: str = "产业合作"
    summary: str = ""
    description: str = ""
    cooperation_mode: str = ""
    cooperation_terms: str = ""


class MatchPayload(BaseModel):
    demand_resource_id: int = Field(gt=0)
    supply_resource_id: int = Field(gt=0)
    note: str = ""


class FollowUpPayload(BaseModel):
    content: str = Field(min_length=1)
    next_action: str = ""
    contact_result: str = ""
    stage_after: str = ""
    next_follow_at: str = ""


class MatchIntentionPayload(BaseModel):
    intention: Literal["interested", "not_interested", "later"]
    reason_code: str = ""
    note: str = ""


class TaskPayload(BaseModel):
    title: str = Field(min_length=1)
    due_date: str = ""
    priority: str = "P2"

class OutcomePayload(BaseModel):
    outcome: Literal["won", "lost", "paused"]
    reason: str = ""
    result_note: str = ""
    cooperation_scale: str = ""
    evidence_text: str = ""


def _actor(request: Request, *, write: bool = False) -> tuple[int, str]:
    security = request.scope.get("security_context", {})
    user = security.get("user") or {}
    if not user.get("id"):
        raise HTTPException(status_code=401, detail="请先登录")
    role = str(user.get("role") or "viewer")
    if write:
        GoldenLoopService.require_writer(role)
    return int(user["id"]), role


@router.get("/workbench")
def workbench(request: Request, db: Session = Depends(get_db)):
    _actor(request)
    return single(GoldenLoopService(db).workbench())


@router.get("/intelligence/{intelligence_id}/trace")
def trace_intelligence(
    intelligence_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _actor(request)
    return single(GoldenLoopService(db).trace(intelligence_id))


@router.post("/intelligence/{intelligence_id}/subjects")
def link_subject(
    intelligence_id: int,
    payload: SubjectLinkPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _actor(request, write=True)
    return single(
        GoldenLoopService(db).link_subject(
            intelligence_id,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            actor_user_id=user_id,
        )
    )


@router.post("/intelligence/{intelligence_id}/resources")
def create_resource(
    intelligence_id: int,
    payload: ResourceFromIntelligencePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _actor(request, write=True)
    fields: dict[str, Any] = payload.model_dump(exclude={"direction"})
    return single(
        GoldenLoopService(db).create_resource_from_intelligence(
            intelligence_id,
            direction=payload.direction,
            actor_user_id=user_id,
            fields=fields,
        )
    )


@router.post("/matches")
def confirm_match(
    payload: MatchPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _actor(request, write=True)
    return single(
        GoldenLoopService(db).confirm_match(
            demand_resource_id=payload.demand_resource_id,
            supply_resource_id=payload.supply_resource_id,
            actor_user_id=user_id,
            note=payload.note,
        )
    )


@router.post("/matches/{match_id}/intention")
def set_match_intention(
    match_id: int,
    payload: MatchIntentionPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _actor(request, write=True)
    return single(
        GoldenLoopService(db).set_match_intention(
            match_id,
            actor_user_id=user_id,
            intention=payload.intention,
            reason_code=payload.reason_code,
            note=payload.note,
        )
    )

@router.get("/matches/{match_id}")
def match_detail(match_id: int, request: Request, db: Session = Depends(get_db)):
    _actor(request)
    return single(GoldenLoopService(db).match_detail(match_id))


@router.post("/matches/{match_id}/convert")
def convert_match(match_id: int, request: Request, db: Session = Depends(get_db)):
    user_id, _ = _actor(request, write=True)
    return single(
        GoldenLoopService(db).convert_match_to_opportunity(
            match_id,
            actor_user_id=user_id,
        )
    )


@router.post("/opportunities/{opportunity_id}/follow-ups")
def add_follow_up(
    opportunity_id: int,
    payload: FollowUpPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, role = _actor(request, write=True)
    service = GoldenLoopService(db)
    opportunity = service._opportunity(opportunity_id)
    if not service.can_manage_opportunity(opportunity, user_id, role):
        raise HTTPException(status_code=403, detail="无权跟进该合作机会")
    return single(
        service.add_follow_up(
            opportunity_id,
            actor_user_id=user_id,
            content=payload.content,
            next_action=payload.next_action,
            contact_result=payload.contact_result,
            stage_after=payload.stage_after,
            next_follow_at=payload.next_follow_at,
        )
    )


@router.post("/opportunities/{opportunity_id}/tasks")
def create_task(
    opportunity_id: int,
    payload: TaskPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, role = _actor(request, write=True)
    service = GoldenLoopService(db)
    opportunity = service._opportunity(opportunity_id)
    if not service.can_manage_opportunity(opportunity, user_id, role):
        raise HTTPException(status_code=403, detail="Opportunity task forbidden")
    return single(
        service.create_task(
            opportunity_id,
            actor_user_id=user_id,
            title=payload.title,
            due_date=payload.due_date,
            priority=payload.priority,
        )
    )

@router.post("/opportunities/{opportunity_id}/outcome")
def close_outcome(
    opportunity_id: int,
    payload: OutcomePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, role = _actor(request, write=True)
    service = GoldenLoopService(db)
    opportunity = service._opportunity(opportunity_id)
    if not service.can_manage_opportunity(opportunity, user_id, role):
        raise HTTPException(status_code=403, detail="无权关闭该合作机会")
    return single(
        service.close_outcome(
            opportunity_id,
            actor_user_id=user_id,
            outcome=payload.outcome,
            reason=payload.reason,
            result_note=payload.result_note,
            cooperation_scale=payload.cooperation_scale,
            evidence_text=payload.evidence_text,
        )
    )
