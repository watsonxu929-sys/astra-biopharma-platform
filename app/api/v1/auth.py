from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.services.api_common import api_user, raise_api_error, single
from app.services.authorization_service import (
    AuthorizationError,
    build_authorization_context,
    list_permissions_for_actor,
    list_roles_for_actor,
)

router = APIRouter(tags=["Authorization"])


def _handle(exc: AuthorizationError) -> None:
    raise_api_error(exc.status_code, exc.code, exc.message)


@router.get("/me/authorization-context")
def my_authorization_context(request: Request, organization_id: int | None = Query(None), membership_id: int | None = Query(None)):
    user = api_user(request)
    try:
        ctx = build_authorization_context(user, organization_id=organization_id, membership_id=membership_id)
        return single(ctx.to_dict())
    except AuthorizationError as exc:
        _handle(exc)


@router.get("/auth/roles")
def auth_roles(request: Request, organization_id: int | None = Query(None)):
    user = api_user(request)
    try:
        return single({"roles": list_roles_for_actor(user, organization_id=organization_id)})
    except AuthorizationError as exc:
        _handle(exc)


@router.get("/auth/permissions")
def auth_permissions(request: Request, organization_id: int | None = Query(None)):
    user = api_user(request)
    try:
        return single({"permissions": list_permissions_for_actor(user, organization_id=organization_id)})
    except AuthorizationError as exc:
        _handle(exc)
