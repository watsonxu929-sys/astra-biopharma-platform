from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.security import permissions_for
from app.v04c_review import db_connection, default_db_path


class MembershipAccessError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


STATUS_LABELS = {
    "pending": "待审核",
    "active": "有效",
    "inactive": "无效",
    "suspended": "已暂停",
    "exited": "已退出",
}

TYPE_LABELS = {
    "standard": "标准会员",
    "premium": "高级会员",
    "vip": "VIP会员",
    "founding": "创始会员",
}


def _path(db_path: str | Path | None) -> Path:
    return Path(db_path) if db_path else default_db_path()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def _has_user_link_column(conn: sqlite3.Connection) -> bool:
    return "user_id" in _columns(conn, "v04f_club_memberships")


def _select_sql(where_sql: str = "", order_sql: str = "ORDER BY m.status DESC, m.created_at DESC") -> str:
    return f"""
        SELECT
            m.id AS membership_id,
            m.id AS id,
            m.member_no,
            m.member_level AS membership_type,
            m.member_level,
            m.status AS membership_status,
            m.status,
            m.user_id,
            m.person_id,
            m.organization_id,
            m.created_at,
            m.updated_at,
            p.name AS person_name,
            p.external_id AS person_external_id,
            o.standard_name AS organization_name,
            o.external_id AS organization_external_id
        FROM v04f_club_memberships m
        LEFT JOIN people p ON p.id=m.person_id
        LEFT JOIN organizations o ON o.id=m.organization_id
        {where_sql}
        {order_sql}
    """


def _summary(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    display_name = item.get("person_name") or item.get("organization_name") or item.get("member_no") or f"会员 {item.get('membership_id')}"
    status = item.get("membership_status") or item.get("status") or ""
    membership_type = item.get("membership_type") or item.get("member_level") or ""
    return {
        "membership_id": item.get("membership_id") or item.get("id"),
        "id": item.get("membership_id") or item.get("id"),
        "membership_no": item.get("member_no"),
        "member_no": item.get("member_no"),
        "membership_name": display_name,
        "name": display_name,
        "membership_status": status,
        "status": status,
        "membership_status_label": STATUS_LABELS.get(str(status), str(status) if status else ""),
        "status_label": STATUS_LABELS.get(str(status), str(status) if status else ""),
        "membership_type": membership_type,
        "membership_type_label": TYPE_LABELS.get(str(membership_type), str(membership_type) if membership_type else ""),
        "member_level": membership_type,
        "member_level_label": TYPE_LABELS.get(str(membership_type), str(membership_type) if membership_type else ""),
        "user_id": item.get("user_id"),
        "person_id": item.get("person_id"),
        "person_name": item.get("person_name"),
        "person_external_id": item.get("person_external_id"),
        "organization_id": item.get("organization_id"),
        "organization_name": item.get("organization_name"),
        "organization_external_id": item.get("organization_external_id"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def _user_id(user: dict[str, Any] | None) -> int | None:
    if not user or user.get("id") is None:
        return None
    return int(user["id"])


def is_membership_admin(user: dict[str, Any] | None) -> bool:
    if not user:
        return False
    perms = permissions_for(user)
    return "manage_club" in perms or "manage_users" in perms


def require_membership_admin(user: dict[str, Any] | None) -> None:
    if not is_membership_admin(user):
        raise MembershipAccessError(403, "FORBIDDEN", "需要会员管理权限")


def get_user_memberships(user_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        if not _has_user_link_column(conn):
            return []
        rows = conn.execute(_select_sql("WHERE m.user_id=?"), (int(user_id),)).fetchall()
    return [_summary(row) for row in rows]


def get_accessible_memberships(user: dict[str, Any] | None, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    uid = _user_id(user)
    if uid is None:
        return []
    return get_user_memberships(uid, db_path)


def get_membership_summary(membership_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with db_connection(_path(db_path)) as conn:
        row = conn.execute(_select_sql("WHERE m.id=?", ""), (int(membership_id),)).fetchone()
    return _summary(row) if row else None


def get_membership_context(user: dict[str, Any] | None, db_path: str | Path | None = None) -> dict[str, Any]:
    memberships = get_accessible_memberships(user, db_path)
    return {
        "has_membership": bool(memberships),
        "membership_count": len(memberships),
        "default_membership_id": memberships[0]["membership_id"] if memberships else None,
        "can_switch": len(memberships) > 1,
        "memberships": memberships,
    }


def get_accessible_membership(
    user: dict[str, Any] | None,
    membership_id: int,
    db_path: str | Path | None = None,
    *,
    allow_admin: bool = False,
) -> dict[str, Any] | None:
    member = get_membership_summary(membership_id, db_path)
    if not member:
        return None
    if allow_admin and is_membership_admin(user):
        return member
    uid = _user_id(user)
    if uid is None or member.get("user_id") is None:
        return None
    return member if int(member["user_id"]) == uid else None


def get_accessible_membership_or_403(
    user: dict[str, Any] | None,
    membership_id: int,
    db_path: str | Path | None = None,
    *,
    allow_admin: bool = False,
) -> dict[str, Any]:
    member = get_accessible_membership(user, membership_id, db_path, allow_admin=allow_admin)
    if member:
        return member
    if get_membership_summary(membership_id, db_path):
        raise MembershipAccessError(403, "FORBIDDEN", "您无权访问该会员身份")
    raise MembershipAccessError(404, "NOT_FOUND", "会员身份不存在")


def can_access_membership(user: dict[str, Any] | None, membership_id: int, db_path: str | Path | None = None) -> bool:
    try:
        get_accessible_membership_or_403(user, membership_id, db_path)
        return True
    except MembershipAccessError:
        return False
