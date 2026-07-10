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
from app.security import current_username
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


def ensure_schema(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else default_db_path()
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


def club_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {
        "members": conn.execute("SELECT COUNT(*) AS c FROM v04f_club_memberships").fetchone()["c"],
        "active_members": conn.execute("SELECT COUNT(*) AS c FROM v04f_club_memberships WHERE status='active'").fetchone()["c"],
        "pending_applications": conn.execute("SELECT COUNT(*) AS c FROM v04f_club_applications WHERE status IN ('submitted','under_review','need_more_info')").fetchone()["c"],
        "needs": conn.execute("SELECT COUNT(*) AS c FROM v04f_club_needs WHERE status='active'").fetchone()["c"],
        "offerings": conn.execute("SELECT COUNT(*) AS c FROM v04f_club_offerings WHERE status='active'").fetchone()["c"],
        "candidate_matches": conn.execute("SELECT COUNT(*) AS c FROM v04f_club_matches WHERE status='candidate'").fetchone()["c"],
        "progressing_matches": conn.execute("SELECT COUNT(*) AS c FROM v04f_club_matches WHERE status='progressing'").fetchone()["c"],
        "successful_matches": conn.execute("SELECT COUNT(*) AS c FROM v04f_club_matches WHERE status='successful'").fetchone()["c"],
    }
    try:
        counts.update(
            {
                "recent_events": conn.execute("SELECT COUNT(*) AS c FROM v05c_club_event_profiles WHERE status IN ('published','registration_open','ongoing')").fetchone()["c"],
                "event_registrations": conn.execute("SELECT COUNT(*) AS c FROM v05c_club_event_registrations WHERE status IN ('submitted','approved','waitlisted')").fetchone()["c"],
                "today_checkins": conn.execute("SELECT COUNT(*) AS c FROM v05c_club_event_participation WHERE date(check_in_time)=date('now','localtime')").fetchone()["c"],
                "post_event_followups": conn.execute("SELECT COUNT(*) AS c FROM actions WHERE source_type='v0.5C Q-BAY活动' AND status NOT IN ('已完成','完成','done')").fetchone()["c"],
            }
        )
    except sqlite3.Error:
        counts.update({"recent_events": 0, "event_registrations": 0, "today_checkins": 0, "post_event_followups": 0})
    return counts


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
    owner = owner.strip() or current_username(request)
    with db_connection() as conn:
        sug = conn.execute("SELECT * FROM v04f_lead_suggestions WHERE id=? AND lead_id=?", (suggestion_id, lead_id)).fetchone()
        lead = conn.execute("SELECT * FROM v04f_lead_records WHERE id=?", (lead_id,)).fetchone()
        if not sug or not lead:
            raise HTTPException(404, "建议不存在")
        if sug["converted_action_id"]:
            return RedirectResponse(f"/leads/{lead_id}", status_code=303)
        action_no = _next_no(conn, "ACT")
        cur = conn.execute(
            """
            INSERT INTO actions(external_id, task, target_external_id, completion_standard, owner, priority, status, suggested_deadline, source_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, '未开始', ?, 'v0.4F线索建议', ?)
            """,
            (action_no, sug["title"], lead["subject_id"], sug["basis"], owner, sug["priority"] or "P2", sug["recommended_due"], now()),
        )
        conn.execute("UPDATE v04f_lead_suggestions SET converted_action_id=?, updated_at=? WHERE id=?", (cur.lastrowid, now(), suggestion_id))
    return RedirectResponse(f"/leads/{lead_id}", status_code=303)


@router.get("/club", response_class=HTMLResponse)
def club_home(request: Request):
    ensure_schema()
    with db_connection() as conn:
        counts = club_counts(conn)
    return templates.TemplateResponse(request, "v04f_club.html", {"mode": "home", "counts": counts})


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
def review_application(request: Request, application_id: int, decision: str = Form(...), person_id: int = Form(0), organization_id: int = Form(0), reviewer: str = Form("admin"), note: str = Form("")):
    reviewer = current_username(request)
    if decision not in {"under_review", "need_more_info", "approved", "rejected"}:
        raise HTTPException(400, "无效审核状态")
    with db_connection() as conn:
        app = conn.execute("SELECT * FROM v04f_club_applications WHERE id=?", (application_id,)).fetchone()
        if not app:
            raise HTTPException(404, "申请不存在")
        if decision == "approved":
            if not person_id:
                raise HTTPException(400, "批准时必须选择现有人物")
            existing = conn.execute("SELECT * FROM v04f_club_memberships WHERE person_id=? AND status IN ('pending','active','suspended')", (person_id,)).fetchone()
            if existing:
                raise HTTPException(400, "该人物已有有效会员身份")
            ts = now()
            member_no = _next_no(conn, "QBM")
            conn.execute(
                """
                INSERT INTO v04f_club_memberships(
                    member_no, person_id, organization_id, member_role, member_level, status, joined_at,
                    source, owner, industry_tags, expertise_tags, cooperation_preferences, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'standard', 'active', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (member_no, person_id, organization_id or None, app["title"], ts, app["application_no"], reviewer, app["industry_tags"], app["expertise_tags"], app["cooperation_needs"], ts, ts),
            )
        conn.execute(
            """
            UPDATE v04f_club_applications
            SET status=?, review_note=?, reviewed_at=?, reviewed_by=?, matched_person_id=?, matched_organization_id=?, updated_at=?
            WHERE id=?
            """,
            (decision, note or None, now(), reviewer, person_id or None, organization_id or None, now(), application_id),
        )
    return RedirectResponse(f"/club/admin/applications/{application_id}", status_code=303)


@router.get("/club/members", response_class=HTMLResponse)
def members_page(request: Request, q: str = "", status: str = "", level: str = "", page: int = 1):
    ensure_schema()
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
    return templates.TemplateResponse(request, "v04f_club.html", {"mode": "members", "members": [dict(r) for r in rows], "filters": {"q": q, "status": status, "level": level, "page": page}})


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
        needs = [dict(r) for r in conn.execute("SELECT * FROM v04f_club_needs WHERE membership_id=? ORDER BY id DESC", (member_id,)).fetchall()]
        offerings = [dict(r) for r in conn.execute("SELECT * FROM v04f_club_offerings WHERE membership_id=? ORDER BY id DESC", (member_id,)).fetchall()]
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
    
    return templates.TemplateResponse(request, "v04f_club.html", {
        "mode": "member_detail",
        "member": member_data,
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
def add_need(member_id: int, title: str = Form(...), description: str = Form(""), need_type: str = Form(""), industry_tags: str = Form(""), region: str = Form(""), urgency: str = Form("normal")):
    with db_connection() as conn:
        if not conn.execute("SELECT 1 FROM v04f_club_memberships WHERE id=?", (member_id,)).fetchone():
            raise HTTPException(404, "会员不存在")
        ts = now()
        conn.execute(
            "INSERT INTO v04f_club_needs(need_no, membership_id, title, description, need_type, industry_tags, region, urgency, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_next_no(conn, "QBN"), member_id, title, description, need_type, industry_tags, region, urgency, ts, ts),
        )
    return RedirectResponse(f"/club/members/{member_id}", status_code=303)


@router.post("/club/members/{member_id}/offerings")
def add_offering(member_id: int, title: str = Form(...), description: str = Form(""), offering_type: str = Form(""), industry_tags: str = Form(""), region: str = Form(""), availability: str = Form("available")):
    with db_connection() as conn:
        if not conn.execute("SELECT 1 FROM v04f_club_memberships WHERE id=?", (member_id,)).fetchone():
            raise HTTPException(404, "会员不存在")
        ts = now()
        conn.execute(
            "INSERT INTO v04f_club_offerings(offering_no, membership_id, title, description, offering_type, industry_tags, region, availability, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_next_no(conn, "QBO"), member_id, title, description, offering_type, industry_tags, region, availability, ts, ts),
        )
    return RedirectResponse(f"/club/members/{member_id}", status_code=303)


@router.post("/club/matches/generate")
def generate_matches():
    ensure_schema()
    created = 0
    with db_connection() as conn:
        needs = [dict(r) for r in conn.execute("SELECT * FROM v04f_club_needs WHERE status='active'").fetchall()]
        offers = [dict(r) for r in conn.execute("SELECT * FROM v04f_club_offerings WHERE status='active'").fetchall()]
        for need in needs:
            for offering in offers:
                result = match_need_offering(need, offering)
                if not result:
                    continue
                if conn.execute("SELECT 1 FROM v04f_club_matches WHERE need_id=? AND offering_id=?", (need["id"], offering["id"])).fetchone():
                    continue
                ts = now()
                conn.execute(
                    """
                    INSERT INTO v04f_club_matches(match_no, need_id, offering_id, match_score, match_grade, reasons_json, missing_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (_next_no(conn, "QBMAT"), need["id"], offering["id"], result["score"], result["grade"], _json(result["reasons"]), _json(result["missing"]), ts, ts),
                )
                created += 1
    return RedirectResponse(f"/club/matches?created={created}", status_code=303)


@router.get("/club/matches", response_class=HTMLResponse)
def matches_page(request: Request, status: str = "", created: int = 0):
    with db_connection() as conn:
        if status:
            rows = conn.execute("SELECT * FROM v04f_club_matches WHERE status=? ORDER BY match_score DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM v04f_club_matches ORDER BY match_score DESC LIMIT 100").fetchall()
    return templates.TemplateResponse(request, "v04f_club.html", {"mode": "matches", "matches": [dict(r) for r in rows], "created": created, "status": status})


@router.post("/club/matches/{match_id}/status")
def update_match(request: Request, match_id: int, status: str = Form(...), note: str = Form(""), actor: str = Form("manual")):
    actor = current_username(request)
    if status not in {"candidate", "confirmed", "contacted", "progressing", "successful", "rejected", "expired"}:
        raise HTTPException(400, "无效匹配状态")
    with db_connection() as conn:
        if not conn.execute("SELECT 1 FROM v04f_club_matches WHERE id=?", (match_id,)).fetchone():
            raise HTTPException(404, "匹配不存在")
        conn.execute("UPDATE v04f_club_matches SET status=?, confirmed_by=?, confirmed_at=?, reject_reason=?, updated_at=? WHERE id=?", (status, actor, now(), note or None, now(), match_id))
    return RedirectResponse("/club/matches", status_code=303)


@router.post("/club/matches/{match_id}/action")
def match_to_action(request: Request, match_id: int, owner: str = Form("")):
    owner = owner.strip() or current_username(request)
    with db_connection() as conn:
        match = conn.execute("SELECT * FROM v04f_club_matches WHERE id=?", (match_id,)).fetchone()
        if not match:
            raise HTTPException(404, "匹配不存在")
        if match["action_id"]:
            return RedirectResponse("/club/matches", status_code=303)
        action_no = _next_no(conn, "ACT")
        cur = conn.execute(
            "INSERT INTO actions(external_id, task, completion_standard, owner, priority, status, source_type, created_at) VALUES (?, ?, ?, ?, 'P2', '未开始', 'v0.4F资源匹配', ?)",
            (action_no, f"跟进 Q-BAY 资源匹配 {match['match_no']}", "确认双方意向并记录跟进结果", owner, now()),
        )
        conn.execute("UPDATE v04f_club_matches SET action_id=?, updated_at=? WHERE id=?", (cur.lastrowid, now(), match_id))
    return RedirectResponse("/club/matches", status_code=303)


@router.get("/v04f/health")
def health():
    path = default_db_path()
    with db_connection(path) as conn:
        tables = conn.execute("SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04f_%'").fetchone()["c"]
    return {"ok": tables >= 8, "version": "0.4F", "database": str(path), "v04f_table_count": tables}
