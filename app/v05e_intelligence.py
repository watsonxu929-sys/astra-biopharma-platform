from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.dashboard_service import dashboard_data
from app.services.signal_service import convert_signal_to_action, generate_from_confirmed_events, get_signal, list_signals, update_signal_status
from app.services.intelligence_flow_service import convert_signal_to_investment_lead
from app.services.signals import generate_signals, list_rules, set_rule_enabled, signal_dashboard
from app.services.watchlist_service import add_item, create_watchlist, list_items, list_watchlists

router = APIRouter(tags=["v0.5E intelligence API and dashboard"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def current_user_dict(request: Request) -> dict:
    user = getattr(request.state, "current_user", None) or {}
    return dict(user)


@router.get("/intelligence/dashboard", response_class=HTMLResponse)
def intelligence_dashboard(request: Request, days: int = 7, industry: str = "", region: str = "", signal_level: str = ""):
    data = dashboard_data(days=days, industry=industry, region=region, signal_level=signal_level)
    return templates.TemplateResponse(request, "v05e_dashboard.html", {"data": data})


@router.get("/signals", response_class=HTMLResponse)
def signals_page(request: Request, signal_type: str = "", signal_level: str = "", status: str = "", q: str = "", page: int = 1):
    data = list_signals(page=page, signal_type=signal_type, signal_level=signal_level, status=status, q=q)
    return templates.TemplateResponse(request, "v05e_signals.html", {"mode": "list", "result": data})


@router.get("/signals/dashboard", response_class=HTMLResponse)
def signals_dashboard_page(request: Request, message: str = ""):
    return templates.TemplateResponse(request, "v05e_signals.html", {"mode": "dashboard", "dashboard": signal_dashboard(), "message": message})


@router.get("/signals/alerts", response_class=HTMLResponse)
def signals_alerts_page(request: Request, status: str = "", q: str = "", page: int = 1):
    data = list_signals(page=page, signal_level="high", status=status, q=q)
    return templates.TemplateResponse(request, "v05e_signals.html", {"mode": "list", "result": data})


@router.get("/signals/rules", response_class=HTMLResponse)
def signals_rules_page(request: Request, message: str = ""):
    return templates.TemplateResponse(request, "v05e_signals.html", {"mode": "rules", "rules": list_rules(), "message": message})


@router.post("/signals/rules/{rule_id:int}/toggle")
def signals_rule_toggle(rule_id: int, enabled: str = Form("")):
    set_rule_enabled(rule_id, bool(enabled))
    return RedirectResponse("/signals/rules?message=updated", status_code=303)


@router.post("/signals/run")
def signals_run(since: str = Form(""), limit: int = Form(100), confirm: str = Form("")):
    result = generate_signals(since=since, limit=limit, dry_run=not bool(confirm))
    return RedirectResponse(f"/signals/dashboard?message=created:{result['created']},candidates:{result['candidates']}", status_code=303)


@router.get("/signals/watchlists", response_class=HTMLResponse)
def signals_watchlists_page():
    return RedirectResponse("/watchlists", status_code=303)


@router.get("/signals/{signal_id:int}", response_class=HTMLResponse)
def signal_detail_page(request: Request, signal_id: int):
    item = get_signal(signal_id)
    return templates.TemplateResponse(request, "v05e_signals.html", {"mode": "detail", "signal": item})


@router.post("/signals/generate")
def signals_generate(limit: int = Form(50)):
    result = generate_from_confirmed_events(limit=limit)
    return RedirectResponse(f"/signals?message=created:{result['created']},skipped:{result['skipped']}", status_code=303)


@router.post("/signals/{signal_id:int}/status")
def signal_status_page(signal_id: int, status: str = Form(...)):
    update_signal_status(signal_id, status)
    return RedirectResponse(f"/signals/{signal_id:int}", status_code=303)


@router.post("/signals/{signal_id:int}/convert-action")
def signal_convert_page(request: Request, signal_id: int):
    convert_signal_to_action(signal_id, owner=current_username(request))
    return RedirectResponse(f"/signals/{signal_id:int}", status_code=303)


@router.post("/signals/{signal_id:int}/convert-lead")
def signal_convert_lead_page(request: Request, signal_id: int):
    convert_signal_to_investment_lead(signal_id, owner=current_username(request))
    return RedirectResponse(f"/signals/{signal_id:int}", status_code=303)


@router.get("/watchlists", response_class=HTMLResponse)
def watchlists_page(request: Request, page: int = 1):
    data = list_watchlists(current_user_dict(request), page=page)
    return templates.TemplateResponse(request, "v05e_watchlists.html", {"mode": "list", "result": data})


@router.post("/watchlists")
def watchlist_create_page(request: Request, name: str = Form(...), category: str = Form("custom"), description: str = Form(""), visibility: str = Form("private")):
    create_watchlist(current_user_dict(request), name=name, category=category, description=description, visibility=visibility)
    return RedirectResponse("/watchlists", status_code=303)


@router.get("/watchlists/{watchlist_id:int}", response_class=HTMLResponse)
def watchlist_detail_page(request: Request, watchlist_id: int, page: int = 1):
    data = list_items(current_user_dict(request), watchlist_id, page=page)
    return templates.TemplateResponse(request, "v05e_watchlists.html", {"mode": "detail", "result": data, "watchlist_id": watchlist_id})


@router.post("/watchlists/{watchlist_id:int}/items")
def watchlist_add_item_page(request: Request, watchlist_id: int, subject_type: str = Form(...), subject_id: str = Form(...), priority: str = Form("medium"), reason: str = Form("")):
    add_item(current_user_dict(request), watchlist_id=watchlist_id, subject_type=subject_type, subject_id=subject_id, priority=priority, reason=reason)
    return RedirectResponse(f"/watchlists/{watchlist_id:int}", status_code=303)


@router.get("/v05e/health")
def health():
    return {"ok": True, "version": "0.5E"}

