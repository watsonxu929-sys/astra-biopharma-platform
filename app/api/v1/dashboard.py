from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.services.api_common import require_permission, single
from app.services.dashboard_service import dashboard_data

router = APIRouter()


@router.get("/dashboard", summary="Industry intelligence dashboard", description="Return dashboard metrics from real database aggregation.")
def dashboard_api(request: Request, days: int = Query(7, ge=1, le=90), industry: str = "", region: str = "", signal_level: str = ""):
    require_permission(request, "view_internal")
    return single(dashboard_data(days=days, industry=industry, region=region, signal_level=signal_level))
