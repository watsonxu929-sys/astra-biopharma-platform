from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.services.club_matching_service import match_need_offering
from app.security import can, current_user, current_username
from app.services.club_operations_service import ClubMembershipService, ClubOperationError, ClubOperationsDashboardService, ClubResourceMatchingService
from app.services.lead_recommendation_service import generate_lead_recommendations
from app.services.lead_scoring_service import manual_grade_requires_reason, score_lead
from app.services.membership_person_link_service import bind_person, get_link_info, get_person_candidates, list_link_audit, unbind_person
from app.services.membership_access_service import get_accessible_membership_or_403, require_membership_admin
from app.services.membership_user_link_service import bind_user, get_link_info as get_user_link_info, list_link_audit as list_user_link_audit, unbind_user
from app.v04c_review import db_connection, default_db_path
from scripts.migrate_v04f import SCHEMA_SQL

router = APIRouter(tags=["v0.4F 线索经营与 Q-BAY 俱乐部"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

LEAD_STAGES = ["待识别", "待补充资料", "待联系", "已联系", "深入沟通", "方案匹配", "合作推进", "已成交或已落地", "暂缓", "失效"]


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today() -> str:
    return date.today().isoformat()


def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    if not allow_migration:
        return path
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
    return path


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_json(value: Any, default: Any = None) -> Any:
    try:
        return json.loads(value) if value else (default if default is not None else {})
    except json.JSONDecodeError:
        return default if default is not None else {}


def _next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04f_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
            seq_value = CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
            seq_date = excluded.seq_date,
            updated_at = excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):04d}"


def _subject(conn: sqlite3.Connection, subject_type: str, subject_id: str) -> dict[str, Any] | None:
    if subject_type == "organization":
        row = conn.execute("SELECT * FROM organizations WHERE external_id=? OR CAST(id AS TEXT)=? LIMIT 1", (subject_id, subject_id)).fetchone()
        if not row:
            return None
        return {
            "type": "organization",
            "type_label": "企业/机构",
            "id": row["id"],
            "external_id": row["external_id"],
            "name": row["standard_name"],
            "tags": row["industry_tags"] or "",
            "region": row["region"] or "",
            "stage": row["org_type"] or "",
            "status": row["verification_status"] or "",
            "profile_url": f"/subjects/organization/{row['external_id']}",
            "detail_url": f"/organizations/{row['id']}",
        }
    if subject_type == "project":
        row = conn.execute("SELECT * FROM projects WHERE external_id=? OR CAST(id AS TEXT)=? LIMIT 1", (subject_id, subject_id)).fetchone()
        if not row:
            return None
        return {
            "type": "project",
            "type_label": "项目",
            "id": row["id"],
            "external_id": row["external_id"],
            "name": row["name"],
            "tags": row["focus_tags"] or "",
            "region": "",
            "stage": row["status"] or row["project_type"] or "",
            "status": row["status"] or "",
            "profile_url": f"/subjects/project/{row['external_id']}",
            "detail_url": f"/projects/{row['id']}",
        }
    return None


def _subject_maps(conn: sqlite3.Connection, leads: list[sqlite3.Row]) -> dict[tuple[str, str], dict[str, Any]]:
    ids = {"organization": [], "project": []}
    for row in leads:
        if row["subject_type"] in ids:
            ids[row["subject_type"]].append(row["subject_id"])
    maps: dict[tuple[str, str], dict[str, Any]] = {}
    for subject_type, table, label_col, tag_col in [
        ("organization", "organizations", "standard_name", "industry_tags"),
        ("project", "projects", "name", "focus_tags"),
    ]:
        if not ids[subject_type]:
            continue
        placeholders = ",".join("?" for _ in ids[subject_type])
        rows = conn.execute(f"SELECT * FROM {table} WHERE external_id IN ({placeholders})", ids[subject_type]).fetchall()
        for row in rows:
            maps[(subject_type, row["external_id"])] = _subject(conn, subject_type, row["external_id"]) or {}
    return maps


def _profile_for_scoring(conn: sqlite3.Connection, lead: sqlite3.Row) -> dict[str, Any]:
    subject = _subject(conn, lead["subject_type"], lead["subject_id"]) or {}
    sid = lead["subject_id"]
    people = conn.execute(
        """
        SELECT COUNT(*) AS c FROM relations
        WHERE is_active=1 AND (source_external_id=? OR target_external_id=?)
        """,
        (sid, sid),
    ).fetchone()["c"]
    stats = {
        "people": people,
        "events": conn.execute("SELECT COUNT(*) AS c FROM events WHERE related_entity=? OR related_organization_id=?", (sid, subject.get("id") or -1)).fetchone()["c"],
        "resources": conn.execute("SELECT COUNT(*) AS c FROM resources WHERE owner_external_id=? OR owner_organization_id=?", (sid, subject.get("id") or -1)).fetchone()["c"],
        "projects": conn.execute("SELECT COUNT(*) AS c FROM projects WHERE owner_external_id=? OR owner_organization_id=?", (sid, subject.get("id") or -1)).fetchone()["c"],
    }
    try:
        review = conn.execute(
            "SELECT COUNT(*) AS open_count, SUM(CASE WHEN item_type='conflict' THEN 1 ELSE 0 END) AS conflict_count FROM v04c_review_items WHERE subject_id=? AND status IN ('pending','in_review','deferred')",
            (sid,),
        ).fetchone()
        review_data = {"open_count": review["open_count"] or 0, "conflict_count": review["conflict_count"] or 0}
    except sqlite3.Error:
        review_data = {"open_count": 0, "conflict_count": 0}
    completeness = {"percent": 70 if subject.get("tags") else 45}
    return {"subject": subject, "stats": stats, "review": review_data, "completeness": completeness, "lead": dict(lead)}


def rescore_lead(conn: sqlite3.Connection, lead_id: int) -> sqlite3.Row:
    lead = conn.execute("SELECT * FROM v04f_lead_records WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        raise ValueError("线索不存在")
    scoring = score_lead(_profile_for_scoring(conn, lead))
    conn.execute(
        """
        UPDATE v04f_lead_records
        SET system_score=?, system_grade=?, scoring_json=?, last_scored_at=?, updated_at=?
        WHERE id=?
        """,
        (scoring["score"], scoring["grade"], _json(scoring), scoring["scored_at"], now(), lead_id),
    )
    return conn.execute("SELECT * FROM v04f_lead_records WHERE id=?", (lead_id,)).fetchone()


def get_or_create_lead(subject_type: str, subject_id: str, owner: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    subject_type = subject_type.strip().lower()
    if subject_type not in {"organization", "project"}:
        raise ValueError("第一版仅支持企业和项目线索")
    with db_connection(db_path) as conn:
        subject = _subject(conn, subject_type, subject_id)
        if not subject:
            raise ValueError("关联主体不存在")
        existing = conn.execute(
            "SELECT * FROM v04f_lead_records WHERE subject_type=? AND subject_id=? AND status='active'",
            (subject_type, subject["external_id"]),
        ).fetchone()
        if existing:
            return dict(existing)
        created_at = now()
        lead_no = _next_no(conn, "LED")
        cur = conn.execute(
            """
            INSERT INTO v04f_lead_records(
                lead_no, subject_type, subject_id, owner, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (lead_no, subject_type, subject["external_id"], owner or None, created_at, created_at),
        )
        conn.execute(
            "INSERT INTO v04f_lead_stage_history(lead_id, old_stage, new_stage, actor, reason, changed_at) VALUES (?, NULL, '待识别', 'system', '创建线索', ?)",
            (cur.lastrowid, created_at),
        )
        row = rescore_lead(conn, cur.lastrowid)
        return dict(row)


def lead_detail(lead_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        lead = conn.execute("SELECT * FROM v04f_lead_records WHERE id=?", (lead_id,)).fetchone()
        if not lead:
            raise ValueError("线索不存在")
        profile = _profile_for_scoring(conn, lead)
        scoring = _load_json(lead["scoring_json"], {})
        recs = generate_lead_recommendations(profile, scoring or score_lead(profile))
        for rec in recs:
            existing = conn.execute(
                "SELECT * FROM v04f_lead_suggestions WHERE lead_id=? AND suggestion_key=?",
                (lead_id, rec["key"]),
            ).fetchone()
            if not existing:
                ts = now()
                conn.execute(
                    """
                    INSERT INTO v04f_lead_suggestions(lead_id, suggestion_key, title, basis, priority, recommended_due, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (lead_id, rec["key"], rec["title"], rec["basis"], rec["priority"], rec["recommended_due"], ts, ts),
                )
        suggestions = [dict(r) for r in conn.execute("SELECT * FROM v04f_lead_suggestions WHERE lead_id=? ORDER BY converted_action_id IS NOT NULL, priority, id", (lead_id,)).fetchall()]
        history = [dict(r) for r in conn.execute("SELECT * FROM v04f_lead_stage_history WHERE lead_id=? ORDER BY id DESC", (lead_id,)).fetchall()]
    return {"lead": dict(lead), "profile": profile, "scoring": scoring, "suggestions": suggestions, "history": history, "stages": LEAD_STAGES}


@router.get("/leads", response_class=HTMLResponse)
def leads_page(request: Request, q: str = "", subject_type: str = "", stage: str = "", owner: str = "", min_score: int = 0, max_score: int = 100, overdue: str = "", page: int = 1):
    ensure_schema()
    page = max(1, page)
    params: list[Any] = []
    clauses = ["status='active'", "system_score BETWEEN ? AND ?"]
    params.extend([min_score, max_score])
    if subject_type in {"organization", "project"}:
        clauses.append("subject_type=?")
        params.append(subject_type)
    if stage:
        clauses.append("funnel_stage=?")
        params.append(stage)
    if owner:
        clauses.append("owner LIKE ?")
        params.append(f"%{owner}%")
    if overdue == "yes":
        clauses.append("next_action_at IS NOT NULL AND next_action_at < ?")
        params.append(today())
    if q:
        clauses.append(
            """
            (
              subject_id LIKE ?
              OR (subject_type='organization' AND subject_id IN (SELECT external_id FROM organizations WHERE standard_name LIKE ? OR industry_tags LIKE ? OR region LIKE ?))
              OR (subject_type='project' AND subject_id IN (SELECT external_id FROM projects WHERE name LIKE ? OR focus_tags LIKE ? OR owner_external_id LIKE ?))
            )
            """
        )
        token = f"%{q}%"
        params.extend([token, token, token, token, token, token, token])
    where = " AND ".join(clauses)
    with db_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM v04f_lead_records WHERE {where}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM v04f_lead_records WHERE {where} ORDER BY system_score DESC, updated_at DESC LIMIT 20 OFFSET ?",
            [*params, (page - 1) * 20],
        ).fetchall()
        subject_map = _subject_maps(conn, rows)
        items = []
        for row in rows:
            subject = subject_map.get((row["subject_type"], row["subject_id"])) or {}
            items.append({"lead": dict(row), "subject": subject})
    return templates.TemplateResponse(request, "v04f_leads.html", {"mode": "list", "items": items, "total": total, "page": page, "pages": max(1, (total + 19) // 20), "filters": locals(), "stages": LEAD_STAGES})


@router.post("/leads/create")
def create_lead(request: Request, subject_type: str = Form(...), subject_id: str = Form(...), owner: str = Form("")):
    owner = owner.strip() or current_username(request)
    try:
        row = get_or_create_lead(subject_type, subject_id, owner)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(f"/leads/{row['id']}", status_code=303)


@router.get("/leads/{lead_id}", response_class=HTMLResponse)
def lead_page(lead_id: int, request: Request):
    try:
        data = lead_detail(lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(request, "v04f_leads.html", {"mode": "detail", **data})


@router.post("/leads/{lead_id}/stage")
def update_stage(request: Request, lead_id: int, new_stage: str = Form(...), actor: str = Form("manual"), reason: str = Form("")):
    actor = current_username(request)
    if new_stage not in LEAD_STAGES:
        raise HTTPException(400, "无效漏斗阶段")
    with db_connection() as conn:
        lead = conn.execute("SELECT * FROM v04f_lead_records WHERE id=?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "线索不存在")
        ts = now()
        conn.execute("UPDATE v04f_lead_records SET funnel_stage=?, updated_at=? WHERE id=?", (new_stage, ts, lead_id))
        conn.execute(
            "INSERT INTO v04f_lead_stage_history(lead_id, old_stage, new_stage, actor, reason, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (lead_id, lead["funnel_stage"], new_stage, actor or "manual", reason or None, ts),
        )
    return RedirectResponse(f"/leads/{lead_id}", status_code=303)


@router.post("/leads/{lead_id}/grade")
def update_grade(lead_id: int, manual_grade: str = Form(""), reason: str = Form("")):
    with db_connection() as conn:
        lead = conn.execute("SELECT * FROM v04f_lead_records WHERE id=?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "线索不存在")
        if manual_grade and manual_grade_requires_reason(lead["system_grade"], manual_grade, reason):
            raise HTTPException(400, "人工等级高于系统等级时必须填写理由")
        conn.execute("UPDATE v04f_lead_records SET manual_grade=?, manual_override_reason=?, updated_at=? WHERE id=?", (manual_grade or None, reason or None, now(), lead_id))
    return RedirectResponse(f"/leads/{lead_id}", status_code=303)


@router.post("/leads/{lead_id}/suggestions/{suggestion_id}/action")
def suggestion_to_action(request: Request, lead_id: int, suggestion_id: int, owner: str = Form("")):
    raise HTTPException(410, "旧行动任务写入口已冻结，请从正式协作入口创建任务")


@router.get("/club", response_class=HTMLResponse)
def club_home(request: Request):
    ensure_schema()
    dashboard = ClubOperationsDashboardService().summary()
    metrics = dashboard.get("metrics", {})
    stats = {
        "total_members": metrics.get("members"),
        "active_members": metrics.get("active_members"),
        "pending_applications": metrics.get("pending_applications"),
        "upcoming_events": 0,
        "open_events": 0,
        "pending_registrations": 0,
        "valid_demands": metrics.get("needs"),
        "valid_supplies": metrics.get("offerings"),
        "pending_matches": metrics.get("candidate_matches"),
        "post_event_followups": 0,
        "lead_candidates": 0,
    }
    with db_connection() as conn:
        today_str = date.today().isoformat()
        try:
            upcoming = conn.execute(
                "SELECT COUNT(*) FROM v05c_club_event_profiles p LEFT JOIN events e ON e.id=p.event_id WHERE p.status IN ('registration_open','ongoing') OR (e.event_date >= ? AND p.status='published')",
                (today_str,),
            ).fetchone()
            stats["upcoming_events"] = int(upcoming[0]) if upcoming else 0
        except sqlite3.Error:
            upcoming = conn.execute(
                "SELECT COUNT(*) FROM v05c_club_event_profiles WHERE status IN ('registration_open','ongoing')",
            ).fetchone()
            stats["upcoming_events"] = int(upcoming[0]) if upcoming else 0
        open_events = conn.execute(
            "SELECT COUNT(*) FROM v05c_club_event_profiles WHERE registration_status='open'",
        ).fetchone()
        stats["open_events"] = int(open_events[0]) if open_events else 0
        pending_reg = conn.execute(
            "SELECT COUNT(*) FROM v05c_club_event_registrations WHERE status='submitted'",
        ).fetchone()
        stats["pending_registrations"] = int(pending_reg[0]) if pending_reg else 0
        try:
            followups = conn.execute(
                "SELECT COUNT(*) FROM p4_event_feedback WHERE status='submitted'",
            ).fetchone()
            stats["post_event_followups"] = int(followups[0]) if followups else 0
        except sqlite3.Error:
            stats["post_event_followups"] = 0
        try:
            leads = conn.execute(
                "SELECT COUNT(*) FROM p4_club_lead_candidates WHERE status='pending_review'",
            ).fetchone()
            stats["lead_candidates"] = int(leads[0]) if leads else 0
        except sqlite3.Error:
            stats["lead_candidates"] = 0
        try:
            upcoming_events = [dict(row) for row in conn.execute(
                "SELECT id, event_no, event_date, venue, status, registration_status FROM v05c_club_event_profiles WHERE event_date >= ? ORDER BY event_date LIMIT 5",
                (today_str,),
            ).fetchall()]
        except sqlite3.Error:
            upcoming_events = [dict(row) for row in conn.execute(
                "SELECT id, event_no, '' as event_date, venue, status, registration_status FROM v05c_club_event_profiles WHERE status='published' LIMIT 5",
            ).fetchall()]
    my_membership = None
    user_id = request.scope.get("user", {}).get("id")
    if user_id:
        with db_connection() as conn:
            member = conn.execute(
                "SELECT * FROM v04f_club_memberships WHERE user_id=? AND status IN ('active','pending') ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if member:
                my_membership = dict(member)
    return templates.TemplateResponse(
        request, "club_home.html", {"stats": stats, "upcoming_events": upcoming_events, "my_membership": my_membership}
    )


@router.get("/club/operations", response_class=HTMLResponse)
def club_operations(request: Request, tab: str = "dashboard"):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部管理权限")
    ensure_schema()
    today_str = date.today().isoformat()
    with db_connection() as conn:
        pending_applications = conn.execute("SELECT COUNT(*) FROM v04f_club_applications WHERE status='under_review'").fetchone()[0]
        pending_registrations = conn.execute("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE status='submitted'").fetchone()[0]
        today_events = conn.execute(
            "SELECT COUNT(*) FROM v05c_club_event_profiles p LEFT JOIN events e ON e.id=p.event_id WHERE p.status='ongoing' OR (e.event_date=? AND p.status IN ('registration_open','published'))",
            (today_str,),
        ).fetchone()[0]
        pending_resources = conn.execute("SELECT COUNT(*) FROM v06_market_resources WHERE status='pending_review'").fetchone()[0]
        try:
            pending_matches = conn.execute("SELECT COUNT(*) FROM p4_resource_match_candidates WHERE status='candidate'").fetchone()[0]
        except sqlite3.Error:
            pending_matches = 0
        try:
            followups = conn.execute("SELECT COUNT(*) FROM p4_event_feedback WHERE status='submitted'").fetchone()[0]
        except sqlite3.Error:
            followups = 0
        try:
            leads = conn.execute("SELECT COUNT(*) FROM p4_club_lead_candidates WHERE status='pending_review'").fetchone()[0]
        except sqlite3.Error:
            leads = 0
        stats = {
            "pending_applications": pending_applications,
            "pending_registrations": pending_registrations,
            "today_events": today_events,
            "pending_resources": pending_resources,
            "pending_matches": pending_matches,
            "followups": followups,
            "leads": leads,
        }
        if tab == "registrations":
            reg_rows = conn.execute(
                """SELECT r.*, e.name AS event_name
                   FROM v05c_club_event_registrations r
                   JOIN v05c_club_event_profiles p ON p.id=r.club_event_id
                   JOIN events e ON e.id=p.event_id
                   WHERE r.status='submitted'
                   ORDER BY r.registered_at DESC LIMIT 50""",
            ).fetchall()
            return templates.TemplateResponse(request, "club_operations.html", {"tab": "registrations", "pending_registrations": [dict(r) for r in reg_rows], "stats": stats})
        elif tab == "checkin":
            event_rows = conn.execute(
                """SELECT p.id, e.name, e.event_date, p.venue
                   FROM v05c_club_event_profiles p
                   JOIN events e ON e.id=p.event_id
                   WHERE p.status='ongoing' OR (e.event_date=? AND p.status IN ('registration_open','published'))
                   ORDER BY e.event_date""",
                (today_str,),
            ).fetchall()
            return templates.TemplateResponse(request, "club_operations.html", {"tab": "checkin", "today_events": [dict(r) for r in event_rows], "stats": stats})
        elif tab == "resources":
            resource_rows = conn.execute(
                """SELECT * FROM v06_market_resources WHERE status='pending_review' ORDER BY id DESC LIMIT 50""",
            ).fetchall()
            return templates.TemplateResponse(request, "club_operations.html", {"tab": "resources", "pending_resources": [dict(r) for r in resource_rows], "stats": stats})
        elif tab == "followups":
            try:
                candidate_rows = conn.execute(
                    """SELECT * FROM p4_event_relationship_candidates ORDER BY id DESC LIMIT 100""",
                ).fetchall()
            except sqlite3.Error:
                candidate_rows = []
            return templates.TemplateResponse(request, "club_operations.html", {"tab": "followups", "relationship_candidates": [dict(r) for r in candidate_rows], "stats": stats})
        elif tab == "leads":
            try:
                lead_rows = conn.execute(
                    """SELECT * FROM p4_club_lead_candidates ORDER BY id DESC LIMIT 100""",
                ).fetchall()
            except sqlite3.Error:
                lead_rows = []
            return templates.TemplateResponse(request, "club_operations.html", {"tab": "leads", "leads": [dict(r) for r in lead_rows], "stats": stats})
    return templates.TemplateResponse(request, "club_operations.html", {"tab": "dashboard", "stats": stats})


@router.get("/club/apply", response_class=HTMLResponse)
def club_apply(request: Request, submitted: str = ""):
    return templates.TemplateResponse(request, "v04f_club_apply.html", {"error": None, "submitted": submitted})


@router.post("/club/apply", response_class=HTMLResponse)
def submit_application(
    request: Request,
    applicant_name: str = Form(...),
    mobile: str = Form(""),
    email: str = Form(""),
    wechat: str = Form(""),
    organization_name: str = Form(""),
    title: str = Form(""),
    city: str = Form(""),
    industry_tags: str = Form(""),
    expertise_tags: str = Form(""),
    offered_resources: str = Form(""),
    cooperation_needs: str = Form(""),
    self_introduction: str = Form(""),
    referral_source: str = Form(""),
    referrer_name: str = Form(""),
    preferred_contact_method: str = Form(""),
    consent_to_store: str | None = Form(None),
    consent_to_contact: str | None = Form(None),
    website: str = Form(""),
):
    ensure_schema()
    if website.strip():
        return templates.TemplateResponse(request, "v04f_club_apply.html", {"error": "提交失败，请稍后重试。", "submitted": ""}, status_code=400)
    if not consent_to_store or not consent_to_contact:
        return templates.TemplateResponse(request, "v04f_club_apply.html", {"error": "请先勾选信息保存和后续联系同意。", "submitted": ""}, status_code=400)
    if not mobile.strip() and not email.strip():
        return templates.TemplateResponse(request, "v04f_club_apply.html", {"error": "手机号或邮箱至少填写一项。", "submitted": ""}, status_code=400)
    with db_connection() as conn:
        duplicate = conn.execute(
            """
            SELECT application_no FROM v04f_club_applications
            WHERE status IN ('submitted','under_review','need_more_info')
              AND ((mobile<>'' AND mobile=?) OR (email<>'' AND email=?))
            ORDER BY id DESC LIMIT 1
            """,
            (mobile.strip(), email.strip()),
        ).fetchone()
        if duplicate:
            return templates.TemplateResponse(request, "v04f_club_apply.html", {"error": f"已有待处理申请：{duplicate['application_no']}", "submitted": ""}, status_code=400)
        ts = now()
        app_no = _next_no(conn, "QBA")
        conn.execute(
            """
            INSERT INTO v04f_club_applications(
                application_no, applicant_name, mobile, email, wechat, organization_name, title, city,
                industry_tags, expertise_tags, offered_resources, cooperation_needs, self_introduction,
                referral_source, referrer_name, preferred_contact_method, consent_to_store, consent_to_contact,
                submitted_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?)
            """,
            (app_no, applicant_name.strip(), mobile.strip(), email.strip(), wechat.strip(), organization_name.strip(), title.strip(), city.strip(), industry_tags.strip(), expertise_tags.strip(), offered_resources.strip(), cooperation_needs.strip(), self_introduction.strip(), referral_source.strip(), referrer_name.strip(), preferred_contact_method.strip(), ts, ts, ts),
        )
    return RedirectResponse(f"/club/apply?submitted={app_no}", status_code=303)


def _application_matches(conn: sqlite3.Connection, app: sqlite3.Row) -> dict[str, list[dict[str, Any]]]:
    name_like = f"%{app['applicant_name']}%"
    org_like = f"%{app['organization_name']}%" if app["organization_name"] else "%"
    people = [dict(r) for r in conn.execute("SELECT id, external_id, name, public_role, organization_network FROM people WHERE name LIKE ? LIMIT 10", (name_like,)).fetchall()]
    orgs = [dict(r) for r in conn.execute("SELECT id, external_id, standard_name, org_type, region FROM organizations WHERE standard_name LIKE ? LIMIT 10", (org_like,)).fetchall()]
    return {"people": people, "organizations": orgs}


@router.get("/club/admin/applications", response_class=HTMLResponse)
def applications_page(request: Request, status: str = ""):
    ensure_schema()
    with db_connection() as conn:
        if status:
            rows = conn.execute("SELECT * FROM v04f_club_applications WHERE status=? ORDER BY submitted_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM v04f_club_applications ORDER BY submitted_at DESC LIMIT 100").fetchall()
    return templates.TemplateResponse(request, "v04f_club.html", {"mode": "applications", "applications": [dict(r) for r in rows], "status": status})


@router.get("/club/admin/applications/{application_id}", response_class=HTMLResponse)
def application_detail(application_id: int, request: Request):
    with db_connection() as conn:
        app = conn.execute("SELECT * FROM v04f_club_applications WHERE id=?", (application_id,)).fetchone()
        if not app:
            raise HTTPException(404, "申请不存在")
        matches = _application_matches(conn, app)
    public = dict(app)
    return templates.TemplateResponse(request, "v04f_club.html", {"mode": "application_detail", "application": public, "matches": matches})


@router.post("/club/admin/applications/{application_id}/review")
def review_application(request: Request, application_id: int, decision: str = Form(...), person_id: int = Form(0), organization_id: int = Form(0), user_id: int = Form(0), reviewer: str = Form("admin"), note: str = Form("")):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部管理权限")
    reviewer = current_username(request)
    user = current_user(request) or {}
    try:
        ClubMembershipService().review_application(
            application_id, decision=decision, actor=reviewer,
            actor_user_id=int(user["id"]) if user.get("id") else None,
            note=note, owner=reviewer, person_id=person_id or None,
            organization_id=organization_id or None, user_id=user_id or None,
        )
    except ClubOperationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return RedirectResponse(f"/club/admin/applications/{application_id}", status_code=303)


@router.post("/club/members/{member_id}/lifecycle")
def membership_lifecycle(
    request: Request, member_id: int, action: str = Form(...), reason: str = Form(""),
    member_level: str = Form(""), organization_id: int = Form(0), member_role: str = Form(""),
    expired_at: str = Form(""),
):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部管理权限")
    user = current_user(request) or {}
    changes = {
        "member_level": member_level or None, "organization_id": organization_id or None,
        "member_role": member_role or None, "expired_at": expired_at or None,
    }
    try:
        ClubMembershipService().transition_membership(
            member_id, action=action, actor=current_username(request),
            actor_user_id=int(user["id"]) if user.get("id") else None,
            reason=reason, changes=changes,
        )
    except ClubOperationError as exc:
        return RedirectResponse(f"/club/members/{member_id}?error={exc.message}", status_code=303)
    return RedirectResponse(f"/club/members/{member_id}?message=会员状态已更新", status_code=303)


@router.get("/club/members", response_class=HTMLResponse)
def members_page(request: Request, q: str = "", status: str = "", level: str = "", page: int = 1, tab: str = "directory"):
    ensure_schema()
    if tab == "applications":
        if not can(request, "manage_club"):
            raise HTTPException(403, "需要俱乐部管理权限")
        with db_connection() as conn:
            rows = conn.execute("SELECT * FROM v04f_club_applications ORDER BY submitted_at DESC LIMIT 100").fetchall()
        return templates.TemplateResponse(request, "club_members.html", {"tab": "applications", "applications": [dict(r) for r in rows]})
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("m.status=?")
        params.append(status)
    if level:
        clauses.append("m.member_level=?")
        params.append(level)
    if q:
        clauses.append("(m.member_no LIKE ? OR COALESCE(p.name,'') LIKE ? OR COALESCE(o.standard_name,'') LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    where = " AND ".join(clauses)
    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT m.*, p.name AS person_name, p.public_role, p.external_id AS person_external_id,
                   o.standard_name AS organization_name, o.external_id AS organization_external_id
            FROM v04f_club_memberships m
            LEFT JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            WHERE {where}
            ORDER BY m.joined_at DESC LIMIT 20 OFFSET ?
            """,
            [*params, (max(1, page) - 1) * 20],
        ).fetchall()
    return templates.TemplateResponse(request, "club_members.html", {"tab": "directory", "members": [dict(r) for r in rows], "filters": {"q": q, "status": status, "level": level, "page": page}})


@router.get("/club/members.csv")
def members_csv():
    ensure_schema()
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.member_no, COALESCE(p.name,'') AS name, COALESCE(o.standard_name,'') AS organization_name, COALESCE(p.public_role,'') AS public_role,
                   m.member_level, m.status, m.expertise_tags, m.cooperation_preferences, m.owner
            FROM v04f_club_memberships m
            LEFT JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            ORDER BY m.joined_at DESC
            """
        ).fetchall()
    lines = ["member_no,name,organization,title,level,status,expertise,preferences,owner"]
    for r in rows:
        lines.append(",".join('"' + str(r[k] or "").replace('"', '""') + '"' for k in r.keys()))
    return Response("\n".join(lines), media_type="text/csv; charset=utf-8")


@router.get("/club/members/{member_id}", response_class=HTMLResponse)
def member_detail(member_id: int, request: Request, message: str = "", error: str = ""):
    with db_connection() as conn:
        member = conn.execute(
            """
            SELECT m.*, p.name AS person_name, p.external_id AS person_external_id, p.public_role,
                   o.standard_name AS organization_name, o.external_id AS organization_external_id
            FROM v04f_club_memberships m
            LEFT JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            WHERE m.id=?
            """,
            (member_id,),
        ).fetchone()
        if not member:
            raise HTTPException(404, "会员不存在")
        member_data = dict(member)
        try:
            contact = conn.execute("SELECT * FROM v05b_member_contacts WHERE membership_id=?", (member_id,)).fetchone()
            avatar = conn.execute(
                "SELECT id,source_type,source_url,created_at FROM v05b_media_assets WHERE membership_id=? AND is_active=1 ORDER BY id DESC LIMIT 1",
                (member_id,),
            ).fetchone()
            member_data["contact"] = dict(contact) if contact else {}
            member_data["avatar_asset_id"] = int(avatar["id"]) if avatar else None
            member_data["avatar_source"] = dict(avatar) if avatar else {}
        except sqlite3.Error:
            member_data["contact"] = {}
            member_data["avatar_asset_id"] = None
            member_data["avatar_source"] = {}
        needs = [dict(r) for r in conn.execute(
            """SELECT id,title,description,resource_type AS need_type,industry_direction AS industry_tags,
                      region,status,'v06_market_resources' AS source_model
               FROM v06_market_resources WHERE direction='demand'
                 AND (owner_person_id=? OR organization_id=? OR (legacy_source_type='qbay_membership' AND legacy_source_id=?))
               ORDER BY id DESC""", (member_data.get("person_id"), member_data.get("organization_id"), str(member_id)),
        ).fetchall()]
        needs.extend(dict(r) for r in conn.execute("SELECT *, 'v04f_club_needs' AS source_model FROM v04f_club_needs WHERE membership_id=? ORDER BY id DESC", (member_id,)).fetchall())
        offerings = [dict(r) for r in conn.execute(
            """SELECT id,title,description,resource_type AS offering_type,industry_direction AS industry_tags,
                      region,status,'v06_market_resources' AS source_model
               FROM v06_market_resources WHERE direction='supply'
                 AND (owner_person_id=? OR organization_id=? OR (legacy_source_type='qbay_membership' AND legacy_source_id=?))
               ORDER BY id DESC""", (member_data.get("person_id"), member_data.get("organization_id"), str(member_id)),
        ).fetchall()]
        offerings.extend(dict(r) for r in conn.execute("SELECT *, 'v04f_club_offerings' AS source_model FROM v04f_club_offerings WHERE membership_id=? ORDER BY id DESC", (member_id,)).fetchall())
        matches = [dict(r) for r in conn.execute(
            """
            SELECT cm.* FROM v04f_club_matches cm
            JOIN v04f_club_needs n ON n.id=cm.need_id
            JOIN v04f_club_offerings o ON o.id=cm.offering_id
            WHERE n.membership_id=? OR o.membership_id=?
            ORDER BY cm.match_score DESC
            """,
            (member_id, member_id),
        ).fetchall()]
        try:
            event_history = [dict(r) for r in conn.execute(
                """
                SELECT ep.event_no,e.name,e.event_date,r.registration_no,r.status AS registration_status,
                       p.attendance_status,p.check_in_time,p.feedback,p.follow_up_note
                FROM v05c_club_event_registrations r
                JOIN v05c_club_event_profiles ep ON ep.id=r.club_event_id
                JOIN events e ON e.id=ep.event_id
                LEFT JOIN v05c_club_event_participation p ON p.registration_id=r.id
                WHERE r.membership_id=?
                ORDER BY COALESCE(p.check_in_time,e.event_date,r.registered_at) DESC
                LIMIT 20
                """,
                (member_id,),
            ).fetchall()]
            activity = conn.execute("SELECT * FROM v05c_member_activity_scores WHERE membership_id=?", (member_id,)).fetchone()
            member_data["event_history"] = event_history
            member_data["activity"] = dict(activity) if activity else {}
        except sqlite3.Error:
            member_data["event_history"] = []
            member_data["activity"] = {}
    
    link_info = get_link_info(member_id)
    candidates = get_person_candidates(member_id)
    audit = list_link_audit(member_id)
    
    user_link_info = get_user_link_info(member_id)
    user_link_audit = list_user_link_audit(member_id)
    try:
        lifecycle_history = ClubMembershipService().history(member_id)
    except sqlite3.Error:
        lifecycle_history = []
    
    return templates.TemplateResponse(request, "v04f_club.html", {
        "mode": "member_detail",
        "member": member_data,
        "lifecycle_history": lifecycle_history,
        "needs": needs,
        "offerings": offerings,
        "matches": matches,
        "link_info": link_info,
        "candidates": candidates,
        "link_audit": audit,
        "user_link_info": user_link_info,
        "user_link_audit": user_link_audit,
        "message": message,
        "error": error,
    })


@router.post("/club/members/{member_id}/person-link")
def bind_member_person(member_id: int, person_id: int = Form(...), reason: str = Form("")):
    actor = "admin"
    try:
        bind_person(member_id, person_id, reason, actor)
        return RedirectResponse(f"/club/members/{member_id}?message=关联人物档案成功", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/club/members/{member_id}?error={str(e)}", status_code=303)


@router.post("/club/members/{member_id}/person-unlink")
def unbind_member_person(member_id: int, reason: str = Form("")):
    actor = "admin"
    try:
        unbind_person(member_id, reason, actor)
        return RedirectResponse(f"/club/members/{member_id}?message=已解除人物档案关联", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/club/members/{member_id}?error={str(e)}", status_code=303)


@router.post("/club/members/{member_id}/user-link")
def bind_member_user(member_id: int, user_id: int = Form(...), reason: str = Form(""), request: Request = None):
    from app.security import current_user, permissions_for
    
    user = current_user(request) if request else None
    
    if user and "manage_club" not in permissions_for(user):
        return RedirectResponse(f"/club/members/{member_id}?error=需要俱乐部管理权限", status_code=303)
    
    actor = user.get("username") if user else "admin"
    try:
        bind_user(member_id, user_id, reason, actor)
        return RedirectResponse(f"/club/members/{member_id}?message=关联登录账号成功", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/club/members/{member_id}?error={str(e)}", status_code=303)


@router.post("/club/members/{member_id}/user-unlink")
def unbind_member_user(member_id: int, reason: str = Form(""), request: Request = None):
    from app.security import current_user, permissions_for
    
    user = current_user(request) if request else None
    
    if user and "manage_club" not in permissions_for(user):
        return RedirectResponse(f"/club/members/{member_id}?error=需要俱乐部管理权限", status_code=303)
    
    actor = user.get("username") if user else "admin"
    try:
        unbind_user(member_id, reason, actor)
        return RedirectResponse(f"/club/members/{member_id}?message=已解除登录账号关联", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/club/members/{member_id}?error={str(e)}", status_code=303)


@router.post("/club/members/{member_id}/needs")
def add_need(request: Request, member_id: int, title: str = Form(...), description: str = Form(""), need_type: str = Form(""), industry_tags: str = Form(""), region: str = Form(""), urgency: str = Form("normal")):
    user = current_user(request) or {}
    if not user:
        raise HTTPException(401, "请先登录")
    try:
        ClubResourceMatchingService().create_member_resource(
            member_id, direction="demand", actor_user_id=int(user["id"]),
            fields={"title": title, "description": description, "resource_type": need_type or "其他",
                    "industry_direction": industry_tags, "tags": industry_tags, "region": region,
                    "summary": description, "status": "pending_review"},
        )
    except ClubOperationError as exc:
        return RedirectResponse(f"/club/members/{member_id}?error={exc.message}", status_code=303)
    return RedirectResponse(f"/club/members/{member_id}?message=需求草稿已提交审核", status_code=303)


@router.post("/club/members/{member_id}/offerings")
def add_offering(request: Request, member_id: int, title: str = Form(...), description: str = Form(""), offering_type: str = Form(""), industry_tags: str = Form(""), region: str = Form(""), availability: str = Form("available")):
    user = current_user(request) or {}
    if not user:
        raise HTTPException(401, "请先登录")
    try:
        ClubResourceMatchingService().create_member_resource(
            member_id, direction="supply", actor_user_id=int(user["id"]),
            fields={"title": title, "description": description, "resource_type": offering_type or "其他",
                    "industry_direction": industry_tags, "tags": industry_tags, "region": region,
                    "summary": description, "status": "pending_review"},
        )
    except ClubOperationError as exc:
        return RedirectResponse(f"/club/members/{member_id}?error={exc.message}", status_code=303)
    return RedirectResponse(f"/club/members/{member_id}?message=供给草稿已提交审核", status_code=303)


@router.post("/club/matches/generate")
def generate_matches(request: Request):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    created = ClubResourceMatchingService().generate_matches()
    return RedirectResponse(f"/club/matches?created={len(created)}", status_code=303)


@router.get("/club/matches", response_class=HTMLResponse)
def matches_page(request: Request, status: str = "", created: int = 0, tab: str = "recommendations"):
    user_id = request.scope.get("user", {}).get("id")
    with db_connection() as conn:
        if tab == "demands":
            rows = conn.execute(
                """SELECT * FROM v06_market_resources WHERE direction='demand' ORDER BY id DESC LIMIT 50""",
            ).fetchall()
            return templates.TemplateResponse(request, "club_matches.html", {"tab": "demands", "demands": [dict(r) for r in rows]})
        elif tab == "supplies":
            rows = conn.execute(
                """SELECT * FROM v06_market_resources WHERE direction='supply' ORDER BY id DESC LIMIT 50""",
            ).fetchall()
            return templates.TemplateResponse(request, "club_matches.html", {"tab": "supplies", "supplies": [dict(r) for r in rows]})
        elif tab == "my" and user_id:
            demands = conn.execute(
                """SELECT * FROM v06_market_resources WHERE owner_person_id IN (SELECT person_id FROM v04f_club_memberships WHERE user_id=?) AND direction='demand' ORDER BY id DESC LIMIT 20""",
                (user_id,),
            ).fetchall()
            supplies = conn.execute(
                """SELECT * FROM v06_market_resources WHERE owner_person_id IN (SELECT person_id FROM v04f_club_memberships WHERE user_id=?) AND direction='supply' ORDER BY id DESC LIMIT 20""",
                (user_id,),
            ).fetchall()
            return templates.TemplateResponse(request, "club_matches.html", {"tab": "my", "my_demands": [dict(r) for r in demands], "my_supplies": [dict(r) for r in supplies]})
        where, params = ("WHERE m.status=?", [status]) if status else ("", [])
        try:
            rows = conn.execute(
                f"""SELECT m.*,m.demand_resource_id AS need_id,m.supply_resource_id AS offering_id,
                           m.score AS match_score,'受控规则' AS match_grade,l.id AS action_id
                    FROM p4_resource_match_candidates m
                    LEFT JOIN p4_club_lead_candidates l ON l.source_type='resource_match' AND l.source_id=CAST(m.id AS TEXT)
                    {where} ORDER BY m.score DESC,m.id DESC LIMIT 100""", params,
            ).fetchall()
            for row in rows:
                row_dict = dict(row)
                for resource_id, field_name in [(row["demand_resource_id"], "need_title"), (row["supply_resource_id"], "offering_title")]:
                    if resource_id:
                        title_row = conn.execute("SELECT title FROM v06_market_resources WHERE id=?", (resource_id,)).fetchone()
                        if title_row:
                            row_dict[field_name] = title_row[0]
        except sqlite3.Error:
            rows = []
        return templates.TemplateResponse(request, "club_matches.html", {"tab": "recommendations", "matches": [dict(r) for r in rows], "created": created, "status": status})


@router.post("/club/matches/{match_id}/status")
def update_match(request: Request, match_id: int, status: str = Form(...), note: str = Form(""), actor: str = Form("manual")):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    user = current_user(request) or {}
    try:
        ClubResourceMatchingService().review_match(
            match_id, decision=status, note=note, actor=current_username(request),
            actor_user_id=int(user["id"]) if user.get("id") else None,
        )
    except ClubOperationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return RedirectResponse("/club/matches", status_code=303)


@router.post("/club/matches/{match_id}/action")
def match_to_action(request: Request, match_id: int, owner: str = Form("")):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    user = current_user(request) or {}
    try:
        ClubResourceMatchingService().create_lead_from_match(
            match_id, actor=current_username(request), actor_user_id=int(user["id"]) if user.get("id") else None,
        )
    except ClubOperationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return RedirectResponse("/club/matches", status_code=303)

@router.get("/club/resources", response_class=HTMLResponse)
def club_resources_page(request: Request, status: str = ""):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    with db_connection() as conn:
        where, params = ("WHERE status=?", [status]) if status else ("", [])
        rows = [dict(row) for row in conn.execute(
            f"SELECT * FROM v06_market_resources {where} ORDER BY id DESC LIMIT 200", params,
        ).fetchall()]
    return templates.TemplateResponse(request, "v04f_club.html", {"mode": "resources", "resources": rows, "status": status})


@router.post("/club/resources/{resource_id}/review")
def review_club_resource(request: Request, resource_id: int, decision: str = Form(...), note: str = Form("")):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    user = current_user(request) or {}
    try:
        ClubResourceMatchingService().review_resource(
            resource_id, decision=decision, note=note, actor=current_username(request),
            actor_user_id=int(user["id"]) if user.get("id") else None,
        )
    except ClubOperationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return RedirectResponse("/club/resources", status_code=303)


@router.post("/club/events/{club_event_id}/relationship-candidates")
def generate_event_relationships_page(request: Request, club_event_id: int):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    ClubResourceMatchingService().generate_event_relationship_candidates(club_event_id)
    return RedirectResponse("/club/relationship-candidates", status_code=303)


@router.get("/club/relationship-candidates", response_class=HTMLResponse)
def relationship_candidates_page(request: Request):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    with db_connection() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM p4_event_relationship_candidates ORDER BY id DESC LIMIT 200").fetchall()]
    return templates.TemplateResponse(request, "v04f_club.html", {"mode": "relationship_candidates", "relationship_candidates": rows})


@router.post("/club/relationship-candidates/{candidate_id}/review")
def review_relationship_candidate_page(request: Request, candidate_id: int, decision: str = Form(...), note: str = Form("")):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    ClubResourceMatchingService().review_event_relationship(candidate_id, decision=decision, note=note, actor=current_username(request))
    return RedirectResponse("/club/relationship-candidates", status_code=303)


@router.get("/club/leads", response_class=HTMLResponse)
def club_leads_page(request: Request):
    if not can(request, "manage_club"):
        raise HTTPException(403, "需要俱乐部运营权限")
    with db_connection() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM p4_club_lead_candidates ORDER BY id DESC LIMIT 200").fetchall()]
    return templates.TemplateResponse(request, "v04f_club.html", {"mode": "club_leads", "club_leads": rows})

@router.get("/v04f/health")
def health():
    path = default_db_path()
    with db_connection(path) as conn:
        tables = conn.execute("SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04f_%'").fetchone()["c"]
    return {"ok": tables >= 8, "version": "0.4F", "database": str(path), "v04f_table_count": tables}
