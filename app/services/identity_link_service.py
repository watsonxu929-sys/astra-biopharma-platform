from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.security import record_audit
from app.v04c_review import db_connection, default_db_path

REQUEST_STATUS_LABELS = {
    "pending": "待审核",
    "approved": "已通过",
    "rejected": "已拒绝",
    "cancelled": "已取消",
}

LINK_STATUS_LABELS = {
    "linked": "已绑定",
    "pending": "待审核",
    "unlinked": "未绑定",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS identity_link_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    request_reason TEXT,
    requested_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    review_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES v05a_users(id),
    FOREIGN KEY(person_id) REFERENCES people(id),
    CHECK(status IN ('pending','approved','rejected','cancelled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_identity_link_pending_user
ON identity_link_requests(user_id)
WHERE status='pending';

CREATE UNIQUE INDEX IF NOT EXISTS ux_identity_link_pending_person
ON identity_link_requests(person_id)
WHERE status='pending';

CREATE INDEX IF NOT EXISTS ix_identity_link_requests_status
ON identity_link_requests(status, requested_at DESC);

CREATE TRIGGER IF NOT EXISTS trg_v05a_users_person_id_insert
BEFORE INSERT ON v05a_users
WHEN NEW.person_id IS NOT NULL AND (SELECT id FROM people WHERE id=NEW.person_id) IS NULL
BEGIN
    SELECT RAISE(ABORT, 'person_id must reference people.id');
END;

CREATE TRIGGER IF NOT EXISTS trg_v05a_users_person_id_update
BEFORE UPDATE OF person_id ON v05a_users
WHEN NEW.person_id IS NOT NULL AND (SELECT id FROM people WHERE id=NEW.person_id) IS NULL
BEGIN
    SELECT RAISE(ABORT, 'person_id must reference people.id');
END;
"""


class IdentityLinkError(ValueError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _path(db_path: str | Path | None = None) -> Path:
    return Path(db_path) if db_path else default_db_path()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_identity_link_schema(db_path: str | Path | None = None) -> Path:
    path = _path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with db_connection(path) as conn:
        if "person_id" not in _columns(conn, "v05a_users"):
            conn.execute("ALTER TABLE v05a_users ADD COLUMN person_id INTEGER")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_v05a_users_person_id
            ON v05a_users(person_id)
            WHERE person_id IS NOT NULL
            """
        )
        conn.executescript(SCHEMA_SQL)
    return path


def backup_database(db_path: str | Path | None = None) -> str:
    path = _path(db_path)
    if not path.exists():
        return ""
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"app_before_identity_link_v1_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(path, target)
    return str(target)


def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _user(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    return _dict(conn.execute("SELECT id,username,display_name,role,status,person_id FROM v05a_users WHERE id=?", (user_id,)).fetchone())


def _person(conn: sqlite3.Connection, person_id: int) -> dict[str, Any] | None:
    return _dict(conn.execute("SELECT id,external_id,name FROM people WHERE id=? AND COALESCE(is_active,1)=1", (person_id,)).fetchone())


def _person_bound_user(conn: sqlite3.Connection, person_id: int, *, exclude_user_id: int | None = None) -> dict[str, Any] | None:
    params: list[Any] = [person_id]
    sql = "SELECT id,username,display_name FROM v05a_users WHERE person_id=?"
    if exclude_user_id is not None:
        sql += " AND id<>?"
        params.append(exclude_user_id)
    return _dict(conn.execute(sql, params).fetchone())


def _pending_for_user(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    return _request_row(conn, "SELECT * FROM identity_link_requests WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (user_id,))


def _request_row(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    data = _dict(row)
    if data:
        data["status_label"] = REQUEST_STATUS_LABELS.get(str(data.get("status")), str(data.get("status")))
    return data


def _audit(action: str, actor: dict[str, Any] | None, detail: dict[str, Any], *, request_path: str, target_id: str, db_path: str | Path | None = None) -> None:
    record_audit(
        action=action,
        actor=actor,
        method="POST" if action not in {"identity_link_cancel", "identity_unlink_person"} else "DELETE",
        path=request_path,
        result="success",
        status_code=200,
        target_type="identity_link",
        target_id=target_id,
        detail=detail,
        db_path=db_path,
    )


def identity_context(user_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(_path(db_path)) as conn:
        user = _user(conn, user_id)
        if not user:
            raise IdentityLinkError(404, "USER_NOT_FOUND", "账号不存在")
        person = _person(conn, int(user["person_id"])) if user.get("person_id") else None
        pending = _pending_for_user(conn, user_id)
        status = "linked" if person else "pending" if pending else "unlinked"
        return {
            "user": {"id": user["id"], "username": user["username"], "display_name": user["display_name"], "status": user["status"]},
            "person": person,
            "link_status": status,
            "link_status_label": LINK_STATUS_LABELS[status],
            "pending_request": pending,
        }


def create_link_request(user_id: int, person_id: int, reason: str, actor: dict[str, Any] | None, db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    try:
        with db_connection(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = _user(conn, user_id)
            if not user:
                raise IdentityLinkError(404, "USER_NOT_FOUND", "账号不存在")
            if user.get("person_id"):
                raise IdentityLinkError(409, "USER_ALREADY_LINKED", "当前账号已绑定人物")
            person = _person(conn, person_id)
            if not person:
                raise IdentityLinkError(404, "PERSON_NOT_FOUND", "人物档案不存在")
            if _person_bound_user(conn, person_id):
                raise IdentityLinkError(409, "PERSON_ALREADY_LINKED", "该人物档案已绑定其他账号")
            if _pending_for_user(conn, user_id):
                raise IdentityLinkError(409, "PENDING_REQUEST_EXISTS", "当前账号已有待审核绑定申请")
            if conn.execute("SELECT 1 FROM identity_link_requests WHERE person_id=? AND status='pending'", (person_id,)).fetchone():
                raise IdentityLinkError(409, "PERSON_PENDING_REQUEST_EXISTS", "该人物档案已有待审核绑定申请")
            cur = conn.execute(
                """
                INSERT INTO identity_link_requests(user_id,person_id,status,request_reason,requested_at,created_at,updated_at)
                VALUES (?,?,'pending',?,?,?,?)
                """,
                (user_id, person_id, reason.strip(), ts, ts, ts),
            )
            request_id = int(cur.lastrowid)
        result = get_link_request(request_id, db_path=path)
        _audit("identity_link_request", actor, {"user_id": user_id, "person_id": person_id, "request_id": request_id, "reason": reason}, request_path="/api/v1/me/person-link", target_id=str(request_id), db_path=path)
        return result
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            raise IdentityLinkError(409, "IDENTITY_LINK_CONFLICT", "身份绑定正在被其他操作处理，请稍后重试") from exc
        raise


def cancel_link_request(user_id: int, actor: dict[str, Any] | None, db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        req = _pending_for_user(conn, user_id)
        if not req:
            raise IdentityLinkError(409, "NO_PENDING_REQUEST", "当前账号没有待取消的绑定申请")
        conn.execute("UPDATE identity_link_requests SET status='cancelled',updated_at=? WHERE id=?", (ts, req["id"]))
    result = get_link_request(int(req["id"]), db_path=path)
    _audit("identity_link_cancel", actor, {"user_id": user_id, "person_id": req["person_id"], "request_id": req["id"], "from_status": "pending", "to_status": "cancelled"}, request_path="/api/v1/me/person-link", target_id=str(req["id"]), db_path=path)
    return result


def get_link_request(request_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(_path(db_path)) as conn:
        row = _request_row(conn, "SELECT * FROM identity_link_requests WHERE id=?", (request_id,))
        if not row:
            raise IdentityLinkError(404, "REQUEST_NOT_FOUND", "绑定申请不存在")
        row["user"] = _user(conn, int(row["user_id"]))
        row["person"] = _person(conn, int(row["person_id"]))
        return row


def list_link_requests(status: str | None = None, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if status:
        where = "WHERE r.status=?"
        params.append(status)
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute(
            f"""
            SELECT r.*, u.username, u.display_name, p.external_id AS person_external_id, p.name AS person_name
            FROM identity_link_requests r
            JOIN v05a_users u ON u.id=r.user_id
            JOIN people p ON p.id=r.person_id
            {where}
            ORDER BY CASE r.status WHEN 'pending' THEN 0 ELSE 1 END, r.requested_at DESC, r.id DESC
            LIMIT 200
            """,
            params,
        ).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        item["status_label"] = REQUEST_STATUS_LABELS.get(item["status"], item["status"])
        output.append(item)
    return output


def approve_link_request(request_id: int, actor: dict[str, Any], db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    changed = False
    try:
        with db_connection(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            req = _request_row(conn, "SELECT * FROM identity_link_requests WHERE id=?", (request_id,))
            if not req:
                raise IdentityLinkError(404, "REQUEST_NOT_FOUND", "绑定申请不存在")
            user = _user(conn, int(req["user_id"]))
            person = _person(conn, int(req["person_id"]))
            if not user or not person:
                raise IdentityLinkError(409, "REQUEST_TARGET_MISSING", "申请关联的账号或人物已不存在")
            if req["status"] == "approved":
                if user.get("person_id") != req["person_id"]:
                    raise IdentityLinkError(409, "REQUEST_STATE_CONFLICT", "申请状态与账号绑定关系不一致")
            elif req["status"] != "pending":
                raise IdentityLinkError(409, "REQUEST_ALREADY_HANDLED", "该申请已处理，不能重复审核")
            else:
                if user.get("person_id"):
                    raise IdentityLinkError(409, "USER_ALREADY_LINKED", "申请账号已绑定其他人物")
                if _person_bound_user(conn, int(req["person_id"]), exclude_user_id=int(req["user_id"])):
                    raise IdentityLinkError(409, "PERSON_ALREADY_LINKED", "申请人物已绑定其他账号")
                conn.execute("UPDATE v05a_users SET person_id=?,updated_at=? WHERE id=?", (req["person_id"], ts, req["user_id"]))
                conn.execute("UPDATE identity_link_requests SET status='approved',reviewed_at=?,reviewed_by=?,updated_at=? WHERE id=?", (ts, actor.get("username"), ts, request_id))
                changed = True
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            raise IdentityLinkError(409, "IDENTITY_LINK_CONFLICT", "身份绑定正在被其他操作处理，请稍后重试") from exc
        raise
    result = get_link_request(request_id, db_path=path)
    if changed:
        _audit("identity_link_approve", actor, {"request_id": request_id, "user_id": result["user_id"], "person_id": result["person_id"], "from_status": "pending", "to_status": "approved"}, request_path=f"/api/v1/identity/link-requests/{request_id}/approve", target_id=str(request_id), db_path=path)
    return result

def reject_link_request(request_id: int, reason: str, actor: dict[str, Any], db_path: str | Path | None = None) -> dict[str, Any]:
    if not reason.strip():
        raise IdentityLinkError(422, "REASON_REQUIRED", "拒绝原因不能为空")
    path = _path(db_path)
    ts = now_iso()
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        req = _request_row(conn, "SELECT * FROM identity_link_requests WHERE id=?", (request_id,))
        if not req:
            raise IdentityLinkError(404, "REQUEST_NOT_FOUND", "绑定申请不存在")
        if req["status"] != "pending" and req["status"] != "rejected":
            raise IdentityLinkError(409, "REQUEST_ALREADY_HANDLED", "该申请已处理，不能重复审核")
        if req["status"] == "pending":
            conn.execute("UPDATE identity_link_requests SET status='rejected',reviewed_at=?,reviewed_by=?,review_note=?,updated_at=? WHERE id=?", (ts, actor.get("username"), reason.strip(), ts, request_id))
    result = get_link_request(request_id, db_path=path)
    _audit("identity_link_reject", actor, {"request_id": request_id, "user_id": result["user_id"], "person_id": result["person_id"], "from_status": "pending", "to_status": "rejected", "reason": reason}, request_path=f"/api/v1/identity/link-requests/{request_id}/reject", target_id=str(request_id), db_path=path)
    return result


def unlink_user_person(user_id: int, reason: str, actor: dict[str, Any], db_path: str | Path | None = None) -> dict[str, Any]:
    if not reason.strip():
        raise IdentityLinkError(422, "REASON_REQUIRED", "解除原因不能为空")
    path = _path(db_path)
    ts = now_iso()
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        user = _user(conn, user_id)
        if not user:
            raise IdentityLinkError(404, "USER_NOT_FOUND", "账号不存在")
        old_person_id = user.get("person_id")
        if not old_person_id:
            result = {"user_id": user_id, "person_id": None, "link_status": "unlinked", "link_status_label": LINK_STATUS_LABELS["unlinked"]}
        else:
            conn.execute("UPDATE v05a_users SET person_id=NULL,updated_at=? WHERE id=?", (ts, user_id))
            result = {"user_id": user_id, "person_id": old_person_id, "link_status": "unlinked", "link_status_label": LINK_STATUS_LABELS["unlinked"]}
    _audit("identity_unlink_person", actor, {"user_id": user_id, "person_id": old_person_id, "from_status": "linked" if old_person_id else "unlinked", "to_status": "unlinked", "reason": reason}, request_path=f"/api/v1/identity/users/{user_id}/person-link", target_id=str(user_id), db_path=path)
    return result

def list_person_options(q: str = "", limit: int = 30, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    value = (q or "").strip()
    params: list[Any] = []
    where = "WHERE COALESCE(p.is_active,1)=1"
    if value:
        where += " AND (p.name LIKE ? OR p.external_id LIKE ?)"
        params.extend([f"%{value}%", f"%{value}%"])
    params.append(limit)
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute(
            f"""
            SELECT p.id,p.external_id,p.name,u.id AS bound_user_id,u.username AS bound_username
            FROM people p
            LEFT JOIN v05a_users u ON u.person_id=p.id
            {where}
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]



