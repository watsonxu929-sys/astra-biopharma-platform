from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.api_common import Pagination, normalize_page, paginated, require_permission, single
from app.services.unified_resource_service import UnifiedResourceService

router = APIRouter()


class ResourceCreate(BaseModel):
    title: str
    direction: str = "supply"
    resource_type: str = "other"
    category: str | None = None
    owner_person_id: int | None = None
    owner_organization_id: int | None = None
    visibility: str = "organization"
    summary: str | None = None
    description: str | None = None
    region: str | None = None
    industry_direction: str | None = None
    tags: str | None = None
    cooperation_mode: str | None = None
    budget_note: str | None = None
    contact_visibility: str = "connected"


@router.get("/resources", summary="List unified resources")
def list_resources(request: Request, direction: str = "", resource_type: str = "", q: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    svc = UnifiedResourceService(db)
    result = svc.list(direction=direction, resource_type=resource_type, q=q, page=page, page_size=page_size)
    items = [svc.to_api(item) for item in result["items"]] + [svc.to_api(item) for item in result.get("legacy_items", [])]
    return paginated(items, Pagination(result["page"], result["page_size"], result["total"]), meta={"canonical_model": svc.canonical_model, "legacy_adapters": list(svc.legacy_adapters)})


@router.get("/resources/{resource_id}", summary="Get unified resource")
def resource_detail(request: Request, resource_id: int, db: Session = Depends(get_db)):
    require_permission(request, "view_internal")
    svc = UnifiedResourceService(db)
    return single(svc.to_api(svc.detail(resource_id)), meta={"canonical_model": svc.canonical_model})


@router.post("/resources", summary="Create unified resource")
def create_resource(request: Request, payload: ResourceCreate, db: Session = Depends(get_db)):
    user = require_permission(request, "edit_data")
    svc = UnifiedResourceService(db)
    resource = svc.create(actor_user_id=int(user["id"]), fields=payload.model_dump())
    return single(svc.to_api(resource), meta={"canonical_model": svc.canonical_model})
