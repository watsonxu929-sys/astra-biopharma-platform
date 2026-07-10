from __future__ import annotations

from fastapi import APIRouter, Request

from app.navigation import navigation_for
from app.services.api_common import require_permission, single

router = APIRouter(prefix="/navigation")


@router.get("", summary="Current navigation tree")
def navigation(request: Request):
    require_permission(request, "view_internal")
    return single(navigation_for(request.scope.get("security_context", {}), request.url.path))
