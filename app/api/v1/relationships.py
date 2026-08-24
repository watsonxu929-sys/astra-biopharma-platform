from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.api_common import Pagination, normalize_page, paginated, require_permission, single
from app.services.relationship_path_service import find_qbay_paths
from app.v04c_review import db_connection

router = APIRouter()


@router.get("/relationships", summary="List relationships")
def relationships_list(request: Request, q: str = "", relation_type: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    clauses = ["review_status<>'archived'"]
    params = []
    if q:
        clauses.append("(relationship_no LIKE ? OR subject_id LIKE ? OR object_id LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if relation_type:
        clauses.append("relationship_type=?")
        params.append(relation_type)
    where = " AND ".join(clauses)
    with db_connection() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM p3_canonical_relationships WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(f"SELECT id,relationship_no,subject_type,subject_id,relationship_type,object_type,object_id,direction,valid_from,valid_to,is_current,confidence,review_status,evidence_status,visibility,created_at FROM p3_canonical_relationships WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()]
    return paginated(rows, Pagination(page, page_size, total))


@router.get("/relationships/{relation_id}", summary="Get relationship detail")
def relationship_detail(request: Request, relation_id: int):
    require_permission(request, "view_internal")
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM p3_canonical_relationships WHERE id=? AND review_status<>'archived'", (relation_id,)).fetchone()
        evidence = [dict(item) for item in conn.execute("SELECT * FROM p3_relationship_evidence WHERE relationship_id=? ORDER BY id", (relation_id,))] if row else []
    if not row:
        raise HTTPException(status_code=404, detail={"code": "RELATIONSHIP_NOT_FOUND", "message": "关系不存在", "details": {}})
    result = dict(row)
    result["evidence"] = evidence
    return single(result)


@router.get("/relationship-paths", summary="Relationship paths", description="Return limited, deduplicated paths based on confirmed relationship data.")
def relationship_paths(request: Request, subject_type: str, subject_id: str, limit: int = Query(10, ge=1, le=30)):
    require_permission(request, "view_internal")
    with db_connection() as conn:
        result = find_qbay_paths(conn, subject_type, subject_id, max_edges=3, max_paths=limit)
    return single(result)
