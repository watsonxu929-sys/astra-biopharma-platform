from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.api_common import Pagination, normalize_page, paginated, require_permission, single
from app.v04c_review import db_connection

router = APIRouter()


@router.get("/events", summary="List events")
def events_list(request: Request, q: str = "", event_type: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    require_permission(request, "view_internal")
    page, page_size = normalize_page(page, page_size)
    clauses = ["COALESCE(is_active,1)=1"]
    params = []
    if q:
        clauses.append("(external_id LIKE ? OR name LIKE ? OR COALESCE(fact_summary,'') LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if event_type:
        clauses.append("event_type=?")
        params.append(event_type)
    where = " AND ".join(clauses)
    with db_connection() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM events WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(f"SELECT id,external_id,event_date,name,event_type,related_entity,fact_summary,verification_status,created_at FROM events WHERE {where} ORDER BY COALESCE(event_date,created_at) DESC,id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()]
    return paginated(rows, Pagination(page, page_size, total))


@router.get("/events/{event_id}", summary="Get event detail")
def event_detail(request: Request, event_id: int):
    require_permission(request, "view_internal")
    with db_connection() as conn:
        row = conn.execute("SELECT id,external_id,event_date,name,event_type,related_entity,fact_summary,system_use,verification_status,source_url,source_type,source_title,created_at FROM events WHERE id=? AND COALESCE(is_active,1)=1", (event_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "message": "事件不存在", "details": {}})
    return single(dict(row))
