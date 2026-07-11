from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Request

from app.services.api_common import api_user, require_permission, raise_api_error, single
from app.services.membership_access_service import (
    MembershipAccessError,
    get_accessible_membership,
    get_accessible_membership_or_403,
    get_accessible_memberships,
    get_membership_context,
    require_membership_admin,
)
from app.services.membership_user_link_service import (
    MembershipUserLinkError,
    approve_membership_link,
    bind_user,
    get_link_info,
    get_link_request,
    get_memberships_for_user,
    is_membership_owned_by_user,
    list_link_audit,
    reject_membership_link,
    request_membership_link,
    unbind_user,
)

router = APIRouter(tags=["Membership User Link"])


class BindUserPayload(BaseModel):
    user_id: int = Field(..., gt=0)
    reason: str = Field("", max_length=500)


class UnlinkPayload(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class RequestLinkPayload(BaseModel):
    membership_id: int = Field(..., gt=0)
    reason: str = Field("", max_length=500)


class RejectPayload(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


def _handle(exc: MembershipUserLinkError) -> None:
    raise_api_error(exc.status_code, exc.code, exc.message)


def _handle_access(exc: MembershipAccessError) -> None:
    raise_api_error(exc.status_code, exc.code, exc.message)


@router.get("/me/memberships")
def my_memberships(request: Request):
    user = require_permission(request, "membership.view_self")
    try:
        return single({"memberships": get_accessible_memberships(user)})
    except MembershipAccessError as exc:
        _handle_access(exc)


@router.get("/me/membership-context")
def my_membership_context(request: Request):
    user = api_user(request)
    try:
        return single(get_membership_context(user))
    except MembershipAccessError as exc:
        _handle_access(exc)


@router.get("/me/memberships/{membership_id}")
def my_membership_detail(membership_id: int, request: Request):
    user = require_permission(request, "membership.view_self")
    try:
        member = get_accessible_membership_or_403(user, membership_id)
        link_info = get_link_info(membership_id)
        return single({"membership": member, "user_link": link_info})
    except MembershipAccessError as exc:
        _handle_access(exc)
    except MembershipUserLinkError as exc:
        _handle(exc)


@router.get("/memberships/{membership_id}/user-link")
def get_membership_user_link(membership_id: int, request: Request):
    user = require_permission(request, "manage_club")
    try:
        get_accessible_membership_or_403(user, membership_id, allow_admin=True)
        return single(get_link_info(membership_id))
    except MembershipAccessError as exc:
        _handle_access(exc)
    except MembershipUserLinkError as exc:
        _handle(exc)


@router.post("/memberships/{membership_id}/user-link")
def bind_membership_user(membership_id: int, payload: BindUserPayload, request: Request):
    actor = require_permission(request, "manage_club")
    try:
        require_membership_admin(actor)
        return single(bind_user(membership_id, payload.user_id, payload.reason, actor.get("username")))
    except MembershipAccessError as exc:
        _handle_access(exc)
    except MembershipUserLinkError as exc:
        _handle(exc)


@router.delete("/memberships/{membership_id}/user-link")
def unbind_membership_user(membership_id: int, payload: UnlinkPayload, request: Request):
    actor = require_permission(request, "manage_club")
    try:
        require_membership_admin(actor)
        return single(unbind_user(membership_id, payload.reason, actor.get("username")))
    except MembershipAccessError as exc:
        _handle_access(exc)
    except MembershipUserLinkError as exc:
        _handle(exc)


@router.post("/me/membership-link-requests")
def request_my_membership_link(payload: RequestLinkPayload, request: Request):
    user = require_permission(request, "membership.user_link.request")
    try:
        return single(request_membership_link(int(user["id"]), payload.membership_id, payload.reason))
    except MembershipUserLinkError as exc:
        _handle(exc)


@router.get("/membership-link-requests/{request_id}")
def get_membership_link_request(request_id: int, request: Request):
    user = require_permission(request, "manage_club")
    try:
        return single(get_link_request(request_id))
    except MembershipUserLinkError as exc:
        _handle(exc)


@router.post("/membership-link-requests/{request_id}/approve")
def approve_my_membership_link_request(request_id: int, request: Request):
    actor = require_permission(request, "manage_club")
    try:
        require_membership_admin(actor)
        return single(approve_membership_link(request_id, actor))
    except MembershipAccessError as exc:
        _handle_access(exc)
    except MembershipUserLinkError as exc:
        _handle(exc)


@router.post("/membership-link-requests/{request_id}/reject")
def reject_my_membership_link_request(request_id: int, payload: RejectPayload, request: Request):
    actor = require_permission(request, "manage_club")
    try:
        require_membership_admin(actor)
        return single(reject_membership_link(request_id, payload.reason, actor))
    except MembershipAccessError as exc:
        _handle_access(exc)
    except MembershipUserLinkError as exc:
        _handle(exc)


@router.get("/memberships/{membership_id}/user-link/audit")
def get_membership_user_link_audit(membership_id: int, request: Request):
    user = require_permission(request, "manage_club")
    try:
        get_accessible_membership_or_403(user, membership_id, allow_admin=True)
        return single({"audit": list_link_audit(membership_id)})
    except MembershipAccessError as exc:
        _handle_access(exc)
    except MembershipUserLinkError as exc:
        _handle(exc)

