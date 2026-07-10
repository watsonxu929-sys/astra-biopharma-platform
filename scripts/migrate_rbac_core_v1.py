from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path
DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"

BUILTIN_ROLES = [
    ("system_admin", "系统管理员", "全平台系统管理角色", 100, 1, 1, "active"),
    ("platform_operator", "平台运营人员", "平台运营和业务审核角色", 80, 1, 1, "active"),
    ("organization_admin", "机构管理员", "管理本组织成员、角色和组织数据", 60, 1, 0, "active"),
    ("organization_editor", "机构业务人员", "编辑本组织业务数据", 40, 1, 0, "active"),
    ("organization_member", "机构普通成员", "查看和使用本组织授权数据", 20, 1, 0, "active"),
    ("organization_viewer", "机构只读成员", "只读查看本组织授权数据", 10, 1, 0, "active"),
]

PERMISSIONS = [
    ("platform:manage", "platform", "manage", "管理全平台", "系统级管理权限"),
    ("audit:view", "audit", "view", "查看审计", "查看安全审计记录"),
    ("role:manage", "role", "manage", "管理角色权限", "管理系统和组织角色"),
    ("organization:view", "organization", "view", "查看组织", "查看组织资料"),
    ("organization:update", "organization", "update", "维护组织", "修改组织资料"),
    ("organization:manage_members", "organization", "manage_members", "管理组织成员", "添加或移除组织成员"),
    ("organization:manage_roles", "organization", "manage_roles", "管理组织角色", "为组织成员分配角色"),
    ("membership:view", "membership", "view", "查看会员", "查看授权范围内的会员身份"),
    ("membership:update", "membership", "update", "维护会员", "修改授权范围内的会员身份"),
    ("membership:approve", "membership", "approve", "审核会员", "审核会员相关申请"),
    ("person:view", "person", "view", "查看人物", "查看授权范围内的人物档案"),
    ("person:update", "person", "update", "维护人物", "修改授权范围内的人物档案"),
    ("person:view_contact", "person", "view_contact", "查看联系方式", "查看授权范围内的敏感联系方式"),
    ("identity_link:review", "identity_link", "review", "审核身份关联", "审核账号与人物关联"),
    ("membership_link:review", "membership_link", "review", "审核会员关联", "审核账号与会员关联"),
    ("data:read", "data", "read", "读取数据", "读取授权范围内的数据"),
    ("data:write", "data", "write", "写入数据", "写入授权范围内的数据"),
]

ROLE_PERMISSIONS = {
    "system_admin": [p[0] for p in PERMISSIONS],
    "platform_operator": ["organization:view", "membership:view", "membership:approve", "identity_link:review", "membership_link:review", "data:read", "data:write"],
    "organization_admin": ["organization:view", "organization:update", "organization:manage_members", "organization:manage_roles", "membership:view", "membership:update", "person:view", "person:view_contact", "data:read", "data:write"],
    "organization_editor": ["organization:view", "membership:view", "person:view", "data:read", "data:write"],
    "organization_member": ["organization:view", "membership:view", "person:view", "data:read"],
    "organization_viewer": ["organization:view", "data:read"],
}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _backup(db_path: Path) -> str:
    if not db_path.exists():
        return ""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"app_before_rbac_core_v1_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(db_path, target)
    return str(target)


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = _backup(db_path) if backup else ""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS auth_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                role_level INTEGER NOT NULL DEFAULT 0,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                is_system_role INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK(status IN ('active','inactive','archived'))
            );
            CREATE TABLE IF NOT EXISTS auth_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_key TEXT NOT NULL UNIQUE,
                resource_key TEXT NOT NULL,
                action_key TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK(status IN ('active','inactive','archived'))
            );
            CREATE TABLE IF NOT EXISTS auth_role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT,
                UNIQUE(role_id, permission_id),
                FOREIGN KEY(role_id) REFERENCES auth_roles(id),
                FOREIGN KEY(permission_id) REFERENCES auth_permissions(id)
            );
            CREATE TABLE IF NOT EXISTS auth_user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                assigned_by INTEGER,
                assigned_at TEXT NOT NULL,
                revoked_by INTEGER,
                revoked_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, role_id, status),
                FOREIGN KEY(user_id) REFERENCES v05a_users(id),
                FOREIGN KEY(role_id) REFERENCES auth_roles(id)
            );
            CREATE INDEX IF NOT EXISTS ix_auth_user_roles_user_status ON auth_user_roles(user_id,status);
            CREATE TABLE IF NOT EXISTS organization_user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                assigned_by INTEGER,
                assigned_at TEXT NOT NULL,
                revoked_by INTEGER,
                revoked_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK(status IN ('active','revoked','inactive')),
                FOREIGN KEY(organization_id) REFERENCES organizations(id),
                FOREIGN KEY(user_id) REFERENCES v05a_users(id),
                FOREIGN KEY(role_id) REFERENCES auth_roles(id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_org_user_role_active
            ON organization_user_roles(organization_id,user_id,role_id)
            WHERE status='active';
            CREATE INDEX IF NOT EXISTS ix_org_user_roles_org_user_status ON organization_user_roles(organization_id,user_id,status);
            CREATE INDEX IF NOT EXISTS ix_org_user_roles_user_status ON organization_user_roles(user_id,status);
            CREATE TABLE IF NOT EXISTS authorization_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                action TEXT NOT NULL,
                organization_id INTEGER,
                target_user_id INTEGER,
                role_id INTEGER,
                role_key TEXT,
                before_json TEXT,
                after_json TEXT,
                result TEXT NOT NULL DEFAULT 'success',
                reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_authorization_audit_org ON authorization_audit_logs(organization_id,created_at DESC);
            CREATE INDEX IF NOT EXISTS ix_authorization_audit_actor ON authorization_audit_logs(actor_user_id,created_at DESC);
            """
        )
        ts = now_iso()
        for role in BUILTIN_ROLES:
            conn.execute(
                """
                INSERT INTO auth_roles(role_key,name,description,role_level,is_builtin,is_system_role,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(role_key) DO UPDATE SET
                  name=excluded.name, description=excluded.description, role_level=excluded.role_level,
                  is_builtin=excluded.is_builtin, is_system_role=excluded.is_system_role,
                  status=excluded.status, updated_at=excluded.updated_at
                """,
                (*role, ts, ts),
            )
        for permission in PERMISSIONS:
            conn.execute(
                """
                INSERT INTO auth_permissions(permission_key,resource_key,action_key,name,description,status,created_at,updated_at)
                VALUES (?,?,?,?,?,'active',?,?)
                ON CONFLICT(permission_key) DO UPDATE SET
                  resource_key=excluded.resource_key, action_key=excluded.action_key,
                  name=excluded.name, description=excluded.description, status='active', updated_at=excluded.updated_at
                """,
                (*permission, ts, ts),
            )
        role_ids = {r["role_key"]: r["id"] for r in conn.execute("SELECT id,role_key FROM auth_roles").fetchall()}
        perm_ids = {p["permission_key"]: p["id"] for p in conn.execute("SELECT id,permission_key FROM auth_permissions").fetchall()}
        for role_key, permission_keys in ROLE_PERMISSIONS.items():
            for permission_key in permission_keys:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO auth_role_permissions(role_id,permission_id,created_at,created_by)
                    VALUES (?,?,?, 'migrate_rbac_core_v1')
                    """,
                    (role_ids[role_key], perm_ids[permission_key], ts),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("RBAC core migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

