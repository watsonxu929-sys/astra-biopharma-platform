﻿﻿﻿from __future__ import annotations

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

AUDIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS membership_person_link_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_no TEXT NOT NULL UNIQUE,
    action TEXT NOT NULL,
    membership_id INTEGER NOT NULL,
    person_id INTEGER,
    old_person_id INTEGER,
    actor TEXT,
    reason TEXT,
    field_differences_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_membership_person_link_audit_membership
ON membership_person_link_audit(membership_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_membership_person_link_audit_person
ON membership_person_link_audit(person_id, created_at DESC);
"""


def _next_no(conn: sqlite3.Connection) -> str:
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
        (stamp, datetime.now().replace(microsecond=0).isoformat()),
    ).fetchone()
    return f"QBPLA-{stamp}-{int(row['seq_value']):04d}"


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _index_exists(conn: sqlite3.Connection, index_name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (index_name,)).fetchone())


def backup_database() -> str:
    if not DB_PATH.exists():
        return ""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"app_before_membership_person_link_v1_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(DB_PATH, target)
    return str(target)


def migrate():
    print("=== 杩佺Щ: Person涓嶮embership鍏煎缁戝畾 v1 ===")
    
    backup_path = backup_database()
    if backup_path:
        print(f"澶囦唤宸插垱寤? {backup_path}")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("BEGIN")
        
        if _index_exists(conn, "ux_v04f_active_member_person"):
            conn.execute("DROP INDEX ux_v04f_active_member_person")
            print("宸插垹闄ゅ敮涓€绱㈠紩 ux_v04f_active_member_person")
        
        cols = _columns(conn, "v04f_club_memberships")
        has_person_id = "person_id" in cols
        
        if has_person_id:
            rows = conn.execute("PRAGMA table_info(v04f_club_memberships)").fetchall()
            person_id_not_null = any(r[1] == "person_id" and r[3] == 1 for r in rows)
            if person_id_not_null:
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.execute("ALTER TABLE v04f_club_memberships RENAME TO v04f_club_memberships_old")
                conn.execute(
                    """
                    CREATE TABLE v04f_club_memberships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        member_no TEXT NOT NULL UNIQUE,
                        person_id INTEGER,
                        organization_id INTEGER,
                        member_role TEXT,
                        member_level TEXT NOT NULL DEFAULT 'standard',
                        status TEXT NOT NULL DEFAULT 'active',
                        joined_at TEXT NOT NULL,
                        expired_at TEXT,
                        source TEXT,
                        owner TEXT,
                        industry_tags TEXT,
                        expertise_tags TEXT,
                        cooperation_preferences TEXT,
                        internal_note TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        deactivated_at TEXT,
                        is_org_contact INTEGER NOT NULL DEFAULT 0,
                        is_org_admin_candidate INTEGER NOT NULL DEFAULT 0,
                        org_admin_status TEXT,
                        CHECK(status IN ('pending','active','inactive','suspended','exited'))
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO v04f_club_memberships
                    SELECT id,member_no,person_id,organization_id,member_role,member_level,status,
                           joined_at,expired_at,source,owner,industry_tags,expertise_tags,
                           cooperation_preferences,internal_note,created_at,updated_at,deactivated_at,
                           COALESCE(is_org_contact,0),COALESCE(is_org_admin_candidate,0),org_admin_status
                    FROM v04f_club_memberships_old
                    """
                )
                conn.execute("DROP TABLE v04f_club_memberships_old")
                conn.execute("CREATE INDEX ix_v04f_member_status ON v04f_club_memberships(status, member_level, joined_at DESC)")
                conn.execute("CREATE INDEX ix_v04f_member_person ON v04f_club_memberships(person_id)")
                conn.execute("PRAGMA foreign_keys = ON")
                print("person_id made nullable")
        else:
            print("person_id column not found, skipped")
        
        conn.executescript(AUDIT_SCHEMA_SQL)
        print("membership_person_link_audit ensured")
        
        conn.commit()
        print("=== migration completed ===")


if __name__ == "__main__":
    migrate()


