from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.security import permissions_for
from app.services.membership_access_service import MembershipAccessError, get_accessible_membership_or_403, get_accessible_memberships
from app.services.organization_access_service import OrganizationAccessError, get_accessible_organization_or_403, get_user_organizations
from app.v04c_review import db_connection, default_db_path


class AuthorizationError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class AuthorizationContext:
    user_id: int
    is_authenticated: bool
    is_system_admin: bool
    active_organization_id: int | None
    active_membership_id: int | None
    organization_role_keys: tuple[str, ...]
    permission_keys: tuple[str, ...]
    available_data_scopes: tuple[str, ...]
    accessible_organization_ids: tuple[int, ...]
    accessible_membership_ids: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "is_authenticated": self.is_authenticated,
            "is_system_admin": self.is_system_admin,
            "active_organization_id": self.active_organization_id,
            "active_membership_id": self.active_membership_id,
            "roles": list(self.organization_role_keys),
            "permissions": list(self.permission_keys),
            "data_scopes": list(self.available_data_scopes),
            "accessible_organization_ids": list(self.accessible_organization_ids),
            "accessible_membership_ids": list(self.accessible_membership_ids),
        }


def _path(db_path: str | Path | None) -> Path:
    return Path(db_path) if db_path else default_db_path()


def _user_id(user: dict[str, Any] | None) -> int:
    if not user or user.get("id") is None:
        raise AuthorizationError(401, "AUTH_REQUIRED", "请先登录")
    return int(user["id"])


def _is_system_admin(user: dict[str, Any] | None, db_path: str | Path | None = None) -> bool:
    if not user:
        return False
    if str(user.get("role")) == "admin" or "manage_club" in permissions_for(user):
        return True
    uid = int(user["id"])
    with db_connection(_path(db_path)) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM auth_user_roles ur
            JOIN auth_roles r ON r.id=ur.role_id
            WHERE ur.user_id=? AND ur.status='active' AND r.role_key='system_admin' AND r.status='active'
            """,
            (uid,),
        ).fetchone()
    return row is not None


def _audit(conn, actor_user_id: int | None, action: str, *, organization_id: int | None = None, target_user_id: int | None = None, role_id: int | None = None, role_key: str | None = None, before: Any = None, after: Any = None, result: str = "success", reason: str | None = None) -> None:
    try:
        conn.execute(
            """
            INSERT INTO authorization_audit_logs(actor_user_id,action,organization_id,target_user_id,role_id,role_key,before_json,after_json,result,reason,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))
            """,
            (
                actor_user_id,
                action,
                organization_id,
                target_user_id,
                role_id,
                role_key,
                json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
                json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
                result,
                reason,
            ),
        )
    except Exception:
        pass


def _role_by_key(conn, role_key: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM auth_roles WHERE role_key=? AND status='active'", (role_key,)).fetchone()
    return dict(row) if row else None


def _role_permissions(conn, role_keys: list[str]) -> set[str]:
    if not role_keys:
        return set()
    marks = ",".join("?" for _ in role_keys)
    rows = conn.execute(
        f"""
        SELECT DISTINCT p.permission_key
        FROM auth_roles r
        JOIN auth_role_permissions rp ON rp.role_id=r.id
        JOIN auth_permissions p ON p.id=rp.permission_id
        WHERE r.role_key IN ({marks}) AND r.status='active' AND p.status='active'
        """,
        role_keys,
    ).fetchall()
    return {str(row["permission_key"]) for row in rows}


def get_accessible_organization_ids(user: dict[str, Any] | None, db_path: str | Path | None = None) -> list[int]:
    uid = _user_id(user)
    return [int(item["organization_id"]) for item in get_user_organizations(uid, db_path)]


def get_accessible_membership_ids(user: dict[str, Any] | None, db_path: str | Path | None = None) -> list[int]:
    return [int(item["membership_id"]) for item in get_accessible_memberships(user, db_path)]


def _organization_roles(user_id: int, organization_id: int | None, db_path: str | Path | None = None) -> list[str]:
    if organization_id is None:
        return []
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT r.role_key
            FROM organization_user_roles ur
            JOIN auth_roles r ON r.id=ur.role_id
            JOIN organization_user_links l ON l.organization_id=ur.organization_id AND l.user_id=ur.user_id AND l.status='active'
            JOIN organizations o ON o.id=ur.organization_id
            WHERE ur.user_id=? AND ur.organization_id=? AND ur.status='active'
              AND r.status='active' AND r.is_system_role=0
              AND COALESCE(o.status, CASE WHEN COALESCE(o.is_active,1)=1 THEN 'active' ELSE 'inactive' END)='active'
            ORDER BY r.role_level DESC,r.role_key
            """,
            (user_id, organization_id),
        ).fetchall()
    return [str(row["role_key"]) for row in rows]


def build_authorization_context(user: dict[str, Any] | None, *, organization_id: int | None = None, membership_id: int | None = None, db_path: str | Path | None = None) -> AuthorizationContext:
    uid = _user_id(user)
    is_system_admin = _is_system_admin(user, db_path)
    org_ids = get_accessible_organization_ids(user, db_path)
    membership_ids = get_accessible_membership_ids(user, db_path)
    active_org_id = None
    if organization_id is not None:
        try:
            get_accessible_organization_or_403(user, organization_id, db_path, allow_admin=is_system_admin)
        except OrganizationAccessError as exc:
            raise AuthorizationError(exc.status_code, exc.code, exc.message) from exc
        active_org_id = int(organization_id)
    elif org_ids:
        active_org_id = org_ids[0]
    active_membership_id = None
    if membership_id is not None:
        try:
            get_accessible_membership_or_403(user, membership_id, db_path)
        except MembershipAccessError as exc:
            raise AuthorizationError(exc.status_code, exc.code, exc.message) from exc
        active_membership_id = int(membership_id)
    elif membership_ids:
        active_membership_id = membership_ids[0]
    role_keys: list[str] = []
    if is_system_admin:
        role_keys.append("system_admin")
    role_keys.extend(_organization_roles(uid, active_org_id, db_path))
    with db_connection(_path(db_path)) as conn:
        permission_keys = _role_permissions(conn, role_keys)
    if is_system_admin:
        permission_keys.add("platform:manage")
    data_scopes = {"public", "own"}
    if is_system_admin:
        data_scopes.add("platform")
    if active_org_id is not None:
        data_scopes.add("organization")
    if active_membership_id is not None:
        data_scopes.add("membership")
    return AuthorizationContext(
        user_id=uid,
        is_authenticated=True,
        is_system_admin=is_system_admin,
        active_organization_id=active_org_id,
        active_membership_id=active_membership_id,
        organization_role_keys=tuple(dict.fromkeys(role_keys)),
        permission_keys=tuple(sorted(permission_keys)),
        available_data_scopes=tuple(sorted(data_scopes)),
        accessible_organization_ids=tuple(org_ids),
        accessible_membership_ids=tuple(membership_ids),
    )


def has_permission(ctx: AuthorizationContext, permission_key: str, *, organization_id: int | None = None, data_scope: str | None = None) -> bool:
    if ctx.is_system_admin and (permission_key == "platform:manage" or permission_key in ctx.permission_keys):
        return True
    if permission_key not in ctx.permission_keys:
        return False
    if organization_id is not None and organization_id != ctx.active_organization_id:
        return False
    if data_scope and data_scope not in ctx.available_data_scopes:
        return False
    return True


def require_permission(ctx: AuthorizationContext, permission_key: str, *, organization_id: int | None = None, data_scope: str | None = None) -> None:
    if not has_permission(ctx, permission_key, organization_id=organization_id, data_scope=data_scope):
        raise AuthorizationError(403, "FORBIDDEN", "当前账号没有所需权限")


def require_any_permission(ctx: AuthorizationContext, permission_keys: list[str], *, organization_id: int | None = None, data_scope: str | None = None) -> None:
    if not any(has_permission(ctx, p, organization_id=organization_id, data_scope=data_scope) for p in permission_keys):
        raise AuthorizationError(403, "FORBIDDEN", "当前账号没有任一所需权限")


def require_system_permission(ctx: AuthorizationContext, permission_key: str = "platform:manage") -> None:
    if not ctx.is_system_admin or permission_key not in ctx.permission_keys:
        raise AuthorizationError(403, "FORBIDDEN", "需要系统级权限")


def require_organization_permission(ctx: AuthorizationContext, organization_id: int, permission_key: str) -> None:
    require_permission(ctx, permission_key, organization_id=organization_id, data_scope="organization")


def resolve_data_scope(ctx: AuthorizationContext, preferred: str) -> str:
    if preferred in ctx.available_data_scopes:
        return preferred
    raise AuthorizationError(403, "FORBIDDEN", "当前账号没有所需数据范围")


def list_roles_for_actor(user: dict[str, Any], *, organization_id: int | None = None, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    ctx = build_authorization_context(user, organization_id=organization_id, db_path=db_path)
    with db_connection(_path(db_path)) as conn:
        if ctx.is_system_admin:
            rows = conn.execute("SELECT * FROM auth_roles WHERE status='active' ORDER BY is_system_role DESC,role_level DESC").fetchall()
        else:
            require_organization_permission(ctx, int(organization_id or ctx.active_organization_id or 0), "organization:manage_roles")
            rows = conn.execute("SELECT * FROM auth_roles WHERE status='active' AND is_system_role=0 ORDER BY role_level DESC").fetchall()
    return [dict(row) for row in rows]


def list_permissions_for_actor(user: dict[str, Any], *, organization_id: int | None = None, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    ctx = build_authorization_context(user, organization_id=organization_id, db_path=db_path)
    if not ctx.is_system_admin and "organization:manage_roles" not in ctx.permission_keys:
        raise AuthorizationError(403, "FORBIDDEN", "需要角色管理权限")
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute("SELECT * FROM auth_permissions WHERE status='active' ORDER BY resource_key,action_key").fetchall()
    return [dict(row) for row in rows]


def _ensure_org_member(conn, organization_id: int, user_id: int) -> None:
    row = conn.execute("SELECT 1 FROM organization_user_links WHERE organization_id=? AND user_id=? AND status='active'", (organization_id, user_id)).fetchone()
    if not row:
        raise AuthorizationError(409, "USER_NOT_ORG_MEMBER", "目标用户不是该组织有效成员")


def can_assign_role(actor: dict[str, Any], organization_id: int, role_key: str, *, db_path: str | Path | None = None) -> bool:
    try:
        ctx = build_authorization_context(actor, organization_id=organization_id, db_path=db_path)
        with db_connection(_path(db_path)) as conn:
            role = _role_by_key(conn, role_key)
        if not role:
            return False
        if ctx.is_system_admin:
            return True
        if role["is_system_role"]:
            return False
        return has_permission(ctx, "organization:manage_roles", organization_id=organization_id, data_scope="organization")
    except AuthorizationError:
        return False


def assign_organization_role(actor: dict[str, Any], organization_id: int, target_user_id: int, role_key: str, *, db_path: str | Path | None = None) -> dict[str, Any]:
    actor_id = int(actor["id"])
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        role = _role_by_key(conn, role_key)
        if not role:
            raise AuthorizationError(404, "ROLE_NOT_FOUND", "角色不存在")
        if not can_assign_role(actor, organization_id, role_key, db_path=db_path):
            _audit(conn, actor_id, "assign_organization_role_denied", organization_id=organization_id, target_user_id=target_user_id, role_id=role["id"], role_key=role_key, result="denied", reason="not_allowed")
            raise AuthorizationError(403, "FORBIDDEN", "不能分配该角色")
        _ensure_org_member(conn, organization_id, target_user_id)
        existing = conn.execute(
            "SELECT * FROM organization_user_roles WHERE organization_id=? AND user_id=? AND role_id=? AND status='active'",
            (organization_id, target_user_id, role["id"]),
        ).fetchone()
        if existing:
            return dict(existing)
        conn.execute(
            """
            INSERT INTO organization_user_roles(organization_id,user_id,role_id,status,assigned_by,assigned_at,created_at,updated_at)
            VALUES (?,?,?,'active',?,datetime('now'),datetime('now'),datetime('now'))
            """,
            (organization_id, target_user_id, role["id"], actor_id),
        )
        row = conn.execute("SELECT * FROM organization_user_roles WHERE organization_id=? AND user_id=? AND role_id=? AND status='active'", (organization_id, target_user_id, role["id"])).fetchone()
        _audit(conn, actor_id, "assign_organization_role", organization_id=organization_id, target_user_id=target_user_id, role_id=role["id"], role_key=role_key, after=dict(row))
    return dict(row)


def _active_org_admin_count(conn, organization_id: int) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM organization_user_roles ur
        JOIN auth_roles r ON r.id=ur.role_id
        JOIN organization_user_links l ON l.organization_id=ur.organization_id AND l.user_id=ur.user_id AND l.status='active'
        JOIN organizations o ON o.id=ur.organization_id
        WHERE ur.organization_id=? AND ur.status='active' AND r.role_key='organization_admin'
          AND COALESCE(o.status, CASE WHEN COALESCE(o.is_active,1)=1 THEN 'active' ELSE 'inactive' END)='active'
        """,
        (organization_id,),
    ).fetchone()
    return int(row["c"] if row else 0)


def revoke_organization_role(actor: dict[str, Any], organization_id: int, target_user_id: int, role_id: int, *, db_path: str | Path | None = None, force: bool = False) -> dict[str, Any]:
    actor_id = int(actor["id"])
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT ur.*,r.role_key FROM organization_user_roles ur JOIN auth_roles r ON r.id=ur.role_id WHERE ur.organization_id=? AND ur.user_id=? AND ur.role_id=? AND ur.status='active'", (organization_id, target_user_id, role_id)).fetchone()
        if not row:
            raise AuthorizationError(404, "ROLE_ASSIGNMENT_NOT_FOUND", "角色分配不存在")
        role_key = row["role_key"]
        if not force and role_key == "organization_admin" and _active_org_admin_count(conn, organization_id) <= 1:
            _audit(conn, actor_id, "revoke_organization_role_denied", organization_id=organization_id, target_user_id=target_user_id, role_id=role_id, role_key=role_key, before=dict(row), result="denied", reason="last_organization_admin")
            raise AuthorizationError(409, "LAST_ORGANIZATION_ADMIN", "不能撤销最后一个机构管理员")
        if not can_assign_role(actor, organization_id, role_key, db_path=db_path):
            raise AuthorizationError(403, "FORBIDDEN", "不能撤销该角色")
        conn.execute("UPDATE organization_user_roles SET status='revoked',revoked_by=?,revoked_at=datetime('now'),updated_at=datetime('now') WHERE id=?", (actor_id, row["id"]))
        _audit(conn, actor_id, "revoke_organization_role", organization_id=organization_id, target_user_id=target_user_id, role_id=role_id, role_key=role_key, before=dict(row), after={"status": "revoked"})
    return {"organization_id": organization_id, "user_id": target_user_id, "role_id": role_id, "status": "revoked"}


def list_user_roles(organization_id: int, user_id: int, actor: dict[str, Any], *, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    ctx = build_authorization_context(actor, organization_id=organization_id, db_path=db_path)
    if not ctx.is_system_admin:
        require_organization_permission(ctx, organization_id, "organization:manage_roles")
    with db_connection(_path(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT ur.id AS assignment_id,ur.organization_id,ur.user_id,ur.role_id,ur.status,ur.assigned_at,r.role_key,r.name,r.role_level,r.is_system_role
            FROM organization_user_roles ur
            JOIN auth_roles r ON r.id=ur.role_id
            WHERE ur.organization_id=? AND ur.user_id=? AND ur.status='active'
            ORDER BY r.role_level DESC,r.role_key
            """,
            (organization_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def filter_user_fields(user_data: dict[str, Any], ctx: AuthorizationContext) -> dict[str, Any]:
    data = dict(user_data)
    if not ctx.is_system_admin:
        data.pop("password_hash", None)
        data.pop("session_version", None)
        data.pop("failed_login_count", None)
        data.pop("locked_until", None)
    return data


def filter_person_fields(person_data: dict[str, Any], ctx: AuthorizationContext) -> dict[str, Any]:
    data = dict(person_data)
    if "person:view_contact" not in ctx.permission_keys and not ctx.is_system_admin:
        for key in ["mobile", "email", "wechat", "id_card", "private_contact"]:
            data.pop(key, None)
    return data


def filter_membership_fields(membership_data: dict[str, Any], ctx: AuthorizationContext) -> dict[str, Any]:
    data = dict(membership_data)
    if not ctx.is_system_admin and "person:view_contact" not in ctx.permission_keys:
        for key in ["mobile", "email", "wechat", "internal_note"]:
            data.pop(key, None)
    return data


def _active_system_admin_count(conn) -> int:
    legacy_admins = int(conn.execute("SELECT COUNT(*) FROM v05a_users WHERE role='admin' AND status='active'").fetchone()[0])
    rbac_admins = int(conn.execute(
        """
        SELECT COUNT(DISTINCT ur.user_id) FROM auth_user_roles ur
        JOIN auth_roles r ON r.id=ur.role_id
        JOIN v05a_users u ON u.id=ur.user_id
        WHERE ur.status='active' AND r.role_key='system_admin' AND u.status='active'
        """
    ).fetchone()[0])
    return legacy_admins + rbac_admins


def revoke_system_role(actor: dict[str, Any], target_user_id: int, role_id: int, *, db_path: str | Path | None = None) -> dict[str, Any]:
    actor_id = int(actor["id"])
    if not _is_system_admin(actor, db_path):
        raise AuthorizationError(403, "FORBIDDEN", "需要系统管理员权限")
    with db_connection(_path(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT ur.*,r.role_key FROM auth_user_roles ur
            JOIN auth_roles r ON r.id=ur.role_id
            WHERE ur.user_id=? AND ur.role_id=? AND ur.status='active'
            """,
            (target_user_id, role_id),
        ).fetchone()
        if not row:
            raise AuthorizationError(404, "ROLE_ASSIGNMENT_NOT_FOUND", "系统角色分配不存在")
        if row["role_key"] == "system_admin" and _active_system_admin_count(conn) <= 1:
            _audit(conn, actor_id, "revoke_system_role_denied", target_user_id=target_user_id, role_id=role_id, role_key=row["role_key"], before=dict(row), result="denied", reason="last_system_admin")
            raise AuthorizationError(409, "LAST_SYSTEM_ADMIN", "不能撤销最后一个系统管理员")
        conn.execute("UPDATE auth_user_roles SET status='revoked',revoked_by=?,revoked_at=datetime('now'),updated_at=datetime('now') WHERE id=?", (actor_id, row["id"]))
        _audit(conn, actor_id, "revoke_system_role", target_user_id=target_user_id, role_id=role_id, role_key=row["role_key"], before=dict(row), after={"status": "revoked"})
    return {"user_id": target_user_id, "role_id": role_id, "status": "revoked"}

