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
    clauses = ["COALESCE(is_active,1)=1"]
    params = []
    if q:
        clauses.append("(external_id LIKE ? OR source_external_id LIKE ? OR target_external_id LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if relation_type:
        clauses.append("relation_type=?")
        params.append(relation_type)
    where = " AND ".join(clauses)
    with db_connection() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM relations WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(f"SELECT id,external_id,source_external_id,relation_type,target_external_id,period,evidence_source,verification_status,created_at FROM relations WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()]
    return paginated(rows, Pagination(page, page_size, total))


@router.get("/relationships/{relation_id}", summary="Get relationship detail")
def relationship_detail(request: Request, relation_id: int):
    require_permission(request, "view_internal")
    with db_connection() as conn:
        row = conn.execute("SELECT id,external_id,source_external_id,relation_type,target_external_id,period,evidence_source,verification_status,source_url,source_type,source_title,created_at FROM relations WHERE id=? AND COALESCE(is_active,1)=1", (relation_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "RELATIONSHIP_NOT_FOUND", "message": "关系不存在", "details": {}})
    return single(dict(row))


@router.get("/relationship-paths", summary="Relationship paths", description="Return limited, deduplicated paths based on confirmed relationship data.")
def relationship_paths(request: Request, subject_type: str, subject_id: str, limit: int = Query(10, ge=1, le=30)):
    require_permission(request, "view_internal")
    with db_connection() as conn:
        result = find_qbay_paths(conn, subject_type, subject_id, max_edges=3, max_paths=limit)
    return single(result)
