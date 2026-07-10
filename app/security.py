from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.v04c_review import db_connection, default_db_path

ROLE_LABELS = {
    "admin": "系统管理员",
    "operator": "业务运营",
    "reviewer": "数据审核",
    "viewer": "只读查看",
}

ALL_PERMISSIONS = {
    "view_internal",
    "edit_data",
    "review_data",
    "identity.view_self",
    "identity.request_link",
    "identity.review_link",
    "identity.unlink",
    "membership.view_self",
    "membership.user_link.request",
    "organization.view_self",
    "manage_club",
    "manage_monitoring",
    "use_recommendations",
    "manage_users",
    "view_sensitive",
    "export_data",
}

ROLE_PERMISSIONS = {
    "admin": set(ALL_PERMISSIONS),
    "operator": {
        "view_internal",
        "identity.view_self",
        "identity.request_link",
        "membership.view_self",
        "membership.user_link.request",
        "organization.view_self",
        "edit_data",
        "manage_club",
        "manage_monitoring",
        "use_recommendations",
        "view_sensitive",
        "export_data",
    },
    "reviewer": {
        "view_internal",
        "identity.view_self",
        "identity.request_link",
        "identity.review_link",
        "membership.view_self",
        "membership.user_link.request",
        "organization.view_self",
        "review_data",
        "use_recommendations",
        "view_sensitive",
    },
    "viewer": {"view_internal", "identity.view_self", "identity.request_link", "membership.view_self", "membership.user_link.request", "organization.view_self"},
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v05a_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    status TEXT NOT NULL DEFAULT 'active',
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    session_version INTEGER NOT NULL DEFAULT 1,
    last_login_at TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deactivated_at TEXT,
    CHECK(role IN ('admin','operator','reviewer','viewer')),
    CHECK(status IN ('active','disabled'))
);

CREATE INDEX IF NOT EXISTS ix_v05a_users_role_status
ON v05a_users(role, status, username);


CREATE TABLE IF NOT EXISTS v05a_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    actor_username TEXT,
    action TEXT NOT NULL,
    method TEXT,
    path TEXT,
    target_type TEXT,
    target_id TEXT,
    result TEXT NOT NULL DEFAULT 'success',
    status_code INTEGER,
    ip_address_masked TEXT,
    detail_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(actor_user_id) REFERENCES v05a_users(id)
);

CREATE INDEX IF NOT EXISTS ix_v05a_audit_created
ON v05a_audit_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05a_audit_actor
ON v05a_audit_logs(actor_username, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05a_audit_path
ON v05a_audit_logs(path, created_at DESC);
"""

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")
SESSION_COOKIE = "biopharma_session"
SESSION_MAX_AGE = 12 * 60 * 60
PBKDF2_ITERATIONS = 310_000
_PUBLIC_EXACT = {
    "/account/login",
    "/account/logout",
    "/account/forbidden",
    "/setup/admin",
    "/club/apply",
    "/health",
    "/favicon.ico",
}
_PUBLIC_PREFIXES = ("/static/",)
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_security_schema(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
    return path


def auth_disabled() -> bool:
    return os.getenv("APP_AUTH_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64_encode(salt)}${_b64_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _b64_decode(salt_text)
        expected = _b64_decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def validate_password(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 10:
        errors.append("密码至少需要 10 个字符")
    if not re.search(r"[A-Za-z]", password):
        errors.append("密码至少包含一个英文字母")
    if not re.search(r"\d", password):
        errors.append("密码至少包含一个数字")
    if password.lower() in {"password123", "admin12345", "1234567890", "qbay123456"}:
        errors.append("密码过于常见")
    return errors


def validate_username(username: str) -> list[str]:
    username = username.strip()
    if not USERNAME_RE.fullmatch(username):
        return ["用户名只能包含字母、数字、点、下划线或短横线，长度为 3 到 40 位"]
    return []

def user_count(db_path: str | Path | None = None) -> int:
    ensure_security_schema(db_path)
    with db_connection(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM v05a_users").fetchone()[0])


def active_admin_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM v05a_users WHERE role='admin' AND status='active'").fetchone()[0])


def create_user(
    username: str,
    display_name: str,
    password: str,
    role: str,
    *,
    created_by: str = "system",
    must_change_password: bool = False,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_security_schema(db_path)
    username = username.strip()
    display_name = display_name.strip() or username
    errors = validate_username(username) + validate_password(password)
    if role not in ROLE_LABELS:
        errors.append("无效角色")
    if errors:
        raise ValueError("；".join(errors))
    ts = now_iso()
    try:
        with db_connection(db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO v05a_users(
                    username, display_name, password_hash, role, status,
                    must_change_password, session_version, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'active', ?, 1, ?, ?, ?)
                """,
                (username, display_name, hash_password(password), role, int(must_change_password), created_by, ts, ts),
            )
            row = conn.execute(
                "SELECT id,username,display_name,role,status,must_change_password,created_at FROM v05a_users WHERE id=?",
                (cur.lastrowid,),
            ).fetchone()
    except sqlite3.IntegrityError as exc:
        raise ValueError("用户名已经存在") from exc
    return dict(row)


def get_user_by_id(user_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_security_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05a_users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_security_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05a_users WHERE lower(username)=lower(?)", (username.strip(),)).fetchone()
    return dict(row) if row else None


def list_users(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    ensure_security_schema(db_path)
    with db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id,username,display_name,role,status,failed_login_count,locked_until,
                   must_change_password,last_login_at,created_by,created_at,updated_at
            FROM v05a_users ORDER BY status, role, username
            """
        ).fetchall()
    return [dict(row) for row in rows]


def authenticate_user(username: str, password: str, db_path: str | Path | None = None) -> tuple[dict[str, Any] | None, str]:
    ensure_security_schema(db_path)
    ts = datetime.now()
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05a_users WHERE lower(username)=lower(?)", (username.strip(),)).fetchone()
        if not row:
            return None, "用户名或密码错误"
        user = dict(row)
        if user["status"] != "active":
            return None, "账号已停用"
        if user.get("locked_until"):
            try:
                locked_until = datetime.fromisoformat(user["locked_until"])
                if locked_until > ts:
                    return None, f"登录失败次数过多，请在 {locked_until.strftime('%H:%M')} 后重试"
            except ValueError:
                pass
        if not verify_password(password, user["password_hash"]):
            failures = int(user.get("failed_login_count") or 0) + 1
            locked_until = None
            if failures >= 5:
                locked_until = (ts + timedelta(minutes=15)).replace(microsecond=0).isoformat()
                failures = 0
            conn.execute(
                "UPDATE v05a_users SET failed_login_count=?,locked_until=?,updated_at=? WHERE id=?",
                (failures, locked_until, now_iso(), user["id"]),
            )
            return None, "用户名或密码错误"
        conn.execute(
            "UPDATE v05a_users SET failed_login_count=0,locked_until=NULL,last_login_at=?,updated_at=? WHERE id=?",
            (now_iso(), now_iso(), user["id"]),
        )
        refreshed = conn.execute("SELECT * FROM v05a_users WHERE id=?", (user["id"],)).fetchone()
    return dict(refreshed), ""


def change_password(user_id: int, old_password: str, new_password: str, db_path: str | Path | None = None) -> None:
    errors = validate_password(new_password)
    if errors:
        raise ValueError("；".join(errors))
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05a_users WHERE id=?", (user_id,)).fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            raise ValueError("当前密码不正确")
        conn.execute(
            """
            UPDATE v05a_users
            SET password_hash=?,must_change_password=0,session_version=session_version+1,updated_at=?
            WHERE id=?
            """,
            (hash_password(new_password), now_iso(), user_id),
        )


def admin_reset_password(user_id: int, new_password: str, db_path: str | Path | None = None) -> None:
    errors = validate_password(new_password)
    if errors:
        raise ValueError("；".join(errors))
    with db_connection(db_path) as conn:
        if not conn.execute("SELECT 1 FROM v05a_users WHERE id=?", (user_id,)).fetchone():
            raise ValueError("用户不存在")
        conn.execute(
            """
            UPDATE v05a_users
            SET password_hash=?,must_change_password=1,failed_login_count=0,locked_until=NULL,
                session_version=session_version+1,updated_at=?
            WHERE id=?
            """,
            (hash_password(new_password), now_iso(), user_id),
        )


def update_user_admin(
    user_id: int,
    *,
    role: str,
    status: str,
    display_name: str,
    actor_user_id: int,
    db_path: str | Path | None = None,
) -> None:
    if role not in ROLE_LABELS or status not in {"active", "disabled"}:
        raise ValueError("角色或状态无效")
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05a_users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("用户不存在")
        last_admin = row["role"] == "admin" and row["status"] == "active" and active_admin_count(conn) <= 1
        if last_admin and (role != "admin" or status != "active"):
            raise ValueError("涓嶈兘鍋滅敤鎴栭檷绾х郴缁熶腑鏈€鍚庝竴涓湁鏁堢鐞嗗憳")
        if user_id == actor_user_id and status != "active":
            raise ValueError("涓嶈兘鍋滅敤褰撳墠鐧诲綍璐﹀彿")
        changed_security = row["role"] != role or row["status"] != status
        conn.execute(
            """
            UPDATE v05a_users
            SET display_name=?,role=?,status=?,deactivated_at=?,
                session_version=session_version+?,updated_at=?
            WHERE id=?
            """,
            (
                display_name.strip() or row["display_name"],
                role,
                status,
                now_iso() if status == "disabled" else None,
                1 if changed_security else 0,
                now_iso(),
                user_id,
            ),
        )


def _secret_path() -> Path:
    return default_db_path().parent / ".session_secret"


def session_secret() -> bytes:
    configured = os.getenv("APP_SESSION_SECRET", "").strip()
    if configured:
        return configured.encode("utf-8")
    path = _secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(64), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text(encoding="utf-8").strip().encode("utf-8")


def create_session_token(user: dict[str, Any], max_age: int = SESSION_MAX_AGE) -> str:
    payload = {
        "uid": int(user["id"]),
        "sv": int(user.get("session_version") or 1),
        "exp": int(datetime.now().timestamp()) + max_age,
        "nonce": secrets.token_hex(6),
    }
    body = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64_encode(hmac.new(session_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_session_token(token: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        expected = _b64_encode(hmac.new(session_secret(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64_decode(body))
        if int(payload["exp"]) < int(datetime.now().timestamp()):
            return None
        user = get_user_by_id(int(payload["uid"]), db_path)
        if not user or user["status"] != "active":
            return None
        if int(payload["sv"]) != int(user.get("session_version") or 1):
            return None
        return user
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def set_session_cookie(response: Response, user: dict[str, Any]) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=os.getenv("APP_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"},
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def permissions_for(user: dict[str, Any] | None) -> set[str]:
    if not user:
        return set()
    return set(ROLE_PERMISSIONS.get(str(user.get("role")), set()))



def auth_disabled_user(db_path: str | Path | None = None) -> dict[str, Any]:
    """Return a real positive-id local principal for APP_AUTH_DISABLED mode."""
    ensure_security_schema(db_path)
    ts = now_iso()
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05a_users WHERE username='auth_disabled_system'").fetchone()
        if row:
            return dict(row)
        admin = conn.execute("SELECT * FROM v05a_users WHERE role='admin' AND status='active' ORDER BY id LIMIT 1").fetchone()
        if admin:
            return dict(admin)
        conn.execute(
            """
            INSERT INTO v05a_users(username, display_name, password_hash, role, status, created_by, created_at, updated_at)
            VALUES ('auth_disabled_system', 'Auth Disabled Local Principal', ?, 'admin', 'active', 'system', ?, ?)
            """,
            (hash_password(secrets.token_urlsafe(32)), ts, ts),
        )
        row = conn.execute("SELECT * FROM v05a_users WHERE username='auth_disabled_system'").fetchone()
        return dict(row)

def build_security_context(user: dict[str, Any] | None, *, disabled: bool = False) -> dict[str, Any]:
    permissions = permissions_for(user)
    return {
        "authenticated": bool(user),
        "auth_disabled": disabled,
        "user": user or {},
        "role_label": ROLE_LABELS.get(str((user or {}).get("role")), "未登录"),
        "permissions": sorted(permissions),
        "can_manage_users": "manage_users" in permissions,
        "can_edit": "edit_data" in permissions,
        "can_review": "review_data" in permissions,
        "can_manage_club": "manage_club" in permissions,
        "can_manage_monitoring": "manage_monitoring" in permissions,
        "can_view_sensitive": "view_sensitive" in permissions,
        "can_export": "export_data" in permissions,
    }


def current_user(request: Request) -> dict[str, Any] | None:
    return getattr(request.state, "current_user", None)


def current_username(request: Request, fallback: str = "manual") -> str:
    user = current_user(request)
    return str(user.get("username")) if user else fallback


def can(request: Request, permission: str) -> bool:
    return permission in permissions_for(current_user(request))


def _is_health(path: str) -> bool:
    return path == "/health" or path.endswith("/health") or bool(re.fullmatch(r"/v[0-9][0-9a-z.-]*/health", path))


def is_public_path(path: str) -> bool:
    return (
        path in _PUBLIC_EXACT
        or path.startswith(_PUBLIC_PREFIXES)
        or path == "/api/v1/health"
        or path == "/member"
        or path.startswith("/member/")
        or _is_health(path)
        or bool(re.fullmatch(r"/club/events/[0-9]+/register", path))
    )


def required_permission(path: str, method: str) -> str | None:
    method = method.upper()
    if is_public_path(path):
        return None
    if path.startswith("/admin/data-integrity"):
        return "review_data"
    if path.startswith("/admin/intelligence"):
        return "review_data"
    if path.startswith("/admin/people") or path.startswith("/admin/organizations"):
        return "edit_data"
    if path.startswith("/admin/"):
        return "manage_users"
    if path.startswith("/system"):
        return "manage_users"
    if path == "/club/members.csv":
        return "export_data"
    if path.startswith("/api/v1/system") and method in {"GET", "HEAD", "OPTIONS"}:
        return "view_internal"
    if path.startswith("/api/v1/system") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "manage_users"
    if path == "/api/v1/me/identity":
        return "identity.view_self"
    if path == "/api/v1/me/person-link":
        return "identity.request_link"
    if path.startswith("/api/v1/identity/link-requests/"):
        return "identity.review_link"
    if path in {"/api/v1/me/organizations", "/api/v1/me/organization-context"}:
        return "organization.view_self"
    if path.startswith("/api/v1/me/organizations/"):
        return "organization.view_self"
    if path.startswith("/api/v1/organizations/") and "/users/" in path and "/roles" in path:
        return "view_internal"
    if path.startswith("/api/v1/organizations"):
        return "manage_club"
    if path.startswith("/api/v1/identity/users/") and path.endswith("/person-link"):
        return "identity.unlink"
    if path.startswith("/api/v1/collection/items") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "review_data"
    if path.startswith("/api/v1/collection") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "manage_monitoring"
    if path.startswith("/api/v1/processing") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "review_data"
    if path.startswith("/api/v1/reports") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "review_data"
    if path.startswith("/api/v1/pipeline") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "review_data"
    if path.startswith("/api/v1/research") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "edit_data"
    if path.startswith("/api/v1/investment-assessments") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "review_data"
    if path in {"/api/v1/client/bootstrap", "/api/v1/client/navigation", "/api/v1/network/people", "/api/v1/network/recommendations/people", "/api/v1/me/clubs", "/api/v1/me/club-context"}:
        return "view_internal"
    if path.startswith("/api/v1/network/people/"):
        return "view_internal"
    if path == "/club" and method in {"GET", "HEAD", "OPTIONS"}:
        return "view_internal"
    if path.startswith("/club/import"):
        return "manage_club"
    if path.startswith("/club/admin/"):
        return "manage_club"
    if path.startswith("/club"):
        return "manage_club"
    if method in {"GET", "HEAD", "OPTIONS"}:
        return "view_internal"
    if path.startswith("/processing"):
        return "review_data"
    if path.startswith("/pipeline") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "review_data"
    if path.startswith("/research/investment") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "review_data"
    if path.startswith("/research") and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "edit_data"
    if path.startswith("/reports") or path.startswith("/signals/rules") or path.startswith("/signals/run"):
        return "review_data"
    if path.startswith("/collection"):
        return "manage_monitoring"
    if path.startswith("/review") or path.startswith("/intelligence/monitoring/proposals"):
        return "review_data"
    if path.startswith("/intelligence/monitoring"):
        return "manage_monitoring"
    if path.startswith("/recommendations"):
        return "use_recommendations"
    return "edit_data"


def _mask_ip(value: str | None) -> str:
    if not value:
        return ""
    if ":" in value:
        parts = value.split(":")
        return ":".join(parts[:3]) + "::"
    parts = value.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3] + ["0"])
    return value[:32]


def _target_from_path(path: str) -> tuple[str | None, str | None]:
    patterns = [
        (r"^/manage/([^/]+)/([^/]+)", 1, 2),
        (r"^/subjects/([^/]+)/([^/]+)", 1, 2),
        (r"^/(recommendations|leads|actions)/([0-9]+)", 1, 2),
        (r"^/club/(members|matches)/([0-9]+)", 1, 2),
        (r"^/collection/(?:sources|jobs|items|snapshots)/([0-9]+)", 0, 1),
        (r"^/intelligence/monitoring/(?:sources|proposals)/([0-9]+)", 0, 1),
        (r"^/review/[^/]+/([0-9]+)", 0, 1),
    ]
    for pattern, type_group, id_group in patterns:
        match = re.match(pattern, path)
        if not match:
            continue
        target_type = match.group(type_group) if type_group else path.strip("/").split("/")[0]
        return target_type, match.group(id_group)
    return None, None


def audit_action(method: str, path: str) -> str:
    tail = path.rstrip("/").split("/")[-1] or "root"
    return f"{method.upper()}:{tail[:80]}"


def record_audit(
    *,
    action: str,
    actor: dict[str, Any] | None = None,
    method: str = "",
    path: str = "",
    result: str = "success",
    status_code: int | None = None,
    ip_address: str = "",
    detail: dict[str, Any] | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    try:
        ensure_security_schema(db_path)
        if target_type is None and path:
            target_type, target_id = _target_from_path(path)
        with db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO v05a_audit_logs(
                    actor_user_id,actor_username,action,method,path,target_type,target_id,
                    result,status_code,ip_address_masked,detail_json,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    int(actor["id"]) if actor and actor.get("id") else None,
                    str(actor.get("username")) if actor else None,
                    action[:120],
                    method[:12],
                    path[:500],
                    target_type,
                    target_id,
                    result[:30],
                    status_code,
                    _mask_ip(ip_address),
                    json.dumps(detail or {}, ensure_ascii=False, default=str)[:4000],
                    now_iso(),
                ),
            )
    except Exception:
        # 审计失败不应破坏用户已经完成的业务操作。
        return


def _safe_next(value: str | None, fallback: str = "/") -> str:
    value = (value or "").strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    return fallback


def safe_next(value: str | None, fallback: str = "/") -> str:
    return _safe_next(value, fallback)


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        disabled = auth_disabled()
        user: dict[str, Any] | None = None
        total_users = 1
        if disabled:
            user = {
                "id": 0,
                "username": "auth-disabled",
                "display_name": "楠岃瘉妯″紡",
                "role": "admin",
                "status": "active",
                "must_change_password": 0,
                "session_version": 1,
            }
        else:
            ensure_security_schema()
            total_users = user_count()
            token = request.cookies.get(SESSION_COOKIE, "")
            if token:
                user = verify_session_token(token)

        request.state.current_user = user
        context = build_security_context(user, disabled=disabled)
        request.state.security = context
        request.scope["security_context"] = context

        if not disabled:
            if total_users == 0 and not is_public_path(path):
                if path.startswith("/setup/admin"):
                    pass
                elif request.method.upper() in {"GET", "HEAD"}:
                    return RedirectResponse(f"/setup/admin?next={quote(path)}", status_code=303)
                else:
                    return HTMLResponse("系统尚未创建管理员，请先完成初始化。", status_code=503)
            elif total_users > 0 and path.startswith("/setup/admin"):
                return RedirectResponse("/account/login", status_code=303)

            if user and int(user.get("must_change_password") or 0) and path not in {
                "/account/change-password",
                "/account/logout",
                "/account/forbidden",
            } and not path.startswith("/static/"):
                return RedirectResponse("/account/change-password?required=1", status_code=303)

            permission = required_permission(path, request.method)
            if permission:
                if not user:
                    if path.startswith("/api/"):
                        return JSONResponse(
                            {"error": {"code": "AUTH_REQUIRED", "message": "璇峰厛鐧诲綍鍚庤闂?API", "details": {}}},
                            status_code=401,
                        )
                    if request.method.upper() in {"GET", "HEAD"}:
                        return RedirectResponse(f"/account/login?next={quote(path)}", status_code=303)
                    return HTMLResponse("请先登录。", status_code=401)
                if permission not in permissions_for(user):
                    if path.startswith("/api/"):
                        return JSONResponse(
                            {"error": {"code": "FORBIDDEN", "message": "当前账号没有访问该 API 的权限", "details": {}}},
                            status_code=403,
                        )
                    if request.method.upper() in {"GET", "HEAD"}:
                        return RedirectResponse(f"/account/forbidden?path={quote(path)}", status_code=303)
                    return HTMLResponse("当前账号没有执行此操作的权限。", status_code=403)

        response = await call_next(request)

        if (
            not disabled
            and request.method.upper() in _MUTATING
            and user
            and path not in {"/account/login", "/account/logout", "/account/change-password", "/setup/admin"}
        ):
            record_audit(
                action=audit_action(request.method, path),
                actor=user,
                method=request.method,
                path=path,
                result="success" if response.status_code < 400 else "failed",
                status_code=response.status_code,
                ip_address=request.client.host if request.client else "",
            )
        return response


















