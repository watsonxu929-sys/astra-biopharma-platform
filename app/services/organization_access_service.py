from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.security import permissions_for
from app.v04c_review import db_connection, default_db_path


class OrganizationAccessError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


ACTIVE_LINK_STATUS = "active"
ACTIVE_ORG_STATUS = {"active"}
ORG_TYPE_VALUES = {
    "company", "institution", "government", "park", "association", "university",
    "research_institute", "investment_institution", "service_provider", "other",
}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _path(db_path: str | Path | None) -> Path:
    return Path(db_path) if db_path else default_db_path()


def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _is_admin(user: dict[str, Any] | None) -> bool:
    if not user:
        return False
    perms = permissions_for(user)
    return "manage_club" in perms or "manage_users" in perms


def require_organization_admin(user: dict[str, Any] | None) -> None:
    if not _is_admin(user):
        raise OrganizationAccessError(403, "FORBIDDEN", "需要组织管理权限")


def _user_id(user: dict[str, Any] | None) -> int | None:
    if not user or user.get("id") is None:
        return None
    return int(user["id"])


def _next_org_no(conn: sqlite3.Connection) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04f_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES ('ORGCORE', ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date, updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (stamp, now_iso()),
    ).fetchone()
    return f"ORG-{stamp}-{int(row['seq_value']):04d}"


def _audit(conn: sqlite3.Connection, actor_user_id: int | None, action: str, organization_id: int | None, *, target_user_id: int | None = None, membership_id: int | None = None, before: Any = None, after: Any = None) -> None:
    try:
        conn.execute(
            """
            INSERT INTO organization_access_audit(actor_user_id,action,organization_id,target_user_id,membership_id,before_json,after_json,created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                actor_user_id,
                action,
                organization_id,
                target_user_id,
                membership_id,
                json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
                json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
                now_iso(),
            ),
        )
    except sqlite3.Error:
        # 审计失败不破坏主事务；调用方仍可从业务错误中定位。
        pass


def _organization_select(where_sql: str = "", order_sql: str = "ORDER BY o.id DESC") -> str:
    return f"""
        SELECT
            o.id AS organization_id,
            o.id AS id,
            COALESCE(o.organization_no,o.external_id) AS organization_no,
            o.external_id,
            COALESCE(o.name,o.standard_name) AS name,
            o.standard_name,
            o.short_name,
            COALESCE(o.organization_type,o.org_type,'company') AS organization_type,
            o.org_type,
            o.unified_social_credit_code,
            COALESCE(o.status, CASE WHEN COALESCE(o.is_active,1)=1 THEN 'active' ELSE 'inactive' END) AS status,
            o.source,
            o.description,
            o.region,
            o.industry_tags,
            o.created_at,
            o.updated_at,
            o.disabled_at,
            o.is_active,
            l.is_primary,
            l.status AS link_status,
            l.joined_at,
            l.left_at
        FROM organizations o
        LEFT JOIN organization_user_links l ON l.organization_id=o.id AND l.status='active'
        {where_sql}
        {order_sql}
    """


def _summary(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    return {
        "organization_id": item.get("organization_id") or item.get("id"),
        "id": item.get("organization_id") or item.get("id"),
        "organization_no": item.get("organization_no") or item.get("external_id"),
        "external_id": item.get("external_id"),
        "name": item.get("name") or item.get("standard_name"),
        "standard_name": item.get("standard_name") or item.get("name"),
        "short_name": item.get("short_name"),
        "organization_type": item.get("organization_type") or item.get("org_type") or "company",
        "organization_type_label": _type_label(item.get("organization_type") or item.get("org_type") or "company"),
        "status": item.get("status") or "active",
        "status_label": {"active": "有效", "inactive": "无效", "archived": "已归档"}.get(str(item.get("status") or "active"), str(item.get("status") or "")),
        "unified_social_credit_code": item.get("unified_social_credit_code"),
        "region": item.get("region"),
        "industry_tags": item.get("industry_tags"),
        "is_primary": bool(item.get("is_primary")),
        "link_status": item.get("link_status"),
        "joined_at": item.get("joined_at"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def _type_label(value: str) -> str:
    labels = {
        "company": "企业",
        "institution": "机构",
        "government": "政府部门",
        "park": "园区",
        "association": "协会",
        "university": "高校",
        "research_institute": "科研院所",
        "investment_institution": "投资机构",
        "service_provider": "服务机构",
        "other": "其他",
    }
    return labels.get(value, value)


def _get_org(conn: sqlite3.Connection, organization_id: int) -> dict[str, Any] | None:
    row = conn.execute(_organization_select("WHERE o.id=?", ""), (organization_id,)).fetchone()
    return _summary(row) if row else None


def _ensure_org_active(org: dict[str, Any]) -> None:
    if org.get("status") not in ACTIVE_ORG_STATUS:
        raise OrganizationAccessError(409, "ORGANIZATION_INACTIVE", "组织已停用或归档")


def list_organizations(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute(_organization_select("", "ORDER BY o.id DESC")).fetchall()
    # LEFT JOIN user links may duplicate; collapse by id.
    seen: set[int] = set()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = _summary(row)
        if int(item["organization_id"]) not in seen:
            seen.add(int(item["organization_id"]))
            item["is_primary"] = False
            item["link_status"] = None
            items.append(item)
    return items


def get_user_organizations(user_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute(
            _organization_select("WHERE l.user_id=? AND l.status='active' AND COALESCE(o.status, CASE WHEN COALESCE(o.is_active,1)=1 THEN 'active' ELSE 'inactive' END)='active'", "ORDER BY l.is_primary DESC, l.joined_at ASC, o.id ASC"),
            (int(user_id),),
        ).fetchall()
    return [_summary(row) for row in rows]


def get_organization_context(user: dict[str, Any] | None, db_path: str | Path | None = None) -> dict[str, Any]:
    uid = _user_id(user)
    organizations = get_user_organizations(uid, db_path) if uid is not None else []
    default_id = organizations[0]["organization_id"] if organizations else None
    return {
        "has_organization": bool(organizations),
        "organization_count": len(organizations),
        "default_organization_id": default_id,
        "can_switch": len(organizations) > 1,
        "organizations": organizations,
    }


def get_accessible_organization(user: dict[str, Any] | None, organization_id: int, db_path: str | Path | None = None, *, allow_admin: bool = False) -> dict[str, Any] | None:
    with db_connection(_path(db_path)) as conn:
        org = _get_org(conn, organization_id)
        if not org:
            return None
        if allow_admin and _is_admin(user):
            return org
        uid = _user_id(user)
        if uid is None:
            return None
        row = conn.execute(
            """
            SELECT 1 FROM organization_user_links
            WHERE organization_id=? AND user_id=? AND status='active'
              AND (left_at IS NULL OR left_at='')
            """,
            (int(organization_id), uid),
        ).fetchone()
        if row and org.get("status") in ACTIVE_ORG_STATUS:
            return org
        return None


def get_accessible_organization_or_403(user: dict[str, Any] | None, organization_id: int, db_path: str | Path | None = None, *, allow_admin: bool = False) -> dict[str, Any]:
    org = get_accessible_organization(user, organization_id, db_path, allow_admin=allow_admin)
    if org:
        return org
    with db_connection(_path(db_path)) as conn:
        exists = conn.execute("SELECT 1 FROM organizations WHERE id=?", (int(organization_id),)).fetchone()
    if exists:
        raise OrganizationAccessError(403, "FORBIDDEN", "您无权访问该组织")
    raise OrganizationAccessError(404, "ORGANIZATION_NOT_FOUND", "组织不存在")


def create_organization(payload: dict[str, Any], actor: dict[str, Any] | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    name = str(payload.get("name") or payload.get("standard_name") or "").strip()
    if not name:
        raise OrganizationAccessError(422, "INVALID_ARGUMENT", "组织名称不能为空")
    org_type = str(payload.get("organization_type") or payload.get("org_type") or "company").strip() or "company"
    if org_type not in ORG_TYPE_VALUES:
        org_type = "other"
    ts = now_iso()
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        org_no = str(payload.get("organization_no") or "").strip() or _next_org_no(conn)
        credit_code = str(payload.get("unified_social_credit_code") or "").strip() or None
        if credit_code:
            exists = conn.execute("SELECT 1 FROM organizations WHERE unified_social_credit_code=?", (credit_code,)).fetchone()
            if exists:
                raise OrganizationAccessError(409, "DUPLICATE_CREDIT_CODE", "统一社会信用代码已存在")
        try:
            cur = conn.execute(
                """
                INSERT INTO organizations(external_id,organization_no,standard_name,name,short_name,org_type,organization_type,unified_social_credit_code,status,source,description,visibility,verification_status,is_active,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
                """,
                (
                    org_no,
                    org_no,
                    name,
                    name,
                    str(payload.get("short_name") or "").strip() or None,
                    org_type,
                    org_type,
                    credit_code,
                    str(payload.get("status") or "active"),
                    str(payload.get("source") or "manual"),
                    str(payload.get("description") or "").strip() or None,
                    "内部",
                    "已确认",
                    ts,
                    ts,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise OrganizationAccessError(409, "DUPLICATE_ORGANIZATION", "组织编号或信用代码已存在") from exc
        org = _get_org(conn, int(cur.lastrowid))
        _audit(conn, _user_id(actor), "create_organization", int(cur.lastrowid), after=org)
    return org or {}


def update_organization(organization_id: int, payload: dict[str, Any], actor: dict[str, Any] | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    allowed = {"name", "short_name", "organization_type", "unified_social_credit_code", "status", "source", "description"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise OrganizationAccessError(422, "INVALID_ARGUMENT", "没有可更新字段")
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        before = _get_org(conn, organization_id)
        if not before:
            raise OrganizationAccessError(404, "ORGANIZATION_NOT_FOUND", "组织不存在")
        if updates.get("unified_social_credit_code"):
            exists = conn.execute("SELECT 1 FROM organizations WHERE unified_social_credit_code=? AND id<>?", (updates["unified_social_credit_code"], organization_id)).fetchone()
            if exists:
                raise OrganizationAccessError(409, "DUPLICATE_CREDIT_CODE", "统一社会信用代码已存在")
        sets: list[str] = []
        values: list[Any] = []
        if "name" in updates:
            sets.extend(["name=?", "standard_name=?"])
            values.extend([str(updates["name"]).strip(), str(updates["name"]).strip()])
        for key in ["short_name", "organization_type", "unified_social_credit_code", "status", "source", "description"]:
            if key in updates:
                sets.append(f"{key}=?")
                values.append(str(updates[key]).strip() or None)
                if key == "organization_type":
                    sets.append("org_type=?")
                    values.append(str(updates[key]).strip() or None)
                if key == "status":
                    sets.append("is_active=?")
                    values.append(1 if updates[key] == "active" else 0)
                    sets.append("disabled_at=?")
                    values.append(now_iso() if updates[key] != "active" else None)
        sets.append("updated_at=?")
        values.append(now_iso())
        values.append(organization_id)
        try:
            conn.execute(f"UPDATE organizations SET {', '.join(sets)} WHERE id=?", values)
        except sqlite3.IntegrityError as exc:
            raise OrganizationAccessError(409, "DUPLICATE_ORGANIZATION", "组织编号或信用代码已存在") from exc
        after = _get_org(conn, organization_id)
        _audit(conn, _user_id(actor), "update_organization", organization_id, before=before, after=after)
    return after or {}


def bind_user_to_organization(organization_id: int, user_id: int, *, is_primary: bool = False, source: str = "manual", actor: dict[str, Any] | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    ts = now_iso()
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        org = _get_org(conn, organization_id)
        if not org:
            raise OrganizationAccessError(404, "ORGANIZATION_NOT_FOUND", "组织不存在")
        _ensure_org_active(org)
        if not conn.execute("SELECT 1 FROM v05a_users WHERE id=?", (int(user_id),)).fetchone():
            raise OrganizationAccessError(404, "USER_NOT_FOUND", "用户不存在")
        existing = conn.execute("SELECT * FROM organization_user_links WHERE organization_id=? AND user_id=? AND status='active'", (organization_id, user_id)).fetchone()
        has_any = conn.execute("SELECT 1 FROM organization_user_links WHERE user_id=? AND status='active'", (user_id,)).fetchone()
        make_primary = bool(is_primary) or not bool(has_any)
        if existing:
            row = dict(existing)
            if make_primary and not row.get("is_primary"):
                conn.execute("UPDATE organization_user_links SET is_primary=0,updated_at=? WHERE user_id=? AND status='active'", (ts, user_id))
                conn.execute("UPDATE organization_user_links SET is_primary=1,updated_at=? WHERE id=?", (ts, row["id"]))
                _audit(conn, _user_id(actor), "set_primary_organization", organization_id, target_user_id=user_id, before=row, after={**row, "is_primary": 1})
            else:
                raise OrganizationAccessError(409, "DUPLICATE_LINK", "用户已加入该组织")
        else:
            if make_primary:
                conn.execute("UPDATE organization_user_links SET is_primary=0,updated_at=? WHERE user_id=? AND status='active'", (ts, user_id))
            cur = conn.execute(
                """
                INSERT INTO organization_user_links(organization_id,user_id,status,is_primary,source,role_key,joined_at,created_by,created_at,updated_at)
                VALUES (?,?,'active',? ,?,'member',?,?,?,?)
                """,
                (organization_id, user_id, int(make_primary), source, ts, (actor or {}).get("username"), ts, ts),
            )
            _audit(conn, _user_id(actor), "bind_user_organization", organization_id, target_user_id=user_id, after={"link_id": cur.lastrowid, "is_primary": make_primary})
    return get_accessible_organization({"id": user_id, "role": "viewer"}, organization_id, db_path) or _get_org_with_path(organization_id, db_path)


def _get_org_with_path(organization_id: int, db_path: str | Path | None) -> dict[str, Any] | None:
    with db_connection(_path(db_path)) as conn:
        return _get_org(conn, organization_id)


def unbind_user_from_organization(organization_id: int, user_id: int, *, actor: dict[str, Any] | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    ts = now_iso()
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        link = conn.execute("SELECT * FROM organization_user_links WHERE organization_id=? AND user_id=? AND status='active'", (organization_id, user_id)).fetchone()
        if not link:
            raise OrganizationAccessError(404, "LINK_NOT_FOUND", "用户未加入该组织")
        before = dict(link)
        conn.execute("UPDATE organization_user_links SET status='removed',is_primary=0,left_at=?,updated_at=? WHERE id=?", (ts, ts, before["id"]))
        if before.get("is_primary"):
            replacement = conn.execute("SELECT id,organization_id FROM organization_user_links WHERE user_id=? AND status='active' ORDER BY joined_at ASC,id ASC LIMIT 1", (user_id,)).fetchone()
            if replacement:
                conn.execute("UPDATE organization_user_links SET is_primary=1,updated_at=? WHERE id=?", (ts, replacement["id"]))
        _audit(conn, _user_id(actor), "unbind_user_organization", organization_id, target_user_id=user_id, before=before, after={"status": "removed"})
    return {"organization_id": organization_id, "user_id": user_id, "status": "removed"}


def list_organization_memberships(organization_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(_path(db_path)) as conn:
        if not _get_org(conn, organization_id):
            raise OrganizationAccessError(404, "ORGANIZATION_NOT_FOUND", "组织不存在")
        rows = conn.execute(
            """
            SELECT l.*,m.member_no,m.member_level,m.status AS membership_status,p.name AS person_name
            FROM organization_membership_links l
            JOIN v04f_club_memberships m ON m.id=l.membership_id
            LEFT JOIN people p ON p.id=m.person_id
            WHERE l.organization_id=? AND l.status='active'
            ORDER BY l.linked_at DESC,l.id DESC
            """,
            (organization_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def bind_membership_to_organization(organization_id: int, membership_id: int, *, source: str = "manual", actor: dict[str, Any] | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    ts = now_iso()
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        org = _get_org(conn, organization_id)
        if not org:
            raise OrganizationAccessError(404, "ORGANIZATION_NOT_FOUND", "组织不存在")
        _ensure_org_active(org)
        if not conn.execute("SELECT 1 FROM v04f_club_memberships WHERE id=?", (membership_id,)).fetchone():
            raise OrganizationAccessError(404, "MEMBERSHIP_NOT_FOUND", "会员身份不存在")
        same = conn.execute("SELECT * FROM organization_membership_links WHERE organization_id=? AND membership_id=? AND status='active'", (organization_id, membership_id)).fetchone()
        if same:
            return dict(same)
        other = conn.execute("SELECT * FROM organization_membership_links WHERE membership_id=? AND status='active'", (membership_id,)).fetchone()
        if other:
            raise OrganizationAccessError(409, "MEMBERSHIP_ALREADY_LINKED", "该会员身份已归属于其他组织")
        cur = conn.execute(
            """
            INSERT INTO organization_membership_links(organization_id,membership_id,status,is_primary,source,linked_at,created_by,created_at,updated_at)
            VALUES (?,?,'active',1,?,?,?, ?,?)
            """,
            (organization_id, membership_id, source, ts, (actor or {}).get("username"), ts, ts),
        )
        _audit(conn, _user_id(actor), "bind_membership_organization", organization_id, membership_id=membership_id, after={"link_id": cur.lastrowid})
        row = conn.execute("SELECT * FROM organization_membership_links WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def unbind_membership_from_organization(organization_id: int, membership_id: int, *, actor: dict[str, Any] | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    ts = now_iso()
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        link = conn.execute("SELECT * FROM organization_membership_links WHERE organization_id=? AND membership_id=? AND status='active'", (organization_id, membership_id)).fetchone()
        if not link:
            raise OrganizationAccessError(404, "LINK_NOT_FOUND", "会员身份未归属该组织")
        before = dict(link)
        conn.execute("UPDATE organization_membership_links SET status='removed',is_primary=0,unlinked_at=?,updated_at=? WHERE id=?", (ts, ts, before["id"]))
        _audit(conn, _user_id(actor), "unbind_membership_organization", organization_id, membership_id=membership_id, before=before, after={"status": "removed"})
    return {"organization_id": organization_id, "membership_id": membership_id, "status": "removed"}
