from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.services.api_common import require_permission, single
from app.services.search_service import search_all

router = APIRouter()


@router.get("/search", summary="Global search", description="Search confirmed business entities and records with per-type limits.")
def global_search_api(request: Request, q: str = Query("", max_length=200), per_type_limit: int = Query(10, ge=1, le=30)):
    require_permission(request, "view_internal")
    return single(search_all(q, per_type_limit=per_type_limit))
