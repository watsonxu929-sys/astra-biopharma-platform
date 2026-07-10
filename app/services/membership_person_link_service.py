from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.security import record_audit
from app.v04c_review import db_connection, default_db_path

LINK_STATUS_LABELS = {
    "linked": "已绑定",
    "unlinked": "未绑定",
}


class MembershipPersonLinkError(ValueError):
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


def _person(conn: sqlite3.Connection, person_id: int) -> dict[str, Any] | None:
    return _dict(conn.execute("SELECT id,external_id,name,public_role,organization_network FROM people WHERE id=? AND COALESCE(is_active,1)=1", (person_id,)).fetchone())


def _contact(conn: sqlite3.Connection, membership_id: int) -> dict[str, Any] | None:
    return _dict(conn.execute("SELECT mobile,email,wechat FROM v05b_member_contacts WHERE membership_id=?", (membership_id,)).fetchone())


def _next_audit_no(conn: sqlite3.Connection) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04f_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES ('QBPLA', ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date, updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (stamp, now_iso()),
    ).fetchone()
    return f"QBPLA-{stamp}-{int(row['seq_value']):04d}"


def _record_audit(conn: sqlite3.Connection, action: str, membership_id: int, person_id: int | None, old_person_id: int | None, actor: str, reason: str, field_differences: dict[str, Any] | None = None):
    conn.execute(
        """
        INSERT INTO membership_person_link_audit(audit_no,action,membership_id,person_id,old_person_id,actor,reason,field_differences_json,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (_next_audit_no(conn), action, membership_id, person_id, old_person_id, actor, reason or None, json.dumps(field_differences, ensure_ascii=False) if field_differences else None, now_iso()),
    )


def _field_differences(membership: dict[str, Any], person: dict[str, Any], contact: dict[str, Any] | None) -> dict[str, Any]:
    differences: dict[str, Any] = {}
    
    membership_name = membership.get("member_role") or ""
    person_name = person.get("name") or ""
    
    if membership_name and person_name:
        name_match = str(membership_name).strip() == str(person_name).strip()
        differences["name"] = {
            "membership": membership_name,
            "person": person_name,
            "match": name_match,
            "status": "一致" if name_match else "存在差异",
        }
    
    membership_title = membership.get("member_role") or ""
    person_title = person.get("public_role") or ""
    
    if membership_title or person_title:
        title_match = str(membership_title).strip() == str(person_title).strip()
        differences["title"] = {
            "membership": membership_title or "缺失",
            "person": person_title or "缺失",
            "match": title_match,
            "status": "一致" if title_match else ("人物档案缺失" if not person_title else "存在差异"),
        }
    
    membership_org = membership.get("owner") or ""
    person_org = person.get("organization_network") or ""
    
    if membership_org or person_org:
        org_match = str(membership_org).strip() == str(person_org).strip()
        differences["organization"] = {
            "membership": membership_org or "缺失",
            "person": person_org or "缺失",
            "match": org_match,
            "status": "一致" if org_match else ("人物档案缺失" if not person_org else "存在差异"),
        }
    
    if contact:
        if contact.get("mobile"):
            differences["mobile"] = {
                "membership": contact["mobile"][:3] + "****" + contact["mobile"][-4:] if len(contact["mobile"]) >= 7 else contact["mobile"],
                "person": "不公开",
                "match": False,
                "status": "无法判断",
            }
        if contact.get("email"):
            email_parts = contact["email"].split("@")
            masked_email = email_parts[0][:2] + "****@" + email_parts[1] if len(email_parts) == 2 else contact["email"]
            differences["email"] = {
                "membership": masked_email,
                "person": "不公开",
                "match": False,
                "status": "无法判断",
            }
    
    return differences


def get_link_info(membership_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(_path(db_path)) as conn:
        membership = _membership(conn, membership_id)
        if not membership:
            raise MembershipPersonLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        person = None
        link_status = "unlinked"
        field_differences = {}
        
        if membership.get("person_id"):
            person = _person(conn, int(membership["person_id"]))
            link_status = "linked" if person else "unlinked"
            if person:
                contact = _contact(conn, membership_id)
                field_differences = _field_differences(membership, person, contact)
        
        return {
            "membership": {
                "id": membership["id"],
                "member_no": membership["member_no"],
                "member_level": membership.get("member_level"),
                "member_level_label": {"standard": "标准会员", "premium": "高级会员", "vip": "VIP会员", "founding": "创始会员"}.get(membership.get("member_level"), membership.get("member_level") or ""),
                "status": membership["status"],
                "status_label": {"pending": "待审核", "active": "有效", "inactive": "无效", "suspended": "已暂停", "exited": "已退出"}.get(membership["status"], membership["status"]),
                "joined_at": membership.get("joined_at"),
                "member_role": membership.get("member_role"),
            },
            "person": person,
            "link_status": link_status,
            "link_status_label": LINK_STATUS_LABELS.get(link_status, link_status),
            "field_differences": field_differences,
        }


def bind_person(membership_id: int, person_id: int, reason: str, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        
        membership = _membership(conn, membership_id)
        if not membership:
            raise MembershipPersonLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        person = _person(conn, person_id)
        if not person:
            raise MembershipPersonLinkError(404, "PERSON_NOT_FOUND", "人物档案不存在")
        
        old_person_id = membership.get("person_id")
        
        contact = _contact(conn, membership_id)
        field_differences = _field_differences(membership, person, contact)
        
        conn.execute("UPDATE v04f_club_memberships SET person_id=?,updated_at=? WHERE id=?", (person_id, ts, membership_id))
        
        _record_audit(conn, "bind_person", membership_id, person_id, old_person_id, actor, reason, field_differences)
    
    return get_link_info(membership_id, db_path=path)


def unbind_person(membership_id: int, reason: str, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    path = _path(db_path)
    ts = now_iso()
    
    with db_connection(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        
        membership = _membership(conn, membership_id)
        if not membership:
            raise MembershipPersonLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        old_person_id = membership.get("person_id")
        if not old_person_id:
            raise MembershipPersonLinkError(409, "NOT_LINKED", "该会员尚未绑定人物")
        
        conn.execute("UPDATE v04f_club_memberships SET person_id=NULL,updated_at=? WHERE id=?", (ts, membership_id))
        
        _record_audit(conn, "unbind_person", membership_id, None, old_person_id, actor, reason)
    
    return get_link_info(membership_id, db_path=path)


def get_person_candidates(membership_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        membership = _membership(conn, membership_id)
        if not membership:
            raise MembershipPersonLinkError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
        
        contact = _contact(conn, membership_id)
        member_name = membership.get("member_role") or ""
        member_org = membership.get("owner") or ""
        
        params: list[Any] = []
        conditions: list[str] = []
        
        if member_name:
            conditions.append("p.name LIKE ?")
            params.append(f"%{member_name}%")
        
        if contact and contact.get("mobile"):
            conditions.append("p.mobile LIKE ?")
            params.append(f"%{contact['mobile'][-8:]}%")
        
        if contact and contact.get("email"):
            conditions.append("p.email LIKE ?")
            params.append(f"%{contact['email']}%")
        
        if member_org:
            conditions.append("p.organization_network LIKE ?")
            params.append(f"%{member_org}%")
        
        if not conditions:
            return []
        
        sql = f"""
            SELECT p.id,p.external_id,p.name,p.public_role,p.organization_network,p.created_at,
                   COUNT(DISTINCT m.id) AS membership_count
            FROM people p
            LEFT JOIN v04f_club_memberships m ON m.person_id=p.id AND m.status IN ('pending','active','suspended')
            WHERE COALESCE(p.is_active,1)=1 AND ({' OR '.join(conditions)})
            GROUP BY p.id,p.external_id,p.name,p.public_role,p.organization_network,p.created_at
            ORDER BY p.created_at DESC
            LIMIT 20
        """
        
        rows = conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            match_basis = []
            match_score = 0
            
            if member_name and member_name in item["name"]:
                match_basis.append("姓名匹配")
                match_score += 30
            
            if contact and contact.get("mobile"):
                match_basis.append("手机号匹配")
                match_score += 40
            
            if contact and contact.get("email"):
                match_basis.append("邮箱匹配")
                match_score += 40
            
            if member_org and member_org in (item.get("organization_network") or ""):
                match_basis.append("机构匹配")
                match_score += 20
            
            item["match_basis"] = match_basis
            item["match_score"] = min(match_score, 100)
            
            if item["membership_count"] > 0:
                item["risk_level"] = "high"
                item["risk_label"] = "高风险（已有会员身份）"
            elif len(match_basis) == 1:
                item["risk_level"] = "medium"
                item["risk_label"] = "中风险（单一匹配依据）"
            else:
                item["risk_level"] = "low"
                item["risk_label"] = "低风险"
            
            results.append(item)
        
        results.sort(key=lambda x: x["match_score"], reverse=True)
        
        return results


def list_memberships_for_person(person_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT m.id,m.member_no,m.member_level,m.status,m.joined_at,m.created_at,
                   o.standard_name AS organization_name
            FROM v04f_club_memberships m
            LEFT JOIN organizations o ON o.id=m.organization_id
            WHERE m.person_id=?
            ORDER BY m.created_at DESC
            """,
            (person_id,),
        ).fetchall()
    
    results = []
    for row in rows:
        item = dict(row)
        item["member_level_label"] = {"standard": "标准会员", "premium": "高级会员", "vip": "VIP会员", "founding": "创始会员"}.get(item.get("member_level"), item.get("member_level") or "")
        item["status_label"] = {"pending": "待审核", "active": "有效", "inactive": "无效", "suspended": "已暂停", "exited": "已退出"}.get(item.get("status"), item.get("status") or "")
        results.append(item)
    
    return results


def list_link_audit(membership_id: int | None = None, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        params: list[Any] = []
        where = ""
        if membership_id:
            where = "WHERE membership_id=?"
            params.append(membership_id)
        
        rows = conn.execute(
            f"""
            SELECT * FROM membership_person_link_audit
            {where}
            ORDER BY created_at DESC
            LIMIT 50
            """,
            params,
        ).fetchall()
    
    results = []
    for row in rows:
        item = dict(row)
        if item.get("field_differences_json"):
            try:
                item["field_differences"] = json.loads(item["field_differences_json"])
            except json.JSONDecodeError:
                item["field_differences"] = {}
        else:
            item["field_differences"] = {}
        results.append(item)
    
    return results
