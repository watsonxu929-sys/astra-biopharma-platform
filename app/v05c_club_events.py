from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.v04c_review import db_connection, default_db_path
from app.v05b_member_import import ensure_schema as ensure_v05b_schema
from scripts.migrate_v05c import SCHEMA_SQL as V05C_SCHEMA_SQL

router = APIRouter(tags=["v0.5C Q-BAY events"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

EVENT_STATUSES = {"draft", "published", "registration_open", "registration_closed", "ongoing", "completed", "cancelled"}
REGISTRATION_STATUSES = {"submitted", "approved", "waitlisted", "rejected", "cancelled"}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None) -> Path:
    path = ensure_v05b_schema(db_path)
    with db_connection(path) as conn:
        conn.executescript(V05C_SCHEMA_SQL)
    return path


def _next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v05c_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date,
          updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now_iso()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):04d}"


def _next_event_external_id(conn: sqlite3.Connection) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    stem = f"EVT-{stamp}-"
    rows = conn.execute("SELECT external_id FROM events WHERE external_id LIKE ?", (f"{stem}%",)).fetchall()
    maximum = 0
    for row in rows:
        tail = str(row[0] or "").replace(stem, "", 1)
        if tail.isdigit():
            maximum = max(maximum, int(tail))
    return f"{stem}{maximum + 1:06d}"


def _event_detail(conn: sqlite3.Connection, club_event_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT p.*, e.external_id, e.name, e.event_date, e.fact_summary, e.source_url
        FROM v05c_club_event_profiles p
        JOIN events e ON e.id=p.event_id
        WHERE p.id=?
        """,
        (club_event_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "活动不存在")
    data = dict(row)
    stats = conn.execute(
        """
        SELECT
          COUNT(*) AS registrations,
          SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved,
          SUM(CASE WHEN membership_id IS NOT NULL THEN 1 ELSE 0 END) AS members,
          SUM(CASE WHEN membership_id IS NULL THEN 1 ELSE 0 END) AS external_applicants
        FROM v05c_club_event_registrations
        WHERE club_event_id=?
        """,
        (club_event_id,),
    ).fetchone()
    checked = conn.execute(
        "SELECT COUNT(*) AS c FROM v05c_club_event_participation WHERE club_event_id=? AND attendance_status IN ('checked_in','attended')",
        (club_event_id,),
    ).fetchone()["c"]
    followups = conn.execute(
        "SELECT COUNT(*) AS c FROM actions WHERE source_type='v0.5C Q-BAY活动' AND target_external_id=?",
        (data["event_no"],),
    ).fetchone()["c"]
    data["stats"] = {
        "registrations": stats["registrations"] or 0,
        "approved": stats["approved"] or 0,
        "checked_in": checked or 0,
        "members": stats["members"] or 0,
        "external_applicants": stats["external_applicants"] or 0,
        "followups": followups or 0,
    }
    return data


def _find_membership(conn: sqlite3.Connection, mobile: str = "", email: str = "") -> int | None:
    clauses: list[str] = []
    params: list[Any] = []
    mobile = re.sub(r"\D", "", mobile or "")
    email = (email or "").strip().lower()
    if mobile:
        clauses.append("REPLACE(REPLACE(REPLACE(c.mobile,' ',''),'-',''),'+86','')=?")
        params.append(mobile[-11:])
    if email:
        clauses.append("lower(c.email)=?")
        params.append(email)
    if not clauses:
        return None
    row = conn.execute(
        f"""
        SELECT m.id
        FROM v05b_member_contacts c
        JOIN v04f_club_memberships m ON m.id=c.membership_id
        WHERE ({' OR '.join(clauses)}) AND m.status IN ('pending','active','suspended')
        ORDER BY m.id DESC LIMIT 2
        """,
        params,
    ).fetchall()
    return int(row[0]["id"]) if len(row) == 1 else None


def _recalculate_activity(conn: sqlite3.Connection, membership_id: int) -> dict[str, Any]:
    registered = conn.execute("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE membership_id=?", (membership_id,)).fetchone()[0]
    checked = conn.execute(
        "SELECT COUNT(*) FROM v05c_club_event_participation WHERE membership_id=? AND attendance_status IN ('checked_in','attended')",
        (membership_id,),
    ).fetchone()[0]
    absent = max(0, int(registered or 0) - int(checked or 0))
    needs = conn.execute("SELECT COUNT(*) FROM v04f_club_needs WHERE membership_id=?", (membership_id,)).fetchone()[0]
    offers = conn.execute("SELECT COUNT(*) FROM v04f_club_offerings WHERE membership_id=?", (membership_id,)).fetchone()[0]
    score = min(100, int(registered or 0) * 8 + int(checked or 0) * 18 + int(needs or 0) * 8 + int(offers or 0) * 8 - absent * 5)
    if score >= 80:
        level = "高度活跃"
    elif score >= 55:
        level = "活跃"
    elif score >= 30:
        level = "一般"
    elif score >= 10:
        level = "待激活"
    else:
        level = "沉默"
    latest = conn.execute(
        "SELECT MAX(check_in_time) FROM v05c_club_event_participation WHERE membership_id=?",
        (membership_id,),
    ).fetchone()[0]
    details = {"registered": registered or 0, "checked_in": checked or 0, "absent": absent, "needs": needs or 0, "offerings": offers or 0}
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO v05c_member_activity_scores(
          membership_id,score,level,details_json,latest_activity_at,risk_reminder,calculated_at,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(membership_id) DO UPDATE SET
          score=excluded.score,level=excluded.level,details_json=excluded.details_json,
          latest_activity_at=excluded.latest_activity_at,risk_reminder=excluded.risk_reminder,
          calculated_at=excluded.calculated_at,updated_at=excluded.updated_at
        """,
        (membership_id, score, level, json.dumps(details, ensure_ascii=False), latest, "连续缺席需人工跟进" if absent >= 2 else None, ts, ts, ts),
    )
    return {"score": score, "level": level, "details": details, "latest_activity_at": latest}


def _render(request: Request, mode: str, **context: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, "v05c_club_events.html", {"mode": mode, **context})


@router.get("/club/events", response_class=HTMLResponse)
def events_page(request: Request, status: str = ""):
    ensure_schema()
    params: list[Any] = []
    where = "1=1"
    if status:
        where = "p.status=?"
        params.append(status)
    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT p.*, e.name, e.event_date
            FROM v05c_club_event_profiles p
            JOIN events e ON e.id=p.event_id
            WHERE {where}
            ORDER BY COALESCE(e.event_date,p.updated_at) DESC, p.id DESC
            LIMIT 100
            """,
            params,
        ).fetchall()
    return _render(request, "events", events=[dict(row) for row in rows], status=status)


@router.post("/club/events/create")
def create_event(
    request: Request,
    name: str = Form(...),
    event_type: str = Form("club"),
    event_date: str = Form(""),
    venue: str = Form(""),
    online_link: str = Form(""),
    capacity: int = Form(0),
    registration_deadline: str = Form(""),
    organizer: str = Form("Q-BAY"),
    owner: str = Form(""),
    visibility: str = Form("internal"),
    member_only: str | None = Form(None),
    description: str = Form(""),
):
    ensure_schema()
    if visibility not in {"public", "controlled", "internal"}:
        raise HTTPException(400, "无效可见性")
    ts = now_iso()
    actor = current_username(request)
    with db_connection() as conn:
        event_external_id = _next_event_external_id(conn)
        event_no = _next_no(conn, "QBE")
        cur = conn.execute(
            """
            INSERT INTO events(
              external_id,event_date,name,event_type,fact_summary,visibility,verification_status,
              created_at,source_type,manually_confirmed,is_active,subject_manually_confirmed
            )
            VALUES (?,?,?,?,?,'internal','已确认',?,'v0.5C Q-BAY活动',1,1,1)
            """,
            (event_external_id, event_date or None, name.strip(), event_type, description or None, ts),
        )
        profile = conn.execute(
            """
            INSERT INTO v05c_club_event_profiles(
              event_id,event_no,event_type,registration_status,capacity,registration_deadline,venue,online_link,
              organizer,owner,visibility,member_only,status,description,created_at,updated_at
            ) VALUES (?,?,?,'closed',?,?,?,?,?,?,?,?, 'draft',?,?,?)
            """,
            (
                cur.lastrowid,
                event_no,
                event_type,
                max(0, int(capacity or 0)),
                registration_deadline or None,
                venue or None,
                online_link or None,
                organizer or None,
                owner or actor,
                visibility,
                1 if member_only else 0,
                description or None,
                ts,
                ts,
            ),
        )
    return RedirectResponse(f"/club/events/{profile.lastrowid}", status_code=303)


@router.get("/club/events/{club_event_id}", response_class=HTMLResponse)
def event_detail(request: Request, club_event_id: int, message: str = Query(""), error: str = Query("")):
    ensure_schema()
    with db_connection() as conn:
        event = _event_detail(conn, club_event_id)
        registrations = [dict(row) for row in conn.execute(
            "SELECT * FROM v05c_club_event_registrations WHERE club_event_id=? ORDER BY registered_at DESC LIMIT 50",
            (club_event_id,),
        ).fetchall()]
        participation = [dict(row) for row in conn.execute(
            "SELECT * FROM v05c_club_event_participation WHERE club_event_id=? ORDER BY check_in_time DESC, id DESC LIMIT 50",
            (club_event_id,),
        ).fetchall()]
    return _render(request, "event_detail", event=event, registrations=registrations, participation=participation, message=message, error=error)


@router.post("/club/events/{club_event_id}/status")
def change_event_status(club_event_id: int, action: str = Form(...)):
    ensure_schema()
    mapping = {
        "publish": ("published", "closed"),
        "open": ("registration_open", "open"),
        "close": ("registration_closed", "closed"),
        "start": ("ongoing", "closed"),
        "complete": ("completed", "closed"),
        "cancel": ("cancelled", "closed"),
    }
    if action not in mapping:
        raise HTTPException(400, "无效活动操作")
    status, reg_status = mapping[action]
    with db_connection() as conn:
        if not conn.execute("SELECT 1 FROM v05c_club_event_profiles WHERE id=?", (club_event_id,)).fetchone():
            raise HTTPException(404, "活动不存在")
        conn.execute(
            "UPDATE v05c_club_event_profiles SET status=?,registration_status=?,updated_at=? WHERE id=?",
            (status, reg_status, now_iso(), club_event_id),
        )
    return RedirectResponse(f"/club/events/{club_event_id}", status_code=303)


@router.post("/club/events/{club_event_id}/copy")
def copy_event(request: Request, club_event_id: int):
    ensure_schema()
    actor = current_username(request)
    ts = now_iso()
    with db_connection() as conn:
        original = _event_detail(conn, club_event_id)
        event_external_id = _next_event_external_id(conn)
        event_no = _next_no(conn, "QBE")
        cur = conn.execute(
            """
            INSERT INTO events(
              external_id,event_date,name,event_type,fact_summary,visibility,verification_status,
              created_at,source_type,manually_confirmed,is_active,subject_manually_confirmed
            )
            VALUES (?,?,?,?,?,'internal','待确认',?,'v0.5C Q-BAY活动复制',1,1,1)
            """,
            (event_external_id, None, f"{original['name']}（复制）", original["event_type"], original.get("description") or original.get("fact_summary"), ts),
        )
        new_profile = conn.execute(
            """
            INSERT INTO v05c_club_event_profiles(
              event_id,event_no,event_type,registration_status,capacity,venue,online_link,organizer,owner,
              visibility,member_only,status,description,created_at,updated_at
            ) VALUES (?,?,?,'closed',?,?,?,?,?,?,?,'draft',?,?,?)
            """,
            (
                cur.lastrowid,
                event_no,
                original["event_type"],
                original["capacity"],
                original.get("venue"),
                original.get("online_link"),
                original.get("organizer"),
                actor,
                original.get("visibility") or "internal",
                int(original.get("member_only") or 0),
                original.get("description") or original.get("fact_summary"),
                ts,
                ts,
            ),
        )
    return RedirectResponse(f"/club/events/{new_profile.lastrowid}", status_code=303)


@router.get("/club/events/{club_event_id}/register", response_class=HTMLResponse)
def public_register_page(request: Request, club_event_id: int, submitted: str = "", error: str = ""):
    ensure_schema()
    with db_connection() as conn:
        event = _event_detail(conn, club_event_id)
    if event["visibility"] == "internal":
        raise HTTPException(404, "活动不存在或未开放")
    return _render(request, "public_register", event=event, submitted=submitted, error=error)


@router.post("/club/events/{club_event_id}/register")
def submit_registration(
    request: Request,
    club_event_id: int,
    applicant_name: str = Form(...),
    organization_name: str = Form(""),
    title: str = Form(""),
    mobile: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
):
    ensure_schema()
    if website.strip():
        return RedirectResponse(f"/club/events/{club_event_id}/register?error=提交失败，请稍后重试", status_code=303)
    if not mobile.strip() and not email.strip():
        return RedirectResponse(f"/club/events/{club_event_id}/register?error=手机或邮箱至少填写一项", status_code=303)
    ts = now_iso()
    with db_connection() as conn:
        event = _event_detail(conn, club_event_id)
        if event["visibility"] == "internal" or event["registration_status"] != "open":
            return RedirectResponse(f"/club/events/{club_event_id}/register?error=活动报名未开放", status_code=303)
        membership_id = _find_membership(conn, mobile, email)
        reg_no = _next_no(conn, "QBR")
        try:
            conn.execute(
                """
                INSERT INTO v05c_club_event_registrations(
                  registration_no,club_event_id,membership_id,applicant_name,organization_name,title,mobile,email,
                  registration_source,status,registered_at,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?, 'public','submitted',?,?,?)
                """,
                (
                    reg_no,
                    club_event_id,
                    membership_id,
                    applicant_name.strip(),
                    organization_name.strip() or None,
                    title.strip() or None,
                    re.sub(r"\D", "", mobile)[-11:] if mobile else None,
                    email.strip().lower() or None,
                    ts,
                    ts,
                    ts,
                ),
            )
        except sqlite3.IntegrityError:
            return RedirectResponse(f"/club/events/{club_event_id}/register?error=该活动已有相同联系方式报名记录", status_code=303)
    return RedirectResponse(f"/club/events/{club_event_id}/register?submitted={reg_no}", status_code=303)


@router.get("/club/events/{club_event_id}/registrations", response_class=HTMLResponse)
def registrations_page(request: Request, club_event_id: int, status: str = ""):
    ensure_schema()
    where = "club_event_id=?"
    params: list[Any] = [club_event_id]
    if status:
        where += " AND status=?"
        params.append(status)
    with db_connection() as conn:
        event = _event_detail(conn, club_event_id)
        rows = [dict(row) for row in conn.execute(
            f"SELECT * FROM v05c_club_event_registrations WHERE {where} ORDER BY registered_at DESC",
            params,
        ).fetchall()]
    return _render(request, "registrations", event=event, registrations=rows, status=status)


@router.get("/club/registrations", response_class=HTMLResponse)
def registrations_all(request: Request):
    ensure_schema()
    with db_connection() as conn:
        rows = [dict(row) for row in conn.execute(
            """
            SELECT r.*, p.event_no, e.name AS event_name
            FROM v05c_club_event_registrations r
            JOIN v05c_club_event_profiles p ON p.id=r.club_event_id
            JOIN events e ON e.id=p.event_id
            ORDER BY r.registered_at DESC LIMIT 200
            """
        ).fetchall()]
    return _render(request, "registrations_all", registrations=rows)


@router.post("/club/events/{club_event_id}/registrations/{registration_id}/review")
def review_registration(club_event_id: int, registration_id: int, status: str = Form(...), review_note: str = Form("")):
    ensure_schema()
    if status not in REGISTRATION_STATUSES:
        raise HTTPException(400, "无效报名状态")
    ts = now_iso()
    with db_connection() as conn:
        registration = conn.execute(
            "SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=?",
            (registration_id, club_event_id),
        ).fetchone()
        if not registration:
            raise HTTPException(404, "报名不存在")
        conn.execute(
            "UPDATE v05c_club_event_registrations SET status=?,review_note=?,reviewed_at=?,updated_at=? WHERE id=?",
            (status, review_note or None, ts, ts, registration_id),
        )
        if status == "approved":
            conn.execute(
                """
                INSERT OR IGNORE INTO v05c_club_event_participation(
                  club_event_id,registration_id,membership_id,attendance_status,created_at,updated_at
                ) VALUES (?,?,?,'registered',?,?)
                """,
                (club_event_id, registration["id"], registration["membership_id"], ts, ts),
            )
    return RedirectResponse(f"/club/events/{club_event_id}/registrations", status_code=303)


@router.post("/club/events/{club_event_id}/checkin")
def check_in(club_event_id: int, identifier: str = Form(...), method: str = Form("manual")):
    ensure_schema()
    ident = identifier.strip()
    ts = now_iso()
    with db_connection() as conn:
        registration = conn.execute(
            """
            SELECT * FROM v05c_club_event_registrations
            WHERE club_event_id=? AND (registration_no=? OR CAST(membership_id AS TEXT)=? OR applicant_name=?)
            ORDER BY status='approved' DESC, id DESC LIMIT 1
            """,
            (club_event_id, ident, ident, ident),
        ).fetchone()
        if not registration:
            raise HTTPException(404, "未找到可签到报名")
        conn.execute(
            "UPDATE v05c_club_event_registrations SET checked_in_at=?,updated_at=? WHERE id=?",
            (ts, ts, registration["id"]),
        )
        conn.execute(
            """
            INSERT INTO v05c_club_event_participation(
              club_event_id,registration_id,membership_id,attendance_status,check_in_method,check_in_time,created_at,updated_at
            ) VALUES (?,?,?,'checked_in',?,?,?,?)
            ON CONFLICT(club_event_id,registration_id) DO UPDATE SET
              attendance_status='checked_in',check_in_method=excluded.check_in_method,
              check_in_time=excluded.check_in_time,updated_at=excluded.updated_at
            """,
            (club_event_id, registration["id"], registration["membership_id"], method, ts, ts, ts),
        )
        if registration["membership_id"]:
            _recalculate_activity(conn, int(registration["membership_id"]))
    return RedirectResponse(f"/club/events/{club_event_id}", status_code=303)


@router.post("/club/events/{club_event_id}/registrations/bulk-checkin")
def bulk_check_in(club_event_id: int, registration_ids: list[int] = Form(...)):
    ensure_schema()
    ts = now_iso()
    with db_connection() as conn:
        for registration_id in registration_ids:
            registration = conn.execute(
                "SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=?",
                (registration_id, club_event_id),
            ).fetchone()
            if not registration:
                continue
            conn.execute("UPDATE v05c_club_event_registrations SET checked_in_at=?,updated_at=? WHERE id=?", (ts, ts, registration_id))
            conn.execute(
                """
                INSERT INTO v05c_club_event_participation(
                  club_event_id,registration_id,membership_id,attendance_status,check_in_method,check_in_time,created_at,updated_at
                ) VALUES (?,?,?,'checked_in','bulk',?,?,?)
                ON CONFLICT(club_event_id,registration_id) DO UPDATE SET
                  attendance_status='checked_in',check_in_method='bulk',check_in_time=excluded.check_in_time,updated_at=excluded.updated_at
                """,
                (club_event_id, registration_id, registration["membership_id"], ts, ts, ts),
            )
            if registration["membership_id"]:
                _recalculate_activity(conn, int(registration["membership_id"]))
    return RedirectResponse(f"/club/events/{club_event_id}/registrations", status_code=303)


@router.post("/club/events/{club_event_id}/registrations/{registration_id}/feedback")
def save_feedback(
    club_event_id: int,
    registration_id: int,
    attendance_status: str = Form("attended"),
    satisfaction_score: int = Form(0),
    feedback: str = Form(""),
    contribution_note: str = Form(""),
    follow_up_note: str = Form(""),
):
    ensure_schema()
    if attendance_status not in {"registered", "checked_in", "attended", "absent", "left_early"}:
        raise HTTPException(400, "无效出席状态")
    ts = now_iso()
    with db_connection() as conn:
        registration = conn.execute("SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=?", (registration_id, club_event_id)).fetchone()
        if not registration:
            raise HTTPException(404, "报名不存在")
        conn.execute(
            """
            INSERT INTO v05c_club_event_participation(
              club_event_id,registration_id,membership_id,attendance_status,contribution_note,follow_up_note,
              satisfaction_score,feedback,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(club_event_id,registration_id) DO UPDATE SET
              attendance_status=excluded.attendance_status,contribution_note=excluded.contribution_note,
              follow_up_note=excluded.follow_up_note,satisfaction_score=excluded.satisfaction_score,
              feedback=excluded.feedback,updated_at=excluded.updated_at
            """,
            (club_event_id, registration_id, registration["membership_id"], attendance_status, contribution_note or None, follow_up_note or None, int(satisfaction_score or 0) or None, feedback or None, ts, ts),
        )
        if registration["membership_id"]:
            _recalculate_activity(conn, int(registration["membership_id"]))
    return RedirectResponse(f"/club/events/{club_event_id}", status_code=303)


@router.post("/club/events/{club_event_id}/followup-action")
def create_followup_action(
    request: Request,
    club_event_id: int,
    registration_ids: list[int] = Form(...),
    task: str = Form(""),
    owner: str = Form(""),
):
    ensure_schema()
    actor = current_username(request)
    created = 0
    ts = now_iso()
    with db_connection() as conn:
        event = _event_detail(conn, club_event_id)
        for registration_id in registration_ids:
            registration = conn.execute(
                "SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=?",
                (registration_id, club_event_id),
            ).fetchone()
            if not registration:
                continue
            action_no = _next_no(conn, "ACT")
            conn.execute(
                """
                INSERT INTO actions(
                  external_id,task,target_external_id,completion_standard,owner,priority,status,source_type,source_text,
                  created_at,manually_confirmed,is_active,subject_manually_confirmed
                )
                VALUES (?,?,?,?,?,'P2','未开始','v0.5C Q-BAY活动',?,?,1,1,1)
                """,
                (
                    action_no,
                    task or f"跟进活动报名人：{registration['applicant_name']}",
                    event["event_no"],
                    f"记录 {event['name']} 会后沟通结果",
                    owner or actor,
                    f"{event['event_no']} / {registration['registration_no']} / {registration['applicant_name']}",
                    ts,
                ),
            )
            created += 1
    return RedirectResponse(f"/club/events/{club_event_id}?message=已创建{created}条会后跟进行动", status_code=303)


@router.get("/club/events/{club_event_id}/registrations.csv")
def registrations_csv(club_event_id: int):
    ensure_schema()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["registration_no", "name", "organization", "title", "status", "registered_at"])
    with db_connection() as conn:
        for row in conn.execute(
            "SELECT registration_no,applicant_name,organization_name,title,status,registered_at FROM v05c_club_event_registrations WHERE club_event_id=? ORDER BY registered_at DESC",
            (club_event_id,),
        ):
            writer.writerow([row["registration_no"], row["applicant_name"], row["organization_name"], row["title"], row["status"], row["registered_at"]])
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8")


@router.get("/v05c/health")
def health():
    path = default_db_path()
    with db_connection(path) as conn:
        tables = conn.execute("SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v05c_%'").fetchone()["c"]
    return {"ok": tables >= 5, "version": "0.5C", "database": str(path), "v05c_table_count": tables}
