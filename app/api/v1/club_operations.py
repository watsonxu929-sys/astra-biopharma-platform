from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.api_common import require_permission, single
from app.services.club_operations_service import ClubEventService, ClubOperationError, ClubOperationsDashboardService, ClubResourceMatchingService

router = APIRouter(tags=["Club Operations"])


class EventTransitionPayload(BaseModel):
    action: str
    note: str = ""


class EventRegistrationPayload(BaseModel):
    membership_id: int | None = None
    person_id: int | None = None
    organization_id: int | None = None
    applicant_name: str
    organization_name: str = ""
    title: str = ""
    mobile: str = ""
    email: str = ""
    application_reason: str = ""
    interest_direction: str = ""
    desired_connections: str = ""
    offered_resources: str = ""
    current_needs: str = ""


class RegistrationReviewPayload(BaseModel):
    decision: str
    note: str = ""


class CheckinTokenPayload(BaseModel):
    registration_id: int
    valid_minutes: int = 240


class CheckinPayload(BaseModel):
    registration_id: int | None = None
    token: str = ""
    supplement: bool = False


class CheckinUndoPayload(BaseModel):
    reason: str


class FeedbackPayload(BaseModel):
    content_score: int | None = None
    speaker_score: int | None = None
    organization_score: int | None = None
    satisfaction_score: int | None = None
    content_feedback: str = ""
    interested_people: str = ""
    interested_organizations: str = ""
    cooperation_intent: str = ""
    new_demand: str = ""
    new_supply: str = ""
    suggestions: str = ""


class ResourceReviewPayload(BaseModel):
    decision: str
    note: str = ""


class CandidateReviewPayload(BaseModel):
    decision: str
    note: str = ""

def _raise(exc: ClubOperationError) -> None:
    raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/club/events/{club_event_id}/transition")
def transition_event(request: Request, club_event_id: int, payload: EventTransitionPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubEventService().transition_event(
            club_event_id, action=payload.action, note=payload.note,
            actor=str(actor.get("username") or actor["id"]), actor_user_id=int(actor["id"]),
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/events/{club_event_id}/registrations")
def register_for_event(request: Request, club_event_id: int, payload: EventRegistrationPayload):
    actor = require_permission(request, "membership.view_self")
    try:
        result = ClubEventService().register(
            club_event_id, {**payload.model_dump(), "user_id": int(actor["id"]), "registration_source": "member"},
            actor_user_id=int(actor["id"]),
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/events/{club_event_id}/registrations/{registration_id}/review")
def review_registration(request: Request, club_event_id: int, registration_id: int, payload: RegistrationReviewPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubEventService().review_registration(
            club_event_id, registration_id, decision=payload.decision, note=payload.note,
            actor=str(actor.get("username") or actor["id"]), actor_user_id=int(actor["id"]),
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/events/{club_event_id}/checkin-token")
def issue_checkin_token(request: Request, club_event_id: int, payload: CheckinTokenPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubEventService().issue_checkin_token(
            club_event_id, payload.registration_id, actor_user_id=int(actor["id"]),
            valid_minutes=payload.valid_minutes,
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/events/{club_event_id}/checkin")
def check_in(request: Request, club_event_id: int, payload: CheckinPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubEventService().check_in(
            club_event_id, registration_id=payload.registration_id, token=payload.token,
            actor=str(actor.get("username") or actor["id"]), actor_user_id=int(actor["id"]),
            method="token" if payload.token else "manual", supplement=payload.supplement,
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/events/{club_event_id}/registrations/{registration_id}/undo-checkin")
def undo_checkin(request: Request, club_event_id: int, registration_id: int, payload: CheckinUndoPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubEventService().undo_checkin(
            club_event_id, registration_id, reason=payload.reason,
            actor=str(actor.get("username") or actor["id"]), actor_user_id=int(actor["id"]),
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/events/{club_event_id}/registrations/{registration_id}/feedback")
def submit_feedback(request: Request, club_event_id: int, registration_id: int, payload: FeedbackPayload):
    actor = require_permission(request, "membership.view_self")
    try:
        result = ClubEventService().submit_feedback(
            club_event_id, registration_id, payload.model_dump(), actor_user_id=int(actor["id"]),
        )
        deposition = ClubResourceMatchingService().deposit_feedback(result["id"], actor_user_id=int(actor["id"]))
    except ClubOperationError as exc:
        _raise(exc)
    return single({"feedback": result, "deposition": deposition})

@router.post("/club/resources/{resource_id}/review")
def review_club_resource(request: Request, resource_id: int, payload: ResourceReviewPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubResourceMatchingService().review_resource(
            resource_id, decision=payload.decision, note=payload.note,
            actor=str(actor.get("username") or actor["id"]), actor_user_id=int(actor["id"]),
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/resource-matches/generate")
def generate_resource_matches(request: Request):
    require_permission(request, "manage_club")
    return single({"created": ClubResourceMatchingService().generate_matches()})


@router.post("/club/resource-matches/{match_id}/review")
def review_resource_match(request: Request, match_id: int, payload: CandidateReviewPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubResourceMatchingService().review_match(
            match_id, decision=payload.decision, note=payload.note,
            actor=str(actor.get("username") or actor["id"]), actor_user_id=int(actor["id"]),
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/resource-matches/{match_id}/lead-candidate")
def create_match_lead(request: Request, match_id: int):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubResourceMatchingService().create_lead_from_match(
            match_id, actor=str(actor.get("username") or actor["id"]), actor_user_id=int(actor["id"]),
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)


@router.post("/club/events/{club_event_id}/relationship-candidates")
def generate_event_relationships(request: Request, club_event_id: int):
    require_permission(request, "manage_club")
    try:
        result = ClubResourceMatchingService().generate_event_relationship_candidates(club_event_id)
    except ClubOperationError as exc:
        _raise(exc)
    return single({"created": result})


@router.post("/club/relationship-candidates/{candidate_id}/review")
def review_event_relationship(request: Request, candidate_id: int, payload: CandidateReviewPayload):
    actor = require_permission(request, "manage_club")
    try:
        result = ClubResourceMatchingService().review_event_relationship(
            candidate_id, decision=payload.decision, note=payload.note,
            actor=str(actor.get("username") or actor["id"]),
        )
    except ClubOperationError as exc:
        _raise(exc)
    return single(result)

@router.get("/club/operations")
def club_operations_dashboard(request: Request):
    require_permission(request, "manage_club")
    return single(ClubOperationsDashboardService().summary())


@router.get("/club/domain-events")
def club_domain_events(request: Request, status: str = "pending", limit: int = 100):
    require_permission(request, "manage_club")
    return single({"items": ClubOperationsDashboardService().domain_events(status=status, limit=limit)})
