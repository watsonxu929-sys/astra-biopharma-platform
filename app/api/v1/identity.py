from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Request

from app.services.api_common import api_user, require_permission, raise_api_error, single
from app.services.identity_link_service import (
    IdentityLinkError,
    approve_link_request,
    cancel_link_request,
    create_link_request,
    identity_context,
    reject_link_request,
    unlink_user_person,
)

router = APIRouter(tags=["Identity"])


class PersonLinkPayload(BaseModel):
    person_id: int = Field(..., gt=0)
    reason: str = Field("", max_length=500)


class RejectPayload(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class UnlinkPayload(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


def _handle(exc: IdentityLinkError) -> None:
    raise_api_error(exc.status_code, exc.code, exc.message)


@router.get("/me/identity")
def my_identity(request: Request):
    user = require_permission(request, "identity.view_self")
    try:
        return single(identity_context(int(user["id"])))
    except IdentityLinkError as exc:
        _handle(exc)


@router.post("/me/person-link")
def request_person_link(payload: PersonLinkPayload, request: Request):
    user = require_permission(request, "identity.request_link")
    try:
        return single(create_link_request(int(user["id"]), payload.person_id, payload.reason, user))
    except IdentityLinkError as exc:
        _handle(exc)


@router.delete("/me/person-link")
def cancel_person_link(request: Request):
    user = require_permission(request, "identity.request_link")
    try:
        return single(cancel_link_request(int(user["id"]), user))
    except IdentityLinkError as exc:
        _handle(exc)


@router.post("/identity/link-requests/{request_id}/approve")
def approve_person_link_request(request_id: int, request: Request):
    actor = require_permission(request, "identity.review_link")
    try:
        return single(approve_link_request(request_id, actor))
    except IdentityLinkError as exc:
        _handle(exc)


@router.post("/identity/link-requests/{request_id}/reject")
def reject_person_link_request(request_id: int, payload: RejectPayload, request: Request):
    actor = require_permission(request, "identity.review_link")
    try:
        return single(reject_link_request(request_id, payload.reason, actor))
    except IdentityLinkError as exc:
        _handle(exc)


@router.delete("/identity/users/{user_id}/person-link")
def unlink_person_from_user(user_id: int, payload: UnlinkPayload, request: Request):
    actor = require_permission(request, "identity.unlink")
    try:
        return single(unlink_user_person(user_id, payload.reason, actor))
    except IdentityLinkError as exc:
        _handle(exc)
