from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.api_common import Pagination, normalize_page, paginated, require_permission, single
from app.services.unified_opportunity_service import UnifiedOpportunityService

router = APIRouter()


class OpportunityCreate(BaseModel):
    title: str
    opp_type: str = "other"
    description: str | None = None
    expected_outcome: str | None = None
    visibility: str = "organization"
    source_type: str | None = None
    source_id: int | None = None
    target_person_id: int | None = None
    target_organization_id: int | None = None
    related_resource_id: int | None = None


class StageUpdate(BaseModel):
    stage: str


class FollowUpCreate(BaseModel):
    follow_type: str = "note"
    content: str
    visibility: str = "organization"


class TaskCreate(BaseModel):
    title: str
    owner_id: int | None = None
    priority: str = "P2"
    participants: str | None = None


def _is_admin(user: dict) -> bool:
    return str(user.get("role")) == "admin" or "manage_users" in user.get("permissions", [])


@router.get("/opportunities", summary="List unified opportunities")
def list_opportunities(request: Request, status: str = "active", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    user = require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    svc = UnifiedOpportunityService(db)
    result = svc.list(user_id=int(user["id"]), is_admin=_is_admin(user), status=status, page=page, page_size=page_size)
    return paginated([svc.to_api(item) for item in result["items"]], Pagination(result["page"], result["page_size"], result["total"]), meta={"canonical_model": svc.canonical_model})


@router.get("/opportunities/{opp_id}", summary="Get unified opportunity")
def opportunity_detail(request: Request, opp_id: int, db: Session = Depends(get_db)):
    user = require_permission(request, "view_internal")
    svc = UnifiedOpportunityService(db)
    return single(svc.to_api(svc.detail(opp_id, user_id=int(user["id"]), is_admin=_is_admin(user))), meta={"canonical_model": svc.canonical_model})


@router.post("/opportunities", summary="Create unified opportunity")
def create_opportunity(request: Request, payload: OpportunityCreate, db: Session = Depends(get_db)):
    user = require_permission(request, "edit_data")
    svc = UnifiedOpportunityService(db)
    opp = svc.create(actor_user_id=int(user["id"]), fields=payload.model_dump())
    return single(svc.to_api(opp), meta={"canonical_model": svc.canonical_model})


@router.post("/opportunities/{opp_id}/stage", summary="Update opportunity stage")
def update_stage(request: Request, opp_id: int, payload: StageUpdate, db: Session = Depends(get_db)):
    user = require_permission(request, "edit_data")
    svc = UnifiedOpportunityService(db)
    return single(svc.to_api(svc.update_stage(opp_id, actor_user_id=int(user["id"]), stage=payload.stage, is_admin=_is_admin(user))))


@router.post("/opportunities/{opp_id}/follow-ups", summary="Create opportunity follow-up")
def create_follow_up(request: Request, opp_id: int, payload: FollowUpCreate, db: Session = Depends(get_db)):
    user = require_permission(request, "edit_data")
    follow = UnifiedOpportunityService(db).create_follow_up(opp_id=opp_id, actor_user_id=int(user["id"]), fields=payload.model_dump(), is_admin=_is_admin(user))
    return single({"id": follow.id, "opportunity_id": follow.opportunity_id})


@router.post("/opportunities/{opp_id}/tasks", summary="Create opportunity task")
def create_task(request: Request, opp_id: int, payload: TaskCreate, db: Session = Depends(get_db)):
    user = require_permission(request, "edit_data")
    owner_id = int(payload.owner_id or user["id"])
    task = UnifiedOpportunityService(db).create_task(opp_id=opp_id, actor_user_id=int(user["id"]), owner_id=owner_id, fields=payload.model_dump(), is_admin=_is_admin(user))
    return single({"id": task.id, "opportunity_id": task.opportunity_id, "owner_id": task.owner_id})
