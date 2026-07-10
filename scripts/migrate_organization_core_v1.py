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


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _index_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,)).fetchone() is not None


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _backup(db_path: Path) -> str:
    if not db_path.exists():
        return ""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"app_before_organization_core_v1_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(db_path, target)
    return str(target)


def _add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = _backup(db_path) if backup else ""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not _table_exists(conn, "organizations"):
            conn.execute(
                """
                CREATE TABLE organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    standard_name TEXT NOT NULL,
                    org_type TEXT,
                    region TEXT,
                    industry_tags TEXT,
                    resources TEXT,
                    needs TEXT,
                    relationship_source TEXT,
                    visibility TEXT DEFAULT '内部',
                    verification_status TEXT DEFAULT '待核验',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
        _add_column(conn, "organizations", "organization_no", "TEXT")
        _add_column(conn, "organizations", "name", "TEXT")
        _add_column(conn, "organizations", "short_name", "TEXT")
        _add_column(conn, "organizations", "organization_type", "TEXT")
        _add_column(conn, "organizations", "unified_social_credit_code", "TEXT")
        _add_column(conn, "organizations", "status", "TEXT")
        _add_column(conn, "organizations", "source", "TEXT")
        _add_column(conn, "organizations", "description", "TEXT")
        _add_column(conn, "organizations", "updated_at", "TEXT")
        _add_column(conn, "organizations", "disabled_at", "TEXT")
        ts = now_iso()
        conn.execute("UPDATE organizations SET organization_no=COALESCE(organization_no, external_id, 'ORG-' || printf('%06d', id))")
        conn.execute("UPDATE organizations SET name=COALESCE(NULLIF(name,''), standard_name)")
        conn.execute("UPDATE organizations SET organization_type=COALESCE(NULLIF(organization_type,''), org_type, 'company')")
        conn.execute("UPDATE organizations SET status=COALESCE(NULLIF(status,''), CASE WHEN COALESCE(is_active,1)=1 THEN 'active' ELSE 'inactive' END)")
        conn.execute("UPDATE organizations SET source=COALESCE(NULLIF(source,''), relationship_source)")
        conn.execute("UPDATE organizations SET updated_at=COALESCE(updated_at, created_at, ?)", (ts,))
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_organizations_organization_no ON organizations(organization_no)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_organizations_credit_code_not_empty ON organizations(unified_social_credit_code) WHERE unified_social_credit_code IS NOT NULL AND unified_social_credit_code<>''")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_organizations_status_type ON organizations(status, organization_type)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organization_user_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                is_primary INTEGER NOT NULL DEFAULT 0,
                source TEXT,
                role_key TEXT DEFAULT 'member',
                joined_at TEXT NOT NULL,
                left_at TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK(status IN ('active','inactive','removed','expired')),
                FOREIGN KEY(organization_id) REFERENCES organizations(id),
                FOREIGN KEY(user_id) REFERENCES v05a_users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_org_user_active
            ON organization_user_links(organization_id,user_id)
            WHERE status='active'
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_org_user_primary
            ON organization_user_links(user_id)
            WHERE status='active' AND is_primary=1
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_org_user_user_status ON organization_user_links(user_id,status,is_primary)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_org_user_org_status ON organization_user_links(organization_id,status)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organization_membership_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                membership_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                is_primary INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                linked_at TEXT NOT NULL,
                unlinked_at TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK(status IN ('active','inactive','removed','expired')),
                FOREIGN KEY(organization_id) REFERENCES organizations(id),
                FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id)
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_org_membership_active
            ON organization_membership_links(membership_id)
            WHERE status='active'
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_org_membership_org_status ON organization_membership_links(organization_id,status)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_org_membership_member_status ON organization_membership_links(membership_id,status)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organization_access_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                action TEXT NOT NULL,
                organization_id INTEGER,
                target_user_id INTEGER,
                membership_id INTEGER,
                before_json TEXT,
                after_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_org_access_audit_org ON organization_access_audit(organization_id,created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_org_access_audit_actor ON organization_access_audit(actor_user_id,created_at DESC)")
        # Ensure the old Person-Membership unique index is not restored by older migrations.
        if _index_exists(conn, "ux_v04f_active_member_person"):
            conn.execute("DROP INDEX ux_v04f_active_member_person")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("Organization core migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

