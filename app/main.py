from pathlib import Path
import re
from typing import Any
from app.v04c_review import db_connection, router as v04c_review_router
from app.v04c1_ingestion import router as v04c1_ingestion_router
from app.v04d_structuring import router as v04d_structuring_router
from app.v04db_prestructure import router as v04db_prestructure_router
from app.v04e_entity_resolution import router as v04e_entity_resolution_router
from app.v04f_operations import router as v04f_operations_router
from app.v04g_monitoring import router as v04g_monitoring_router
from app.v04h_recommendations import router as v04h_recommendations_router
from app.v05a_security import router as v05a_security_router
from app.v05b_member_import import router as v05b_member_import_router
from app.v05c_club_events import router as v05c_club_events_router
from app.v05d_member_portal import router as v05d_member_portal_router
from app.v05e_intelligence import router as v05e_intelligence_router
from app.v05f_collection import router as v05f_collection_router
from app.v05g_processing import router as v05g_processing_router
from app.v05h_reports import router as v05h_reports_router
from app.v05i_pipeline import router as v05i_pipeline_router
from app.v05j_research import router as v05j_research_router
from app.p2_3_research import router as p2_3_research_router
from app.p3_network import router as p3_network_router
from app.p5_collaboration import router as p5_collaboration_router
from app.v05kl_operations import router as v05kl_operations_router
from app.api.v1.router import router as api_v1_router
from app.identity import router as identity_router
from app.routes_platform import router as platform_router
from app.routes_golden_loop import router as golden_loop_router
from app.security import SecurityMiddleware
from datetime import datetime
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import bindparam, desc, func, or_, select, text
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from .crud_config import ENTITY_CONFIGS
from .entity_analyzer import analyze_entity
from .services.manual_ingestion import inspect_entity_text, validate_entity_submission
from .services.subject_links import (
    ensure_person_organization_relation,
    lookup_organizations,
    person_has_org_relation,
    relation_view_rows,
    resolve_organization,
)
from .services.subject_profile_service import (
    normalize_subject_type,
    subject_center,
    subject_profile,
)
from .services.recommendation_service import subject_recommendations
from .services.search_service import search_all
from .navigation import navigation_for
from .services.suspicious_review import (
    deactivate_suspicious_record,
    suspicious_records,
)
from .web_extractor import fetch_and_extract
from .database import get_db
from .services.data_quality import (
    check_organization_duplicates,
    organization_reference_count,
    resolve_owner_organization,
)
from .services.id_generator import assign_system_id
from .models import (
    ActionItem,
    HistoricalEvent,
    ImportLog,
    Organization,
    Person,
    ProjectPool,
    RawIntelligence,
    Relation,
    Resource,
)

app = FastAPI(title="生物医药产业情报系统")


@app.on_event("startup")
async def startup_event():
    import os
    from app.services.collection_scheduler import start_scheduler
    db_url = os.environ.get("DATABASE_URL", "")
    app.state.is_acceptance = "acceptance" in db_url.lower()
    print(f"[ENVIRONMENT] Acceptance Mode: {app.state.is_acceptance}")
    try:
        started = start_scheduler()
        print(f"[SCHEDULER] Started: {started}")
    except Exception as exc:
        print(f"[SCHEDULER] Startup failed: {exc}")


@app.on_event("shutdown")
async def shutdown_event():
    from app.services.collection_scheduler import stop_scheduler
    try:
        stop_scheduler()
        print("[SCHEDULER] Stopped")
    except Exception as exc:
        print(f"[SCHEDULER] Shutdown failed: {exc}")
app.state.navigation_for = navigation_for
app.add_middleware(SecurityMiddleware)
app.include_router(v04c_review_router)
app.include_router(v04c1_ingestion_router)
app.include_router(v04d_structuring_router)
app.include_router(v04db_prestructure_router)
app.include_router(v04e_entity_resolution_router)
app.include_router(v04f_operations_router)
app.include_router(v04g_monitoring_router)
app.include_router(v04h_recommendations_router)
app.include_router(v05a_security_router)
app.include_router(v05b_member_import_router)
app.include_router(v05c_club_events_router)
app.include_router(v05d_member_portal_router)
app.include_router(v05e_intelligence_router)
app.include_router(v05f_collection_router)
app.include_router(v05g_processing_router)
app.include_router(v05h_reports_router)
app.include_router(v05i_pipeline_router)
app.include_router(v05j_research_router)
app.include_router(p2_3_research_router)
app.include_router(p3_network_router)
app.include_router(p5_collaboration_router)
app.include_router(v05kl_operations_router)
app.include_router(identity_router)
app.include_router(platform_router)
app.include_router(golden_loop_router)
app.include_router(api_v1_router)
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.middleware("http")
async def custom_404_middleware(request: Request, call_next):
    """Middleware: intercept 404 responses and serve custom HTML error page."""
    response = await call_next(request)
    if response.status_code == 404 and request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND", "message": "API \u8def\u5f84\u4e0d\u5b58\u5728", "details": {}}})
    if response.status_code == 404 and not request.url.path.startswith("/api/") and not request.url.path.startswith("/static/"):
        return templates.TemplateResponse(request=request, name="platform/error_404.html", context={"request": request}, status_code=404)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = detail.get("code") or ("NOT_FOUND" if exc.status_code == 404 else "API_ERROR")
        message = detail.get("message") or (str(exc.detail) if exc.detail else "API request failed")
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": message, "details": detail.get("details") or {}}})
    if exc.status_code == 404:
        return templates.TemplateResponse(request=request, name="platform/error_404.html", context={"request": request}, status_code=404)
    if exc.status_code == 403:
        return templates.TemplateResponse(request=request, name="platform/error_403.html", context={"request": request}, status_code=403)
    return templates.TemplateResponse(request=request, name="platform/error_500.html", context={"request": request}, status_code=500)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"[500 ERROR] {request.url.path}: {exc}", flush=True)
    traceback.print_exc()
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}})
    return templates.TemplateResponse(request=request, name="platform/error_500.html", context={"request": request}, status_code=500)


def render(request: Request, name: str, **context):
    return templates.TemplateResponse(request=request, name=name, context=context)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like_any(term: str, *columns) -> ColumnElement[bool]:
    pattern = f"%{_escape_like(term.lower())}%"
    return or_(
        *[
            func.lower(func.coalesce(column, "")).like(pattern, escape="\\")
            for column in columns
        ]
    )


def _text_join(*values: Any) -> str:
    return " / ".join(str(value).strip() for value in values if value not in (None, ""))


def _review_summary(db: Session, subject_type: str, subject_id: str | None) -> dict[str, int | str]:
    if not subject_id:
        return {"open_count": 0, "conflict_count": 0, "url": "/review"}
    aliases = {
        "org": ["org", "organization", "organizations"],
        "person": ["person", "people"],
        "project": ["project", "projects"],
        "resource": ["resource", "resources"],
        "event": ["event", "events"],
    }.get(subject_type, [subject_type])
    try:
        data = db.execute(
            text(
                """
                SELECT
                  COUNT(*) AS open_count,
                  SUM(CASE WHEN item_type='conflict' THEN 1 ELSE 0 END) AS conflict_count
                FROM v04c_review_items
                WHERE subject_id = :subject_id
                  AND subject_type IN :subject_types
                  AND status IN ('pending','in_review','deferred')
                """
            ).bindparams(bindparam("subject_types", expanding=True)),
            {"subject_id": subject_id, "subject_types": aliases},
        ).mappings().first()
    except OperationalError:
        data = None
    open_count = int(data["open_count"] or 0) if data else 0
    conflict_count = int(data["conflict_count"] or 0) if data else 0
    return {
        "open_count": open_count,
        "conflict_count": conflict_count,
        "url": f"/review?q={subject_id}",
    }


def _search_group(
    db: Session,
    *,
    term: str,
    label: str,
    model,
    fields: list[Any],
    title_getter,
    summary_getter,
    status_getter,
    url_getter,
    limit: int,
    order_by=None,
) -> dict[str, Any]:
    stmt = select(model).where(_like_any(term, *fields)).limit(limit)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    rows = db.scalars(stmt).all()
    seen: set[tuple[str, Any]] = set()
    items = []
    for row in rows:
        key = (model.__tablename__, getattr(row, "id", id(row)))
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "code": getattr(row, "external_id", None) or f"#{getattr(row, 'id', '')}",
                "title": title_getter(row),
                "summary": summary_getter(row),
                "status": status_getter(row),
                "url": url_getter(row),
            }
        )
    return {"label": label, "results": items, "count": len(items)}


def _form_value(field, form):
    value = str(form.get(field.name, "")).strip()
    if field.name == "manually_confirmed":
        return value == "true"
    return value or None


def _form_context(
    config,
    item,
    error=None,
    mode="new",
    duplicate_result=None,
    ref_count=0,
    validation_warnings=None,
    diagnostics=None,
):
    return {
        "config": config,
        "item": item,
        "error": error,
        "mode": mode,
        "duplicate_result": duplicate_result,
        "ref_count": ref_count,
        "validation_warnings": validation_warnings or [],
        "diagnostics": diagnostics,
    }


def _commit_with_generated_id(db: Session, obj, entity_key: str):
    for _ in range(5):
        assign_system_id(db, obj, entity_key)
        try:
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return
        except IntegrityError:
            db.rollback()
            obj.external_id = None
    raise HTTPException(500, "系统编号生成失败，请重试。")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    # Redirect to platform home for authenticated users
    sec = request.scope.get("security_context", {})
    if sec.get("authenticated"):
        return RedirectResponse("/platform", status_code=302)
    # Legacy dashboard for unauthenticated / backward compatibility
    counts = {
        "raw_intelligence": db.scalar(select(func.count()).select_from(RawIntelligence)) or 0,
        "organizations": db.scalar(select(func.count()).select_from(Organization)) or 0,
        "people": db.scalar(select(func.count()).select_from(Person)) or 0,
        "projects": db.scalar(select(func.count()).select_from(ProjectPool)) or 0,
        "resources": db.scalar(select(func.count()).select_from(Resource)) or 0,
        "events": db.scalar(select(func.count()).select_from(HistoricalEvent)) or 0,
        "relations": db.scalar(select(func.count()).select_from(Relation)) or 0,
        "actions": db.scalar(select(func.count()).select_from(ActionItem)) or 0,
    }
    try:
        review_counts = db.execute(
            text(
                """
                SELECT
                  COUNT(*) AS open_count,
                  SUM(CASE WHEN item_type='conflict' THEN 1 ELSE 0 END) AS conflict_count
                FROM v04c_review_items
                WHERE status IN ('pending','in_review','deferred')
                """
            )
        ).mappings().first()
    except OperationalError:
        review_counts = None
    counts["open_reviews"] = int(review_counts["open_count"] or 0) if review_counts else 0
    counts["open_conflicts"] = int(review_counts["conflict_count"] or 0) if review_counts else 0
    try:
        flow_counts = db.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM v04g_monitoring_sources WHERE is_enabled=1 AND deactivated_at IS NULL) AS collection_sources,
                  (SELECT COUNT(*) FROM v05f_collection_items WHERE date(created_at)=date('now','localtime')) AS today_collection_items,
                  (SELECT COUNT(*) FROM v05f_collection_items WHERE processing_status='queued') AS pending_processing,
                  (SELECT COUNT(*) FROM v04g_monitoring_runs WHERE status='failed') AS failed_collection_jobs,
                  (SELECT COUNT(*) FROM v05g_extraction_candidates WHERE review_status IN ('pending','needs_review')) AS pending_candidates,
                  (SELECT COUNT(*) FROM v05g_subject_match_candidates WHERE status='ambiguous') AS ambiguous_subject_matches,
                  (SELECT COUNT(*) FROM v05e_industry_signals WHERE signal_level IN ('critical','high') AND status IN ('new','important','reviewed')) AS high_signals,
                  (SELECT COUNT(*) FROM v05e_industry_signals WHERE signal_type IN ('resource_need','strategic_cooperation','financing') AND status IN ('new','important','reviewed')) AS investment_opportunities,
                  (SELECT COUNT(*) FROM v04f_lead_records WHERE status='active') AS active_leads,
                  (SELECT COUNT(*) FROM v05h_generated_reports WHERE status IN ('under_review','generated')) AS pending_reports
                """
            )
        ).mappings().first()
    except OperationalError:
        flow_counts = None
    for key in ["collection_sources", "today_collection_items", "pending_processing", "failed_collection_jobs", "pending_candidates", "ambiguous_subject_matches", "high_signals", "investment_opportunities", "active_leads", "pending_reports"]:
        counts[key] = int(flow_counts[key] or 0) if flow_counts else 0
    latest_actions = db.scalars(select(ActionItem).order_by(desc(ActionItem.created_at)).limit(6)).all()
    latest_events = db.scalars(select(HistoricalEvent).order_by(desc(HistoricalEvent.created_at)).limit(6)).all()
    return render(request, "dashboard.html", counts=counts, latest_actions=latest_actions, latest_events=latest_events)


@app.get("/dashboard", include_in_schema=False)
def legacy_dashboard_alias():
    return RedirectResponse("/platform", status_code=303)


@app.get("/search", response_class=HTMLResponse)
def global_search(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    result = search_all(q, per_type_limit=30)
    return render(request, "search_results.html", q=result["q"], groups=result["groups"], total=result["total"])
    term = (q or "").strip()
    limit = 30
    groups: list[dict[str, Any]] = []
    if term:
        groups = [
            _search_group(
                db,
                term=term,
                label="浼佷笟/鏈烘瀯",
                model=Organization,
                fields=[
                    Organization.external_id,
                    Organization.standard_name,
                    Organization.org_type,
                    Organization.region,
                    Organization.industry_tags,
                    Organization.resources,
                    Organization.needs,
                    Organization.relationship_source,
                    Organization.source_title,
                    Organization.source_text,
                ],
                title_getter=lambda row: row.standard_name,
                summary_getter=lambda row: _text_join(row.org_type, row.region, row.industry_tags),
                status_getter=lambda row: "已失效" if row.is_active is False else row.verification_status,
                url_getter=lambda row: f"/organizations/{row.id}",
                limit=limit,
                order_by=Organization.standard_name,
            ),
            _search_group(
                db,
                term=term,
                label="浜虹墿",
                model=Person,
                fields=[
                    Person.external_id,
                    Person.name,
                    Person.public_role,
                    Person.organization_network,
                    Person.ability_tags,
                    Person.value_provided,
                    Person.relationship_source,
                    Person.source_title,
                    Person.source_text,
                ],
                title_getter=lambda row: row.name,
                summary_getter=lambda row: _text_join(row.public_role, row.organization_network, row.ability_tags),
                status_getter=lambda row: "已失效" if row.is_active is False else row.verification_status,
                url_getter=lambda row: f"/people/{row.id}",
                limit=limit,
                order_by=Person.name,
            ),
            _search_group(
                db,
                term=term,
                label="椤圭洰",
                model=ProjectPool,
                fields=[
                    ProjectPool.external_id,
                    ProjectPool.name,
                    ProjectPool.project_type,
                    ProjectPool.owner_external_id,
                    ProjectPool.focus_tags,
                    ProjectPool.typical_needs,
                    ProjectPool.target_actions,
                    ProjectPool.status,
                    ProjectPool.source_title,
                    ProjectPool.source_text,
                ],
                title_getter=lambda row: row.name,
                summary_getter=lambda row: _text_join(row.project_type, row.owner_external_id, row.focus_tags),
                status_getter=lambda row: "已失效" if row.is_active is False else row.status,
                url_getter=lambda row: f"/projects/{row.id}",
                limit=limit,
                order_by=ProjectPool.name,
            ),
            _search_group(
                db,
                term=term,
                label="浜嬩欢",
                model=HistoricalEvent,
                fields=[
                    HistoricalEvent.external_id,
                    HistoricalEvent.name,
                    HistoricalEvent.event_type,
                    HistoricalEvent.related_entity,
                    HistoricalEvent.fact_summary,
                    HistoricalEvent.system_use,
                    HistoricalEvent.verification_status,
                    HistoricalEvent.source_title,
                    HistoricalEvent.source_text,
                ],
                title_getter=lambda row: row.name,
                summary_getter=lambda row: _text_join(row.event_date, row.event_type, row.fact_summary),
                status_getter=lambda row: "已失效" if row.is_active is False else row.verification_status,
                url_getter=lambda row: f"/events/{row.id}",
                limit=limit,
                order_by=desc(HistoricalEvent.created_at),
            ),
            _search_group(
                db,
                term=term,
                label="璧勬簮",
                model=Resource,
                fields=[
                    Resource.external_id,
                    Resource.owner_external_id,
                    Resource.category,
                    Resource.description,
                    Resource.region,
                    Resource.applicable_to,
                    Resource.verification_status,
                    Resource.source_title,
                    Resource.source_text,
                ],
                title_getter=lambda row: row.category or row.external_id,
                summary_getter=lambda row: _text_join(row.region, row.description, row.applicable_to),
                status_getter=lambda row: "已失效" if row.is_active is False else row.verification_status,
                url_getter=lambda row: f"/resources/{row.id}",
                limit=limit,
                order_by=Resource.external_id,
            ),
            _search_group(
                db,
                term=term,
                label="鍏崇郴",
                model=Relation,
                fields=[
                    Relation.external_id,
                    Relation.source_external_id,
                    Relation.relation_type,
                    Relation.target_external_id,
                    Relation.period,
                    Relation.evidence_source,
                    Relation.verification_status,
                    Relation.source_title,
                    Relation.source_text,
                ],
                title_getter=lambda row: f"{row.source_external_id} - {row.relation_type} - {row.target_external_id}",
                summary_getter=lambda row: _text_join(row.period, row.evidence_source),
                status_getter=lambda row: "已失效" if row.is_active is False else row.verification_status,
                url_getter=lambda row: f"/relations?q={row.external_id}",
                limit=limit,
                order_by=Relation.external_id,
            ),
            _search_group(
                db,
                term=term,
                label="琛屽姩浠诲姟",
                model=ActionItem,
                fields=[
                    ActionItem.external_id,
                    ActionItem.task,
                    ActionItem.target_external_id,
                    ActionItem.completion_standard,
                    ActionItem.owner,
                    ActionItem.priority,
                    ActionItem.status,
                    ActionItem.source_title,
                    ActionItem.source_text,
                ],
                title_getter=lambda row: row.task,
                summary_getter=lambda row: _text_join(row.owner, row.priority, row.completion_standard),
                status_getter=lambda row: "已失效" if row.is_active is False else row.status,
                url_getter=lambda row: f"/actions?q={row.external_id}",
                limit=limit,
                order_by=ActionItem.external_id,
            ),
            _search_group(
                db,
                term=term,
                label="鎯呮姤璁板綍",
                model=RawIntelligence,
                fields=[
                    RawIntelligence.title,
                    RawIntelligence.source_url,
                    RawIntelligence.source_type,
                    RawIntelligence.content,
                    RawIntelligence.review_status,
                ],
                title_getter=lambda row: row.title,
                summary_getter=lambda row: _text_join(row.source_type, row.content[:120] if row.content else ""),
                status_getter=lambda row: row.review_status,
                url_getter=lambda row: f"/intelligence/{row.id}",
                limit=limit,
                order_by=desc(RawIntelligence.created_at),
            ),
            _search_group(
                db,
                term=term,
                label="瀵煎叆璁板綍",
                model=ImportLog,
                fields=[ImportLog.filename, ImportLog.result_json],
                title_getter=lambda row: row.filename,
                summary_getter=lambda row: row.result_json[:120] if row.result_json else "",
                status_getter=lambda row: "已导入",
                url_getter=lambda row: "/imports",
                limit=limit,
                order_by=desc(ImportLog.imported_at),
            ),
        ]
    total = sum(group["count"] for group in groups)
    return render(request, "search_results.html", q=term, groups=groups, total=total)


# ---------- Raw intelligence ----------
@app.get("/intelligence/new", response_class=HTMLResponse)
def new_intelligence(request: Request):
    return render(request, "new_intelligence.html", error=None)


@app.post("/intelligence/new")
def create_intelligence(
    request: Request,
    title: str = Form(...),
    source_url: str = Form(""),
    source_type: str = Form("人工录入"),
    content: str = Form(...),
    visibility: str = Form("内部"),
    db: Session = Depends(get_db),
):
    title, content, source_url = title.strip(), content.strip(), source_url.strip()
    if not title or len(content) < 10:
        return templates.TemplateResponse(
            request=request, name="new_intelligence.html",
            context={"error": "标题不能为空，正文至少 10 个字符。"}, status_code=400
        )
    item = RawIntelligence(
        title=title, source_url=source_url or None, source_type=source_type,
        content=content, visibility=visibility, review_status="待分析"
    )
    db.add(item); db.commit(); db.refresh(item)
    return RedirectResponse(url=f"/intelligence/{item.id}", status_code=303)


@app.get("/intelligence/legacy", response_class=HTMLResponse)
def list_intelligence(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    stmt = select(RawIntelligence).order_by(desc(RawIntelligence.created_at))
    if q.strip():
        k = f"%{q.strip()}%"
        stmt = stmt.where(or_(RawIntelligence.title.like(k), RawIntelligence.content.like(k), RawIntelligence.source_type.like(k)))
    return render(request, "intelligence_list.html", items=db.scalars(stmt).all(), q=q)


@app.get("/intelligence/legacy/{item_id:int}", response_class=HTMLResponse)
def intelligence_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.get(RawIntelligence, item_id)
    if not item: raise HTTPException(404, "情报不存在")
    return render(request, "intelligence_detail.html", item=item)


@app.post("/intelligence/legacy/{item_id:int}/status")
def update_intelligence_status(item_id: int, review_status: str = Form(...), db: Session = Depends(get_db)):
    item = db.get(RawIntelligence, item_id)
    if not item: raise HTTPException(404, "情报不存在")
    item.review_status = review_status; db.commit()
    return RedirectResponse(url=f"/intelligence/legacy/{item_id}", status_code=303)


@app.post("/intelligence/legacy/{item_id:int}/delete")
def delete_intelligence(item_id: int, db: Session = Depends(get_db)):
    item = db.get(RawIntelligence, item_id)
    if not item: raise HTTPException(404, "情报不存在")
    db.delete(item); db.commit()
    return RedirectResponse(url="/intelligence", status_code=303)


# ---------- Generic CRUD ----------
@app.get("/manage/{entity_key}/new", response_class=HTMLResponse)
def generic_new(entity_key: str, request: Request):
    config = ENTITY_CONFIGS.get(entity_key)
    if not config: raise HTTPException(404, "未知数据类型")
    return render(request, "generic_form.html", **_form_context(config, None, mode="new"))


@app.post("/manage/{entity_key}/new")
async def generic_create(entity_key: str, request: Request, db: Session = Depends(get_db)):
    config = ENTITY_CONFIGS.get(entity_key)
    if not config:
        raise HTTPException(404, "未知数据类型")

    form = await request.form()
    values: dict[str, Any] = {}
    missing_labels: list[str] = []
    for field in config.fields:
        value = _form_value(field, form)
        values[field.name] = value or None
        if field.required and not value:
            missing_labels.append(field.label)

    obj = config.model(**values)
    if missing_labels:
        return templates.TemplateResponse(
            request=request,
            name="generic_form.html",
            context=_form_context(
                config,
                obj,
                f"以下必填项不能为空：{'、'.join(missing_labels)}。",
                "new",
            ),
            status_code=400,
        )

    validation = validate_entity_submission(entity_key, values)
    if validation["errors"]:
        return templates.TemplateResponse(
            request=request,
            name="generic_form.html",
            context=_form_context(
                config,
                obj,
                "；".join(validation["errors"]),
                "new",
                validation_warnings=validation["warnings"],
                diagnostics=validation["diagnostics"],
            ),
            status_code=400,
        )
    if validation["requires_confirmation"] and form.get("confirm_risky_save") != "1":
        return templates.TemplateResponse(
            request=request,
            name="generic_form.html",
            context=_form_context(
                config,
                obj,
                "系统发现可能的数据归属问题，请核对后勾选确认再保存。",
                "new",
                validation_warnings=validation["warnings"],
                diagnostics=validation["diagnostics"],
            ),
            status_code=400,
        )

    if entity_key == "organizations":
        duplicate_result = check_organization_duplicates(db, obj.standard_name)
        if duplicate_result.blocks_save:
            return templates.TemplateResponse(
                request=request,
                name="generic_form.html",
                context=_form_context(
                    config,
                    obj,
                    "已存在相同或标准化后相同的机构，不能重复新增。",
                    "new",
                    duplicate_result,
                ),
                status_code=400,
            )
        if duplicate_result.similar and form.get("confirm_similar_duplicate") != "1":
            return templates.TemplateResponse(
                request=request,
                name="generic_form.html",
                context=_form_context(
                    config,
                    obj,
                    "发现疑似重复机构，请确认后再保存。",
                    "new",
                    duplicate_result,
                ),
                status_code=400,
            )

    resolve_owner_organization(db, obj)
    obj.auto_generated_fields = "external_id"
    if not obj.source_type:
        obj.source_type = "人工录入"
    if hasattr(obj, "manually_confirmed") and form.get("confirm_risky_save") == "1":
        obj.manually_confirmed = True
        obj.confirmed_fields = "人工核对网页拆分结果"
    _commit_with_generated_id(db, obj, entity_key)
    return RedirectResponse(config.list_path, status_code=303)


@app.get("/manage/{entity_key}/{item_id}/edit", response_class=HTMLResponse)
def generic_edit(entity_key: str, item_id: int, request: Request, db: Session = Depends(get_db)):
    config = ENTITY_CONFIGS.get(entity_key)
    if not config: raise HTTPException(404, "未知数据类型")
    item = db.get(config.model, item_id)
    if not item: raise HTTPException(404, "记录不存在")
    ref_count = organization_reference_count(db, item) if entity_key == "organizations" else 0
    return render(request, "generic_form.html", **_form_context(config, item, mode="edit", ref_count=ref_count))


@app.post("/manage/{entity_key}/{item_id}/edit")
async def generic_update(entity_key: str, item_id: int, request: Request, db: Session = Depends(get_db)):
    config = ENTITY_CONFIGS.get(entity_key)
    if not config:
        raise HTTPException(404, "未知数据类型")
    item = db.get(config.model, item_id)
    if not item:
        raise HTTPException(404, "记录不存在")

    form = await request.form()
    values: dict[str, Any] = {}
    missing_labels: list[str] = []
    for field in config.fields:
        value = _form_value(field, form)
        values[field.name] = value or None
        if field.required and not value:
            missing_labels.append(field.label)

    preview = config.model(**values)
    preview.id = item.id
    preview.external_id = item.external_id
    if missing_labels:
        return templates.TemplateResponse(
            request=request,
            name="generic_form.html",
            context=_form_context(
                config,
                preview,
                f"以下必填项不能为空：{'、'.join(missing_labels)}。",
                "edit",
            ),
            status_code=400,
        )

    validation = validate_entity_submission(entity_key, values)
    if validation["errors"]:
        return templates.TemplateResponse(
            request=request,
            name="generic_form.html",
            context=_form_context(
                config,
                preview,
                "；".join(validation["errors"]),
                "edit",
                validation_warnings=validation["warnings"],
                diagnostics=validation["diagnostics"],
            ),
            status_code=400,
        )
    if validation["requires_confirmation"] and form.get("confirm_risky_save") != "1":
        return templates.TemplateResponse(
            request=request,
            name="generic_form.html",
            context=_form_context(
                config,
                preview,
                "系统发现可能的数据归属问题，请核对后勾选确认再保存。",
                "edit",
                validation_warnings=validation["warnings"],
                diagnostics=validation["diagnostics"],
            ),
            status_code=400,
        )

    if entity_key == "organizations":
        duplicate_result = check_organization_duplicates(db, values.get("standard_name"), item.id)
        if duplicate_result.blocks_save:
            return templates.TemplateResponse(
                request=request,
                name="generic_form.html",
                context=_form_context(
                    config,
                    preview,
                    "已存在相同或标准化后相同的机构，不能重复新增。",
                    "edit",
                    duplicate_result,
                ),
                status_code=400,
            )
        if duplicate_result.similar and form.get("confirm_similar_duplicate") != "1":
            return templates.TemplateResponse(
                request=request,
                name="generic_form.html",
                context=_form_context(
                    config,
                    preview,
                    "发现疑似重复机构，请确认后再保存。",
                    "edit",
                    duplicate_result,
                ),
                status_code=400,
            )

    for field in config.fields:
        setattr(item, field.name, values[field.name])
    if hasattr(item, "manually_confirmed") and (
        item.manually_confirmed or form.get("confirm_risky_save") == "1"
    ):
        item.manually_confirmed = True
        item.confirmed_fields = "人工编辑确认"
    resolve_owner_organization(db, item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="generic_form.html",
            context=_form_context(config, preview, "ID 与其他记录重复。", "edit"),
            status_code=400,
        )
    return RedirectResponse(config.list_path, status_code=303)


@app.post("/manage/{entity_key}/{item_id}/delete")
def generic_delete(entity_key: str, item_id: int, db: Session = Depends(get_db)):
    config = ENTITY_CONFIGS.get(entity_key)
    if not config: raise HTTPException(404, "未知数据类型")
    item = db.get(config.model, item_id)
    if not item: raise HTTPException(404, "记录不存在")
    if entity_key == "organizations":
        ref_count = organization_reference_count(db, item)
        if ref_count:
            item.is_active = False
            item.verification_status = "已失效"
            item.deactivated_at = datetime.now()
            item.deactivated_reason = f"有关联记录 {ref_count} 条，已执行停用而非物理删除。"
            db.commit()
            return RedirectResponse(f"/organizations/{item.id}", status_code=303)
    db.delete(item); db.commit()
    return RedirectResponse(config.list_path, status_code=303)


@app.post("/manage/{entity_key}/{item_id}/restore")
def generic_restore(entity_key: str, item_id: int, db: Session = Depends(get_db)):
    config = ENTITY_CONFIGS.get(entity_key)
    if not config: raise HTTPException(404, "未知数据类型")
    item = db.get(config.model, item_id)
    if not item: raise HTTPException(404, "记录不存在")
    if hasattr(item, "is_active"):
        item.is_active = True
        if getattr(item, "verification_status", "") == "已失效":
            item.verification_status = "待核验"
        item.deactivated_at = None
        item.deactivated_reason = None
        db.commit()
    return RedirectResponse(config.list_path, status_code=303)



@app.get("/processing/review", response_class=HTMLResponse)
def processing_review_legacy_redirect():
    return RedirectResponse("/processing/candidates", status_code=302)


@app.get("/reviews", response_class=HTMLResponse)
def reviews_legacy_redirect():
    return RedirectResponse("/review", status_code=302)
# ---------- Lists and details ----------
@app.get("/subjects", response_class=HTMLResponse)
def subjects_center(
    request: Request,
    subject_type: str = Query(""),
    q: str = Query(""),
    tag: str = Query(""),
    status: str = Query(""),
    has_review: str = Query(""),
    missing_core: bool = Query(False),
    page: int = Query(1),
    db: Session = Depends(get_db),
):
    try:
        data = subject_center(
            db,
            subject_type=subject_type,
            q=q,
            tag=tag,
            status=status,
            has_review=has_review,
            missing_core=missing_core,
            page=page,
            page_size=20,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="涓嶆敮鎸佺殑涓讳綋绫诲瀷") from exc
    return render(request, "subject_center.html", **data, q=q)


@app.get("/subjects/{subject_type}/{subject_id}", response_class=HTMLResponse)
def subject_profile_page(subject_type: str, subject_id: str, request: Request, db: Session = Depends(get_db)):
    normalized_type = normalize_subject_type(subject_type)
    if normalized_type not in {"organization", "person", "project"}:
        raise HTTPException(status_code=404, detail="涓嶆敮鎸佺殑涓讳綋绫诲瀷")
    data = subject_profile(db, normalized_type, subject_id)
    recommendations = []
    if data.get("found") and data.get("subject"):
        try:
            with db_connection() as conn:
                recommendations = subject_recommendations(
                    conn,
                    normalized_type,
                    data["subject"]["external_id"],
                    limit=8,
                )
        except OperationalError:
            recommendations = []
    return render(request, "subject_profile.html", **data, recommendations=recommendations)


@app.get("/organizations", response_class=HTMLResponse)
def organizations(request: Request, q: str = "", status: str = "", db: Session = Depends(get_db)):
    stmt = select(Organization).order_by(Organization.standard_name)
    if q.strip():
        k=f"%{q.strip()}%"; stmt=stmt.where(or_(Organization.standard_name.like(k),Organization.org_type.like(k),Organization.region.like(k),Organization.industry_tags.like(k)))
    if status.strip(): stmt=stmt.where(Organization.verification_status==status)
    return render(request,"organizations.html",items=db.scalars(stmt).all(),q=q,status=status)


@app.get("/organizations/{item_id}", response_class=HTMLResponse)
def organization_detail(item_id:int,request:Request,db:Session=Depends(get_db)):
    item=db.get(Organization,item_id)
    if not item: raise HTTPException(404, "主体不存在")
    outgoing = db.scalars(select(Relation).where(Relation.source_external_id==item.external_id, Relation.is_active.is_(True))).all()
    incoming = db.scalars(select(Relation).where(Relation.target_external_id==item.external_id, Relation.is_active.is_(True))).all()
    outgoing_views = relation_view_rows(db, list(outgoing))
    incoming_views = relation_view_rows(db, list(incoming))
    related_people = [
        row for row in incoming_views
        if row["source"]["kind"] == "人物"
    ]
    return render(request,"organization_detail.html",item=item,
        review_summary=_review_summary(db, "org", item.external_id),
        ref_count=organization_reference_count(db,item),
        related_resources=db.scalars(select(Resource).where(Resource.owner_external_id==item.external_id)).all(),
        related_events=db.scalars(select(HistoricalEvent).where(HistoricalEvent.related_entity==item.external_id)).all(),
        outgoing=outgoing, incoming=incoming,
        outgoing_views=outgoing_views, incoming_views=incoming_views,
        related_people=related_people)


@app.get("/people",response_class=HTMLResponse)
def people(request:Request,q:str="",status:str="",db:Session=Depends(get_db)):
    stmt=select(Person).order_by(Person.name)
    if q.strip():
        k=f"%{q.strip()}%"; stmt=stmt.where(or_(Person.name.like(k),Person.public_role.like(k),Person.organization_network.like(k),Person.ability_tags.like(k)))
    if status.strip(): stmt=stmt.where(Person.verification_status==status)
    return render(request,"people.html",items=db.scalars(stmt).all(),q=q,status=status)


@app.get("/people/{item_id}",response_class=HTMLResponse)
def person_detail(item_id:int,request:Request,db:Session=Depends(get_db)):
    item=db.get(Person,item_id)
    if not item: raise HTTPException(404, "人物不存在")
    outgoing = db.scalars(select(Relation).where(Relation.source_external_id==item.external_id, Relation.is_active.is_(True))).all()
    incoming = db.scalars(select(Relation).where(Relation.target_external_id==item.external_id, Relation.is_active.is_(True))).all()
    try:
        avatar_asset_id = db.execute(text("SELECT id FROM v05b_media_assets WHERE person_id=:person_id AND is_active=1 ORDER BY id DESC LIMIT 1"), {"person_id": item.id}).scalar()
    except OperationalError:
        avatar_asset_id = None
    return render(request,"person_detail.html",item=item,
        avatar_asset_id=avatar_asset_id,
        review_summary=_review_summary(db, "person", item.external_id),
        outgoing=outgoing, incoming=incoming,
        outgoing_views=relation_view_rows(db, list(outgoing)),
        incoming_views=relation_view_rows(db, list(incoming)))


@app.get("/projects",response_class=HTMLResponse)
def projects(request:Request,q:str="",db:Session=Depends(get_db)):
    stmt=select(ProjectPool).order_by(ProjectPool.name)
    if q.strip():
        k=f"%{q.strip()}%"; stmt=stmt.where(or_(ProjectPool.name.like(k),ProjectPool.focus_tags.like(k),ProjectPool.typical_needs.like(k),ProjectPool.target_actions.like(k)))
    return render(request,"projects.html",items=db.scalars(stmt).all(),q=q)


@app.get("/projects/{item_id}",response_class=HTMLResponse)
def project_detail(item_id:int,request:Request,db:Session=Depends(get_db)):
    item=db.get(ProjectPool,item_id)
    if not item: raise HTTPException(404, "项目不存在")
    owner = db.get(Organization, item.owner_organization_id) if item.owner_organization_id else None
    return render(request,"project_detail.html",item=item,owner=owner,review_summary=_review_summary(db, "project", item.external_id))


@app.get("/resources/legacy",response_class=HTMLResponse)
def resources(request:Request,q:str="",db:Session=Depends(get_db)):
    stmt=select(Resource).order_by(Resource.category,Resource.external_id)
    if q.strip():
        k=f"%{q.strip()}%"; stmt=stmt.where(or_(Resource.category.like(k),Resource.description.like(k),Resource.region.like(k),Resource.applicable_to.like(k)))
    return render(request,"resources.html",items=db.scalars(stmt).all(),q=q)


@app.get("/resources/legacy/{item_id:int}",response_class=HTMLResponse)
def resource_detail(item_id:int,request:Request,db:Session=Depends(get_db)):
    item=db.get(Resource,item_id)
    if not item: raise HTTPException(404, "资源不存在")
    return render(request,"resource_detail.html",item=item,review_summary=_review_summary(db, "resource", item.external_id))


@app.get("/events",response_class=HTMLResponse)
def events(request:Request,q:str="",db:Session=Depends(get_db)):
    stmt=select(HistoricalEvent).order_by(desc(HistoricalEvent.created_at))
    if q.strip():
        k=f"%{q.strip()}%"; stmt=stmt.where(or_(HistoricalEvent.name.like(k),HistoricalEvent.event_type.like(k),HistoricalEvent.fact_summary.like(k),HistoricalEvent.system_use.like(k)))
    return render(request,"events.html",items=db.scalars(stmt).all(),q=q)


@app.get("/events/{item_id}",response_class=HTMLResponse)
def event_detail(item_id:int,request:Request,db:Session=Depends(get_db)):
    item=db.get(HistoricalEvent,item_id)
    if not item: raise HTTPException(404, "事件不存在")
    return render(request,"event_detail.html",item=item,review_summary=_review_summary(db, "event", item.external_id))


@app.get("/relations",response_class=HTMLResponse)
def relations(request:Request,q:str="",db:Session=Depends(get_db)):
    stmt=select(Relation).order_by(Relation.external_id)
    if q.strip():
        k=f"%{q.strip()}%"; stmt=stmt.where(or_(Relation.source_external_id.like(k),Relation.relation_type.like(k),Relation.target_external_id.like(k),Relation.evidence_source.like(k)))
    return render(request,"relations.html",items=db.scalars(stmt).all(),q=q)


@app.get("/actions",response_class=HTMLResponse)
def actions(request:Request,q:str="",status:str="",db:Session=Depends(get_db)):
    stmt=select(ActionItem).order_by(ActionItem.priority,ActionItem.external_id)
    if q.strip():
        k=f"%{q.strip()}%"; stmt=stmt.where(or_(ActionItem.task.like(k),ActionItem.owner.like(k),ActionItem.completion_standard.like(k),ActionItem.target_external_id.like(k)))
    if status.strip(): stmt=stmt.where(ActionItem.status==status)
    return render(request,"actions.html",items=db.scalars(stmt).all(),q=q,status=status)


@app.post("/actions/{item_id}/status")
def action_status(item_id:int,status:str=Form(...),db:Session=Depends(get_db)):
    item=db.get(ActionItem,item_id)
    if not item: raise HTTPException(404, "任务不存在")
    item.status=status; db.commit()
    return RedirectResponse("/actions",status_code=303)


@app.get("/imports",response_class=HTMLResponse)
def imports(request:Request,db:Session=Depends(get_db)):
    return render(request,"imports.html",items=db.scalars(select(ImportLog).order_by(desc(ImportLog.imported_at))).all())


@app.get("/health")
def health():
    return {"status":"ok"}

# === V03B DIRECT SMART PASTE ROUTES ===
from datetime import datetime as _paste_datetime
from uuid import uuid4 as _paste_uuid4

from .analyzer import analyze_text as _analyze_text


def _paste_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _paste_semi(value: str) -> list[str]:
    return [
        item.strip()
        for item in value.replace("；", ";").replace("，", ";").split(";")
        if item.strip()
    ]

@app.get("/analyze/paste", response_class=HTMLResponse)
def smart_paste_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="paste_analyze.html",
        context={"error": None},
    )


@app.post("/analyze/paste/preview", response_class=HTMLResponse)
def smart_paste_preview(
    request: Request,
    text: str = Form(...),
    source_type: str = Form("人工录入"),
    source_url: str = Form(""),
    visibility: str = Form("内部"),
):
    text = text.strip()
    if len(text) < 20:
        return templates.TemplateResponse(
            request=request,
            name="paste_analyze.html",
            context={"error": "请至少粘贴 20 个字符。"},
            status_code=400,
        )

    result = _analyze_text(text, source_type)

    return templates.TemplateResponse(
        request=request,
        name="paste_preview.html",
        context={
            "result": result,
            "raw_text": text,
            "source_type": source_type,
            "source_url": source_url,
            "visibility": visibility,
        },
    )


@app.post("/analyze/paste/confirm")
def smart_paste_confirm(
    title: str = Form(...),
    event_date: str = Form(""),
    organizations: str = Form(""),
    event_type: str = Form("其他"),
    industry_tags: str = Form(""),
    amount: str = Form(""),
    facts: str = Form(""),
    potential_needs: str = Form(""),
    recommended_actions: str = Form(""),
    source_grade: str = Form("D"),
    confidence: str = Form("0"),
    review_reasons: str = Form(""),
    raw_text: str = Form(...),
    source_type: str = Form("人工录入"),
    source_url: str = Form(""),
    visibility: str = Form("内部"),
    create_event: str | None = Form(None),
    create_organization: str | None = Form(None),
    create_action: str | None = Form(None),
    db: Session = Depends(get_db),
):
    intelligence = RawIntelligence(
        title=title.strip() or "未命名情报",
        source_url=source_url.strip() or None,
        source_type=source_type,
        content=raw_text,
        visibility=visibility,
        review_status="待审核",
    )
    db.add(intelligence)
    event_external_id = None

    if create_event:
        summary_parts = _paste_lines(facts)
        if amount.strip():
            summary_parts.append(f"涉及金额：{amount.strip()}")
        event = HistoricalEvent(
            external_id="",
            event_date=event_date.strip() or None,
            name=title.strip() or "自动分析事件",
            event_type=event_type.strip() or "其他",
            related_entity=None,
            fact_summary="\n".join(summary_parts),
            system_use=(
                "潜在需求：" + "；".join(_paste_semi(potential_needs))
                + "\n建议动作：" + "\n".join(_paste_lines(recommended_actions))
                + f"\n来源等级：{source_grade}；分析置信度：{confidence}"
                + "\n人工复核原因：" + "\n".join(_paste_lines(review_reasons))
            ),
            visibility=visibility,
            verification_status="待核验",
            source_url=source_url.strip() or None,
            source_type=source_type,
            source_text=raw_text,
            analyzed_at=_paste_datetime.now(),
            model_version="local-rule-v0.4B",
            manually_confirmed=False,
            auto_generated_fields="name,event_type,fact_summary,system_use",
        )
        assign_system_id(db, event, "events")
        event_external_id = event.external_id
        db.add(event)

    if create_organization:
        for org_name in _paste_lines(organizations):
            existing = db.scalar(select(Organization).where(Organization.standard_name == org_name))
            if existing:
                continue
            org = Organization(
                external_id="",
                standard_name=org_name,
                org_type="待分类",
                region=None,
                industry_tags="；".join(_paste_semi(industry_tags)) or None,
                resources=None,
                needs="；".join(_paste_semi(potential_needs)) or None,
                relationship_source="粘贴自动分析",
                visibility=visibility,
                verification_status="待核验",
                source_url=source_url.strip() or None,
                source_type=source_type,
                source_text=raw_text,
                analyzed_at=_paste_datetime.now(),
                model_version="local-rule-v0.4B",
                manually_confirmed=False,
                auto_generated_fields="standard_name,industry_tags,needs",
            )
            assign_system_id(db, org, "organizations")
            db.add(org)

    if create_action:
        actions = _paste_lines(recommended_actions) or ["人工复核该条情报并确认下一步。"]
        for action_text in actions[:5]:
            action = ActionItem(
                external_id="",
                task=action_text,
                target_external_id=event_external_id,
                completion_standard="完成需求核实、证据补充或资源对接，并记录结果。",
                owner="项目负责人",
                priority="P1",
                status="未开始",
                suggested_deadline=None,
                source_url=source_url.strip() or None,
                source_type=source_type,
                source_text=raw_text,
                analyzed_at=_paste_datetime.now(),
                model_version="local-rule-v0.4B",
                manually_confirmed=False,
                auto_generated_fields="task,completion_standard,priority",
            )
            assign_system_id(db, action, "actions")
            db.add(action)

    db.commit()
    return RedirectResponse(url="/intelligence", status_code=303)

# === MANUAL-FIRST ENTITY INGESTION API ===
from pydantic import BaseModel as _SmartPasteBaseModel


class _EntityPasteRequest(_SmartPasteBaseModel):
    text: str


@app.post("/manage/{entity_key}/analyze")
def analyze_entity_paste(entity_key: str, payload: _EntityPasteRequest):
    if entity_key not in ENTITY_CONFIGS:
        raise HTTPException(status_code=404, detail="未知数据类型")
    value = payload.text.strip()
    if len(value) < 10:
        raise HTTPException(status_code=400, detail="请至少粘贴 10 个字符")
    diagnostics = inspect_entity_text(entity_key, value)
    return {
        "entity": entity_key,
        "fields": analyze_entity(entity_key, value),
        "diagnostics": diagnostics,
        "manual_review_required": True,
    }



class _BatchPersonCandidate(_SmartPasteBaseModel):
    label: str = ""
    subtitle: str = ""
    text: str


class _BatchPersonAnalyzeRequest(_SmartPasteBaseModel):
    candidates: list[_BatchPersonCandidate]
    source_url: str = ""
    source_title: str = ""
    organization_hint: str = ""


class _BatchPersonSaveItem(_SmartPasteBaseModel):
    name: str
    public_role: str = ""
    organization_network: str = ""
    ability_tags: str = ""
    value_provided: str = ""
    source_url: str = ""
    source_title: str = ""
    source_text: str = ""
    allow_duplicate: bool = False


class _BatchPersonSaveRequest(_SmartPasteBaseModel):
    confirmed: bool = False
    items: list[_BatchPersonSaveItem]
    organization_reference: str = ""
    relation_type: str = "浠昏亴"
    create_relations: bool = False


def _normalized_person_name(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip()).lower()


def _person_exact_matches(db: Session, name: str, limit: int = 8) -> list[Person]:
    normalized = _normalized_person_name(name)
    if not normalized:
        return []
    raw_name = (name or "").strip().lower()
    rows = db.scalars(
        select(Person)
        .where(
            Person.is_active.is_(True),
            func.lower(func.trim(Person.name)) == raw_name,
        )
        .order_by(Person.id.desc())
        .limit(limit)
    ).all()
    return list(rows)


@app.get("/manage/organizations/lookup")
def organization_lookup_api(q: str = Query(""), db: Session = Depends(get_db)):
    value = q.strip()
    if len(value) < 1:
        return {"items": [], "count": 0}
    rows = lookup_organizations(db, value, limit=10)
    return {
        "items": [
            {
                "id": row.id,
                "external_id": row.external_id,
                "standard_name": row.standard_name,
                "org_type": row.org_type or "",
                "region": row.region or "",
                "url": f"/organizations/{row.id}",
            }
            for row in rows
        ],
        "count": len(rows),
    }


@app.post("/manage/people/batch-analyze")
def batch_analyze_people(
    payload: _BatchPersonAnalyzeRequest,
    db: Session = Depends(get_db),
):
    # 批量解析团队页候选，只生成可编辑草稿，不写入数据库。
    if not payload.candidates:
        raise HTTPException(status_code=400, detail="请至少粘贴 10 个字符")
    if len(payload.candidates) > 30:
        raise HTTPException(status_code=400, detail="单次最多处理 30 个人物候选。")

    source_url = payload.source_url.strip()[:2000]
    source_title = payload.source_title.strip()[:300]
    organization_hint = payload.organization_hint.strip()[:300]
    organization_match, organization_candidates = resolve_organization(db, organization_hint) if organization_hint else (None, [])
    results: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for index, candidate in enumerate(payload.candidates):
        text_value = candidate.text.strip()
        if len(text_value) < 10:
            results.append({
                "index": index,
                "can_save": False,
                "fields": {},
                "errors": ["候选正文少于 10 个字符。"],
                "warnings": [],
                "duplicate_matches": [],
                "batch_duplicate": False,
                "source_text": text_value,
            })
            continue

        fields = analyze_entity("people", text_value)
        if not str(fields.get("name") or "").strip() and candidate.label.strip():
            fields["name"] = candidate.label.strip()
        if not str(fields.get("public_role") or "").strip() and candidate.subtitle.strip():
            fields["public_role"] = candidate.subtitle.strip()
        if organization_match:
            fields["organization_network"] = organization_match.standard_name
        elif organization_hint and not str(fields.get("organization_network") or "").strip():
            fields["organization_network"] = organization_hint

        fields.update({
            "source_url": source_url,
            "source_type": "公开网页（批量人工核对）",
            "source_title": source_title,
            "source_text": text_value[:10000],
            "relationship_source": "团队页批量采集",
            "visibility": "内部",
            "verification_status": "待核验",
            "manually_confirmed": True,
        })

        validation = validate_entity_submission("people", fields)
        name = str(fields.get("name") or "").strip()
        normalized_name = _normalized_person_name(name)
        batch_duplicate = bool(normalized_name and normalized_name in seen_names)
        if normalized_name:
            seen_names.add(normalized_name)

        duplicate_rows = _person_exact_matches(db, name) if name else []
        duplicate_matches = [
            {
                "id": row.id,
                "external_id": row.external_id,
                "name": row.name,
                "organization_network": row.organization_network or "",
                "same_organization": bool(
                    organization_match
                    and person_has_org_relation(db, row.external_id, organization_match.external_id)
                ),
                "url": f"/people/{row.id}",
            }
            for row in duplicate_rows
        ]

        warnings = list(validation["warnings"])
        if any(item["same_organization"] for item in duplicate_matches):
            warnings.append("系统中已有同名且已关联同一机构的人物，极可能是重复记录，默认不保存。")
        elif duplicate_matches:
            warnings.append("系统中已有同名人物，默认不保存；确认并非重复后可选择同名仍保存。")
        if batch_duplicate:
            warnings.append("本批次中出现重复姓名，该重复条目不会保存。")

        results.append({
            "index": index,
            "can_save": bool(name and not validation["errors"] and not batch_duplicate),
            "fields": fields,
            "errors": validation["errors"],
            "warnings": list(dict.fromkeys(warnings)),
            "duplicate_matches": duplicate_matches,
            "batch_duplicate": batch_duplicate,
            "source_text": text_value[:10000],
        })

    return {
        "entity": "people",
        "items": results,
        "count": len(results),
        "manual_review_required": True,
        "max_batch_size": 30,
        "organization_match": ({
            "id": organization_match.id,
            "external_id": organization_match.external_id,
            "standard_name": organization_match.standard_name,
            "url": f"/organizations/{organization_match.id}",
        } if organization_match else None),
        "organization_candidates": [
            {
                "id": row.id,
                "external_id": row.external_id,
                "standard_name": row.standard_name,
                "url": f"/organizations/{row.id}",
            }
            for row in organization_candidates
        ],
    }


@app.post("/manage/people/batch-save")
def batch_save_people(
    payload: _BatchPersonSaveRequest,
    db: Session = Depends(get_db),
):
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="请先确认已逐条核对姓名、职务和机构。")
    if not payload.items:
        raise HTTPException(status_code=400, detail="没有选择需要保存的人物。")
    if len(payload.items) > 30:
        raise HTTPException(status_code=400, detail="单次最多保存 30 个人物。")

    organization = None
    organization_candidates: list[Organization] = []
    if payload.create_relations:
        organization, organization_candidates = resolve_organization(db, payload.organization_reference)
        if not organization:
            suggestion = "、".join(f"{row.standard_name}（{row.external_id}）" for row in organization_candidates[:5])
            detail = "请先选择系统中唯一的关联机构，再创建人物-机构关系。"
            if suggestion:
                detail += f" 可选：{suggestion}"
            raise HTTPException(status_code=400, detail=detail)

    relation_type = (payload.relation_type or "任职").strip()[:120] or "任职"
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    batch_names: set[str] = set()

    for index, raw in enumerate(payload.items):
        organization_network = raw.organization_network.strip()
        if organization and not organization_network:
            organization_network = organization.standard_name
        values = {
            "name": raw.name.strip()[:200],
            "public_role": raw.public_role.strip() or None,
            "organization_network": organization_network or None,
            "ability_tags": raw.ability_tags.strip() or None,
            "value_provided": raw.value_provided.strip() or None,
            "relationship_source": "团队页批量采集",
            "visibility": "内部",
            "verification_status": "待核验",
            "source_url": raw.source_url.strip()[:2000] or None,
            "source_type": "公开网页（批量人工核对）",
            "source_title": raw.source_title.strip()[:300] or None,
            "source_text": raw.source_text.strip()[:10000] or None,
            "manually_confirmed": True,
        }
        name = values["name"]
        normalized_name = _normalized_person_name(name)
        if normalized_name and normalized_name in batch_names:
            skipped.append({"index": index, "name": name, "reason": "本批次重复姓名，已跳过。"})
            continue
        if normalized_name:
            batch_names.add(normalized_name)

        validation = validate_entity_submission("people", values)
        if validation["errors"]:
            skipped.append({"index": index, "name": name or "未命名", "reason": "；".join(validation["errors"])})
            continue

        duplicate_rows = _person_exact_matches(db, name)
        same_org_duplicate = bool(
            organization and any(person_has_org_relation(db, row.external_id, organization.external_id) for row in duplicate_rows)
        )
        if duplicate_rows and not raw.allow_duplicate:
            skipped.append({
                "index": index,
                "name": name,
                "reason": "系统中已有同名且关联同一机构的人物，已按高概率重复跳过。" if same_org_duplicate else "系统中已有同名人物，未勾选同名仍保存。",
                "existing": [{"id": row.id, "external_id": row.external_id, "name": row.name, "url": f"/people/{row.id}"} for row in duplicate_rows],
            })
            continue

        person = Person(
            **values,
            captured_at=datetime.now(),
            analyzed_at=datetime.now(),
            model_version="local-rule-v0.4D4",
            auto_generated_fields="external_id,候选字段",
            confirmed_fields="批量采集逐条人工核对",
            is_active=True,
        )
        try:
            _commit_with_generated_id(db, person, "people")
        except Exception as exc:
            db.rollback()
            skipped.append({"index": index, "name": name, "reason": getattr(exc, "detail", None) or str(exc) or "保存失败"})
            continue

        relation_info = None
        relation_warning = None
        if organization:
            try:
                relation, relation_created = ensure_person_organization_relation(
                    db,
                    person=person,
                    organization=organization,
                    relation_type=relation_type,
                    public_role=person.public_role or "",
                    source_url=person.source_url or "",
                    source_title=person.source_title or "",
                    source_text=person.source_text or "",
                )
                relation_info = {
                    "external_id": relation.external_id,
                    "relation_type": relation.relation_type,
                    "organization_external_id": organization.external_id,
                    "organization_name": organization.standard_name,
                    "created": relation_created,
                }
            except Exception as exc:
                db.rollback()
                relation_warning = f"人物已保存，但机构关系创建失败：{str(exc) or '未知错误'}"

        created.append({
            "index": index,
            "id": person.id,
            "external_id": person.external_id,
            "name": person.name,
            "url": f"/people/{person.id}",
            "relation": relation_info,
            "warning": relation_warning,
        })

    return {
        "created": created,
        "skipped": skipped,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "partial_success": bool(created and skipped),
        "organization": ({"id": organization.id, "external_id": organization.external_id, "standard_name": organization.standard_name, "url": f"/organizations/{organization.id}"} if organization else None),
        "relations_created": sum(1 for item in created if item.get("relation") and item["relation"].get("created")),
    }

@app.get("/review/suspicious-entities", response_class=HTMLResponse)
def suspicious_entity_review(
    request: Request,
    entity: str = Query(""),
    message: str = Query(""),
    db: Session = Depends(get_db),
):
    all_records = suspicious_records(db, limit=300)
    counts: dict[str, int] = {}
    for record in all_records:
        counts[record.entity_key] = counts.get(record.entity_key, 0) + 1
    records = [record for record in all_records if not entity or record.entity_key == entity]
    return render(
        request,
        "suspicious_entities.html",
        records=records,
        entity=entity,
        counts=counts,
        message=message,
    )


@app.post("/review/suspicious-entities/{entity_key}/{item_id}/deactivate")
def deactivate_suspicious_entity(
    entity_key: str,
    item_id: int,
    reason: str = Form("疑似错误主体人工复核后停用"),
    db: Session = Depends(get_db),
):
    item = deactivate_suspicious_record(db, entity_key, item_id, reason)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在或类型不支持")
    return RedirectResponse(
        url="/review/suspicious-entities?message=已停用疑似错误记录",
        status_code=303,
    )


@app.post("/review/suspicious-entities/bulk-deactivate")
async def bulk_deactivate_suspicious_entities(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    if form.get("confirm_bulk") != "1":
        return RedirectResponse(
            url="/review/suspicious-entities?message=请先确认批量停用",
            status_code=303,
        )
    tokens = [str(value) for value in form.getlist("records")]
    count = 0
    for token in tokens[:100]:
        try:
            entity_key, raw_id = token.split(":", 1)
            item_id = int(raw_id)
        except (ValueError, TypeError):
            continue
        item = deactivate_suspicious_record(
            db, entity_key, item_id, "疑似错误主体批量人工复核后停用"
        )
        if item:
            count += 1
    return RedirectResponse(
        url=f"/review/suspicious-entities?message=已批量停用 {count} 条记录",
        status_code=303,
    )

class _WebFetchRequest(_SmartPasteBaseModel):
    url: str
    entity_key: str | None = None


@app.post("/manage/fetch-webpage")
def fetch_webpage_for_smart_paste(payload: _WebFetchRequest):
    try:
        result = fetch_and_extract(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entity_key = payload.entity_key if payload.entity_key in ENTITY_CONFIGS else None
    diagnostics = inspect_entity_text(entity_key, result.text) if entity_key else None
    return {
        "result": result.to_dict(),
        "diagnostics": diagnostics,
        "manual_review_required": True,
    }











