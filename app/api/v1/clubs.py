from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.services.api_common import require_permission, single
from app.services.membership_access_service import get_membership_context

router = APIRouter(tags=["Club Context"])


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
