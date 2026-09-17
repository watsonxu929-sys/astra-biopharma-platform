from __future__ import annotations

from fastapi import APIRouter, Query, Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.api_common import Pagination, normalize_page, paginated, require_permission, single
from app.services.unified_intelligence_service import UnifiedIntelligenceService
from app.services.intelligence_product_service import IntelligenceProductService

router = APIRouter()


@router.get("/intelligence", summary="List published intelligence")
def list_intelligence(request: Request, q: str = "", intel_type: str = "", industry_direction: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    user = require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    svc = UnifiedIntelligenceService(db)
    result = svc.list(user_id=int(user["id"]), intel_type=intel_type, industry_direction=industry_direction, q=q, page=page, page_size=page_size)
    return paginated([svc.to_api(item) for item in result["items"]], Pagination(result["page"], result["page_size"], result["total"]), meta={"canonical_model": svc.canonical_model})


@router.get("/intelligence/{item_id}", summary="Get published intelligence")
def intelligence_detail(request: Request, item_id: int, db: Session = Depends(get_db)):
    require_permission(request, "view_internal")
    svc = UnifiedIntelligenceService(db)
    return single(svc.to_api(svc.detail(item_id)), meta={"canonical_model": svc.canonical_model})

@router.get("/intelligence/{item_id}/evidence", summary="Trace product evidence")
def intelligence_evidence(request: Request, item_id: int, db: Session = Depends(get_db)):
    require_permission(request, "view_internal")
    UnifiedIntelligenceService(db).detail(item_id)
    try:
        trace = IntelligenceProductService(db.get_bind().url.database).trace(item_id)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail={"code": "INTELLIGENCE_NOT_FOUND", "message": str(exc), "details": {}}) from exc
    return single({"product_id": item_id, "candidates": trace["candidates"], "evidence": trace["evidence"]})
