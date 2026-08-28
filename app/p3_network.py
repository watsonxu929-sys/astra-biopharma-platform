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

from app.services.collection_service import (
    discover_source_candidates,
    organization_monitoring_context,
    propose_official_domain_candidate,
    review_official_domain_candidate,
)

router = APIRouter(tags=["P3 entity relationship network"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

ENTITY_TYPE_LABELS = {
    "person": "人物",
    "organization": "机构",
    "project": "项目",
    "product": "产品",
}

RELATION_TYPE_LABELS = {
    "employment": "雇佣关系",
    "board_membership": "董事/监事",
    "investment": "投资关系",
    "cooperation": "合作关系",
    "cooperates_with": "合作关系",
    "licensing": "授权许可",
    "partnership": "战略伙伴",
    "supply": "供应关系",
    "distribution": "分销关系",
    "clinical_trial": "临床试验",
    "research_collaboration": "研究合作",
    "acquisition": "收购并购",
    "equity": "股权关系",
}

EVIDENCE_STATUS_LABELS = {
    "evidence_backed": "有证据",
    "manual_unverified": "人工录入，待补证据",
}

QUALITY_STATUS_LABELS = {
    "accepted": "已接受",
    "duplicate": "重复内容",
    "low_quality": "低质量",
    "access_denied": "访问受限",
}


def _render(request: Request, mode: str, **context):
    context.setdefault("ENTITY_TYPE_LABELS", ENTITY_TYPE_LABELS)
    context.setdefault("RELATION_TYPE_LABELS", RELATION_TYPE_LABELS)
    context.setdefault("EVIDENCE_STATUS_LABELS", EVIDENCE_STATUS_LABELS)
    context.setdefault("QUALITY_STATUS_LABELS", QUALITY_STATUS_LABELS)
    return templates.TemplateResponse(request, "p3_network.html", {"mode": mode, **context})


def _can_access_governance(request: Request) -> bool:
    sec = request.scope.get("security_context", {})
    permissions = set(sec.get("permissions") or [])
    return bool(sec.get("can_manage_users") or "review_data" in permissions or "edit_data" in permissions or "manage_users" in permissions)


@router.get("/network/governance", response_class=HTMLResponse)
def governance_page(request: Request, status: str = ""):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="主体治理权限不足")
    try:
        candidates = list_resolution_candidates(status=status)
        merges = list_merge_records()
    except sqlite3.OperationalError:
        candidates, merges = [], []
    return _render(request, "governance", candidates=candidates, merges=merges, status=status)
def _business_trace(entity_type: str, internal_id: int) -> dict[str, list[dict]]:
    service = CanonicalRelationshipService()
    with sqlite3.connect(service.db_path) as conn:
        conn.row_factory = sqlite3.Row
        intelligence = [dict(row) for row in conn.execute(
            """SELECT DISTINCT i.id,i.title FROM core_intelligence_subject_links l
               JOIN v06_intelligence_items i ON i.id=l.intelligence_item_id
               WHERE l.subject_type=? AND l.subject_id=? ORDER BY i.id DESC LIMIT 20""",
            (entity_type, int(internal_id)),
        )]
        resource_column = {"organization": "organization_id", "person": "owner_person_id", "project": "project_id"}.get(entity_type)
        resources = [dict(row) for row in conn.execute(
            f"SELECT id,title,direction FROM v06_market_resources WHERE {resource_column}=? ORDER BY id DESC LIMIT 20",
            (int(internal_id),),
        )] if resource_column else []
        if entity_type == "organization":
            opportunities = [dict(row) for row in conn.execute(
                """SELECT DISTINCT id,title,status,outcome_status FROM v06_opportunities
                   WHERE organization_id=? OR demand_organization_id=? OR supply_organization_id=?
                      OR target_organization_id=? ORDER BY id DESC LIMIT 20""",
                (int(internal_id),) * 4,
            )]
        elif entity_type == "person":
            opportunities = [dict(row) for row in conn.execute(
                """SELECT DISTINCT id,title,status,outcome_status FROM v06_opportunities
                   WHERE target_person_id=? ORDER BY id DESC LIMIT 20""",
                (int(internal_id),),
            )]
        else:
            opportunities = []
        opportunity_ids = [int(row["id"]) for row in opportunities]
        if opportunity_ids:
            placeholders = ",".join("?" for _ in opportunity_ids)
            follow_ups = [dict(row) for row in conn.execute(
                f"""SELECT f.id,f.content,f.next_action,f.followed_at,o.id AS opportunity_id,o.title AS opportunity_title
                    FROM v06_follow_ups f JOIN v06_opportunities o ON o.id=f.opportunity_id
                    WHERE o.id IN ({placeholders}) ORDER BY f.followed_at DESC LIMIT 5""",
                opportunity_ids,
            )]
        else:
            follow_ups = []
    return {"intelligence": intelligence, "resources": resources, "opportunities": opportunities, "follow_ups": follow_ups}




@router.get("/network/entities/{entity_type}/{entity_id}", response_class=HTMLResponse)
def entity_page(request: Request, entity_type: str, entity_id: str, history: bool = False):
    entity = EntityRegistryService().get(entity_type, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="主体不存在")
    include_private = _can_access_governance(request)
    relationships = CanonicalRelationshipService().entity_relationships(entity_type, entity["resolved_id"], history=history, include_private=include_private)
    business_trace = _business_trace(entity_type, int(entity["id"]))
    monitoring = organization_monitoring_context(entity["resolved_id"]) if entity_type == "organization" else None
    return _render(
        request, "entity", entity_type=entity_type, entity=entity, relationships=relationships,
        business_trace=business_trace, monitoring=monitoring, can_manage_monitoring=include_private,
        history=history,
    )


@router.post("/network/entities/organization/{entity_id}/monitoring/discover")
def discover_organization_sources(request: Request, entity_id: str):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="来源发现权限不足")
    entity = EntityRegistryService().get("organization", entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="主体不存在")
    context = organization_monitoring_context(entity["resolved_id"])
    homepage = ""
    if context["official_domain"]:
        homepage = str(context["official_domain"]["identifier_value"])
    elif context["active_sources"]:
        homepage = str(context["active_sources"][0]["url"])
    if not homepage:
        for evidence_url in context["evidence_urls"]:
            proposal = propose_official_domain_candidate(
                entity["resolved_id"], entity["canonical_label"], evidence_url,
                "Canonical档案或已关联情报中的公开链接", current_username(request),
            )
            if proposal.get("validation", {}).get("ok"):
                return RedirectResponse(
                    f"/network/entities/organization/{entity['resolved_id']}?message=已生成可解释的官网候选，请人工确认",
                    status_code=303,
                )
        return RedirectResponse(
            f"/network/entities/organization/{entity['resolved_id']}?error=未找到可靠官网证据，请人工提供候选URL",
            status_code=303,
        )
    result = discover_source_candidates(
        homepage, entity["resolved_id"], entity["canonical_label"],
        owner=current_username(request),
    )
    return RedirectResponse(
        f"/network/entities/organization/{entity['resolved_id']}?message=来源发现完成：新增{result['created']}，重复{result['duplicates']}，无效{result['invalid']}",
        status_code=303,
    )


@router.post("/network/entities/organization/{entity_id}/monitoring/domain-candidates")
def propose_organization_domain(request: Request, entity_id: str, candidate_url: str = Form(...)):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="官网候选权限不足")
    entity = EntityRegistryService().get("organization", entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="主体不存在")
    result = propose_official_domain_candidate(
        entity["resolved_id"], entity["canonical_label"], candidate_url,
        "管理员从Organization详情提交", current_username(request),
    )
    if not result.get("validation", {}).get("ok"):
        status = result.get("validation", {}).get("status", "VALIDATION_FAILED")
        return RedirectResponse(
            f"/network/entities/organization/{entity['resolved_id']}?error=官网候选未通过验证：{status}",
            status_code=303,
        )
    return RedirectResponse(
        f"/network/entities/organization/{entity['resolved_id']}?message=官网候选已保存，等待人工确认",
        status_code=303,
    )


@router.post("/network/entities/organization/{entity_id}/monitoring/domain-candidates/{candidate_id}/review")
def review_organization_domain(
    request: Request, entity_id: str, candidate_id: int, decision: str = Form(...),
):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="官网候选审核权限不足")
    entity = EntityRegistryService().get("organization", entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="主体不存在")
    try:
        candidate = review_official_domain_candidate(candidate_id, entity["resolved_id"], decision, current_username(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if candidate["entity_id"] != entity["resolved_id"]:
        raise HTTPException(status_code=400, detail="官网候选与主体不匹配")
    if decision == "approved":
        result = discover_source_candidates(
            candidate["identifier_value"], entity["resolved_id"], entity["canonical_label"],
            owner=current_username(request),
        )
        message = f"官网已确认；来源候选新增{result['created']}，重复{result['duplicates']}"
    else:
        message = "官网候选已忽略，不会进入正式主体事实"
    return RedirectResponse(
        f"/network/entities/organization/{entity['resolved_id']}?message={message}", status_code=303,
    )

@router.get("/network/products/{product_id}", response_class=HTMLResponse)
def product_page(request: Request, product_id: str):
    return entity_page(request, "product", product_id, history=True)


@router.post("/network/resolution-candidates/{candidate_id}/review")
def resolution_review(request: Request, candidate_id: int, decision: str = Form(...), note: str = Form("")):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="审核权限不足")
    EntityResolutionService().review(candidate_id, decision, actor=current_username(request), permissions={"review_data"}, note=note)
    return RedirectResponse("/network/governance", status_code=303)


@router.post("/network/merges/preview")
def merge_preview(
    request: Request, entity_type: str = Form(...), source_entity_id: str = Form(...),
    target_entity_id: str = Form(...), reason: str = Form(...),
):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="合并权限不足")
    record = EntityMergeService().preview(entity_type, source_entity_id, target_entity_id, reason=reason, actor=current_username(request))
    return RedirectResponse(f"/network/merges/{record['id']}", status_code=303)


@router.get("/network/merges/{merge_id}", response_class=HTMLResponse)
def merge_detail(request: Request, merge_id: int):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="合并预览权限不足")
    records = [row for row in list_merge_records() if int(row["id"]) == merge_id]
    if not records:
        raise HTTPException(status_code=404, detail="合并记录不存在")
    return _render(request, "merge", merge=records[0])


@router.post("/network/merges/{merge_id}/submit")
def merge_submit(request: Request, merge_id: int):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="提交合并权限不足")
    EntityMergeService().submit(merge_id, actor=current_username(request), permissions={"edit_data"})
    return RedirectResponse(f"/network/merges/{merge_id}", status_code=303)


@router.post("/network/merges/{merge_id}/approve")
def merge_approve(request: Request, merge_id: int):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="批准合并权限不足")
    EntityMergeService().execute(merge_id, actor=current_username(request), permissions={"review_data"})
    return RedirectResponse(f"/network/merges/{merge_id}", status_code=303)


@router.post("/network/merges/{merge_id}/rollback")
def merge_rollback(request: Request, merge_id: int, reason: str = Form(...)):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="回滚权限不足")
    EntityMergeService().rollback(merge_id, actor=current_username(request), permissions={"review_data"}, reason=reason)
    return RedirectResponse(f"/network/merges/{merge_id}", status_code=303)


@router.get("/network/relationship-candidates", response_class=HTMLResponse)
def relationship_queue(request: Request, status: str = ""):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="关系审核权限不足")
    try:
        candidates, types = list_relationship_candidates(status=status), list_relationship_types()
    except sqlite3.OperationalError:
        candidates, types = [], []
    return _render(request, "relationship_queue", candidates=candidates, relationship_types=types, status=status)


@router.post("/network/relationship-candidates/{candidate_id}/review")
def relationship_review(request: Request, candidate_id: int, decision: str = Form(...), note: str = Form("")):
    if not _can_access_governance(request):
        raise HTTPException(status_code=403, detail="审核权限不足")
    CanonicalRelationshipService().review_candidate(candidate_id, decision, actor=current_username(request), permissions={"review_data"}, note=note)
    return RedirectResponse("/network/relationship-candidates", status_code=303)


@router.get("/network/relationships/{relationship_id}", response_class=HTMLResponse)
def relationship_detail(request: Request, relationship_id: int):
    include_private = _can_access_governance(request)
    relationship = CanonicalRelationshipService().detail(relationship_id, include_private=include_private)
    if not relationship:
        raise HTTPException(status_code=404, detail="关系不存在")
    registry = EntityRegistryService()
    subject = registry.get(relationship["subject_type"], relationship["subject_id"])
    object_entity = registry.get(relationship["object_type"], relationship["object_id"])
    return _render(request, "relationship", relationship=relationship,
                   subject=subject, object_entity=object_entity)


@router.get("/network/paths", response_class=HTMLResponse)
def path_page(
    request: Request, source_type: str = "person", source_id: str = "",
    target_type: str = "organization", target_id: str = "", as_of: str = "",
    max_depth: int = Query(3, ge=1, le=3), include_history: bool = False,
):
    result = None
    if source_id and target_id:
        result = RelationshipNetworkService().find_paths(
            source_type, source_id, target_type, target_id,
            max_depth=max_depth, as_of=as_of or None, include_history=include_history,
        )
    return _render(request, "paths", result=result, source_type=source_type, source_id=source_id,
                   target_type=target_type, target_id=target_id, as_of=as_of,
                   max_depth=max_depth, include_history=include_history)


@router.get("/network/graph", response_class=HTMLResponse)
def graph_page(request: Request, entity_type: str = "organization", entity_id: str = "", depth: int = Query(2, ge=1, le=3)):
    result = RelationshipNetworkService().graph(entity_type, entity_id, depth=depth) if entity_id else None
    return _render(request, "graph", result=result, entity_type=entity_type, entity_id=entity_id, depth=depth)


@router.get("/network/recommendations", response_class=HTMLResponse)
def recommendations_page(request: Request, source_person_id: str = ""):
    if not source_person_id:
        sec = request.scope.get("security_context", {})
        user_info = sec.get("user", {})
        source_person_id = user_info.get("person_id", "")
    
    recommendations = []
    if source_person_id:
        recommendations = ConnectionRecommendationService().recommend(source_person_id)
    
    return _render(request, "connections", source_person_id=source_person_id, recommendations=recommendations)


@router.get("/network/connection-candidates/{source_person_id}", response_class=HTMLResponse)
def connection_page(request: Request, source_person_id: str):
    recommendations = ConnectionRecommendationService().recommend(source_person_id)
    return _render(request, "connections", source_person_id=source_person_id, recommendations=recommendations)


@router.get("/network/timeline", response_class=HTMLResponse)
def timeline_page(request: Request, entity_type: str = "organization", entity_id: str = ""):
    relationships = []
    if entity_id:
        include_private = _can_access_governance(request)
        relationships = CanonicalRelationshipService().entity_relationships(
            entity_type, entity_id, history=True, include_private=include_private
        )
    return _render(request, "timeline", entity_type=entity_type, entity_id=entity_id, relationships=relationships)
