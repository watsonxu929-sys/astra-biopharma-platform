from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import (
    ROLE_LABELS,
    admin_reset_password,
    authenticate_user,
    can,
    change_password,
    clear_session_cookie,
    create_user,
    current_user,
    current_username,
    ensure_security_schema,
    get_user_by_id,
    list_users,
    record_audit,
    safe_next,
    set_session_cookie,
    update_user_admin,
    user_count,
)
from app.v04c_review import db_connection

router = APIRouter(tags=["v0.5A 登录、权限与审计"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def render(request: Request, mode: str, **context: Any):
    return templates.TemplateResponse(
        request=request,
        name="v05a_security.html",
        context={"mode": mode, "roles": ROLE_LABELS, **context},
    )


def _require_user(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    return user


def _require_admin(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    if not can(request, "manage_users"):
        raise HTTPException(403, "仅管理员可以执行此操作")
    return user


@router.get("/setup/admin", response_class=HTMLResponse)
def setup_admin_page(request: Request, next: str = Query("/")):
    ensure_security_schema()
    if user_count() > 0:
        return RedirectResponse("/account/login", status_code=303)
    return render(request, "setup", error="", next=safe_next(next))


@router.post("/setup/admin", response_class=HTMLResponse)
def setup_admin_submit(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    next: str = Form("/"),
):
    ensure_security_schema()
    if user_count() > 0:
        return RedirectResponse("/account/login", status_code=303)
    if password != confirm_password:
        return render(request, "setup", error="两次输入的密码不一致", next=safe_next(next), values={"username": username, "display_name": display_name})
    try:
        user = create_user(username, display_name, password, "admin", created_by="first-run")
    except ValueError as exc:
        return render(request, "setup", error=str(exc), next=safe_next(next), values={"username": username, "display_name": display_name})
    response = RedirectResponse(safe_next(next), status_code=303)
    set_session_cookie(response, user)
    record_audit(
        action="setup_admin",
        actor=user,
        method="POST",
        path="/setup/admin",
        result="success",
        status_code=303,
        ip_address=request.client.host if request.client else "",
    )
    return response


@router.get("/account/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = Query("/"), message: str = Query("")):
    if current_user(request):
        return RedirectResponse(safe_next(next), status_code=303)
    return render(request, "login", error="", next=safe_next(next), message=message)


@router.post("/account/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    user, error = authenticate_user(username, password)
    if not user:
        record_audit(
            action="login_failed",
            actor=None,
            method="POST",
            path="/account/login",
            result="failed",
            status_code=401,
            ip_address=request.client.host if request.client else "",
            detail={"username": username.strip()[:40]},
        )
        return render(request, "login", error=error, next=safe_next(next), username=username)
    response = RedirectResponse("/account/change-password?required=1" if user.get("must_change_password") else safe_next(next), status_code=303)
    set_session_cookie(response, user)
    record_audit(
        action="login_success",
        actor=user,
        method="POST",
        path="/account/login",
        result="success",
        status_code=303,
        ip_address=request.client.host if request.client else "",
    )
    return response


@router.post("/account/logout")
def logout(request: Request):
    user = current_user(request)
    response = RedirectResponse("/account/login?message=已安全退出", status_code=303)
    clear_session_cookie(response)
    record_audit(
        action="logout",
        actor=user,
        method="POST",
        path="/account/logout",
        result="success",
        status_code=303,
        ip_address=request.client.host if request.client else "",
    )
    return response


@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request, message: str = Query("")):
    user = _require_user(request)
    return render(request, "account", user=user, message=message)


@router.get("/account/change-password", response_class=HTMLResponse)
def change_password_page(request: Request, required: int = Query(0)):
    user = _require_user(request)
    return render(request, "change_password", user=user, error="", required=bool(required))


@router.post("/account/change-password", response_class=HTMLResponse)
def change_password_submit(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    user = _require_user(request)
    if new_password != confirm_password:
        return render(request, "change_password", user=user, error="两次输入的新密码不一致", required=bool(user.get("must_change_password")))
    try:
        change_password(int(user["id"]), old_password, new_password)
    except ValueError as exc:
        return render(request, "change_password", user=user, error=str(exc), required=bool(user.get("must_change_password")))
    refreshed = get_user_by_id(int(user["id"]))
    response = RedirectResponse("/account?message=密码已更新，其他旧会话已失效", status_code=303)
    if refreshed:
        set_session_cookie(response, refreshed)
    record_audit(
        action="change_password",
        actor=user,
        method="POST",
        path="/account/change-password",
        result="success",
        status_code=303,
        ip_address=request.client.host if request.client else "",
    )
    return response


@router.get("/account/forbidden", response_class=HTMLResponse)
def forbidden_page(request: Request, path: str = Query("")):
    return render(request, "forbidden", blocked_path=path)


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, message: str = Query(""), error: str = Query("")):
    _require_admin(request)
    return render(request, "users", users=list_users(), message=message, error=error)


@router.post("/admin/users")
def admin_create_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    role: str = Form("viewer"),
    temporary_password: str = Form(...),
):
    actor = _require_admin(request)
    try:
        created = create_user(
            username,
            display_name,
            temporary_password,
            role,
            created_by=current_username(request),
            must_change_password=True,
        )
    except ValueError as exc:
        return RedirectResponse(f"/admin/users?error={str(exc)}", status_code=303)
    record_audit(
        action="create_user",
        actor=actor,
        method="POST",
        path="/admin/users",
        target_type="user",
        target_id=str(created["id"]),
        detail={"username": created["username"], "role": created["role"]},
        status_code=303,
        ip_address=request.client.host if request.client else "",
    )
    return RedirectResponse(f"/admin/users?message=已创建用户 {created['username']}", status_code=303)


@router.get("/admin/users/{user_id}", response_class=HTMLResponse)
def admin_user_detail(request: Request, user_id: int, message: str = Query(""), error: str = Query("")):
    _require_admin(request)
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return render(request, "user_detail", target_user=safe_user, message=message, error=error)


@router.post("/admin/users/{user_id}/update")
def admin_user_update(
    request: Request,
    user_id: int,
    display_name: str = Form(...),
    role: str = Form(...),
    status: str = Form(...),
):
    actor = _require_admin(request)
    try:
        update_user_admin(
            user_id,
            role=role,
            status=status,
            display_name=display_name,
            actor_user_id=int(actor["id"]),
        )
    except ValueError as exc:
        return RedirectResponse(f"/admin/users/{user_id}?error={str(exc)}", status_code=303)
    record_audit(
        action="update_user",
        actor=actor,
        method="POST",
        path=f"/admin/users/{user_id}/update",
        target_type="user",
        target_id=str(user_id),
        detail={"role": role, "status": status},
        status_code=303,
        ip_address=request.client.host if request.client else "",
    )
    return RedirectResponse(f"/admin/users/{user_id}?message=用户资料已更新", status_code=303)


@router.post("/admin/users/{user_id}/reset-password")
def admin_user_reset_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    actor = _require_admin(request)
    if new_password != confirm_password:
        return RedirectResponse(f"/admin/users/{user_id}?error=两次输入的密码不一致", status_code=303)
    try:
        admin_reset_password(user_id, new_password)
    except ValueError as exc:
        return RedirectResponse(f"/admin/users/{user_id}?error={str(exc)}", status_code=303)
    record_audit(
        action="reset_user_password",
        actor=actor,
        method="POST",
        path=f"/admin/users/{user_id}/reset-password",
        target_type="user",
        target_id=str(user_id),
        detail={"must_change_password": True},
        status_code=303,
        ip_address=request.client.host if request.client else "",
    )
    return RedirectResponse(f"/admin/users/{user_id}?message=临时密码已重置，用户下次登录必须修改密码", status_code=303)


@router.get("/admin/audit", response_class=HTMLResponse)
def audit_page(
    request: Request,
    q: str = Query(""),
    actor: str = Query(""),
    result: str = Query(""),
    page: int = Query(1, ge=1),
):
    _require_admin(request)
    ensure_security_schema()
    clauses = ["1=1"]
    params: list[Any] = []
    if q.strip():
        token = f"%{q.strip()}%"
        clauses.append("(action LIKE ? OR path LIKE ? OR target_id LIKE ? OR detail_json LIKE ?)")
        params.extend([token, token, token, token])
    if actor.strip():
        clauses.append("actor_username LIKE ?")
        params.append(f"%{actor.strip()}%")
    if result in {"success", "failed"}:
        clauses.append("result=?")
        params.append(result)
    where = " AND ".join(clauses)
    offset = (page - 1) * 30
    with db_connection() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v05a_audit_logs WHERE {where}", params).fetchone()[0])
        rows = conn.execute(
            f"""
            SELECT * FROM v05a_audit_logs
            WHERE {where}
            ORDER BY id DESC LIMIT 30 OFFSET ?
            """,
            [*params, offset],
        ).fetchall()
    return render(
        request,
        "audit",
        logs=[dict(row) for row in rows],
        total=total,
        page=page,
        pages=max(1, (total + 29) // 30),
        filters={"q": q, "actor": actor, "result": result},
    )


@router.get("/v05a/health")
def security_health():
    ensure_security_schema()
    with db_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('v05a_users','v05a_audit_logs')"
            ).fetchall()
        }
    return {"status": "ok", "version": "v0.5A", "tables": sorted(tables), "user_count": user_count()}
