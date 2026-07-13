from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.api_common import require_permission, single
from app.services.club_operations_service import ClubMembershipService, ClubOperationError
from app.services.membership_access_service import get_membership_context

router = APIRouter(tags=["Club Context"])


class MembershipApplicationCreate(BaseModel):
    person_id: int
    organization_id: int
    member_type: str = "standard"
    professional_direction: str = ""
    offered_resources: str = ""
    cooperation_needs: str = ""
    application_reason: str
    referrer_name: str = ""
    source_event_id: int | None = None


class MembershipReviewPayload(BaseModel):
    decision: str
    note: str = ""
    person_id: int | None = None
    organization_id: int | None = None
    user_id: int | None = None
    owner: str = ""


class MembershipTransitionPayload(BaseModel):
    action: str
    reason: str = ""
    member_level: str | None = None
    organization_id: int | None = None
    member_role: str | None = None
    expired_at: str | None = None


def _club_context(user: dict[str, Any] | None) -> dict[str, Any]:
    membership_ctx = get_membership_context(user)
    memberships = membership_ctx.get("memberships") or []
    clubs = []
    if memberships:
        clubs.append({"club_id": "legacy-qbay", "name": "Q-BAY\u4ff1\u4e50\u90e8", "membership_count": len(memberships), "memberships": memberships})
    return {"has_club": bool(clubs), "club_count": len(clubs), "default_club_id": clubs[0]["club_id"] if clubs else None, "can_switch": len(clubs) > 1, "clubs": clubs}


@router.get("/me/clubs")
def my_clubs(request: Request):
    user = require_permission(request, "membership.view_self")
    context = _club_context(user)
    return single({"clubs": context["clubs"]})


@router.get("/me/club-context")
def my_club_context(request: Request):
    user = require_permission(request, "membership.view_self")
    return single(_club_context(user))

@router.post("/club/membership-applications")
def create_membership_application(request: Request, payload: MembershipApplicationCreate):
    actor = require_permission(request, "membership.view_self")
    try:
        application = ClubMembershipService().submit_application(
            {**payload.model_dump(), "user_id": int(actor["id"])}, actor_user_id=int(actor["id"]),
        )
    except ClubOperationError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    return single(application)

@router.post("/club/membership-applications/{application_id}/review")
def review_membership_application(request: Request, application_id: int, payload: MembershipReviewPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubMembershipService().review_application(
            application_id, decision=payload.decision, actor=str(actor.get("username") or actor["id"]),
            actor_user_id=int(actor["id"]), note=payload.note, owner=payload.owner,
            person_id=payload.person_id, organization_id=payload.organization_id, user_id=payload.user_id,
        )
    except ClubOperationError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    return single(result)


@router.post("/club/memberships/{membership_id}/transition")
def transition_membership(request: Request, membership_id: int, payload: MembershipTransitionPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubMembershipService().transition_membership(
            membership_id, action=payload.action, reason=payload.reason,
            actor=str(actor.get("username") or actor["id"]), actor_user_id=int(actor["id"]),
            changes=payload.model_dump(exclude={"action", "reason"}, exclude_none=True),
        )
    except ClubOperationError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    return single(result)
