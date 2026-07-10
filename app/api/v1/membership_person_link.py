﻿from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Request

from app.services.api_common import api_user, require_permission, raise_api_error, single
from app.services.membership_person_link_service import (
    MembershipPersonLinkError,
    bind_person,
    get_link_info,
    get_person_candidates,
    list_link_audit,
    list_memberships_for_person,
    unbind_person,
)

router = APIRouter(tags=["Membership Person Link"])


class BindPayload(BaseModel):
    person_id: int = Field(..., gt=0)
    reason: str = Field("", max_length=500)


class UnbindPayload(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


def _handle(exc: MembershipPersonLinkError) -> None:
    raise_api_error(exc.status_code, exc.code, exc.message)


@router.get("/memberships/{membership_id}/person-link")
def get_membership_person_link(membership_id: int, request: Request):
    require_permission(request, "manage_club")
    try:
        return single(get_link_info(membership_id))
    except MembershipPersonLinkError as exc:
        _handle(exc)


@router.post("/memberships/{membership_id}/person-link")
def bind_membership_to_person(membership_id: int, payload: BindPayload, request: Request):
    actor = require_permission(request, "manage_club")
    try:
        return single(bind_person(membership_id, payload.person_id, payload.reason, actor.get("username") or "system"))
    except MembershipPersonLinkError as exc:
        _handle(exc)


@router.delete("/memberships/{membership_id}/person-link")
def unbind_membership_person(membership_id: int, payload: UnbindPayload, request: Request):
    actor = require_permission(request, "manage_club")
    try:
        return single(unbind_person(membership_id, payload.reason, actor.get("username") or "system"))
    except MembershipPersonLinkError as exc:
        _handle(exc)


@router.get("/memberships/{membership_id}/person-candidates")
def get_membership_person_candidates(membership_id: int, request: Request):
    require_permission(request, "manage_club")
    try:
        return {"items": get_person_candidates(membership_id)}
    except MembershipPersonLinkError as exc:
        _handle(exc)


@router.get("/memberships/{membership_id}/person-link/audit")
def get_membership_link_audit(membership_id: int, request: Request):
    require_permission(request, "manage_club")
    try:
        return {"items": list_link_audit(membership_id)}
    except MembershipPersonLinkError as exc:
        _handle(exc)


@router.get("/persons/{person_id}/memberships")
def get_person_memberships(person_id: int, request: Request):
    require_permission(request, "manage_club")
    try:
        return {"items": list_memberships_for_person(person_id)}
    except MembershipPersonLinkError as exc:
        _handle(exc)

