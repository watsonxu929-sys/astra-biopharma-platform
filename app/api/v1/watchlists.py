from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.security import record_audit
from app.services.api_common import require_permission, single
from app.services.watchlist_service import add_item, create_watchlist, list_items, list_watchlists, remove_item

router = APIRouter(prefix="/watchlists")


@router.get("", summary="List watchlists")
def watchlists_list(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    user = require_permission(request, "view_internal")
    return list_watchlists(user, page=page, page_size=page_size)


@router.post("", summary="Create watchlist")
def watchlist_create(request: Request, name: str, category: str = "custom", description: str = "", visibility: str = "private"):
    user = require_permission(request, "edit_data")
    try:
        item = create_watchlist(user, name=name, category=category, description=description, visibility=visibility)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_WATCHLIST", "message": str(exc), "details": {}})
    record_audit(action="api_watchlist_create", actor=user, method="POST", path="/api/v1/watchlists", target_type="watchlist", target_id=str(item["id"]))
    return single(item)


@router.get("/{watchlist_id}/items", summary="List watchlist items")
def watchlist_items(request: Request, watchlist_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    user = require_permission(request, "view_internal")
    data = list_items(user, watchlist_id, page=page, page_size=page_size)
    if not data["meta"].get("watchlist_found", True):
        raise HTTPException(status_code=404, detail={"code": "WATCHLIST_NOT_FOUND", "message": "关注清单不存在", "details": {}})
    return data


@router.post("/{watchlist_id}/items", summary="Add subject to watchlist")
def watchlist_add_item(request: Request, watchlist_id: int, subject_type: str, subject_id: str, priority: str = "medium", reason: str = "", note: str = ""):
    user = require_permission(request, "edit_data")
    try:
        result = add_item(user, watchlist_id=watchlist_id, subject_type=subject_type, subject_id=subject_id, priority=priority, reason=reason, note=note)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_WATCHLIST_ITEM", "message": str(exc), "details": {}})
    if result.get("reason") == "watchlist_not_found":
        raise HTTPException(status_code=404, detail={"code": "WATCHLIST_NOT_FOUND", "message": "关注清单不存在", "details": {}})
    if result.get("reason") == "subject_not_found":
        raise HTTPException(status_code=404, detail={"code": "SUBJECT_NOT_FOUND", "message": "主体不存在", "details": {}})
    record_audit(action="api_watchlist_add_item", actor=user, method="POST", path=f"/api/v1/watchlists/{watchlist_id}/items", target_type="watchlist", target_id=str(watchlist_id), detail={"subject_type": subject_type, "subject_id": subject_id})
    return single(result)


@router.post("/items/{item_id}/remove", summary="Soft remove watchlist item")
def watchlist_remove_item(request: Request, item_id: int):
    user = require_permission(request, "edit_data")
    ok = remove_item(user, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": "WATCHLIST_ITEM_NOT_FOUND", "message": "关注项不存在", "details": {}})
    record_audit(action="api_watchlist_remove_item", actor=user, method="POST", path=f"/api/v1/watchlists/items/{item_id}/remove", target_type="watchlist_item", target_id=str(item_id))
    return single({"removed": True})
