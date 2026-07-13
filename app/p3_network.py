from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
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


router = APIRouter(tags=["P3 entity relationship network"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _render(request: Request, mode: str, **context):
    return templates.TemplateResponse(request, "p3_network.html", {"mode": mode, **context})


@router.get("/network/governance", response_class=HTMLResponse)
def governance_page(request: Request, status: str = ""):
    try:
        candidates = list_resolution_candidates(status=status)
        merges = list_merge_records()
    except sqlite3.OperationalError:
        candidates, merges = [], []
    return _render(request, "governance", candidates=candidates, merges=merges, status=status)


@router.get("/network/entities/{entity_type}/{entity_id}", response_class=HTMLResponse)
def entity_page(request: Request, entity_type: str, entity_id: str, history: bool = False):
    entity = EntityRegistryService().get(entity_type, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="entity not found")
    relationships = CanonicalRelationshipService().entity_relationships(entity_type, entity["resolved_id"], history=history)
    return _render(request, "entity", entity_type=entity_type, entity=entity, relationships=relationships, history=history)


@router.get("/network/products/{product_id}", response_class=HTMLResponse)
def product_page(request: Request, product_id: str):
    return entity_page(request, "product", product_id, history=True)


@router.post("/network/resolution-candidates/{candidate_id}/review")
def resolution_review(request: Request, candidate_id: int, decision: str = Form(...), note: str = Form("")):
    EntityResolutionService().review(candidate_id, decision, actor=current_username(request), permissions={"review_data"}, note=note)
    return RedirectResponse("/network/governance", status_code=303)


@router.post("/network/merges/preview")
def merge_preview(
    request: Request, entity_type: str = Form(...), source_entity_id: str = Form(...),
    target_entity_id: str = Form(...), reason: str = Form(...),
):
    record = EntityMergeService().preview(entity_type, source_entity_id, target_entity_id, reason=reason, actor=current_username(request))
    return RedirectResponse(f"/network/merges/{record['id']}", status_code=303)


@router.get("/network/merges/{merge_id}", response_class=HTMLResponse)
def merge_detail(request: Request, merge_id: int):
    records = [row for row in list_merge_records() if int(row["id"]) == merge_id]
    if not records:
        raise HTTPException(status_code=404, detail="merge record not found")
    return _render(request, "merge", merge=records[0])


@router.post("/network/merges/{merge_id}/submit")
def merge_submit(request: Request, merge_id: int):
    EntityMergeService().submit(merge_id, actor=current_username(request), permissions={"edit_data"})
    return RedirectResponse(f"/network/merges/{merge_id}", status_code=303)


@router.post("/network/merges/{merge_id}/approve")
def merge_approve(request: Request, merge_id: int):
    EntityMergeService().execute(merge_id, actor=current_username(request), permissions={"review_data"})
    return RedirectResponse(f"/network/merges/{merge_id}", status_code=303)


@router.post("/network/merges/{merge_id}/rollback")
def merge_rollback(request: Request, merge_id: int, reason: str = Form(...)):
    EntityMergeService().rollback(merge_id, actor=current_username(request), permissions={"review_data"}, reason=reason)
    return RedirectResponse(f"/network/merges/{merge_id}", status_code=303)


@router.get("/network/relationship-candidates", response_class=HTMLResponse)
def relationship_queue(request: Request, status: str = ""):
    try:
        candidates, types = list_relationship_candidates(status=status), list_relationship_types()
    except sqlite3.OperationalError:
        candidates, types = [], []
    return _render(request, "relationship_queue", candidates=candidates, relationship_types=types, status=status)


@router.post("/network/relationship-candidates/{candidate_id}/review")
def relationship_review(request: Request, candidate_id: int, decision: str = Form(...), note: str = Form("")):
    CanonicalRelationshipService().review_candidate(candidate_id, decision, actor=current_username(request), permissions={"review_data"}, note=note)
    return RedirectResponse("/network/relationship-candidates", status_code=303)


@router.get("/network/relationships/{relationship_id}", response_class=HTMLResponse)
def relationship_detail(request: Request, relationship_id: int):
    relationship = CanonicalRelationshipService().detail(relationship_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="relationship not found")
    return _render(request, "relationship", relationship=relationship)


@router.get("/network/paths", response_class=HTMLResponse)
def path_page(
    request: Request, source_type: str = "person", source_id: str = "",
    target_type: str = "organization", target_id: str = "", as_of: str = "",
):
    result = None
    if source_id and target_id:
        result = RelationshipNetworkService().find_paths(source_type, source_id, target_type, target_id, as_of=as_of or None)
    return _render(request, "paths", result=result, source_type=source_type, source_id=source_id, target_type=target_type, target_id=target_id, as_of=as_of)


@router.get("/network/graph", response_class=HTMLResponse)
def graph_page(request: Request, entity_type: str = "organization", entity_id: str = "", depth: int = Query(2, ge=1, le=3)):
    result = RelationshipNetworkService().graph(entity_type, entity_id, depth=depth) if entity_id else None
    return _render(request, "graph", result=result, entity_type=entity_type, entity_id=entity_id, depth=depth)


@router.get("/network/connection-candidates/{source_person_id}", response_class=HTMLResponse)
def connection_page(request: Request, source_person_id: str):
    recommendations = ConnectionRecommendationService().recommend(source_person_id)
    return _render(request, "connections", source_person_id=source_person_id, recommendations=recommendations)
