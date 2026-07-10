from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, Request

from app.security import auth_disabled, permissions_for
from app.services.api_common import current_scope, require_permission
from app.services.membership_access_service import get_membership_context
from app.services.navigation_service import get_client_navigation
from app.services.organization_access_service import get_organization_context
from app.v04c_review import db_connection

router = APIRouter(prefix="/client", tags=["Client Bootstrap"])
VALID_CLIENTS = {"web", "app", "miniprogram"}


def _safe_client(client: str) -> str:
    return client if client in VALID_CLIENTS else "web"


def _club_context(user: dict[str, Any] | None) -> dict[str, Any] | None:
    membership_ctx = get_membership_context(user)
    memberships = membership_ctx.get("memberships") or []
    if not memberships:
        return None
    return {"club_id": "legacy-qbay", "name": "Q-BAY俱乐部", "membership_count": len(memberships), "has_club": True}


def _current_person(user_id: int | None) -> dict[str, Any] | None:
    if user_id is None:
        return None
    try:
        with db_connection() as conn:
            row = conn.execute(
                """
                SELECT p.id,p.external_id,p.name,p.public_role,p.organization_network
                FROM people p JOIN identity_link_requests l ON p.id=l.person_id
                WHERE l.user_id=? AND l.status='approved' AND p.is_active=1
                ORDER BY l.id DESC LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error:
        return None


def _todo_counts(user_id: int | None) -> dict[str, int]:
    if user_id is None:
        return {"pending_intents": 0, "tasks": 0, "club_applications": 0}
    try:
        with db_connection() as conn:
            tasks = conn.execute("SELECT COUNT(*) AS c FROM v06_collab_tasks WHERE owner_id=? AND status!='completed'", (user_id,)).fetchone()["c"]
            intents = conn.execute("SELECT COUNT(*) AS c FROM v06_contact_intents WHERE from_user_id=? AND status='pending'", (user_id,)).fetchone()["c"]
            apps = conn.execute("SELECT COUNT(*) AS c FROM v04f_club_applications WHERE status IN ('submitted','under_review','need_more_info')").fetchone()["c"]
        return {"pending_intents": int(intents or 0), "tasks": int(tasks or 0), "club_applications": int(apps or 0)}
    except sqlite3.Error:
        return {"pending_intents": 0, "tasks": 0, "club_applications": 0}


def _scope_context(request: Request, user: dict[str, Any]) -> dict[str, Any]:
    permissions = sorted(permissions_for(user))
    return {
        "authenticated": True,
        "auth_disabled": auth_disabled(),
        "user": user,
        "permissions": permissions,
        "can_manage_users": "manage_users" in permissions,
        "can_manage_club": "manage_club" in permissions,
        "can_review": "review_data" in permissions,
    }


def _nav_items(nav: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for group in ["primary", "secondary", "account", "admin"]:
        for item in nav.get(group, []):
            row = {key: item.get(key) for key in ["capability_key", "name", "category", "parent_key", "icon_key", "api_prefix", "status", "order", "badge_count", "permissions_summary"]}
            row["route"] = item.get("route") or item.get("endpoint")
            row["deeplink"] = row["route"]
            items.append(row)
    return items


@router.get("/bootstrap")
def bootstrap(request: Request, client: str = Query("web")):
    client = _safe_client(client)
    user = require_permission(request, "view_internal")
    context = _scope_context(request, user)
    nav = get_client_navigation(context, client=client, path=request.url.path)
    try:
        membership_ctx = get_membership_context(user)
    except Exception:
        membership_ctx = {"memberships": []}
    try:
        organization_ctx = get_organization_context(user)
    except Exception:
        organization_ctx = {"organizations": []}
    person = _current_person(int(user["id"]))
    return {
        "schema_version": "client-bootstrap.v1",
        "api_version": "v1",
        "server_time": datetime.now().replace(microsecond=0).isoformat(),
        "current_user": {"id": user.get("id"), "username": user.get("username"), "display_name": user.get("display_name"), "role": user.get("role")},
        "current_person": person,
        "current_membership": (membership_ctx.get("memberships") or [None])[0],
        "current_organization": (organization_ctx.get("organizations") or [None])[0],
        "current_club": _club_context(user),
        "authorization_summary": {"role": user.get("role"), "permissions": sorted(permissions_for(user)), "auth_scope": current_scope(request)},
        "available_capabilities": _nav_items(nav),
        "counters": _todo_counts(int(user["id"])),
        "feature_flags": {"mobile_client_contract": True, "data_integrity_admin": "review_data" in permissions_for(user) or "manage_users" in permissions_for(user)},
    }


@router.get("/navigation")
def navigation(request: Request, client: str = Query("web")):
    client = _safe_client(client)
    user = require_permission(request, "view_internal")
    context = _scope_context(request, user)
    nav = get_client_navigation(context, client=client, path=request.url.path)
    return {
        "schema_version": "client-navigation.v1",
        "api_version": "v1",
        "client": client,
        "items": _nav_items(nav),
        "groups": nav,
        "server_time": datetime.now().replace(microsecond=0).isoformat(),
    }
