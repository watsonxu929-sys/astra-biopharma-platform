from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.security import (
    current_username,
    current_user,
    hash_password,
    record_audit,
    session_secret,
    validate_password,
    verify_password,
)
from app.v04c_review import db_connection, default_db_path
from app.v04f_operations import _next_no as v04f_next_no
from app.services.membership_access_service import get_membership_summary, get_user_memberships
from app.v05b_member_import import MAX_UPLOAD_BYTES, SUPPORTED_IMAGES, _bind_asset, _insert_asset
from app.v05c_club_events import ensure_schema as ensure_v05c_schema
from scripts.migrate_v05d import SCHEMA_SQL as V05D_SCHEMA_SQL

router = APIRouter(tags=["v0.5D Q-BAY member portal"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

MEMBER_COOKIE = "qbay_member_session"
SESSION_MAX_AGE = 12 * 60 * 60


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _get_accessible_memberships_for_user(user_id: int, conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return get_user_memberships(user_id)

def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = ensure_v05c_schema(db_path, allow_migration=allow_migration)
    if not allow_migration:
        return path
    with db_connection(path) as conn:
        conn.executescript(V05D_SCHEMA_SQL)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(v04f_club_memberships)").fetchall()}
        for column, ddl in {
            "is_org_contact": "INTEGER NOT NULL DEFAULT 0",
            "is_org_admin_candidate": "INTEGER NOT NULL DEFAULT 0",
            "org_admin_status": "TEXT",
        }.items():
            if column not in cols:
                conn.execute(f"ALTER TABLE v04f_club_memberships ADD COLUMN {column} {ddl}")
    return path


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    return _b64(hmac.new(session_secret(), body.encode("ascii"), hashlib.sha256).digest())


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_token(account: sqlite3.Row) -> tuple[str, str]:
    csrf = secrets.token_urlsafe(24)
    payload = {
        "aid": int(account["id"]),
        "mid": int(account["membership_id"]),
        "sv": int(account["session_version"]),
        "csrf": csrf,
        "exp": int(datetime.now().timestamp()) + SESSION_MAX_AGE,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}", csrf


def _decode_session(token: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        if not hmac.compare_digest(_sign(body), signature):
            return None
        payload = json.loads(_unb64(body))
        if int(payload.get("exp") or 0) < int(datetime.now().timestamp()):
            return None
        return payload
    except Exception:
        return None


def _member_context(request: Request, *, required: bool = True) -> dict[str, Any] | None:
    payload = _decode_session(request.cookies.get(MEMBER_COOKIE, ""))
    if not payload:
        if required:
            raise HTTPException(status_code=303, headers={"Location": "/member/login"})
        return None
    ensure_schema()
    with db_connection() as conn:
        account = conn.execute("SELECT * FROM v05d_member_accounts WHERE id=?", (int(payload["aid"]),)).fetchone()
        if not account or account["status"] != "active" or int(account["session_version"]) != int(payload["sv"]):
            if required:
                raise HTTPException(status_code=303, headers={"Location": "/member/login"})
            return None
        
        primary_membership_id = int(account["membership_id"])
        
        user_id = conn.execute("SELECT user_id FROM v04f_club_memberships WHERE id=?", (primary_membership_id,)).fetchone()
        user_id = user_id[0] if user_id else None
        
        user_info = None
        if user_id:
            user_info = conn.execute("SELECT id,username,display_name,role,status FROM v05a_users WHERE id=?", (user_id,)).fetchone()
        
        if user_id:
            accessible = _get_accessible_memberships_for_user(user_id, conn)
        else:
            member = get_membership_summary(primary_membership_id)
            accessible = [member] if member else []
        
        if not accessible:
            return {
                "account": dict(account),
                "member": None,
                "user": dict(user_info) if user_info else {},
                "accessible_memberships": [],
                "current_membership_id": None,
                "can_switch": False,
                "csrf_token": payload["csrf"],
            }
        
        stored_mid = payload.get("mid")
        cookie_mid = None
        
        cookie_header = request.headers.get("cookie", "")
        for cookie in cookie_header.split(";"):
            if cookie.strip().startswith("qbay_member_mid="):
                try:
                    cookie_mid = int(cookie.strip().split("=")[1])
                except (ValueError, IndexError):
                    pass
                break
        
        current_id = None
        
        if cookie_mid and any(m["id"] == cookie_mid for m in accessible):
            current_id = cookie_mid
        elif stored_mid and any(m["id"] == int(stored_mid) for m in accessible):
            current_id = int(stored_mid)
        else:
            current_id = accessible[0]["id"]
        
        member = _load_member(conn, current_id)
        if not member or member["status"] not in {"active", "pending"}:
            if len(accessible) > 1:
                for m in accessible:
                    if m["status"] in {"active", "pending"}:
                        current_id = m["id"]
                        member = _load_member(conn, current_id)
                        break
        
        return {
            "account": dict(account),
            "member": member,
            "user": dict(user_info) if user_info else {},
            "accessible_memberships": accessible,
            "current_membership_id": current_id,
            "can_switch": len(accessible) > 1,
            "csrf_token": payload["csrf"],
        }


def _require_csrf(request: Request, form: Any) -> None:
    ctx = _member_context(request)
    if str(form.get("csrf_token") or "") != ctx["csrf_token"]:
        raise HTTPException(403, "CSRF token invalid")


def _load_member(conn: sqlite3.Connection, membership_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT m.*,p.name AS person_name,p.external_id AS person_external_id,p.public_role,p.ability_tags,
               o.standard_name AS organization_name,o.external_id AS organization_external_id,
               c.mobile,c.email,c.wechat,c.preferred_contact_method,
               a.id AS avatar_asset_id
        FROM v04f_club_memberships m
        LEFT JOIN people p ON p.id=m.person_id
        LEFT JOIN organizations o ON o.id=m.organization_id
        LEFT JOIN v05b_member_contacts c ON c.membership_id=m.id
        LEFT JOIN v05b_media_assets a ON a.membership_id=m.id AND a.is_active=1
        WHERE m.id=?
        ORDER BY a.id DESC LIMIT 1
        """,
        (membership_id,),
    ).fetchone()
    return dict(row) if row else None


def _next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v05d_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date, updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now_iso()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):04d}"


def _notify(conn: sqlite3.Connection, membership_id: int, category: str, title: str, body: str = "", related_type: str = "", related_id: str = "") -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO v05d_member_notifications(notification_no,membership_id,category,title,body,related_type,related_id,status,created_at)
        VALUES (?,?,?,?,?,?,?,'unread',?)
        """,
        (_next_no(conn, "QBNOT"), membership_id, category, title, body or None, related_type or None, related_id or None, ts),
    )


def _render(request: Request, mode: str, **context: Any) -> HTMLResponse:
    ctx = _member_context(request, required=False)
    return templates.TemplateResponse(request, "v05d_member_portal.html", {"mode": mode, "portal": ctx, **context})


@router.get("/member/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return _render(request, "login", error=error)


@router.post("/member/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    ensure_schema()
    with db_connection() as conn:
        account = conn.execute("SELECT * FROM v05d_member_accounts WHERE lower(username)=lower(?)", (username.strip(),)).fetchone()
        if not account or account["status"] not in {"active", "locked"}:
            return RedirectResponse("/member/login?error=invalid", status_code=303)
        if account["locked_until"]:
            try:
                if datetime.fromisoformat(account["locked_until"]) > datetime.now():
                    return RedirectResponse("/member/login?error=locked", status_code=303)
            except ValueError:
                pass
        member = conn.execute("SELECT status FROM v04f_club_memberships WHERE id=?", (account["membership_id"],)).fetchone()
        if not member or member["status"] not in {"active", "pending"}:
            return RedirectResponse("/member/login?error=member_inactive", status_code=303)
        if not account["password_hash"] or not verify_password(password, account["password_hash"]):
            failures = int(account["failed_login_count"] or 0) + 1
            locked_until = None
            status = account["status"]
            if failures >= 5:
                locked_until = (datetime.now() + timedelta(minutes=15)).replace(microsecond=0).isoformat()
                failures = 0
                status = "locked"
            conn.execute("UPDATE v05d_member_accounts SET failed_login_count=?,locked_until=?,status=?,updated_at=? WHERE id=?", (failures, locked_until, status, now_iso(), account["id"]))
            return RedirectResponse("/member/login?error=invalid", status_code=303)
        conn.execute("UPDATE v05d_member_accounts SET failed_login_count=0,locked_until=NULL,status='active',last_login_at=?,updated_at=? WHERE id=?", (now_iso(), now_iso(), account["id"]))
        refreshed = conn.execute("SELECT * FROM v05d_member_accounts WHERE id=?", (account["id"],)).fetchone()
    token, _csrf = _session_token(refreshed)
    response = RedirectResponse("/member", status_code=303)
    response.set_cookie(MEMBER_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax", path="/")
    response.set_cookie("qbay_member_mid", str(account["membership_id"]), max_age=SESSION_MAX_AGE, path="/member")
    return response


@router.post("/member/switch-membership")
async def switch_membership(request: Request):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    
    try:
        new_mid = int(form.get("membership_id"))
    except (ValueError, TypeError):
        return RedirectResponse("/member?error=无效的会员身份", status_code=303)
    
    accessible = ctx.get("accessible_memberships", [])
    if not any(m["id"] == new_mid for m in accessible):
        return RedirectResponse("/member?error=您无权访问该会员身份", status_code=303)
    
    response = RedirectResponse("/member", status_code=303)
    response.set_cookie("qbay_member_mid", str(new_mid), max_age=SESSION_MAX_AGE, path="/member")
    return response


@router.post("/member/logout")
async def logout(request: Request):
    payload = _decode_session(request.cookies.get(MEMBER_COOKIE, ""))
    if payload:
        try:
            with db_connection() as conn:
                conn.execute(
                    "UPDATE v05d_member_accounts SET session_version=session_version+1,updated_at=? WHERE id=?",
                    (now_iso(), int(payload["aid"])),
                )
        except Exception:
            pass
    response = RedirectResponse("/member/login", status_code=303)
    response.delete_cookie(MEMBER_COOKIE, path="/")
    response.delete_cookie("qbay_member_mid", path="/member")
    return response


@router.get("/member/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request, message: str = "", error: str = ""):
    return _render(request, "forgot_password", message=message, error=error)


@router.post("/member/forgot-password")
def forgot_password(request: Request, username: str = Form(...), verification_note: str = Form("")):
    ensure_schema()
    ts = now_iso()
    with db_connection() as conn:
        account = conn.execute("SELECT * FROM v05d_member_accounts WHERE lower(username)=lower(?)", (username.strip(),)).fetchone()
        conn.execute(
            """
            INSERT INTO v05d_password_reset_requests(
              request_no,account_id,username,verification_note,status,submitted_at,created_at,updated_at
            ) VALUES (?,?,?,?, 'submitted',?,?,?)
            """,
            (
                _next_no(conn, "QBPR"),
                int(account["id"]) if account else None,
                username.strip()[:120],
                verification_note.strip()[:500] or None,
                ts,
                ts,
                ts,
            ),
        )
        if account:
            _notify(conn, int(account["membership_id"]), "account", "密码重置申请已提交", "运营人员将核验后通过人工渠道反馈。")
    return RedirectResponse("/member/forgot-password?message=submitted", status_code=303)


@router.get("/member/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = Query("")):
    ensure_schema()
    row = None
    if token:
        with db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM v05d_password_reset_requests WHERE token_hash=? AND status='token_created'",
                (_token_hash(token),),
            ).fetchone()
    if not row or not row["expires_at"] or datetime.fromisoformat(row["expires_at"]) < datetime.now():
        return _render(request, "reset_invalid")
    return _render(request, "reset_password", token=token)


@router.post("/member/reset-password")
def reset_password(request: Request, token: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    ensure_schema()
    if password != confirm_password or validate_password(password):
        return RedirectResponse(f"/member/reset-password?token={quote(token, safe='')}&error=password", status_code=303)
    token_hash = _token_hash(token)
    ts = now_iso()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM v05d_password_reset_requests WHERE token_hash=? AND status='token_created'",
            (token_hash,),
        ).fetchone()
        if not row or not row["account_id"] or not row["expires_at"] or datetime.fromisoformat(row["expires_at"]) < datetime.now():
            return RedirectResponse("/member/login?error=token", status_code=303)
        conn.execute(
            "UPDATE v05d_member_accounts SET password_hash=?,status='active',failed_login_count=0,locked_until=NULL,session_version=session_version+1,updated_at=? WHERE id=?",
            (hash_password(password), ts, int(row["account_id"])),
        )
        conn.execute("UPDATE v05d_password_reset_requests SET status='used',used_at=?,updated_at=? WHERE id=?", (ts, ts, int(row["id"])))
        account = conn.execute("SELECT * FROM v05d_member_accounts WHERE id=?", (int(row["account_id"]),)).fetchone()
        if account:
            _notify(conn, int(account["membership_id"]), "account", "密码重置申请已提交", "运营人员将核验后通过人工渠道反馈。")
    return RedirectResponse("/member/login?message=password_reset", status_code=303)


@router.get("/member/activate", response_class=HTMLResponse)
def activate_page(request: Request, token: str = Query("")):
    ensure_schema()
    token_hash = _token_hash(token)
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT t.*,a.username,m.member_no,p.name AS person_name,o.standard_name AS organization_name
            FROM v05d_activation_tokens t
            JOIN v05d_member_accounts a ON a.id=t.account_id
            JOIN v04f_club_memberships m ON m.id=a.membership_id
            LEFT JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            WHERE t.token_hash=? AND t.status='active'
            """,
            (token_hash,),
        ).fetchone()
    if not row:
        return _render(request, "activate_invalid")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now():
        return _render(request, "activate_invalid")
    return _render(request, "activate", activation=dict(row), token=token)


@router.post("/member/activate")
def activate_account(
    request: Request,
    token: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    agree: str | None = Form(None),
):
    ensure_schema()
    if not agree:
        return RedirectResponse(f"/member/activate?token={token}&error=agree", status_code=303)
    if password != confirm_password:
        return RedirectResponse(f"/member/activate?token={token}&error=password", status_code=303)
    errors = validate_password(password)
    if errors:
        return RedirectResponse(f"/member/activate?token={token}&error=password_rule", status_code=303)
    ts = now_iso()
    token_hash = _token_hash(token)
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM v05d_activation_tokens WHERE token_hash=? AND status='active'", (token_hash,)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now():
            return RedirectResponse("/member/login?error=token", status_code=303)
        if conn.execute("SELECT 1 FROM v05a_users WHERE lower(username)=lower(?)", (username.strip(),)).fetchone():
            return RedirectResponse(f"/member/activate?token={token}&error=username", status_code=303)
        other = conn.execute("SELECT id FROM v05d_member_accounts WHERE lower(username)=lower(?) AND id<>?", (username.strip(), row["account_id"])).fetchone()
        if other:
            return RedirectResponse(f"/member/activate?token={token}&error=username", status_code=303)
        conn.execute(
            """
            UPDATE v05d_member_accounts
            SET username=?,password_hash=?,status='active',must_change_password=0,activated_at=?,session_version=session_version+1,updated_at=?
            WHERE id=? AND status IN ('invited','active')
            """,
            (username.strip(), hash_password(password), ts, ts, row["account_id"]),
        )
        conn.execute("UPDATE v05d_activation_tokens SET status='used',used_at=? WHERE id=?", (ts, row["id"]))
        account = conn.execute("SELECT * FROM v05d_member_accounts WHERE id=?", (row["account_id"],)).fetchone()
        _notify(conn, int(account["membership_id"]), "account", "密码重置申请已提交", "运营人员将核验后通过人工渠道反馈。")
    session, _csrf = _session_token(account)
    response = RedirectResponse("/member", status_code=303)
    response.set_cookie(MEMBER_COOKIE, session, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax", path="/")
    return response


@router.get("/member/request-membership-link", response_class=HTMLResponse)
def request_membership_link_page(request: Request):
    ctx = _member_context(request)
    mid = int(ctx["member"]["id"])
    with db_connection() as conn:
        user_id = conn.execute("SELECT user_id FROM v04f_club_memberships WHERE id=?", (mid,)).fetchone()[0]
        if user_id:
            return RedirectResponse("/member?error=会员身份已关联账号", status_code=303)
        existing_req = conn.execute("SELECT 1 FROM membership_user_link_requests WHERE membership_id=? AND status='pending'", (mid,)).fetchone()
        if existing_req:
            return RedirectResponse("/member?error=已有待审核的关联申请", status_code=303)
    return _render(request, "request_link")


@router.post("/member/request-membership-link")
async def submit_membership_link_request(request: Request):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    mid = int(ctx["member"]["id"])
    member_no = str(form.get("member_no") or "").strip()
    invite_code = str(form.get("invite_code") or "").strip()
    reason = str(form.get("reason") or "").strip()
    
    if not member_no and not invite_code:
        return RedirectResponse("/member/request-membership-link?error=请输入会员编号或邀请码", status_code=303)
    
    with db_connection() as conn:
        user_id = conn.execute("SELECT user_id FROM v04f_club_memberships WHERE id=?", (mid,)).fetchone()[0]
        if user_id:
            return RedirectResponse("/member?error=会员身份已关联账号", status_code=303)

        existing_req = conn.execute("SELECT 1 FROM membership_user_link_requests WHERE membership_id=? AND status='pending'", (mid,)).fetchone()
        if existing_req:
            return RedirectResponse("/member?error=已有待审核的关联申请", status_code=303)

        target_member = None
        if member_no:
            target_member = conn.execute("SELECT id FROM v04f_club_memberships WHERE member_no=?", (member_no,)).fetchone()
        elif invite_code:
            target_member = conn.execute("SELECT id FROM v04f_club_memberships WHERE invite_code=?", (invite_code,)).fetchone()

        if not target_member:
            return RedirectResponse("/member/request-membership-link?error=未找到对应的会员身份", status_code=303)

        target_id = int(target_member["id"])
        if target_id != mid:
            return RedirectResponse("/member/request-membership-link?error=只能申请关联当前登录的会员身份", status_code=303)

        ts = now_iso()
        conn.execute(
            """
            INSERT INTO membership_user_link_requests(membership_id,user_id,member_no,invite_code,reason,status,created_at,updated_at)
            VALUES (?,?,?,?,?,'pending',?,?)
            """,
            (mid, None, member_no, invite_code, reason, ts, ts)
        )

    return RedirectResponse("/member?message=关联申请已提交，请等待管理员审核", status_code=303)


@router.get("/member", response_class=HTMLResponse)
def member_home(request: Request):
    return RedirectResponse("/club", status_code=303)


@router.get("/member/profile", response_class=HTMLResponse)
def profile_page(request: Request, message: str = "", error: str = ""):
    ctx = _member_context(request)
    mid = int(ctx["member"]["id"])
    with db_connection() as conn:
        pending = [dict(r) for r in conn.execute("SELECT * FROM v05d_profile_change_requests WHERE membership_id=? ORDER BY id DESC LIMIT 50", (mid,)).fetchall()]
        pref = _privacy(conn, mid)
    return _render(request, "profile", pending=pending, privacy=pref, message=message, error=error)


@router.post("/member/profile")
async def submit_profile(request: Request):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    member = ctx["member"]
    mid = int(member["id"])
    fields = {
        "display_name": member["person_name"],
        "organization_name": member.get("organization_name") or "",
        "title": member.get("public_role") or member.get("member_role") or "",
        "city": "",
        "expertise_tags": member.get("expertise_tags") or "",
        "cooperation_preferences": member.get("cooperation_preferences") or "",
        "mobile": member.get("mobile") or "",
        "email": member.get("email") or "",
        "wechat": member.get("wechat") or "",
        "preferred_contact_method": member.get("preferred_contact_method") or "",
    }
    auto_fields = {"mobile", "email", "wechat", "preferred_contact_method"}
    created = applied = 0
    ts = now_iso()
    with db_connection() as conn:
        for field, old in fields.items():
            proposed = str(form.get(field) or "").strip()
            if proposed == (old or ""):
                continue
            existing = conn.execute("SELECT 1 FROM v05d_profile_change_requests WHERE membership_id=? AND field_name=? AND status='pending'", (mid, field)).fetchone()
            if existing:
                continue
            status = "applied" if field in auto_fields else "pending"
            request_no = _next_no(conn, "QBPCR")
            conn.execute(
                """
                INSERT INTO v05d_profile_change_requests(
                  request_no,membership_id,field_name,current_value,proposed_value,evidence_note,status,submitted_at,applied_at,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (request_no, mid, field, old or None, proposed or None, str(form.get("evidence_note") or "")[:500], status, ts, ts if status == "applied" else None, ts, ts),
            )
            created += 1
            if field in auto_fields:
                _apply_profile_field(conn, member, field, proposed)
                applied += 1
                _notify(conn, mid, "profile", "联系方式已更新", f"{field} 已按规则自动更新。", "profile_change", request_no)
        _update_privacy(conn, mid, form)
    return RedirectResponse(f"/member/profile?message=已提交{created}项修改，其中{applied}项联系方式已自动更新", status_code=303)


@router.post("/member/profile/changes/{change_id}/withdraw")
async def withdraw_profile_change(request: Request, change_id: int):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    with db_connection() as conn:
        conn.execute("UPDATE v05d_profile_change_requests SET status='withdrawn',updated_at=? WHERE id=? AND membership_id=? AND status='pending'", (now_iso(), change_id, ctx["member"]["id"]))
    return RedirectResponse("/member/profile", status_code=303)


@router.post("/member/avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    filename = Path(file.filename or "avatar").name
    if Path(filename).suffix.lower() not in SUPPORTED_IMAGES:
        return RedirectResponse("/member/profile?error=头像仅支持 JPG、PNG、WEBP", status_code=303)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return RedirectResponse("/member/profile?error=头像文件过大", status_code=303)
    member = ctx["member"]
    with db_connection() as conn:
        asset_id = _insert_asset(
            conn,
            data=data,
            original_filename=filename,
            source_type="member_upload",
            membership_id=int(member["id"]),
            person_id=int(member["person_id"]),
            actor=f"member:{ctx['account']['username']}",
        )
        _bind_asset(conn, asset_id, int(member["id"]), int(member["person_id"]), f"member:{ctx['account']['username']}")
    return RedirectResponse("/member/profile?message=头像已更新", status_code=303)


@router.get("/member/needs", response_class=HTMLResponse)
def my_needs(request: Request):
    return _content_page(request, "need")


@router.get("/member/resources", response_class=HTMLResponse)
def my_resources(request: Request):
    return _content_page(request, "offering")


def _content_page(request: Request, content_type: str):
    ctx = _member_context(request)
    mid = int(ctx["member"]["id"])
    with db_connection() as conn:
        drafts = [dict(r) for r in conn.execute("SELECT * FROM v05d_member_content_requests WHERE membership_id=? AND content_type=? ORDER BY id DESC", (mid, content_type)).fetchall()]
        direction = "demand" if content_type == "need" else "supply"
        official = [dict(r) for r in conn.execute(
            """SELECT * FROM v06_market_resources WHERE direction=? AND
               (owner_person_id=? OR organization_id=? OR (legacy_source_type='qbay_membership' AND legacy_source_id=?))
               ORDER BY id DESC""",
            (direction, ctx["member"].get("person_id"), ctx["member"].get("organization_id"), str(mid)),
        ).fetchall()]
    return _render(request, "content", content_type=content_type, drafts=drafts, official=official)


@router.post("/member/content")
async def submit_content(request: Request):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    content_type = str(form.get("content_type") or "")
    if content_type not in {"need", "offering"}:
        raise HTTPException(400, "invalid content type")
    ts = now_iso()
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO v05d_member_content_requests(
              request_no,membership_id,content_type,title,description,category,industry_tags,region,
              urgency_or_availability,valid_until,cooperation_preference,allow_matching,related_candidate,
              status,submitted_at,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'submitted',?,?,?)
            """,
            (
                _next_no(conn, "QBCR"),
                ctx["member"]["id"],
                content_type,
                str(form.get("title") or "").strip(),
                str(form.get("description") or "").strip(),
                str(form.get("category") or "").strip(),
                str(form.get("industry_tags") or "").strip(),
                str(form.get("region") or "").strip(),
                str(form.get("urgency_or_availability") or "").strip(),
                str(form.get("valid_until") or "").strip(),
                str(form.get("cooperation_preference") or "").strip(),
                1 if form.get("allow_matching") else 0,
                str(form.get("related_candidate") or "").strip(),
                ts,
                ts,
                ts,
            ),
        )
    return RedirectResponse("/member/needs" if content_type == "need" else "/member/resources", status_code=303)


@router.get("/member/events", response_class=HTMLResponse)
def member_events(request: Request):
    ctx = _member_context(request)
    mid = int(ctx["member"]["id"])
    with db_connection() as conn:
        events = [dict(r) for r in conn.execute(
            """
            SELECT p.*,e.name,e.event_date,e.fact_summary,r.id AS registration_id,r.registration_no,r.status AS registration_status,r.checked_in_at
            FROM v05c_club_event_profiles p
            JOIN events e ON e.id=p.event_id
            LEFT JOIN v05c_club_event_registrations r ON r.club_event_id=p.id AND r.membership_id=?
            WHERE p.status IN ('published','registration_open','registration_closed','ongoing','completed','cancelled')
              AND p.visibility IN ('public','controlled','internal')
            ORDER BY COALESCE(e.event_date,p.updated_at) DESC
            """,
            (mid,),
        ).fetchall()]
    return _render(request, "events", events=events)


@router.post("/member/events/{club_event_id}/register")
async def member_register_event(request: Request, club_event_id: int):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    member = ctx["member"]
    ts = now_iso()
    with db_connection() as conn:
        event = conn.execute("SELECT * FROM v05c_club_event_profiles WHERE id=?", (club_event_id,)).fetchone()
        if not event or event["registration_status"] != "open":
            return RedirectResponse("/member/events?error=closed", status_code=303)
        if conn.execute("SELECT 1 FROM v05c_club_event_registrations WHERE club_event_id=? AND membership_id=? AND status<>'cancelled'", (club_event_id, member["id"])).fetchone():
            return RedirectResponse("/member/events?error=duplicate", status_code=303)
        count = conn.execute("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE club_event_id=? AND status IN ('submitted','approved')", (club_event_id,)).fetchone()[0]
        status = "waitlisted" if int(event["capacity"] or 0) and count >= int(event["capacity"]) else "submitted"
        conn.execute(
            """
            INSERT INTO v05c_club_event_registrations(
              registration_no,club_event_id,membership_id,applicant_name,organization_name,title,mobile,email,
              registration_source,status,review_note,registered_at,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?, 'member_portal',?,?,?, ?,?)
            """,
            (
                _next_no(conn, "QBR"),
                club_event_id,
                member["id"],
                member["person_name"],
                member.get("organization_name"),
                member.get("public_role") or member.get("member_role"),
                member.get("mobile"),
                member.get("email"),
                status,
                str(form.get("note") or "")[:500],
                ts,
                ts,
                ts,
            ),
        )
        _notify(conn, int(member["id"]), "event", "活动报名已提交", "你已通过会员门户提交活动报名。", "event", str(club_event_id))
    return RedirectResponse("/member/events", status_code=303)


@router.post("/member/events/{registration_id}/cancel")
async def member_cancel_event(request: Request, registration_id: int):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    with db_connection() as conn:
        conn.execute(
            "UPDATE v05c_club_event_registrations SET status='cancelled',review_note=COALESCE(review_note,'') || ' / member cancelled',updated_at=? WHERE id=? AND membership_id=? AND status IN ('submitted','approved','waitlisted')",
            (now_iso(), registration_id, ctx["member"]["id"]),
        )
    return RedirectResponse("/member/events", status_code=303)


@router.get("/member/matches", response_class=HTMLResponse)
def member_matches(request: Request):
    ctx = _member_context(request)
    mid = int(ctx["member"]["id"])
    with db_connection() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT cm.*,d.title AS need_title,s.title AS offering_title
            FROM p4_resource_match_candidates cm
            JOIN v06_market_resources d ON d.id=cm.demand_resource_id
            JOIN v06_market_resources s ON s.id=cm.supply_resource_id
            WHERE d.owner_person_id=? OR d.organization_id=? OR (d.legacy_source_type='qbay_membership' AND d.legacy_source_id=?)
               OR s.owner_person_id=? OR s.organization_id=? OR (s.legacy_source_type='qbay_membership' AND s.legacy_source_id=?)
            ORDER BY cm.created_at DESC
            """,
            (ctx["member"].get("person_id"), ctx["member"].get("organization_id"), str(mid),
             ctx["member"].get("person_id"), ctx["member"].get("organization_id"), str(mid)),
        ).fetchall()]
        feedback = [dict(r) for r in conn.execute("SELECT * FROM v05d_member_match_feedback WHERE membership_id=? ORDER BY created_at DESC", (mid,)).fetchall()]
    return _render(request, "matches", matches=rows, feedback=feedback)


@router.post("/member/matches/{match_id}/feedback")
async def match_feedback(request: Request, match_id: int):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    mid = int(ctx["member"]["id"])
    feedback = str(form.get("feedback") or "")
    if feedback not in {"interested", "unsure", "not_interested", "already_cooperating", "need_operator_contact", "info_inaccurate"}:
        raise HTTPException(400, "invalid feedback")
    with db_connection() as conn:
        match = conn.execute(
            """
            SELECT cm.*,
              CASE WHEN d.owner_person_id=? OR d.organization_id=? OR (d.legacy_source_type='qbay_membership' AND d.legacy_source_id=?) THEN 1 ELSE 0 END AS owns_demand,
              CASE WHEN s.owner_person_id=? OR s.organization_id=? OR (s.legacy_source_type='qbay_membership' AND s.legacy_source_id=?) THEN 1 ELSE 0 END AS owns_supply
            FROM p4_resource_match_candidates cm
            JOIN v06_market_resources d ON d.id=cm.demand_resource_id
            JOIN v06_market_resources s ON s.id=cm.supply_resource_id
            WHERE cm.id=?
            """,
            (ctx["member"].get("person_id"), ctx["member"].get("organization_id"), str(mid),
             ctx["member"].get("person_id"), ctx["member"].get("organization_id"), str(mid), match_id),
        ).fetchone()
        if not match or not (match["owns_demand"] or match["owns_supply"]):
            raise HTTPException(404, "match not found")
        side = "requester" if match["owns_demand"] else "provider"
        status_after = f"{side}_{feedback}"
        conn.execute(
            """
            INSERT INTO v05d_member_match_feedback(feedback_no,match_id,membership_id,side,feedback,note,status_after,created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (_next_no(conn, "QBMF"), match_id, mid, side, feedback, str(form.get("note") or "")[:500], status_after, now_iso()),
        )
    return RedirectResponse("/member/matches", status_code=303)


@router.get("/member/notifications", response_class=HTMLResponse)
def notifications_page(request: Request):
    ctx = _member_context(request)
    with db_connection() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM v05d_member_notifications WHERE membership_id=? ORDER BY created_at DESC LIMIT 100", (ctx["member"]["id"],)).fetchall()]
    return _render(request, "notifications", notifications=rows)


@router.post("/member/notifications")
async def update_notifications(request: Request, action: str = Form(...), notification_id: int = Form(0), csrf_token: str = Form(...)):
    form = {"csrf_token": csrf_token}
    _require_csrf(request, form)
    ctx = _member_context(request)
    mid = int(ctx["member"]["id"])
    with db_connection() as conn:
        if action == "read_all":
            conn.execute("UPDATE v05d_member_notifications SET status='read',read_at=COALESCE(read_at,?) WHERE membership_id=? AND status='unread'", (now_iso(), mid))
        elif action == "read":
            conn.execute("UPDATE v05d_member_notifications SET status='read',read_at=COALESCE(read_at,?) WHERE id=? AND membership_id=?", (now_iso(), notification_id, mid))
        elif action == "archive":
            conn.execute("UPDATE v05d_member_notifications SET status='archived' WHERE id=? AND membership_id=?", (notification_id, mid))
    return RedirectResponse("/member/notifications", status_code=303)


@router.get("/member/account", response_class=HTMLResponse)
def member_account(request: Request, message: str = "", error: str = ""):
    _member_context(request)
    return _render(request, "account", message=message, error=error)


@router.post("/member/change-password")
async def member_change_password(request: Request):
    form = await request.form()
    _require_csrf(request, form)
    ctx = _member_context(request)
    old = str(form.get("old_password") or "")
    new = str(form.get("new_password") or "")
    if new != str(form.get("confirm_password") or ""):
        return RedirectResponse("/member/account?error=password_mismatch", status_code=303)
    errors = validate_password(new)
    if errors:
        return RedirectResponse("/member/account?error=password_rule", status_code=303)
    with db_connection() as conn:
        account = conn.execute("SELECT * FROM v05d_member_accounts WHERE id=?", (ctx["account"]["id"],)).fetchone()
        if not account or not verify_password(old, account["password_hash"]):
            return RedirectResponse("/member/account?error=old_password", status_code=303)
        conn.execute("UPDATE v05d_member_accounts SET password_hash=?,session_version=session_version+1,updated_at=? WHERE id=?", (hash_password(new), now_iso(), account["id"]))
        _notify(conn, int(account["membership_id"]), "account", "密码重置申请已提交", "运营人员将核验后通过人工渠道反馈。")
    response = RedirectResponse("/member/login?message=password_changed", status_code=303)
    response.delete_cookie(MEMBER_COOKIE, path="/")
    return response


@router.get("/club/member-accounts", response_class=HTMLResponse)
def member_accounts_admin(request: Request, invite_link: str = "", message: str = ""):
    ensure_schema()
    with db_connection() as conn:
        accounts = [dict(r) for r in conn.execute(
            """
            SELECT a.*,m.member_no,p.name AS person_name,o.standard_name AS organization_name
            FROM v05d_member_accounts a
            JOIN v04f_club_memberships m ON m.id=a.membership_id
            LEFT JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            ORDER BY a.updated_at DESC LIMIT 200
            """
        ).fetchall()]
        members = [dict(r) for r in conn.execute(
            """
            SELECT m.id,m.member_no,p.name AS person_name,o.standard_name AS organization_name
            FROM v04f_club_memberships m
            LEFT JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            WHERE m.status IN ('active','pending')
            ORDER BY m.id DESC LIMIT 200
            """
        ).fetchall()]
    return templates.TemplateResponse(request, "v05d_member_admin.html", {"mode": "accounts", "accounts": accounts, "members": members, "invite_link": invite_link, "message": message})


@router.post("/club/members/{member_id}/invite-account")
def invite_member_account(request: Request, member_id: int):
    ensure_schema()
    actor = current_username(request)
    ts = now_iso()
    raw_token = secrets.token_urlsafe(32)
    with db_connection() as conn:
        member = conn.execute("SELECT * FROM v04f_club_memberships WHERE id=? AND status IN ('active','pending')", (member_id,)).fetchone()
        if not member:
            raise HTTPException(400, "只有有效会员可以生成账号邀请")
        account = conn.execute("SELECT * FROM v05d_member_accounts WHERE membership_id=?", (member_id,)).fetchone()
        if not account:
            account_no = _next_no(conn, "QBACC")
            cur = conn.execute(
                "INSERT INTO v05d_member_accounts(account_no,membership_id,username,status,created_at,updated_at) VALUES (?,?,?,'invited',?,?)",
                (account_no, member_id, f"member_{member_id}", ts, ts),
            )
            account_id = cur.lastrowid
        else:
            if account["status"] == "active":
                return RedirectResponse("/club/member-accounts?message=该会员账号已激活", status_code=303)
            account_id = account["id"]
            conn.execute("UPDATE v05d_member_accounts SET status='invited',session_version=session_version+1,updated_at=? WHERE id=?", (ts, account_id))
        conn.execute("UPDATE v05d_activation_tokens SET status='revoked' WHERE account_id=? AND status='active'", (account_id,))
        conn.execute(
            "INSERT INTO v05d_activation_tokens(account_id,token_hash,status,expires_at,created_by,created_at) VALUES (?,?,'active',?,?,?)",
            (account_id, _token_hash(raw_token), (datetime.now() + timedelta(hours=48)).replace(microsecond=0).isoformat(), actor, ts),
        )
        _notify(conn, member_id, "account", "会员账号邀请已生成", "运营人员已生成账号激活链接，请通过人工渠道获取。")
    link = f"/member/activate?token={raw_token}"
    record_audit(action="member_account_invite", actor=getattr(request.state, "current_user", None), method="POST", path=f"/club/members/{member_id}/invite-account", target_type="club_member", target_id=str(member_id), detail={"token": "masked"})
    return RedirectResponse(f"/club/member-accounts?invite_link={quote(link, safe='')}", status_code=303)


@router.post("/club/member-accounts/{account_id}/status")
def update_member_account_status(request: Request, account_id: int, status: str = Form(...)):
    if status not in {"active", "suspended", "deactivated"}:
        raise HTTPException(400, "invalid status")
    with db_connection() as conn:
        conn.execute("UPDATE v05d_member_accounts SET status=?,session_version=session_version+1,deactivated_at=CASE WHEN ?='deactivated' THEN ? ELSE deactivated_at END,updated_at=? WHERE id=?", (status, status, now_iso(), now_iso(), account_id))
    return RedirectResponse("/club/member-accounts", status_code=303)


@router.get("/club/profile-changes", response_class=HTMLResponse)
def profile_changes_admin(request: Request):
    ensure_schema()
    with db_connection() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT c.*,m.member_no,p.name AS person_name
            FROM v05d_profile_change_requests c
            JOIN v04f_club_memberships m ON m.id=c.membership_id
            LEFT JOIN people p ON p.id=m.person_id
            ORDER BY c.id DESC LIMIT 200
            """
        ).fetchall()]
    return templates.TemplateResponse(request, "v05d_member_admin.html", {"mode": "profile_changes", "changes": rows})


@router.post("/club/profile-changes/{change_id}/review")
def review_profile_change(request: Request, change_id: int, decision: str = Form(...), review_note: str = Form("")):
    if decision not in {"approved", "rejected"}:
        raise HTTPException(400, "invalid decision")
    actor = current_username(request)
    ts = now_iso()
    with db_connection() as conn:
        change = conn.execute("SELECT * FROM v05d_profile_change_requests WHERE id=?", (change_id,)).fetchone()
        if not change or change["status"] != "pending":
            return RedirectResponse("/club/profile-changes", status_code=303)
        status = "rejected"
        applied_at = None
        if decision == "approved":
            member = _load_member(conn, int(change["membership_id"]))
            try:
                _apply_profile_field(conn, member, change["field_name"], change["proposed_value"] or "")
                status = "applied"
                applied_at = ts
                _notify(conn, int(change["membership_id"]), "profile", "资料修改已通过", f"{change['field_name']} 已更新。", "profile_change", change["request_no"])
            except sqlite3.Error:
                status = "apply_failed"
        else:
            _notify(conn, int(change["membership_id"]), "profile", "资料修改未通过", review_note or "请根据运营反馈调整后重新提交。", "profile_change", change["request_no"])
        conn.execute("UPDATE v05d_profile_change_requests SET status=?,reviewed_by=?,review_note=?,reviewed_at=?,applied_at=?,updated_at=? WHERE id=?", (status, actor, review_note or None, ts, applied_at, ts, change_id))
    return RedirectResponse("/club/profile-changes", status_code=303)


@router.get("/club/member-content", response_class=HTMLResponse)
def content_admin(request: Request):
    ensure_schema()
    with db_connection() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT c.*,m.member_no,p.name AS person_name
            FROM v05d_member_content_requests c
            JOIN v04f_club_memberships m ON m.id=c.membership_id
            LEFT JOIN people p ON p.id=m.person_id
            ORDER BY c.id DESC LIMIT 200
            """
        ).fetchall()]
    return templates.TemplateResponse(request, "v05d_member_admin.html", {"mode": "content", "items": rows})


@router.post("/club/member-content/{request_id}/review")
def review_content(request: Request, request_id: int, decision: str = Form(...), review_note: str = Form("")):
    if decision not in {"approved", "rejected", "need_more_info"}:
        raise HTTPException(400, "invalid decision")
    actor = current_username(request)
    ts = now_iso()
    with db_connection() as conn:
        source = conn.execute("""SELECT c.*,m.person_id,m.organization_id,m.user_id
            FROM v05d_member_content_requests c JOIN v04f_club_memberships m ON m.id=c.membership_id
            WHERE c.id=?""", (request_id,)).fetchone()
        item = dict(source) if source else None
    if not item or item["status"] not in {"submitted", "need_more_info"}:
        return RedirectResponse("/club/member-content", status_code=303)
    status, official_id = decision, item["official_record_id"]
    if decision == "approved":
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.services.unified_resource_service import UnifiedResourceService
        user = current_user(request) or {}
        actor_user_id = int(user.get("id") or item.get("user_id") or 0)
        if not actor_user_id:
            raise HTTPException(403, "operator account required")
        path = default_db_path()
        engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})
        try:
            with Session(engine) as session:
                resource = UnifiedResourceService(session).create(actor_user_id=actor_user_id, fields={
                    "title": item["title"], "direction": "demand" if item["content_type"] == "need" else "supply",
                    "resource_type": item["category"] or "Q-BAY会员供需", "category": item["category"],
                    "description": item["description"], "owner_person_id": item.get("person_id"),
                    "organization_id": item.get("organization_id"), "region": item["region"],
                    "industry_direction": item["industry_tags"], "cooperation_terms": item["urgency_or_availability"],
                    "legacy_source_type": "qbay_member_content_request", "legacy_source_id": str(request_id),
                    "status": "published", "visibility": "organization",
                })
                official_id = resource.id
        finally:
            engine.dispose()
        status = "published"
    with db_connection() as conn:
        if decision == "approved":
            _notify(conn, int(item["membership_id"]), "resource", "供需内容已发布", f"{item['title']} 已审核通过。", "resource", str(official_id))
        elif decision == "rejected":
            _notify(conn, int(item["membership_id"]), item["content_type"], "供需内容未通过", review_note or "请修改后重新提交。", item["content_type"], item["request_no"])
        conn.execute("UPDATE v05d_member_content_requests SET status=?,official_record_id=?,reviewed_by=?,review_note=?,reviewed_at=?,updated_at=? WHERE id=?", (status, official_id, actor, review_note or None, ts, ts, request_id))
    return RedirectResponse("/club/member-content", status_code=303)


@router.get("/club/announcements", response_class=HTMLResponse)
def announcements_admin(request: Request):
    ensure_schema()
    with db_connection() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM v05d_announcements ORDER BY id DESC LIMIT 100").fetchall()]
    return templates.TemplateResponse(request, "v05d_member_admin.html", {"mode": "announcements", "announcements": rows})


@router.post("/club/announcements/create")
def create_announcement(request: Request, title: str = Form(...), body: str = Form(...), target_type: str = Form("all"), target_value: str = Form("")):
    if target_type not in {"all", "level", "industry", "event", "member"}:
        raise HTTPException(400, "invalid target")
    ts = now_iso()
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO v05d_announcements(announcement_no,title,body,target_type,target_value,status,created_by,created_at,updated_at) VALUES (?,?,?,?,?,'draft',?,?,?)",
            (_next_no(conn, "QBAN"), title.strip(), body.strip(), target_type, target_value.strip() or None, current_username(request), ts, ts),
        )
    return RedirectResponse("/club/announcements", status_code=303)


@router.post("/club/announcements/{announcement_id}/publish")
def publish_announcement(request: Request, announcement_id: int, confirm_publish: str | None = Form(None)):
    if not confirm_publish:
        return RedirectResponse("/club/announcements?message=需要确认发布", status_code=303)
    ts = now_iso()
    with db_connection() as conn:
        ann = conn.execute("SELECT * FROM v05d_announcements WHERE id=?", (announcement_id,)).fetchone()
        if not ann or ann["status"] != "draft":
            return RedirectResponse("/club/announcements", status_code=303)
        members = _announcement_recipients(conn, ann["target_type"], ann["target_value"])
        for mid in members:
            _notify(conn, int(mid), "system", ann["title"], ann["body"], "announcement", ann["announcement_no"])
        conn.execute("UPDATE v05d_announcements SET status='published',recipient_count=?,published_by=?,published_at=?,updated_at=? WHERE id=?", (len(members), current_username(request), ts, ts, announcement_id))
    return RedirectResponse("/club/announcements", status_code=303)


@router.post("/club/announcements/{announcement_id}/revoke")
def revoke_announcement(request: Request, announcement_id: int):
    with db_connection() as conn:
        conn.execute("UPDATE v05d_announcements SET status='revoked',revoked_at=?,updated_at=? WHERE id=? AND status='published'", (now_iso(), now_iso(), announcement_id))
    return RedirectResponse("/club/announcements", status_code=303)


@router.get("/v05d/health")
def health():
    path = default_db_path()
    with db_connection(path) as conn:
        tables = conn.execute("SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v05d_%'").fetchone()["c"]
    return {"ok": tables >= 8, "version": "0.5D", "database": str(path), "v05d_table_count": tables}


def _privacy(conn: sqlite3.Connection, membership_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM v05d_member_privacy_preferences WHERE membership_id=?", (membership_id,)).fetchone()
    if row:
        return dict(row)
    ts = now_iso()
    conn.execute("INSERT INTO v05d_member_privacy_preferences(membership_id,updated_at) VALUES (?,?)", (membership_id, ts))
    return dict(conn.execute("SELECT * FROM v05d_member_privacy_preferences WHERE membership_id=?", (membership_id,)).fetchone())


def _update_privacy(conn: sqlite3.Connection, membership_id: int, form: Any) -> None:
    _privacy(conn, membership_id)
    flags = [
        "show_avatar",
        "show_organization",
        "show_title",
        "show_city",
        "show_expertise",
        "show_offerings",
        "show_needs",
        "allow_matching",
        "allow_event_invites",
        "allow_internal_contact",
        "allow_member_directory",
    ]
    values = {flag: 1 if form.get(flag) else 0 for flag in flags}
    conn.execute(
        f"UPDATE v05d_member_privacy_preferences SET {', '.join(flag + '=?' for flag in flags)}, updated_at=? WHERE membership_id=?",
        [*(values[flag] for flag in flags), now_iso(), membership_id],
    )


def _apply_profile_field(conn: sqlite3.Connection, member: dict[str, Any], field: str, value: str) -> None:
    mid = int(member["id"])
    if field == "display_name":
        conn.execute("UPDATE people SET name=? WHERE id=?", (value, member["person_id"]))
    elif field == "title":
        conn.execute("UPDATE people SET public_role=? WHERE id=?", (value, member["person_id"]))
        conn.execute("UPDATE v04f_club_memberships SET member_role=?,updated_at=? WHERE id=?", (value, now_iso(), mid))
    elif field == "expertise_tags":
        conn.execute("UPDATE v04f_club_memberships SET expertise_tags=?,updated_at=? WHERE id=?", (value, now_iso(), mid))
    elif field == "cooperation_preferences":
        conn.execute("UPDATE v04f_club_memberships SET cooperation_preferences=?,updated_at=? WHERE id=?", (value, now_iso(), mid))
    elif field in {"mobile", "email", "wechat", "preferred_contact_method"}:
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO v05b_member_contacts(membership_id,mobile,email,wechat,preferred_contact_method,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(membership_id) DO UPDATE SET
              mobile=CASE WHEN ?='mobile' THEN excluded.mobile ELSE v05b_member_contacts.mobile END,
              email=CASE WHEN ?='email' THEN excluded.email ELSE v05b_member_contacts.email END,
              wechat=CASE WHEN ?='wechat' THEN excluded.wechat ELSE v05b_member_contacts.wechat END,
              preferred_contact_method=CASE WHEN ?='preferred_contact_method' THEN excluded.preferred_contact_method ELSE v05b_member_contacts.preferred_contact_method END,
              updated_at=excluded.updated_at
            """,
            (
                mid,
                value if field == "mobile" else member.get("mobile"),
                value if field == "email" else member.get("email"),
                value if field == "wechat" else member.get("wechat"),
                value if field == "preferred_contact_method" else member.get("preferred_contact_method"),
                ts,
                ts,
                field,
                field,
                field,
                field,
            ),
        )


def _announcement_recipients(conn: sqlite3.Connection, target_type: str, target_value: str | None) -> list[int]:
    if target_type == "member" and target_value and target_value.isdigit():
        return [int(target_value)]
    if target_type == "level" and target_value:
        rows = conn.execute("SELECT id FROM v04f_club_memberships WHERE status='active' AND member_level=?", (target_value,)).fetchall()
    elif target_type == "industry" and target_value:
        rows = conn.execute("SELECT id FROM v04f_club_memberships WHERE status='active' AND industry_tags LIKE ?", (f"%{target_value}%",)).fetchall()
    elif target_type == "event" and target_value and target_value.isdigit():
        rows = conn.execute("SELECT DISTINCT membership_id AS id FROM v05c_club_event_registrations WHERE club_event_id=? AND membership_id IS NOT NULL", (int(target_value),)).fetchall()
    else:
        rows = conn.execute("SELECT id FROM v04f_club_memberships WHERE status='active'").fetchall()
    return [int(row["id"]) for row in rows]













