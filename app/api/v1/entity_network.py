from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services.api_common import require_permission, single
from app.services.canonical_relationship_service import (
    CanonicalRelationshipService,
    ConnectionRecommendationService,
    RelationshipNetworkService,
    list_relationship_candidates,
    list_relationship_types,
)
from app.services.entity_governance_service import (
    EntityMergeService,
    EntityRegistryService,
    EntityResolutionService,
    list_merge_records,
    list_resolution_candidates,
)


router = APIRouter(prefix="/entity-network", tags=["P3 entity relationship network"])


class ResolutionIn(BaseModel):
    entity_type: str
    raw_name: str = Field(..., min_length=1, max_length=300)
    external_identifiers: dict[str, str] = Field(default_factory=dict)
    context: dict[str, str] = Field(default_factory=dict)
    source_record_type: str = "api"
    source_record_id: str = ""


class ReviewIn(BaseModel):
    decision: str
    note: str = ""


class MergeIn(BaseModel):
    entity_type: str
    source_entity_id: str
    target_entity_id: str
    reason: str = Field(..., min_length=2)
    evidence: list[dict] = Field(default_factory=list)


class RollbackIn(BaseModel):
    reason: str = Field(..., min_length=2)


class RelationshipIn(BaseModel):
    subject_type: str
    subject_id: str
    relationship_type: str
    object_type: str
    object_id: str
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: int = Field(50, ge=0, le=100)
    evidence: list[dict] = Field(default_factory=list)
    source_record_type: str = "api"
    source_record_id: str = ""
    visibility: str = "internal"


def _actor(user: dict) -> str:
    return str(user.get("username") or "api")


@router.get("/entities/{entity_type}/{entity_id}")
def entity(request: Request, entity_type: str, entity_id: str):
    require_permission(request, "view_internal")
    row = EntityRegistryService().get(entity_type, entity_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "ENTITY_NOT_FOUND", "message": "主体不存在", "details": {}})
    return single(row)


@router.post("/resolution-candidates")
def resolution_propose(request: Request, payload: ResolutionIn):
    user = require_permission(request, "edit_data")
    return {"data": EntityResolutionService().propose(
        payload.entity_type, payload.raw_name, external_identifiers=payload.external_identifiers,
        context=payload.context, source_record_type=payload.source_record_type,
        source_record_id=payload.source_record_id, actor=_actor(user),
    )}


@router.get("/resolution-candidates")
def resolutions(request: Request, status: str = ""):
    require_permission(request, "view_internal")
    return {"data": list_resolution_candidates(status=status)}


@router.post("/resolution-candidates/{candidate_id}/review")
def resolution_review(request: Request, candidate_id: int, payload: ReviewIn):
    user = require_permission(request, "review_data")
    return single(EntityResolutionService().review(candidate_id, payload.decision, actor=_actor(user), permissions={"review_data"}, note=payload.note))


@router.post("/merges/preview")
def merge_preview(request: Request, payload: MergeIn):
    user = require_permission(request, "edit_data")
    return single(EntityMergeService().preview(payload.entity_type, payload.source_entity_id, payload.target_entity_id, reason=payload.reason, actor=_actor(user), evidence=payload.evidence))


@router.get("/merges")
def merges(request: Request):
    require_permission(request, "view_internal")
    return {"data": list_merge_records()}


@router.post("/merges/{merge_id}/submit")
def merge_submit(request: Request, merge_id: int):
    user = require_permission(request, "edit_data")
    return single(EntityMergeService().submit(merge_id, actor=_actor(user), permissions={"edit_data"}))


@router.post("/merges/{merge_id}/approve")
def merge_approve(request: Request, merge_id: int):
    user = require_permission(request, "review_data")
    return single(EntityMergeService().execute(merge_id, actor=_actor(user), permissions={"review_data"}))


@router.post("/merges/{merge_id}/rollback")
def merge_rollback(request: Request, merge_id: int, payload: RollbackIn):
    user = require_permission(request, "review_data")
    return single(EntityMergeService().rollback(merge_id, actor=_actor(user), permissions={"review_data"}, reason=payload.reason))


@router.get("/relationship-types")
def relationship_types(request: Request):
    require_permission(request, "view_internal")
    return {"data": list_relationship_types()}


@router.post("/relationship-candidates")
def relationship_candidate(request: Request, payload: RelationshipIn):
    user = require_permission(request, "edit_data")
    return single(CanonicalRelationshipService().create_candidate(
        subject_type=payload.subject_type, subject_id=payload.subject_id,
        relationship_type=payload.relationship_type, object_type=payload.object_type,
        object_id=payload.object_id, actor=_actor(user), valid_from=payload.valid_from,
        valid_to=payload.valid_to, confidence=payload.confidence, evidence=payload.evidence,
        source_record_type=payload.source_record_type, source_record_id=payload.source_record_id,
        visibility=payload.visibility,
    ))


@router.get("/relationship-candidates")
def relationship_candidates(request: Request, status: str = ""):
    require_permission(request, "view_internal")
    return {"data": list_relationship_candidates(status=status)}


@router.post("/relationship-candidates/{candidate_id}/review")
def relationship_candidate_review(request: Request, candidate_id: int, payload: ReviewIn):
    user = require_permission(request, "review_data")
    return single(CanonicalRelationshipService().review_candidate(candidate_id, payload.decision, actor=_actor(user), permissions={"review_data"}, note=payload.note))


@router.get("/relationships/{relationship_id}")
def relationship(request: Request, relationship_id: int):
    require_permission(request, "view_internal")
    row = CanonicalRelationshipService().detail(relationship_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "RELATIONSHIP_NOT_FOUND", "message": "关系不存在", "details": {}})
    return single(row)


@router.get("/paths")
def paths(
    request: Request, source_type: str, source_id: str, target_type: str, target_id: str,
    max_depth: int = Query(3, ge=1, le=3), as_of: str = "", include_history: bool = False,
):
    require_permission(request, "view_internal")
    return single(RelationshipNetworkService().find_paths(
        source_type, source_id, target_type, target_id, max_depth=max_depth,
        as_of=as_of or None, include_history=include_history,
    ))


@router.get("/graph/{entity_type}/{entity_id}")
def graph(request: Request, entity_type: str, entity_id: str, depth: int = Query(2, ge=1, le=3)):
    require_permission(request, "view_internal")
    return single(RelationshipNetworkService().graph(entity_type, entity_id, depth=depth))


@router.get("/connection-candidates/{source_person_id}")
def connections(request: Request, source_person_id: str, limit: int = Query(10, ge=1, le=20)):
    require_permission(request, "use_recommendations")
    return {"data": ConnectionRecommendationService().recommend(source_person_id, limit=limit)}
