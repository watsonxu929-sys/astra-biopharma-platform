from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.v04c_review import db_connection, default_db_path

LINK_STATUS_LABELS = {
    "linked": "已关联",
    "unlinked": "未关联",
}


class MembershipUserLinkError(ValueError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _path(db_path: str | Path | None = None) -> Path:
    return Path(db_path) if db_path else default_db_path()


def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _membership(conn: sqlite3.Connection, membership_id: int) -> dict[str, Any] | None:
    return _dict(conn.execute("SELECT * FROM v04f_club_memberships WHERE id=?", (membership_id,)).fetchone())


def _user(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    return _dict(conn.execute("SELECT id,username,display_name,role,status FROM v05a_users WHERE id=?", (user_id,)).fetchone())


def _next_audit_no(conn: sqlite3.Connection) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04f_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES ('QBULA', ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date, updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (stamp, now_iso()),
    ).fetchone()
    return f"QBULA-{stamp}-{int(row['seq_value']):04d}"


def _next_request_no(conn: sqlite3.Connection) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04f_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES ('QBUAR', ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date, updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (stamp, now_iso()),
    ).fetchone()
    return f"QBUAR-{stamp}-{int(row['seq_value']):04d}"


def _record_audit(conn: sqlite3.Connection, action: str, membership_id: int, user_id: int | None, 
                  old_user_id: int | None, actor: str, reason: str, request_id: int | None = None):
    conn.execute(
        """
        INSERT INTO membership_user_link_audit(audit_no,action,membership_id,user_id,old_user_id,actor,reason,request_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (_next_audit_no(conn), action, membership_id, user_id, old_user_id, actor, reason or None, request_id, now_iso()),
    )


def get_link_info(membership_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(_path(db_path)) as conn:
        membership = _membership(conn, membership_id)
        if not membership:
            raise MembershipUserLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        user = None
        link_status = "unlinked"
        
        if membership.get("user_id"):
            user = _user(conn, int(membership["user_id"]))
            link_status = "linked" if user else "unlinked"
        
        audit_count = conn.execute(
            "SELECT COUNT(*) AS c FROM membership_user_link_audit WHERE membership_id=?",
            (membership_id,)
        ).fetchone()["c"]
        
        return {
            "membership": {
                "id": membership["id"],
                "member_no": membership["member_no"],
                "member_level": membership.get("member_level"),
                "member_level_label": {"standard": "标准会员", "premium": "高级会员", "vip": "VIP会员", "founding": "创始会员"}.get(membership.get("member_level"), membership.get("member_level") or ""),
                "status": membership["status"],
                "status_label": {"pending": "待审核", "active": "有效", "inactive": "无效", "suspended": "已暂停", "exited": "已退出"}.get(membership["status"], membership["status"]),
                "joined_at": membership.get("joined_at"),
            },
            "user": user,
            "link_status": link_status,
            "link_status_label": LINK_STATUS_LABELS.get(link_status, link_status),
            "audit_summary": {"count": audit_count},
        }


def get_memberships_for_user(user_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT m.id,m.member_no,m.member_level,m.status,m.joined_at,m.created_at,
                   p.name AS person_name, p.external_id AS person_external_id,
                   o.standard_name AS organization_name
            FROM v04f_club_memberships m
            LEFT JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            WHERE m.user_id=?
            ORDER BY m.created_at DESC
            """,
            (user_id,),
        ).fetchall()
    
    results = []
    for row in rows:
        item = dict(row)
        item["member_level_label"] = {"standard": "标准会员", "premium": "高级会员", "vip": "VIP会员", "founding": "创始会员"}.get(item.get("member_level"), item.get("member_level") or "")
        item["status_label"] = {"pending": "待审核", "active": "有效", "inactive": "无效", "suspended": "已暂停", "exited": "已退出"}.get(item.get("status"), item.get("status") or "")
        results.append(item)
    
    return results


def is_membership_owned_by_user(user_id: int, membership_id: int, db_path: str | Path | None = None) -> bool:
    with db_connection(_path(db_path)) as conn:
        row = conn.execute(
            "SELECT 1 FROM v04f_club_memberships WHERE id=? AND user_id=?",
            (membership_id, user_id)
        ).fetchone()
        return row is not None


def bind_user(membership_id: int, user_id: int, reason: str, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        
        membership = _membership(conn, membership_id)
        if not membership:
            raise MembershipUserLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        user = _user(conn, user_id)
        if not user:
            raise MembershipUserLinkError(404, "USER_NOT_FOUND", "用户不存在")
        
        old_user_id = membership.get("user_id")
        if old_user_id == user_id:
            return get_link_info(membership_id, db_path=path)
        
        if old_user_id:
            raise MembershipUserLinkError(409, "ALREADY_LINKED_TO_OTHER", "该会员已关联其他账号")
        
        conn.execute("UPDATE v04f_club_memberships SET user_id=?,updated_at=? WHERE id=?", (user_id, ts, membership_id))
        
        _record_audit(conn, "bind_user", membership_id, user_id, old_user_id, actor, reason)
    
    return get_link_info(membership_id, db_path=path)


def unbind_user(membership_id: int, reason: str, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        
        membership = _membership(conn, membership_id)
        if not membership:
            raise MembershipUserLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        old_user_id = membership.get("user_id")
        if not old_user_id:
            raise MembershipUserLinkError(409, "NOT_LINKED", "该会员尚未关联账号")
        
        conn.execute("UPDATE v04f_club_memberships SET user_id=NULL,updated_at=? WHERE id=?", (ts, membership_id))
        
        _record_audit(conn, "unbind_user", membership_id, None, old_user_id, actor, reason)
    
    return get_link_info(membership_id, db_path=path)


def request_membership_link(user_id: int, membership_id: int, reason: str, db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        
        user = _user(conn, user_id)
        if not user:
            raise MembershipUserLinkError(404, "USER_NOT_FOUND", "用户不存在")
        
        membership = _membership(conn, membership_id)
        if not membership:
            raise MembershipUserLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        if membership.get("user_id") == user_id:
            raise MembershipUserLinkError(409, "ALREADY_LINKED", "该会员已关联当前账号")
        
        if membership.get("user_id"):
            raise MembershipUserLinkError(409, "ALREADY_LINKED_TO_OTHER", "该会员已关联其他账号")
        
        existing_pending = conn.execute(
            "SELECT id FROM membership_user_link_requests WHERE user_id=? AND membership_id=? AND status='pending'",
            (user_id, membership_id)
        ).fetchone()
        if existing_pending:
            raise MembershipUserLinkError(409, "DUPLICATE_REQUEST", "已有待审核的绑定申请")
        
        request_no = _next_request_no(conn)
        cur = conn.execute(
            """
            INSERT INTO membership_user_link_requests(request_no,user_id,membership_id,reason,status,created_at,updated_at)
            VALUES (?,?,?,?, 'pending', ?, ?)
            """,
            (request_no, user_id, membership_id, reason or None, ts, ts),
        )
        request_id = cur.lastrowid
        
        _record_audit(conn, "request_link", membership_id, user_id, None, user["username"], reason, request_id)
    
    return get_link_request(request_id, db_path=path)


def get_link_request(request_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(_path(db_path)) as conn:
        row = conn.execute(
            """
            SELECT r.*, u.username, u.display_name, m.member_no, m.member_level, m.status
            FROM membership_user_link_requests r
            JOIN v05a_users u ON u.id=r.user_id
            JOIN v04f_club_memberships m ON m.id=r.membership_id
            WHERE r.id=?
            """,
            (request_id,)
        ).fetchone()
        if not row:
            raise MembershipUserLinkError(404, "REQUEST_NOT_FOUND", "申请不存在")
        
        result = dict(row)
        result["status_label"] = {"pending": "待审核", "approved": "已通过", "rejected": "已拒绝", "cancelled": "已取消"}.get(result.get("status"), result.get("status") or "")
        return result


def approve_membership_link(request_id: int, reviewer: dict[str, Any], db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        
        req = conn.execute("SELECT * FROM membership_user_link_requests WHERE id=?", (request_id,)).fetchone()
        if not req:
            raise MembershipUserLinkError(404, "REQUEST_NOT_FOUND", "申请不存在")
        
        req_dict = dict(req)
        if req_dict["status"] != "pending":
            raise MembershipUserLinkError(409, "REQUEST_NOT_PENDING", "申请状态不是待审核")
        
        membership = _membership(conn, req_dict["membership_id"])
        if not membership:
            raise MembershipUserLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        if membership.get("user_id"):
            raise MembershipUserLinkError(409, "ALREADY_LINKED_TO_OTHER", "该会员已关联其他账号")
        
        conn.execute("UPDATE v04f_club_memberships SET user_id=?,updated_at=? WHERE id=?", (req_dict["user_id"], ts, req_dict["membership_id"]))
        
        conn.execute("UPDATE membership_user_link_requests SET status='approved', reviewed_by=?, reviewed_at=?, updated_at=? WHERE id=?", 
                     (reviewer.get("username"), ts, ts, request_id))
        
        _record_audit(conn, "approve_link", req_dict["membership_id"], req_dict["user_id"], None, reviewer.get("username"), "管理员批准", request_id)
    
    return get_link_info(req_dict["membership_id"], db_path=path)


def reject_membership_link(request_id: int, reason: str, reviewer: dict[str, Any], db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        
        req = conn.execute("SELECT * FROM membership_user_link_requests WHERE id=?", (request_id,)).fetchone()
        if not req:
            raise MembershipUserLinkError(404, "REQUEST_NOT_FOUND", "申请不存在")
        
        req_dict = dict(req)
        if req_dict["status"] != "pending":
            raise MembershipUserLinkError(409, "REQUEST_NOT_PENDING", "申请状态不是待审核")
        
        conn.execute("UPDATE membership_user_link_requests SET status='rejected', reviewed_by=?, reviewed_at=?, review_note=?, updated_at=? WHERE id=?", 
                     (reviewer.get("username"), ts, reason, ts, request_id))
        
        _record_audit(conn, "reject_link", req_dict["membership_id"], req_dict["user_id"], None, reviewer.get("username"), reason, request_id)
    
    return get_link_request(request_id, db_path=path)


def list_link_audit(membership_id: int | None = None, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        params: list[Any] = []
        where = ""
        if membership_id:
            where = "WHERE membership_id=?"
            params.append(membership_id)
        
        rows = conn.execute(
            f"""
            SELECT * FROM membership_user_link_audit
            {where}
            ORDER BY created_at DESC
            LIMIT 50
            """,
            params,
        ).fetchall()
    
    results = []
    for row in rows:
        item = dict(row)
        results.append(item)
    
    return results