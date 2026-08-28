"""v0.6 Platform routes -- product pages for the industry connection platform."""
from datetime import datetime
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, select, func, text

from app.database import get_db
from app.models import Organization, Person
from app.models_platform import (
    IndustryTag, PersonProfile, PersonTag,
    Favorite, Follow, ContactIntent,
    IntelligenceItem, IntelSubscription,
    MarketResource, CooperationOpportunity,
    FollowUp, CollabTask, TimelineEntry,
)
from app.services.unified_intelligence_service import UnifiedIntelligenceService
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.unified_resource_service import UnifiedResourceService
from app.services.unified_opportunity_service import UnifiedOpportunityService
from app.services.golden_loop_service import GoldenLoopService
from app.services.collection_service import (
    organization_monitoring_context, preview_website_import, save_website_import,
    set_admin_confirmed_official_domain,
)
from app.services.entity_governance_service import (
    EntityRegistryService, classify_identity, organization_duplicate_candidates,
)
from app.services.organization_access_service import OrganizationAccessError, update_organization
from app.services.platform_service import (
    get_user_person, get_person_full_profile, upsert_person_profile, set_person_tags,
    list_tags, seed_default_tags,
    toggle_favorite, is_favorited, list_favorites,
    toggle_follow, is_following,
    create_contact_intent, respond_contact_intent, list_contact_intents,
    discover_people, recommend_people,
    list_intelligence, personalized_feed,
    list_market_resources, match_resources,
    create_opportunity, update_opportunity_stage, get_opportunity_timeline,
    create_follow_up, create_collab_task, list_user_tasks,
    unified_search,
)

STATUS_LABELS = {
    # 合作机会阶段
    "lead": "线索", "contacted": "已联系", "qualified": "已确认",
    "negotiating": "洽谈中", "proposal": "方案阶段", "due_diligence": "尽职调查",
    "agreement": "协议阶段", "won": "已达成", "lost": "未成交", "closed": "已关闭",
    # 联系意向状态
    "identified": "已识别", "evaluating": "评估中", "active": "跟进中", "paused": "已暂停",
    "pending": "待处理", "pending_processing": "待判断", "pending_review": "待审核",
    "reviewed": "稍后处理", "accepted": "已确认", "confirmed": "已确认",
    "declined": "已拒绝", "ignored": "已忽略", "interested": "感兴趣",
    "not_interested": "不感兴趣", "later": "稍后处理",
    # 任务状态
    "completed": "已完成", "in_progress": "进行中", "todo": "待办", "cancelled": "已取消",
    # 资源/情报状态
    "published": "有效", "draft": "草稿", "archived": "已归档", "matched": "已匹配",
    "expired": "已过期", "supply": "供给", "demand": "需求",
    # 会员等级
    "standard": "标准", "premium": "高级", "exited": "已退出",
    # 审核状态
    "submitted": "已提交", "approved": "已通过", "rejected": "已驳回",
}
def status_label(value: str) -> str:
    """Map English status/stage to Chinese label."""
    raw = str(value or "").strip()
    if not raw:
        return "未设置"
    if any("\u4e00" <= char <= "\u9fff" for char in raw):
        return raw
    return STATUS_LABELS.get(raw.lower(), "待确认")


router = APIRouter()

# Initialize template engine once with custom filters
from fastapi.templating import Jinja2Templates
from pathlib import Path
_BASE_DIR = Path(__file__).resolve().parent
_templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
_templates.env.filters["status_label"] = status_label


def render(request: Request, name: str, **context):
    """Render a Jinja2 template with platform status_label filter."""
    return _templates.TemplateResponse(request=request, name=name, context=context)


def is_platform_admin(request: Request) -> bool:
    sec = request.scope.get("security_context", {})
    return bool(sec.get("can_manage_users") or "platform:manage" in sec.get("permissions", []))


def get_current_user_id(request: Request) -> int | None:
    sec = request.scope.get("security_context", {})
    return sec.get("user", {}).get("id")


def get_user_role(request: Request) -> str:
    sec = request.scope.get("security_context", {})
    return sec.get("user", {}).get("role", "viewer")


def get_workspace_for_role(request: Request, db: Session, user_id: int | None):
    role = get_user_role(request)
    workspace = {"role": role, "role_label": "", "cards": []}

    role_labels = {
        "admin": "管理员",
        "operator": "俱乐部运营",
        "reviewer": "研究人员",
        "viewer": "普通会员",
    }
    workspace["role_label"] = role_labels.get(role, "用户")

    if role == "reviewer":
        from app.services.collection_service import dashboard as collection_dashboard
        from app.services.processing import dashboard as processing_dashboard
        from app.services.reports import list_reports
        try:
            coll_counts = collection_dashboard()["counts"]
            proc_counts = processing_dashboard()["counts"]
            pending_reports = list_reports(status="under_review")["pagination"]["total"]
        except Exception:
            coll_counts = {}
            proc_counts = {}
            pending_reports = 0

        workspace["cards"] = [
            {"title": "今日新增情报", "value": coll_counts.get("today_collection_items", 0), "url": "/collection/items", "icon": "newspaper"},
            {"title": "待处理原始情报", "value": coll_counts.get("queued_items", 0), "url": "/collection/items", "icon": "file-search"},
            {"title": "待审核事实", "value": proc_counts.get("pending_candidates", 0), "url": "/processing/candidates", "icon": "git-compare"},
            {"title": "关注专题", "value": 0, "url": "/research", "icon": "flask-conical"},
            {"title": "待审核报告", "value": pending_reports, "url": "/reports", "icon": "file-text"},
            {"title": "异常数据源", "value": coll_counts.get("failed_sources", 0), "url": "/collection/sources", "icon": "alert-circle"},
        ]

    elif role == "operator":
        try:
            pending_members = db.scalar(select(func.count()).select_from(
                db.query(CooperationOpportunity).filter(CooperationOpportunity.status == "active")
            )) or 0
            pending_registrations = db.scalar(select(func.count()).select_from(
                db.query(ContactIntent).filter(ContactIntent.status == "pending")
            )) or 0
        except Exception:
            pending_members = 0
            pending_registrations = 0

        workspace["cards"] = [
            {"title": "待审核会员", "value": pending_members, "url": "/club/admin/applications", "icon": "users-round"},
            {"title": "待审核报名", "value": pending_registrations, "url": "/club/events", "icon": "clipboard-check"},
            {"title": "今日活动", "value": 0, "url": "/club/events", "icon": "calendar"},
            {"title": "待处理匹配", "value": 0, "url": "/club/matches", "icon": "shuffle"},
            {"title": "会后待跟进", "value": 0, "url": "/opportunities?tab=followups", "icon": "message-square"},
            {"title": "潜在线索", "value": 0, "url": "/opportunities", "icon": "target"},
        ]

    elif role == "admin":
        people_count = int(db.scalar(select(func.count()).select_from(Person).where(Person.is_active == True)) or 0)
        org_count = int(db.scalar(select(func.count()).select_from(Organization).where(Organization.is_active == True)) or 0)
        from sqlalchemy import text
        member_count = int(db.scalar(text("SELECT COUNT(*) FROM v04f_club_memberships WHERE status='active'"))) or 0
        user_count = int(db.scalar(text("SELECT COUNT(*) FROM v05a_users"))) or 0
        workspace["cards"] = [
            {"title": "系统管理", "value": "", "url": "/admin/platform", "icon": "shield"},
            {"title": "人物与机构", "value": f"{people_count}人 {org_count}家", "url": "/admin/people", "icon": "users-round"},
            {"title": "会员管理", "value": member_count, "url": "/club/members", "icon": "id-card"},
            {"title": "情报运营", "value": 0, "url": "/admin/intelligence", "icon": "newspaper"},
            {"title": "数据治理", "value": 0, "url": "/admin/data-integrity", "icon": "shield-alert"},
            {"title": "用户与权限", "value": user_count, "url": "/admin/users", "icon": "user-cog"},
        ]

    else:
        if user_id:
            my_events_count = db.scalar(select(func.count()).select_from(
                db.query(MarketResource).filter(MarketResource.publisher_id == user_id)
            )) or 0
            my_resources_count = db.scalar(select(func.count()).select_from(
                db.query(CooperationOpportunity).filter(
                    CooperationOpportunity.initiator_id == user_id,
                    CooperationOpportunity.status == "active"
                )
            )) or 0
        else:
            my_events_count = 0
            my_resources_count = 0

        workspace["cards"] = [
            {"title": "我的活动", "value": my_events_count, "url": "/member/events", "icon": "calendar"},
            {"title": "我的需求与供给", "value": my_resources_count, "url": "/member/needs", "icon": "package"},
            {"title": "推荐认识的人", "value": 0, "url": "/network/people", "icon": "sparkles"},
            {"title": "我的合作进展", "value": 0, "url": "/opportunities", "icon": "handshake"},
            {"title": "我的通知", "value": 0, "url": "/member/notifications", "icon": "bell"},
        ]

    return workspace


@router.get("/platform", response_class=HTMLResponse)
def platform_home(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    rec_people = recommend_people(db, user_id, limit=4) if user_id is not None else []
    recent_people = list(db.scalars(
        select(Person).where(Person.is_active == True).order_by(desc(Person.created_at)).limit(4)
    ).all())
    golden = GoldenLoopService(db)
    feed = golden.priority_feed(limit=4)
    supplies = list(db.scalars(
        select(MarketResource).where(MarketResource.status == "published", MarketResource.direction == "supply").order_by(desc(MarketResource.created_at)).limit(4)
    ).all())
    demands = list(db.scalars(
        select(MarketResource).where(MarketResource.status == "published", MarketResource.direction == "demand").order_by(desc(MarketResource.created_at)).limit(4)
    ).all())
    opps = list(db.scalars(
        select(CooperationOpportunity).where(CooperationOpportunity.status == "active").order_by(desc(CooperationOpportunity.updated_at)).limit(4)
    ).all())

    workspace = get_workspace_for_role(request, db, user_id)
    tasks = list_user_tasks(db, user_id) if user_id else []

    home_metrics = golden.workbench()["home_metrics"]
    return render(request, "platform/home.html",
        rec_people=rec_people, recent_people=recent_people,
        feed=feed, supplies=supplies, demands=demands,
        opps=opps, user_id=user_id,
        workspace=workspace, tasks=tasks, home_metrics=home_metrics,
    )


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  IDENTITY CENTER  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.get("/me/industry-profile", response_class=HTMLResponse)
def industry_profile(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403, "please login first")
    person = get_user_person(db, user_id)
    linked = [person] if person else []
    try:
        from app.services.membership_access_service import get_membership_context
        memberships = get_membership_context({"id": user_id}, db_path=None).get("memberships", [])
    except Exception:
        memberships = []

    all_tags = list_tags(db)
    person_data = None
    my_tags = []
    if person:
        person_data = get_person_full_profile(db, person.id)
        my_tags = person_data.get("tags", [])

    return render(request, "platform/identity.html",
        linked=linked, memberships=memberships, person_data=person_data,
        all_tags=all_tags, my_tags=my_tags, user_id=user_id,
    )

@router.post("/me/industry-profile/update")
async def update_industry_profile(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403, "璇峰厛鐧诲綍")
    form = await request.form()
    person = get_user_person(db, user_id)
    if person is None:
        raise HTTPException(404, "当前账号尚未绑定有效人物，请先提交身份关联申请")
    submitted_person_id = int(form.get("person_id", "0") or 0)
    if submitted_person_id and submitted_person_id != person.id:
        raise HTTPException(403, "不能修改其他人物档案")
    person_id = person.id

    profile_fields = ["title", "bio", "city", "province", "cooperation_preferences",
                      "contact_email", "contact_phone", "contact_wechat", "contact_visibility"]
    profile_data = {k: str(form.get(k, "")).strip() or None for k in profile_fields}
    upsert_person_profile(db, person_id, **profile_data)

    # Update tags
    tag_ids = [int(v) for k, v in form.multi_items() if k == "tag_ids" and v]
    if tag_ids:
        set_person_tags(db, person_id, tag_ids)

    # Update basic person fields
    person = db.get(Person, person_id)
    if person:
        person.name = str(form.get("name", person.name)).strip()
        person.public_role = str(form.get("public_role", person.public_role or "")).strip() or None
        person.ability_tags = str(form.get("ability_tags", person.ability_tags or "")).strip() or None
        db.commit()

    return RedirectResponse("/me/industry-profile", 303)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  NETWORK  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.get("/network", response_class=HTMLResponse)
def network_home(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    rec = recommend_people(db, user_id, limit=8) if user_id is not None else []
    
    people_count = int(db.scalar(select(func.count()).select_from(Person).where(Person.is_active == True)) or 0)
    org_count = int(db.scalar(select(func.count()).select_from(Organization).where(Organization.is_active == True)) or 0)
    
    stats = {
        "people_count": people_count,
        "org_count": org_count,
        "project_count": 0,
        "relation_count": 0,
        "history_relation_count": 0,
        "pending_review_count": 0,
        "unidentified_count": 0,
        "duplicate_count": 0,
    }
    
    try:
        from app.v04c_review import db_connection, default_db_path
        from app.settings import resolved_db_path
        db_path = resolved_db_path()
        with db_connection(db_path) as conn:
            stats["relation_count"] = int(conn.execute("SELECT COUNT(*) FROM p3_canonical_relationships WHERE review_status='approved' AND is_current=1").fetchone()[0] or 0)
            stats["history_relation_count"] = int(conn.execute("SELECT COUNT(*) FROM p3_canonical_relationships WHERE review_status='approved' AND is_current=0").fetchone()[0] or 0)
            stats["pending_review_count"] = int(conn.execute("SELECT COUNT(*) FROM p3_relationship_candidates WHERE status='pending'").fetchone()[0] or 0)
            stats["unidentified_count"] = int(conn.execute("SELECT COUNT(*) FROM p3_entity_resolution_candidates WHERE resolution_status='pending'").fetchone()[0] or 0)
            stats["duplicate_count"] = int(conn.execute("SELECT COUNT(*) FROM p3_entity_merge_records WHERE merge_status='preview'").fetchone()[0] or 0)
    except Exception:
        pass
    
    can_access_governance = _can_manage_people_orgs(request)
    
    return render(request, "platform/network.html", 
        rec=rec, stats=stats, can_access_governance=can_access_governance, user_id=user_id)


@router.get("/network/people", response_class=HTMLResponse)
def network_people(
    request: Request,
    name: str = Query(""),
    user_type: str = Query(""),
    industry_direction: str = Query(""),
    capability: str = Query(""),
    need: str = Query(""),
    organization: str = Query(""),
    region: str = Query(""),
    page: int = Query(1),
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(request)
    result = discover_people(db, current_user_id=user_id, name=name, user_type=user_type,
        industry_direction=industry_direction, capability=capability, need=need,
        organization=organization, region=region, page=page)
    all_tags = list_tags(db)
    return render(request, "platform/people_discovery.html",
        items=result["items"], total=result["total"], page=result["page"],
        all_tags=all_tags, name_filter=name, user_type=user_type, industry_direction=industry_direction,
        capability=capability, need=need, organization=organization, region=region,
        user_id=user_id,
    )


@router.get("/network/people/{person_id}", response_class=HTMLResponse)
def person_card(request: Request, person_id: int, history: bool = False, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(404, "person not found")
    person_data = get_person_full_profile(db, person_id)
    user_id = get_current_user_id(request)
    fav = is_favorited(db, user_id, "person", person_id) if user_id is not None else False
    following = is_following(db, user_id, "person", person_id) if user_id is not None else False
    
    person_relationships = []
    evidence_list = []
    RELATION_TYPE_LABELS = {
        "employment": "雇佣关系", "board_membership": "董事/监事",
        "investment": "投资关系", "cooperation": "合作关系",
        "licensing": "授权许可", "partnership": "战略伙伴",
        "supply": "供应关系", "distribution": "分销关系",
        "clinical_trial": "临床试验", "research_collaboration": "研究合作",
        "acquisition": "收购并购", "equity": "股权关系",
    }
    
    try:
        from app.services.canonical_relationship_service import CanonicalRelationshipService
        external_id = person.external_id
        if external_id:
            include_private = _can_manage_people_orgs(request)
            person_relationships = CanonicalRelationshipService().entity_relationships(
                "person", external_id, history=history, include_private=include_private
            )
            for rel in person_relationships:
                rel_evidence = CanonicalRelationshipService().detail(rel["id"], include_private=include_private)
                if rel_evidence and rel_evidence.get("evidence"):
                    evidence_list.extend(rel_evidence["evidence"])
    except Exception:
        pass
    
    intelligence = db.execute(text("""
        SELECT i.id,i.title FROM core_intelligence_subject_links l
        JOIN v06_intelligence_items i ON i.id=l.intelligence_item_id
        WHERE l.subject_type='person' AND l.subject_id=:person_id ORDER BY i.id DESC LIMIT 10
    """), {"person_id": int(person_id)}).mappings().all()
    resources = db.execute(text("SELECT id,title,direction FROM v06_market_resources WHERE owner_person_id=:person_id ORDER BY id DESC LIMIT 10"), {"person_id": int(person_id)}).mappings().all()
    opportunities = db.execute(text("SELECT id,title,status,outcome_status FROM v06_opportunities WHERE target_person_id=:person_id ORDER BY id DESC LIMIT 10"), {"person_id": int(person_id)}).mappings().all()
    follow_ups = db.execute(text("""
        SELECT f.id,f.content,f.next_action,f.followed_at,o.id AS opportunity_id,o.title AS opportunity_title
        FROM v06_follow_ups f JOIN v06_opportunities o ON o.id=f.opportunity_id
        WHERE o.target_person_id=:person_id ORDER BY f.followed_at DESC LIMIT 5
    """), {"person_id": int(person_id)}).mappings().all()
    business_trace = {"intelligence": intelligence, "resources": resources, "opportunities": opportunities, "follow_ups": follow_ups}
    return render(request, "platform/person_card.html",
        person=person, person_data=person_data, is_favorited=fav, is_following=following,
        user_id=user_id, person_relationships=person_relationships, business_trace=business_trace,
        evidence_list=evidence_list, RELATION_TYPE_LABELS=RELATION_TYPE_LABELS)


@router.get("/network/organizations", response_class=HTMLResponse)
def network_organizations(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    stmt = select(Organization).where(Organization.is_active == True).order_by(Organization.standard_name)
    if q:
        stmt = stmt.where(Organization.standard_name.contains(q))
    orgs = list(db.scalars(stmt).all())
    return render(request, "platform/organizations.html", orgs=orgs, q=q)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  CONTACT INTENTS  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.post("/network/contact-intent/create")
async def create_intent(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403, "璇峰厛鐧诲綍")
    form = await request.form()
    ci = create_contact_intent(db, from_user_id=user_id,
        target_type=form.get("target_type", "person"),
        target_id=int(form.get("target_id", 0)),
        intent_type=form.get("intent_type", "connection"),
        message=form.get("message", ""))
    return RedirectResponse(f"/network/people/{form.get('target_id')}", 303)


@router.post("/network/contact-intent/{intent_id}/respond")
async def respond_intent(intent_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403, "璇峰厛鐧诲綍")
    form = await request.form()
    ci = respond_contact_intent(db, intent_id, form.get("status", "accepted"),
        form.get("response_message", ""), user_id)
    if not ci:
        raise HTTPException(404, "request failed")
    return RedirectResponse("/network", 303)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  INTELLIGENCE  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.get("/intelligence", response_class=HTMLResponse)
def intelligence_center(
    request: Request,
    intel_type: str = Query(""),
    industry_direction: str = Query(""),
    q: str = Query(""),
    source: str = Query(""),
    time_range: str = Query(""),
    workflow: str = Query(""),
    page: int = Query(1),
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(request)
    result = list_intelligence(db, user_id=user_id,
        intel_type=intel_type or None,
        industry_direction=industry_direction or None,
        q=q or None, source=source, time_range=time_range, workflow=workflow, page=page)
    feed = personalized_feed(db, user_id, limit=6) if user_id is not None else []
    intel_type_options = [v for v in db.scalars(select(IntelligenceItem.intel_type).where(IntelligenceItem.status == "published", IntelligenceItem.intel_type.is_not(None), IntelligenceItem.intel_type != "").distinct().order_by(IntelligenceItem.intel_type)).all() if v]
    industry_direction_options = [v for v in db.scalars(select(IntelligenceItem.industry_directions).where(IntelligenceItem.status == "published", IntelligenceItem.industry_directions.is_not(None), IntelligenceItem.industry_directions != "").distinct().order_by(IntelligenceItem.industry_directions)).all() if v]
    return render(request, "platform/intelligence.html",
        items=result["items"], total=result["total"], page=result["page"],
        feed=feed, intel_type=intel_type, industry_direction=industry_direction,
        q=q, user_id=user_id,
        intel_type_options=intel_type_options,
        industry_direction_options=industry_direction_options,
        source=source, time_range=time_range, workflow=workflow,
    )


@router.get("/intelligence/{item_id:int}", response_class=HTMLResponse)
def intelligence_detail(
    item_id: int, request: Request, subject_q: str = Query(""),
    message: str = Query(""), db: Session = Depends(get_db),
):
    item = UnifiedIntelligenceService(db).detail(item_id)
    evidence = IntelligenceProductService().trace(item_id)["evidence"]
    user_id = get_current_user_id(request)
    fav = is_favorited(db, user_id, "intelligence", item_id) if user_id is not None else False
    golden = GoldenLoopService(db)
    trace = golden.trace(item_id)
    event_insight, subject_candidates = golden.event_insight(item_id), golden.subject_candidates(item_id)
    opportunity_context = golden.opportunity_discovery(
        item_id, trace=trace, has_subject_candidate=bool(subject_candidates),
    )
    query = subject_q.strip()
    pattern = f"%{query}%"
    people = db.execute(text("SELECT id,name FROM people WHERE COALESCE(is_active,1)=1 AND instr(name,'�')=0 AND (:q='' OR name LIKE :pattern) ORDER BY name LIMIT 80"), {"q": query, "pattern": pattern}).mappings().all()
    organizations = db.execute(text("SELECT id,standard_name FROM organizations WHERE COALESCE(is_active,1)=1 AND (:q='' OR standard_name LIKE :pattern) ORDER BY standard_name LIMIT 80"), {"q": query, "pattern": pattern}).mappings().all()
    projects = db.execute(text("SELECT id,name FROM projects WHERE (:q='' OR name LIKE :pattern) ORDER BY name LIMIT 80"), {"q": query, "pattern": pattern}).mappings().all()
    role = get_user_role(request)
    return render(
        request, "platform/intelligence_detail.html", item=item, evidence=evidence,
        is_favorited=fav, user_id=user_id, trace=trace, subject_q=query,
        people=people, organizations=organizations, projects=projects,
        event_insight=event_insight, subject_candidates=subject_candidates,
        opportunity_context=opportunity_context,
        can_write=role in {"operator", "reviewer", "admin"}, message=message,
    )


@router.get("/intelligence/subscriptions", response_class=HTMLResponse)
def intelligence_subscriptions(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    subs = list(db.scalars(select(IntelSubscription).where(IntelSubscription.user_id == user_id)).all())
    return render(request, "platform/subscriptions.html", subs=subs, user_id=user_id)


@router.post("/intelligence/subscriptions/save")
async def save_subscription(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    sub = IntelSubscription(
        user_id=user_id,
        intel_types=form.get("intel_types"),
        industry_directions=form.get("industry_directions"),
        companies=form.get("companies"),
        tags=form.get("tags"),
        regions=form.get("regions"),
        min_importance=int(form.get("min_importance", "1")),
    )
    db.add(sub)
    db.commit()
    return RedirectResponse("/intelligence/subscriptions", 303)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  RESOURCES  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.get("/resources/demand", include_in_schema=False)
def legacy_resource_demand():
    return RedirectResponse("/resources?direction=demand", status_code=303)


@router.get("/resources/supply", include_in_schema=False)
def legacy_resource_supply():
    return RedirectResponse("/resources?direction=supply", status_code=303)


@router.get("/resources/matching", include_in_schema=False)
def legacy_resource_matching():
    return RedirectResponse("/resources", status_code=303)


@router.get("/resources", response_class=HTMLResponse)
def resource_market(
    request: Request,
    direction: str = Query(""),
    resource_type: str = Query(""),
    q: str = Query(""),
    industry_direction: str = Query(""),
    region: str = Query(""),
    page: int = Query(1),
    db: Session = Depends(get_db),
    status: str = Query("published"),
    message: str = Query(""),
    error: str = Query(""),
):
    result = list_market_resources(db,
        direction=direction or None, resource_type=resource_type or None,
        q=q or None,
        industry_direction=industry_direction or None, region=region or None, status=status, page=page)
    resource_type_options = [v for v in db.scalars(select(MarketResource.resource_type).where(MarketResource.status == "published", MarketResource.resource_type.is_not(None), MarketResource.resource_type != "").distinct().order_by(MarketResource.resource_type)).all() if v]
    item_ids = [int(item.id) for item in result["items"]]
    organization_ids = {int(item.organization_id) for item in result["items"] if item.organization_id}
    person_ids = {int(item.owner_person_id) for item in result["items"] if item.owner_person_id}
    organization_names = {int(row.id): row.standard_name for row in db.scalars(select(Organization).where(Organization.id.in_(organization_ids))).all()} if organization_ids else {}
    person_names = {int(row.id): row.name for row in db.scalars(select(Person).where(Person.id.in_(person_ids))).all()} if person_ids else {}
    candidate_counts: dict[int, int] = {}
    if item_ids:
        identifiers = ",".join(str(value) for value in item_ids)
        rows = db.execute(text(f"""
            SELECT resource_id,COUNT(*) AS candidate_count FROM (
              SELECT demand_resource_id AS resource_id FROM p4_resource_match_candidates
              WHERE demand_resource_id IN ({identifiers}) AND status<>'rejected'
              UNION ALL
              SELECT supply_resource_id AS resource_id FROM p4_resource_match_candidates
              WHERE supply_resource_id IN ({identifiers}) AND status<>'rejected'
            ) GROUP BY resource_id
        """)).mappings().all()
        candidate_counts = {int(row["resource_id"]): int(row["candidate_count"]) for row in rows}
    for item in result["items"]:
        item.owner_label = organization_names.get(int(item.organization_id)) if item.organization_id else None
        item.owner_label = item.owner_label or (person_names.get(int(item.owner_person_id)) if item.owner_person_id else None) or "主体信息待补充"
        item.candidate_count = candidate_counts.get(int(item.id), 0)
    return render(request, "platform/resources.html",
        items=result["items"], total=result["total"], page=result["page"],
        status=status or "published",
        direction=direction, resource_type=resource_type, q=q,
        industry_direction=industry_direction, region=region,
        resource_type_options=resource_type_options,
        message=message, error=error,
        can_write=get_user_role(request) in {"operator", "reviewer", "admin"},
    )


@router.get("/resources/{resource_id:int}", response_class=HTMLResponse)
def resource_detail(resource_id: int, request: Request, message: str = Query(""),
                    error: str = Query(""), db: Session = Depends(get_db)):
    resource_service = UnifiedResourceService(db)
    resource = resource_service.detail(resource_id)
    references = resource_service.reference_counts(resource_id)
    trace = GoldenLoopService(db).resource_trace(resource_id)
    golden_resource = trace["resource"]
    user_id = get_current_user_id(request)
    fav = is_favorited(db, user_id, "resource", resource_id) if user_id is not None else False
    matches = match_resources(db, resource_id, limit=6)
    role = get_user_role(request)
    return render(request, "platform/resource_detail.html",
        resource=resource, golden_resource=golden_resource, trace=trace, is_favorited=fav,
        matches=matches, user_id=user_id, can_write=role in {"operator", "reviewer", "admin"},
        message=message, error=error, references=references)


@router.get("/resources/new", response_class=HTMLResponse)
def new_resource(
    request: Request, direction: str = Query("supply"), owner_type: str = Query(""),
    owner_id: int | None = Query(None), db: Session = Depends(get_db),
):
    direction = direction if direction in {"demand", "supply"} else "supply"
    owner_label = ""
    if owner_id and owner_type == "organization":
        owner = db.get(Organization, int(owner_id))
        owner_label = owner.standard_name if owner else ""
    elif owner_id and owner_type == "person":
        owner = db.get(Person, int(owner_id))
        owner_label = owner.name if owner else ""
    if owner_id and not owner_label:
        raise HTTPException(404, "主体不存在")
    return render(request, "platform/resource_form.html", resource=None, mode="new",
        direction=direction, owner_type=owner_type, owner_id=owner_id, owner_label=owner_label)


@router.post("/resources/new")
async def create_resource(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    resource = UnifiedResourceService(db).create(actor_user_id=user_id, fields={
        "title": form.get("title", ""),
        "direction": form.get("direction", "supply"),
        "resource_type": form.get("resource_type", "其他"),
        "summary": form.get("summary"),
        "description": form.get("description"),
        "region": form.get("region"),
        "industry_direction": form.get("industry_direction"),
        "tags": form.get("tags"),
        "cooperation_mode": form.get("cooperation_mode"),
        "budget_note": form.get("budget_note"),
        "contact_visibility": form.get("contact_visibility", "connected"),
        "owner_person_id": int(form.get("owner_person_id")) if form.get("owner_person_id") else None,
        "organization_id": int(form.get("organization_id")) if form.get("organization_id") else None,
        "valid_until": form.get("valid_until"),
        "status": "published",
    })
    return RedirectResponse(f"/resources/{resource.id}", 303)


@router.get("/resources/{resource_id:int}/edit", response_class=HTMLResponse)
def edit_resource(resource_id: int, request: Request, db: Session = Depends(get_db)):
    resource = UnifiedResourceService(db).detail(resource_id)
    user_id = get_current_user_id(request)
    if resource.publisher_id != user_id and not is_platform_admin(request):
        raise HTTPException(403, "无权修改该资源")
    owner_type = "organization" if resource.organization_id else ("person" if resource.owner_person_id else "")
    owner_id = resource.organization_id or resource.owner_person_id
    return render(request, "platform/resource_form.html", resource=resource, mode="edit",
        direction=resource.direction, owner_type=owner_type, owner_id=owner_id, owner_label="")


@router.post("/resources/{resource_id:int}/edit")
async def save_resource(resource_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    UnifiedResourceService(db).update(resource_id, actor_user_id=user_id, is_admin=is_platform_admin(request), fields={
        "title": form.get("title", ""), "direction": form.get("direction", "supply"),
        "resource_type": form.get("resource_type", "其他"), "summary": form.get("summary"),
        "description": form.get("description"), "region": form.get("region"),
        "industry_direction": form.get("industry_direction"), "tags": form.get("tags"),
        "cooperation_mode": form.get("cooperation_mode"), "budget_note": form.get("budget_note"),
        "contact_visibility": form.get("contact_visibility", "connected"),
        "valid_until": form.get("valid_until"), "status": form.get("status", "published"),
        "owner_person_id": form.get("owner_person_id"), "organization_id": form.get("organization_id"),
        "visibility": form.get("visibility", "organization"),
    })
    return RedirectResponse(f"/resources/{resource_id}?message=资源已更新", 303)


@router.post("/resources/{resource_id:int}/close")
def close_resource(resource_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    UnifiedResourceService(db).close(resource_id, actor_user_id=user_id, is_admin=is_platform_admin(request))
    return RedirectResponse(f"/resources/{resource_id}?message=资源已关闭并归档", 303)


@router.post("/resources/{resource_id:int}/delete")
def delete_resource(resource_id: int, request: Request, confirm: str = Form(""), db: Session = Depends(get_db)):
    if confirm != "1":
        raise HTTPException(400, "请确认删除")
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    try:
        UnifiedResourceService(db).delete_safe(resource_id, actor_user_id=user_id, is_admin=is_platform_admin(request))
    except HTTPException as exc:
        if exc.status_code == 409:
            return RedirectResponse(f"/resources/{resource_id}?error=资源已有下游业务记录，请改用关闭归档", 303)
        raise
    return RedirectResponse("/resources?message=资源已删除", 303)


@router.post("/resources/bulk-delete")
async def bulk_delete_resources(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    ids = [int(value) for value in form.getlist("resource_ids") if str(value).isdigit()]
    result = UnifiedResourceService(db).bulk_delete(ids, actor_user_id=user_id, is_admin=is_platform_admin(request))
    protected = "、".join(map(str, result["protected"])) or "无"
    message = f"批量处理完成：删除{len(result['deleted'])}项；未删除{len(result['protected'])}项（受保护ID：{protected}）"
    return RedirectResponse(f"/resources?status=all&message={message}", 303)


@router.post("/resources/{resource_id}/status")
async def update_resource_status(resource_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    form = await request.form()
    UnifiedResourceService(db).update_status(resource_id, actor_user_id=user_id, status=form.get("status", "published"), is_admin=is_platform_admin(request))
    return RedirectResponse(f"/resources/{resource_id}", 303)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  OPPORTUNITIES  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.get("/opportunities", response_class=HTMLResponse)
def opportunities(request: Request,
    status: str = Query(""),
    stage: str = Query(""),
    q: str = Query(""),
    outcome: str = Query(""),
    owner_id: int | None = Query(None),
    updated_period: str = Query(""),
    follow_scope: str = Query(""),
    closed_period: str = Query(""),
    page: int = Query(1),
    db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    result = UnifiedOpportunityService(db).list(
        user_id=user_id, is_admin=is_platform_admin(request),
        status=status or "active", stage=stage, q=q, outcome=outcome, owner_id=owner_id,
        updated_period=updated_period, follow_scope=follow_scope, closed_period=closed_period, page=page, page_size=20)
    owners = db.execute(text("SELECT id,username FROM v05a_users WHERE status='active' ORDER BY username")).mappings().all()
    owner_names = {int(item["id"]): item["username"] for item in owners}
    return render(request, "platform/opportunities.html",
        opps=result["items"], total=result["total"],
        page=result["page"], status=status or "active", stage=stage, q=q, outcome=outcome, owner_id=owner_id,
        updated_period=updated_period, follow_scope=follow_scope, closed_period=closed_period, owners=owners, owner_names=owner_names, user_id=user_id)


@router.get("/opportunities/{opp_id}", response_class=HTMLResponse)
def opportunity_detail(opp_id: int, request: Request, message: str = Query(""), db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    svc = UnifiedOpportunityService(db)
    opp = svc.detail(opp_id, user_id=user_id, is_admin=is_platform_admin(request))
    timeline = svc.timeline(opp_id, user_id=user_id, is_admin=is_platform_admin(request))
    follow_ups = svc.follow_ups(opp_id, user_id=user_id, is_admin=is_platform_admin(request))
    tasks = svc.tasks(opp_id, user_id=user_id, is_admin=is_platform_admin(request))
    golden_service = GoldenLoopService(db)
    golden = golden_service._opportunity(opp_id)
    trace = golden_service.opportunity_trace(opp_id)
    role = get_user_role(request)
    can_write = role in {"operator", "reviewer", "admin"} and user_id is not None and golden_service.can_manage_opportunity(golden, int(user_id), role)
    return render(request, "platform/opportunity_detail.html",
        opp=opp, golden=golden, trace=trace, timeline=timeline, follow_ups=follow_ups, tasks=tasks, user_id=user_id, can_write=can_write, message=message)


@router.post("/opportunities/create")
async def create_opp(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    opp = create_opportunity(db,
        title=form.get("title", ""),
        opp_type=form.get("opp_type", "鍏朵粬"),
        initiator_id=user_id,
        description=form.get("description"),
        expected_outcome=form.get("expected_outcome"),
        status="active",
        visibility=form.get("visibility", "organization"),
    )
    return RedirectResponse(f"/opportunities/{opp.id}", 303)


@router.post("/opportunities/{opp_id}/stage")
async def update_stage(opp_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    form = await request.form()
    opp = UnifiedOpportunityService(db).update_stage(opp_id, actor_user_id=user_id, stage=form.get("stage", "lead"), is_admin=is_platform_admin(request))
    if not opp:
        raise HTTPException(404)
    return RedirectResponse(f"/opportunities/{opp_id}", 303)


@router.post("/opportunities/{opp_id}/follow-up")
async def add_follow_up(opp_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    create_follow_up(db,
        opportunity_id=opp_id,
        follow_type=form.get("follow_type", "note"),
        content=form.get("content", ""),
        created_by=user_id,
        visibility=form.get("visibility", "organization"),
    )
    return RedirectResponse(f"/opportunities/{opp_id}", 303)


@router.post("/opportunities/{opp_id}/task")
async def add_task(opp_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    create_collab_task(db,
        title=form.get("title", ""),
        opportunity_id=opp_id,
        owner_id=int(form.get("owner_id", user_id)),
        priority=form.get("priority", "P2"),
        created_by=user_id,
    )
    return RedirectResponse(f"/opportunities/{opp_id}", 303)


@router.post("/opportunities/convert/{intent_id}")
async def convert_intent_to_opp(intent_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    opp = UnifiedOpportunityService(db).convert_contact_intent(intent_id=intent_id, actor_user_id=user_id, is_admin=is_platform_admin(request))
    return RedirectResponse(f"/opportunities/{opp.id}", 303)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  WORKSPACE  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.get("/workspace", response_class=HTMLResponse)
def workspace(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    tasks = list_user_tasks(db, user_id)
    my_opps = list(db.scalars(
        select(CooperationOpportunity).where(
            CooperationOpportunity.initiator_id == user_id,
            CooperationOpportunity.status == "active",
        ).order_by(desc(CooperationOpportunity.updated_at))
    ).all())
    pending_intents = list_contact_intents(db, user_id, "received") if user_id is not None else []
    pending_intents = [c for c in pending_intents if c.status == "pending"]
    my_resources = list(db.scalars(
        select(MarketResource).where(MarketResource.publisher_id == user_id).order_by(desc(MarketResource.updated_at))
    ).all())
    favs = list_favorites(db, user_id)
    return render(request, "platform/workspace.html",
        tasks=tasks, my_opps=my_opps, pending_intents=pending_intents,
        my_resources=my_resources, favs=favs, user_id=user_id,
    )


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  FAVORITES & FOLLOWS (AJAX)  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.post("/api/v1/favorites/toggle")
async def api_toggle_favorite(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    result = toggle_favorite(db, user_id, form.get("target_type", ""), int(form.get("target_id", 0)))
    return result


@router.post("/api/v1/follows/toggle")
async def api_toggle_follow(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(403)
    form = await request.form()
    result = toggle_follow(db, user_id, form.get("target_type", ""), int(form.get("target_id", 0)))
    return result


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  UNIFIED SEARCH  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.get("/platform/search", response_class=HTMLResponse)
def platform_search(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    result = unified_search(db, q)
    return render(request, "platform/search_results.html", result=result)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲  ADMIN  鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

@router.get("/admin/platform", response_class=HTMLResponse)
def admin_platform(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    sec = request.scope.get("security_context", {})
    if not sec.get("can_manage_users") and "platform:manage" not in sec.get("permissions", []):
        raise HTTPException(403, "需要管理员权限")
    tags = list_tags(db)
    return render(request, "platform/admin.html", tags=tags)


@router.post("/admin/tags/create")
async def admin_create_tag(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    tag_key = f"{form.get('tag_group')}:{form.get('label')}"
    existing = db.scalar(select(IndustryTag).where(IndustryTag.tag_key == tag_key))
    if not existing:
        db.add(IndustryTag(
            tag_key=tag_key,
            tag_group=form.get("tag_group", ""),
            label=form.get("label", ""),
        ))
        db.commit()
    return RedirectResponse("/admin/platform", 303)










# v0.6D data integrity admin
from app.services.data_integrity_service import connect as _di_connect, current_fk_issues as _di_current_fk_issues, sync_issues as _di_sync_issues, list_registered_issues as _di_list_issues, issue_summary as _di_summary, audit_trail as _di_audit_trail, update_issue_status as _di_update_status


def _can_manage_data_integrity(request: Request) -> bool:
    sec = request.scope.get("security_context", {})
    permissions = set(sec.get("permissions") or [])
    return bool(sec.get("can_manage_users") or "review_data" in permissions or "manage_users" in permissions)


@router.get("/admin", response_class=HTMLResponse)
def admin_root():
    return RedirectResponse("/admin/platform", status_code=303)


@router.get("/admin/data-integrity", response_class=HTMLResponse)
def admin_data_integrity(request: Request, status: str = "", table: str = "", severity: str = ""):
    if not _can_manage_data_integrity(request):
        raise HTTPException(403, "data integrity admin permission required")
    with _di_connect() as conn:
        issues = _di_current_fk_issues(conn)
        _di_sync_issues(conn, issues, actor="admin_page_recheck")
        conn.commit()
        return render(request, "platform/data_integrity.html", summary=_di_summary(conn), issues=_di_list_issues(conn, status=status, table=table, severity=severity), audit_entries=_di_audit_trail(conn), filters={"status": status, "table": table, "severity": severity})


@router.post("/admin/data-integrity/{issue_id}/status")
def admin_data_integrity_status(request: Request, issue_id: int, status: str = Form(...), note: str = Form("")):
    if not _can_manage_data_integrity(request):
        raise HTTPException(403, "data integrity admin permission required")
    actor = request.scope.get("security_context", {}).get("user", {}).get("username", "admin")
    with _di_connect() as conn:
        _di_update_status(conn, issue_id, status=status, actor=actor, note=note)
        conn.commit()
    return RedirectResponse("/admin/data-integrity", status_code=303)

# v0.6E product recovery routes
from app.services.product_recovery_service import pipeline_counts as _v06e_pipeline_counts, latest_pipeline_records as _v06e_pipeline_records, publish_collection_item as _v06e_publish_collection_item
from app.services.intelligence_product_service import IntelligenceProductService


def _v06e_permissions(request: Request) -> set[str]:
    return set(request.scope.get("security_context", {}).get("permissions") or [])


def _can_manage_people_orgs(request: Request) -> bool:
    sec = request.scope.get("security_context", {})
    perms = _v06e_permissions(request)
    return bool(sec.get("can_manage_users") or "manage_users" in perms or "edit_data" in perms or "review_data" in perms)


def _can_manage_intelligence(request: Request) -> bool:
    sec = request.scope.get("security_context", {})
    perms = _v06e_permissions(request)
    return bool(sec.get("can_manage_users") or "manage_users" in perms or "review_data" in perms or "manage_monitoring" in perms)


def _next_external_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now():%Y%m%d%H%M%S%f}"


@router.get("/intelligence/operations", response_class=HTMLResponse)
def intelligence_operations(request: Request):
    if not _can_manage_intelligence(request):
        raise HTTPException(403, "intelligence operations permission required")
    records = _v06e_pipeline_records()
    return render(
        request,
        "platform/intelligence_operations.html",
        counts=_v06e_pipeline_counts(),
        records=records,
        latest_jobs=records.get("jobs", []),
        latest_items=records.get("items", []),
        latest_candidates=records.get("candidates", []),
    )


@router.get("/admin/people", response_class=HTMLResponse)
def admin_people(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "people admin permission required")
    stmt = select(Person).order_by(desc(Person.created_at))
    if q:
        stmt = stmt.where((Person.name.contains(q)) | (Person.public_role.contains(q)) | (Person.organization_network.contains(q)))
    people = list(db.scalars(stmt.limit(100)).all())
    return render(request, "platform/admin_people.html", people=people, person=None, q=q)


@router.post("/admin/people")
async def admin_create_person(request: Request, db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "people admin permission required")
    form = await request.form()
    person = Person(
        external_id=_next_external_id("PER"),
        name=str(form.get("name", "")).strip(),
        public_role=str(form.get("public_role", "")).strip() or None,
        organization_network=str(form.get("organization_network", "")).strip() or None,
        ability_tags=str(form.get("ability_tags", "")).strip() or None,
        value_provided=str(form.get("value_provided", "")).strip() or None,
        visibility=str(form.get("visibility", "内部")).strip() or "内部",
        verification_status=str(form.get("verification_status", "待核验")).strip() or "待核验",
        manually_confirmed=True,
        is_active=bool(form.get("is_active")),
    )
    db.add(person)
    db.commit()
    return RedirectResponse(f"/admin/people/{person.id}", 303)


@router.get("/admin/people/{person_id:int}", response_class=HTMLResponse)
def admin_person_detail(person_id: int, request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "people admin permission required")
    person = db.get(Person, int(person_id))
    if not person:
        raise HTTPException(404, "person not found")
    people = list(db.scalars(select(Person).order_by(desc(Person.created_at)).limit(100)).all())
    return render(request, "platform/admin_people.html", people=people, person=person, q=q)


@router.post("/admin/people/{person_id:int}/update")
async def admin_update_person(person_id: int, request: Request, db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "people admin permission required")
    person = db.get(Person, int(person_id))
    if not person:
        raise HTTPException(404, "person not found")
    form = await request.form()
    person.name = str(form.get("name", person.name)).strip() or person.name
    person.public_role = str(form.get("public_role", "")).strip() or None
    person.organization_network = str(form.get("organization_network", "")).strip() or None
    person.ability_tags = str(form.get("ability_tags", "")).strip() or None
    person.value_provided = str(form.get("value_provided", "")).strip() or None
    person.visibility = str(form.get("visibility", person.visibility)).strip() or person.visibility
    person.verification_status = str(form.get("verification_status", person.verification_status)).strip() or person.verification_status
    person.is_active = bool(form.get("is_active"))
    person.manually_confirmed = True
    if not person.is_active:
        person.deactivated_at = datetime.now()
    db.commit()
    return RedirectResponse(f"/admin/people/{person.id}", 303)


@router.get("/admin/organizations", response_class=HTMLResponse)
def admin_organizations(request: Request, q: str = Query(""), priority: bool = Query(False), db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "organization admin permission required")
    stmt = select(Organization).order_by(desc(Organization.created_at)).limit(100)
    all_rows = list(db.scalars(stmt).all())
    db_path = Path(str(db.get_bind().url.database))
    registry = EntityRegistryService(db_path)
    items = []
    for org in all_rows:
        priority_info = GoldenLoopService(db).subject_priority("organization", org.id)
        if priority and not priority_info.get("is_priority"):
            continue
        if q and q not in " ".join(filter(None, [org.standard_name, org.short_name, org.region, org.industry_tags])):
            continue
        monitoring = organization_monitoring_context(org.external_id, db_path) if priority_info.get("is_priority") else None
        identity = classify_identity(
            "organization", org.standard_name, verification_status=org.verification_status,
            has_monitoring_seed=bool(monitoring and (monitoring["official_domain"] or monitoring["sources"])),
        )
        people_count = db.scalar(select(func.count()).select_from(Person).where(Person.organization_network.contains(org.standard_name))) or 0
        items.append({"org": org, "people_count": int(people_count), "priority": priority_info, "identity": identity})
    incomplete = sum(1 for item in items if item["priority"].get("is_priority") and item["identity"]["status"] != "IDENTITY_CONFIRMED")
    return render(request, "platform/admin_organizations.html", orgs=items, org=None, related_people=[], q=q,
                  priority_filter=priority, incomplete_count=incomplete, show_form=False, website_import=False)


@router.get("/admin/organizations/new", response_class=HTMLResponse)
def admin_new_organization(request: Request):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "organization admin permission required")
    return render(request, "platform/admin_organizations.html", orgs=[], org=None, related_people=[], q="",
                  show_form=True, website_import=False, priority_filter=False, incomplete_count=0)


@router.post("/admin/organizations")
async def admin_create_organization(request: Request, db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "organization admin permission required")
    form = await request.form()
    org = Organization(
        external_id=_next_external_id("ORG"), standard_name=str(form.get("standard_name", "")).strip(),
        short_name=str(form.get("short_name", "")).strip() or None,
        org_type=str(form.get("org_type", "")).strip() or None, region=str(form.get("region", "")).strip() or None,
        industry_tags=str(form.get("industry_tags", "")).strip() or None, resources=str(form.get("resources", "")).strip() or None,
        needs=str(form.get("needs", "")).strip() or None, visibility=str(form.get("visibility", "内部")).strip() or "内部",
        verification_status=str(form.get("verification_status", "待核验")).strip() or "待核验",
        manually_confirmed=True, is_active=bool(form.get("is_active")),
    )
    db.add(org)
    db.commit()
    return RedirectResponse(f"/admin/organizations/{org.id}", 303)


@router.get("/admin/organizations/website-import", response_class=HTMLResponse)
def admin_organization_website_import(request: Request):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "organization admin permission required")
    return render(request, "platform/admin_organizations.html", orgs=[], org=None, related_people=[], q="",
                  show_form=False, website_import=True, website_preview=[], source_text="",
                  priority_filter=False, incomplete_count=0)


async def _website_csv_text(request: Request) -> str:
    form = await request.form()
    upload = form.get("file")
    if upload and getattr(upload, "read", None) and getattr(upload, "filename", ""):
        uploaded_text = (await upload.read()).decode("utf-8-sig")
        if uploaded_text.strip():
            return uploaded_text
    return str(form.get("source_text") or "")


@router.post("/admin/organizations/website-import/preview", response_class=HTMLResponse)
async def admin_organization_website_preview(request: Request, db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "organization admin permission required")
    source_text = await _website_csv_text(request)
    preview = preview_website_import(source_text, Path(str(db.get_bind().url.database)))
    return render(request, "platform/admin_organizations.html", orgs=[], org=None, related_people=[], q="",
                  show_form=False, website_import=True, website_preview=preview, source_text=source_text,
                  priority_filter=False, incomplete_count=0)


@router.post("/admin/organizations/website-import/confirm")
async def admin_organization_website_confirm(request: Request, db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "organization admin permission required")
    source_text = await _website_csv_text(request)
    actor = request.scope.get("security_context", {}).get("user", {}).get("username", "admin")
    result = save_website_import(source_text, actor, Path(str(db.get_bind().url.database)))
    return RedirectResponse(f"/admin/organizations?priority=1&message=官网已保存{result['saved']}条，跳过{result['skipped']}条", 303)


@router.get("/admin/organizations/{org_id:int}", response_class=HTMLResponse)
def admin_organization_detail(org_id: int, request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "organization admin permission required")
    org = db.get(Organization, int(org_id))
    if not org:
        raise HTTPException(404, "organization not found")
    db_path = Path(str(db.get_bind().url.database))
    entity = EntityRegistryService(db_path).get("organization", org.external_id)
    monitoring = organization_monitoring_context(org.external_id, db_path)
    priority_info = GoldenLoopService(db).subject_priority("organization", org.id)
    identity = classify_identity("organization", org.standard_name, verification_status=org.verification_status,
                                 has_monitoring_seed=bool(monitoring["official_domain"] or monitoring["sources"]))
    related_people = list(db.scalars(select(Person).where(Person.organization_network.contains(org.standard_name)).limit(50)).all())
    return render(request, "platform/admin_organizations.html", orgs=[], org=org, related_people=related_people, q=q,
                  entity=entity, monitoring=monitoring, priority_info=priority_info, identity=identity,
                  duplicate_candidates=organization_duplicate_candidates(org.external_id, db_path), show_form=True,
                  website_import=False, priority_filter=False, incomplete_count=0)


@router.post("/admin/organizations/{org_id:int}/update")
async def admin_update_organization(org_id: int, request: Request, db: Session = Depends(get_db)):
    if not _can_manage_people_orgs(request):
        raise HTTPException(403, "organization admin permission required")
    org = db.get(Organization, int(org_id))
    if not org:
        raise HTTPException(404, "organization not found")
    form = await request.form()
    actor_user = request.scope.get("security_context", {}).get("user", {})
    actor = actor_user.get("username", "admin")
    db_path = Path(str(db.get_bind().url.database))
    try:
        update_organization(org_id, {
            "name": str(form.get("standard_name", org.standard_name)).strip(),
            "short_name": str(form.get("short_name", "")).strip(), "organization_type": str(form.get("org_type", "")).strip(),
            "region": str(form.get("region", "")).strip(), "industry_tags": str(form.get("industry_tags", "")).strip(),
            "resources": str(form.get("resources", "")).strip(), "needs": str(form.get("needs", "")).strip(),
            "visibility": str(form.get("visibility", "内部")).strip(),
            "verification_status": str(form.get("verification_status", "待核验")).strip(),
            "status": "active" if form.get("is_active") else "inactive",
        }, actor_user, db_path)
        alias = str(form.get("new_alias", "")).strip()
        if alias:
            EntityRegistryService(db_path).add_alias(
                "organization", org.external_id, alias,
                alias_type=str(form.get("alias_type", "brand_name")).strip() or "brand_name",
                source="管理员主数据", actor=actor, permissions={"review_data"},
            )
        website = str(form.get("official_website", "")).strip()
        if website:
            set_admin_confirmed_official_domain(org.external_id, website, actor, db_path=db_path)
    except (OrganizationAccessError, ValueError) as exc:
        detail = getattr(exc, "message", str(exc))
        return RedirectResponse(f"/admin/organizations/{org_id}?error={detail}", 303)
    return RedirectResponse(f"/admin/organizations/{org_id}?message=机构主数据已保存", 303)

@router.get("/admin/intelligence", response_class=HTMLResponse)
def admin_intelligence(request: Request, db: Session = Depends(get_db)):
    if not _can_manage_intelligence(request):
        raise HTTPException(403, "intelligence admin permission required")
    items = list(db.scalars(select(IntelligenceItem).order_by(desc(IntelligenceItem.updated_at), desc(IntelligenceItem.created_at)).limit(100)).all())
    return render(request, "platform/admin_intelligence.html", items=items, item=None)


@router.post("/admin/intelligence")
async def admin_create_intelligence(request: Request, db: Session = Depends(get_db)):
    if not _can_manage_intelligence(request):
        raise HTTPException(403, "intelligence admin permission required")
    form = await request.form()
    actor = request.scope.get("security_context", {}).get("user", {}).get("username", "admin")
    item = IntelligenceProductService(db.get_bind().url.database).create_manual_draft({
        "title": str(form.get("title", "")).strip(), "summary": str(form.get("summary", "")).strip() or None,
        "content": str(form.get("content", "")).strip() or None, "intel_type": str(form.get("intel_type", "manual")).strip() or "manual",
        "companies": str(form.get("companies", "")).strip() or None, "industry_directions": str(form.get("industry_directions", "")).strip() or None,
        "tags": str(form.get("tags", "")).strip() or None, "source_url": str(form.get("source_url", "")).strip() or None,
        "visibility": str(form.get("visibility", "public")).strip() or "public", "credibility": int(form.get("credibility", 3) or 3),
        "importance": int(form.get("importance", 2) or 2), "created_by": get_current_user_id(request),
    }, actor=actor)
    return RedirectResponse(f"/admin/intelligence/{item['id']}", 303)


@router.get("/admin/intelligence/{item_id:int}", response_class=HTMLResponse)
def admin_intelligence_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    if not _can_manage_intelligence(request):
        raise HTTPException(403, "intelligence admin permission required")
    item = db.get(IntelligenceItem, int(item_id))
    if not item:
        raise HTTPException(404, "intelligence not found")
    items = list(db.scalars(select(IntelligenceItem).order_by(desc(IntelligenceItem.updated_at), desc(IntelligenceItem.created_at)).limit(100)).all())
    return render(request, "platform/admin_intelligence.html", items=items, item=item)


@router.post("/admin/intelligence/{item_id:int}/update")
async def admin_update_intelligence(item_id: int, request: Request, db: Session = Depends(get_db)):
    if not _can_manage_intelligence(request):
        raise HTTPException(403, "intelligence admin permission required")
    form = await request.form()
    actor = request.scope.get("security_context", {}).get("user", {}).get("username", "admin")
    try:
        item = IntelligenceProductService(db.get_bind().url.database).update_product(item_id, dict(form), actor=actor)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return RedirectResponse(f"/admin/intelligence/{item['id']}", 303)


@router.post("/admin/intelligence/{item_id:int}/publish")
def admin_publish_intelligence(item_id: int, request: Request, db: Session = Depends(get_db)):
    if not _can_manage_intelligence(request):
        raise HTTPException(403, "intelligence admin permission required")
    actor = request.scope.get("security_context", {}).get("user", {}).get("username", "admin")
    try:
        item = IntelligenceProductService(db.get_bind().url.database).publish_existing(
            item_id, actor=actor, permissions=_v06e_permissions(request))
    except (ValueError, PermissionError) as exc:
        raise HTTPException(409, str(exc)) from exc
    return RedirectResponse(f"/admin/intelligence/{item['id']}", 303)


@router.post("/admin/intelligence/collection/{collection_item_id:int}/publish")
def admin_publish_collection_item(collection_item_id: int, request: Request, db: Session = Depends(get_db)):
    if not _can_manage_intelligence(request):
        raise HTTPException(403, "intelligence admin permission required")
    item = _v06e_publish_collection_item(db, int(collection_item_id), actor_user_id=get_current_user_id(request), status="published")
    return RedirectResponse(f"/admin/intelligence/{item.id}", 303)


