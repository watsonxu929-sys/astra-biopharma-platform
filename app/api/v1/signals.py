from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.security import record_audit
from app.services.api_common import require_permission, single
from app.services.signal_service import convert_signal_to_action, generate_from_confirmed_events, get_signal, list_signals, update_signal_status
from app.services.signals import list_rules, signal_dashboard

router = APIRouter(prefix="/signals")


@router.get("", summary="List industry signals")
def signals_list(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), signal_type: str = "", signal_level: str = "", status: str = "", q: str = ""):
    require_permission(request, "view_internal")
    return list_signals(page=page, page_size=page_size, signal_type=signal_type, signal_level=signal_level, status=status, q=q)


@router.get("/dashboard", summary="Signal dashboard")
def signals_dashboard(request: Request):
    require_permission(request, "view_internal")
    return single(signal_dashboard())


@router.get("/rules", summary="Signal rules")
def signals_rules(request: Request):
    require_permission(request, "view_internal")
    return single({"rules": list_rules()})


@router.post("/generate-from-events", summary="Generate signals from confirmed events", description="Manual and limited generation; never converts unreviewed drafts into formal signals.")
def generate_signals(request: Request, limit: int = Query(50, ge=1, le=200)):
    user = require_permission(request, "review_data")
    result = generate_from_confirmed_events(limit=limit)
    record_audit(action="api_generate_signals", actor=user, method="POST", path="/api/v1/signals/generate-from-events", detail=result)
    return single(result)


@router.get("/{signal_id:int}", summary="Get industry signal")
def signal_detail(request: Request, signal_id: int):
    require_permission(request, "view_internal")
    item = get_signal(signal_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "SIGNAL_NOT_FOUND", "message": "signal not found", "details": {}})
    return single(item)


@router.post("/{signal_id:int}/status", summary="Update signal status")
def signal_status(request: Request, signal_id: int, status: str):
    user = require_permission(request, "review_data")
    try:
        item = update_signal_status(signal_id, status)
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATUS", "message": "invalid signal status", "details": {"status": status}})
    if not item:
        raise HTTPException(status_code=404, detail={"code": "SIGNAL_NOT_FOUND", "message": "signal not found", "details": {}})
    record_audit(action="api_signal_status", actor=user, method="POST", path=f"/api/v1/signals/{signal_id:int}/status", target_type="signal", target_id=str(signal_id), detail={"status": status})
    return single(item)


@router.post("/{signal_id:int}/read", summary="Mark signal as read")
def signal_read(request: Request, signal_id: int):
    return signal_status(request, signal_id, "reviewed")


@router.post("/{signal_id:int}/important", summary="Mark signal as important")
def signal_important(request: Request, signal_id: int):
    return signal_status(request, signal_id, "important")


@router.post("/{signal_id:int}/ignore", summary="Ignore signal")
def signal_ignore(request: Request, signal_id: int):
    return signal_status(request, signal_id, "ignored")


@router.post("/{signal_id:int}/convert-action", summary="Convert signal to action after manual confirmation")
def signal_convert_action(request: Request, signal_id: int):
    user = require_permission(request, "edit_data")
    result = convert_signal_to_action(signal_id, owner=user.get("username") or "manual")
    if result.get("reason") == "not_found":
        raise HTTPException(status_code=404, detail={"code": "SIGNAL_NOT_FOUND", "message": "signal not found", "details": {}})
    record_audit(action="api_signal_convert_action", actor=user, method="POST", path=f"/api/v1/signals/{signal_id:int}/convert-action", target_type="signal", target_id=str(signal_id), detail=result)
    return single(result)

