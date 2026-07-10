from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.services.api_common import api_user, require_permission, raise_api_error, single
from app.services.authorization_service import AuthorizationError, assign_organization_role, list_user_roles, revoke_organization_role
from app.services.organization_access_service import (
    OrganizationAccessError,
    bind_membership_to_organization,
    bind_user_to_organization,
    create_organization,
    get_accessible_organization_or_403,
    get_organization_context,
    get_user_organizations,
    list_organization_memberships,
    list_organizations,
    require_organization_admin,
    unbind_membership_from_organization,
    unbind_user_from_organization,
    update_organization,
)

router = APIRouter(tags=["Organization Access"])


class OrganizationPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    short_name: str = Field("", max_length=120)
    organization_type: str = Field("company", max_length=80)
    unified_social_credit_code: str = Field("", max_length=80)
    status: str = Field("active", max_length=40)
    source: str = Field("manual", max_length=120)
    description: str = Field("", max_length=2000)


class OrganizationUpdatePayload(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    short_name: str | None = Field(None, max_length=120)
    organization_type: str | None = Field(None, max_length=80)
    unified_social_credit_code: str | None = Field(None, max_length=80)
    status: str | None = Field(None, max_length=40)
    source: str | None = Field(None, max_length=120)
    description: str | None = Field(None, max_length=2000)


class BindUserPayload(BaseModel):
    user_id: int = Field(..., gt=0)
    is_primary: bool = False
    source: str = Field("manual", max_length=120)


class BindMembershipPayload(BaseModel):
    membership_id: int = Field(..., gt=0)
    source: str = Field("manual", max_length=120)


class AssignRolePayload(BaseModel):
    role_key: str = Field(..., min_length=1, max_length=120)


def _handle(exc: OrganizationAccessError | AuthorizationError) -> None:
    raise_api_error(exc.status_code, exc.code, exc.message)


@router.get("/me/organizations")
def my_organizations(request: Request):
    user = require_permission(request, "organization.view_self")
    return single({"organizations": get_user_organizations(int(user["id"]))})


@router.get("/me/organization-context")
def my_organization_context(request: Request):
    user = require_permission(request, "organization.view_self")
    return single(get_organization_context(user))


@router.get("/me/organizations/{organization_id}")
def my_organization_detail(organization_id: int, request: Request):
    user = require_permission(request, "organization.view_self")
    try:
        return single({"organization": get_accessible_organization_or_403(user, organization_id)})
    except OrganizationAccessError as exc:
        _handle(exc)


@router.get("/organizations")
def admin_list_organizations(request: Request):
    user = require_permission(request, "manage_club")
    try:
        require_organization_admin(user)
        return single({"organizations": list_organizations()})
    except OrganizationAccessError as exc:
        _handle(exc)


@router.post("/organizations")
def admin_create_organization(payload: OrganizationPayload, request: Request):
    user = require_permission(request, "manage_club")
    try:
        require_organization_admin(user)
        return single({"organization": create_organization(payload.model_dump(), actor=user)})
    except OrganizationAccessError as exc:
        _handle(exc)


@router.get("/organizations/{organization_id}")
def admin_get_organization(organization_id: int, request: Request):
    user = require_permission(request, "manage_club")
    try:
        require_organization_admin(user)
        org = get_accessible_organization_or_403(user, organization_id, allow_admin=True)
        return single({"organization": org, "memberships": list_organization_memberships(organization_id)})
    except OrganizationAccessError as exc:
        _handle(exc)


@router.patch("/organizations/{organization_id}")
def admin_update_organization(organization_id: int, payload: OrganizationUpdatePayload, request: Request):
    user = require_permission(request, "manage_club")
    body: dict[str, Any] = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        require_organization_admin(user)
        return single({"organization": update_organization(organization_id, body, actor=user)})
    except OrganizationAccessError as exc:
        _handle(exc)


@router.post("/organizations/{organization_id}/users")
def admin_bind_user_to_organization(organization_id: int, payload: BindUserPayload, request: Request):
    user = require_permission(request, "manage_club")
    try:
        require_organization_admin(user)
        return single({"organization": bind_user_to_organization(organization_id, payload.user_id, is_primary=payload.is_primary, source=payload.source, actor=user)})
    except OrganizationAccessError as exc:
        _handle(exc)


@router.delete("/organizations/{organization_id}/users/{user_id}")
def admin_unbind_user_from_organization(organization_id: int, user_id: int, request: Request):
    actor = require_permission(request, "manage_club")
    try:
        require_organization_admin(actor)
        return single(unbind_user_from_organization(organization_id, user_id, actor=actor))
    except OrganizationAccessError as exc:
        _handle(exc)


@router.post("/organizations/{organization_id}/memberships")
def admin_bind_membership_to_organization(organization_id: int, payload: BindMembershipPayload, request: Request):
    user = require_permission(request, "manage_club")
    try:
        require_organization_admin(user)
        return single({"link": bind_membership_to_organization(organization_id, payload.membership_id, source=payload.source, actor=user)})
    except OrganizationAccessError as exc:
        _handle(exc)


@router.delete("/organizations/{organization_id}/memberships/{membership_id}")
def admin_unbind_membership_from_organization(organization_id: int, membership_id: int, request: Request):
    actor = require_permission(request, "manage_club")
    try:
        require_organization_admin(actor)
        return single(unbind_membership_from_organization(organization_id, membership_id, actor=actor))
    except OrganizationAccessError as exc:
        _handle(exc)

@router.get("/organizations/{organization_id}/users/{user_id}/roles")
def admin_get_organization_user_roles(organization_id: int, user_id: int, request: Request):
    actor = api_user(request)
    try:
        return single({"roles": list_user_roles(organization_id, user_id, actor)})
    except AuthorizationError as exc:
        _handle(exc)


@router.post("/organizations/{organization_id}/users/{user_id}/roles")
def admin_assign_organization_user_role(organization_id: int, user_id: int, payload: AssignRolePayload, request: Request):
    actor = api_user(request)
    try:
        return single({"assignment": assign_organization_role(actor, organization_id, user_id, payload.role_key)})
    except AuthorizationError as exc:
        _handle(exc)


@router.delete("/organizations/{organization_id}/users/{user_id}/roles/{role_id}")
def admin_revoke_organization_user_role(organization_id: int, user_id: int, role_id: int, request: Request):
    actor = api_user(request)
    try:
        return single(revoke_organization_role(actor, organization_id, user_id, role_id))
    except AuthorizationError as exc:
        _handle(exc)



