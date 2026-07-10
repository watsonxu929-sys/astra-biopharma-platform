from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.recommendation_service import (
    CATEGORY_LABELS,
    STATUS_LABELS,
    create_action_from_recommendation,
    ensure_schema,
    list_recommendations,
    recommendation_detail,
    recommendation_stats,
    refresh_recommendations,
    update_decision,
)
from app.services.relationship_path_service import find_qbay_paths, path_to_template_parts
from app.v04c_review import db_connection

router = APIRouter(tags=["v0.4H recommendations"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def render(request: Request, **context):
    return templates.TemplateResponse(
        request=request,
        name="v04h_recommendations.html",
        context=context,
    )


@router.get("/recommendations", response_class=HTMLResponse)
def recommendation_center(
    request: Request,
    q: str = Query(""),
    category: str = Query(""),
    status: str = Query("open"),
    min_score: int = Query(0, ge=0, le=100),
    page: int = Query(1, ge=1),
):
    ensure_schema()
    with db_connection() as conn:
        result = list_recommendations(
            conn,
            q=q,
            category=category,
            status=status,
            min_score=min_score,
            page=page,
        )
        stats = recommendation_stats(conn)
    return render(
        request,
        mode="list",
        stats=stats,
        categories=CATEGORY_LABELS,
        statuses=STATUS_LABELS,
        filters={"q": q, "category": category, "status": status, "min_score": min_score},
        **result,
    )


@router.post("/recommendations/refresh")
def refresh_center(
    lead_limit: int = Form(200),
    pair_limit: int = Form(2500),
):
    safe_lead_limit = max(1, min(500, int(lead_limit or 200)))
    safe_pair_limit = max(100, min(10000, int(pair_limit or 2500)))
    result = refresh_recommendations(lead_limit=safe_lead_limit, pair_limit=safe_pair_limit)
    return RedirectResponse(
        f"/recommendations?status=open&refresh_created={result['created']}&refresh_updated={result['updated']}",
        status_code=303,
    )


@router.get("/recommendations/path", response_class=HTMLResponse)
def relationship_path_explorer(
    request: Request,
    subject_type: str = Query("organization"),
    subject_id: str = Query(""),
):
    ensure_schema()
    result = {"subject": None, "paths": [], "anchor_count": 0}
    if subject_id.strip():
        with db_connection() as conn:
            result = find_qbay_paths(
                conn,
                subject_type,
                subject_id.strip(),
                max_edges=3,
                max_paths=20,
            )
    for path in result["paths"]:
        path["parts"] = path_to_template_parts(path)
    return render(
        request,
        mode="path",
        subject_type=subject_type,
        subject_id=subject_id,
        result=result,
    )


@router.get("/recommendations/{recommendation_id:int}", response_class=HTMLResponse)
def recommendation_view(request: Request, recommendation_id: int):
    ensure_schema()
    with db_connection() as conn:
        item = recommendation_detail(conn, recommendation_id)
    if not item:
        raise HTTPException(404, "recommendation not found")
    return render(
        request,
        mode="detail",
        item=item,
        categories=CATEGORY_LABELS,
        statuses=STATUS_LABELS,
        default_snooze=(date.today() + timedelta(days=7)).isoformat(),
    )


@router.post("/recommendations/{recommendation_id:int}/decision")
def recommendation_decision(
    request: Request,
    recommendation_id: int,
    status: str = Form(...),
    actor: str = Form("manual"),
    reason: str = Form(""),
    snoozed_until: str = Form(""),
):
    actor = current_username(request)
    try:
        update_decision(
            recommendation_id,
            status,
            actor=actor,
            reason=reason,
            snoozed_until=snoozed_until,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(f"/recommendations/{recommendation_id:int}", status_code=303)


@router.post("/recommendations/{recommendation_id:int}/action")
def recommendation_action(
    request: Request,
    recommendation_id: int,
    owner: str = Form(""),
    deadline: str = Form(""),
):
    owner = owner.strip() or current_username(request)
    try:
        create_action_from_recommendation(
            recommendation_id,
            owner=owner,
            deadline=deadline,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(f"/recommendations/{recommendation_id:int}", status_code=303)


@router.get("/v04h/health")
def v04h_health():
    ensure_schema()
    return {"status": "ok", "version": "v0.4H"}



